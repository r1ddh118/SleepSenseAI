"""
pipeline/events.py  –  Per-night event timeline
================================================

Produces one row per event, with ``start_ts``, ``end_ts``, ``duration_s``,
and event-specific metadata.

Event types
-----------
lights_off        – first timestamp of the recording.
sleep_onset       – first epoch qualifying as sleep onset.
final_wake        – last wake epoch inside the sleep period.
lights_on         – last timestamp of the recording.
stage_segment     – every stage transition (one row per continuous stage run).
awakening         – wake run ≥ 120 s that starts AFTER onset and BEFORE final_wake.
micro_arousal     – wake run < 120 s inside the sleep period.
pre_sleep_wake    – wake before onset.
morning_wake      – wake after final_wake.
desaturation      – every run of desat_flag == 1 within the sleep period,
                    including its SpO₂ nadir.
sensor_gap        – epoch where is_gap_after == 1 (missing time).

Run-length helper
-----------------
The run-length id is built in two separate withColumn calls so that no
window function is nested inside another (which Spark does not allow).
"""

from __future__ import annotations

from pyspark.sql import DataFrame
from pyspark.sql import functions as F
from pyspark.sql.window import Window

from sleepsense_night.config import WAKE_BOUT_MIN_SECONDS


# ── Internal helpers ──────────────────────────────────────────────────

def _add_run_id(df: DataFrame, col: str, partition_cols: list[str]) -> DataFrame:
    """Add ``{col}_run_id`` – a contiguous-run identifier for *col*.

    Two-step to avoid nesting window functions.
    """
    wo = Window.partitionBy(*partition_cols).orderBy("ts")
    cum_w = wo.rowsBetween(Window.unboundedPreceding, 0)

    df = df.withColumn(
        f"_chg_{col}",
        F.coalesce(
            (F.col(col) != F.lag(col).over(wo)).cast("int"),
            F.lit(1),
        ),
    )
    df = df.withColumn(
        f"{col}_run_id",
        F.sum(f"_chg_{col}").over(cum_w),
    )
    df = df.drop(f"_chg_{col}")
    return df


def _runs(
    df: DataFrame,
    group_cols: list[str],
    run_id_col: str,
    extra_aggs: list,
) -> DataFrame:
    """Collapse a run-encoded DataFrame to one row per run."""
    return (
        df.groupBy(*group_cols, run_id_col)
          .agg(
              F.min("ts").alias("start_ts"),
              F.max("ts").alias("end_ts"),
              F.sum("dur_s").alias("duration_s"),
              *extra_aggs,
          )
          .drop(run_id_col)
    )


# ── Public function ───────────────────────────────────────────────────

def build_events(
    feats: DataFrame,
    marks: DataFrame,
    cfg=None,
    step: int = 10,
) -> DataFrame:
    """Build the event timeline for all nights.

    Parameters
    ----------
    feats  : epoch-level DataFrame with columns from features.py.
    marks  : per-night DataFrame from compute_marks() (bedtime_ts, onset_ts,
             final_wake_ts, last_ts).
    cfg    : PipelineConfig (unused, kept for forward compat).
    step   : sampling step in seconds.

    Returns
    -------
    DataFrame with columns:
        user_id, night_date, event_type, start_ts, end_ts, duration_s,
        + optional metadata columns (stage, spo2_nadir, etc.)
    """
    part = ["user_id", "night_date"]
    has_spo2 = "spo2_pct" in feats.columns

    # Join marks to get onset/wake timestamps on every epoch row
    df = feats.join(marks, on=part, how="left")

    # ── 1. Key-time events (one per night each) ───────────────────────
    def _key_time(marks_df: DataFrame, ts_col: str, event_name: str) -> DataFrame:
        return (
            marks_df
            .select(*part, F.col(ts_col).alias("start_ts"))
            .withColumn("end_ts",     F.col("start_ts"))
            .withColumn("duration_s", F.lit(0).cast("long"))
            .withColumn("event_type", F.lit(event_name))
        )

    lights_off_ev  = _key_time(marks, "bedtime_ts",    "lights_off")
    sleep_onset_ev = _key_time(marks, "onset_ts",      "sleep_onset")
    final_wake_ev  = _key_time(marks, "final_wake_ts", "final_wake")
    lights_on_ev   = _key_time(marks, "last_ts",       "lights_on")

    # ── 2. Stage segments ─────────────────────────────────────────────
    stage_runs = _runs(
        df,
        group_cols=part,
        run_id_col="stage_run_id",
        extra_aggs=[F.first("stage").alias("stage")],
    ).withColumn("event_type", F.lit("stage_segment"))

    # ── 3. Wake runs – classify against onset and final_wake ──────────
    # We need to know onset_ts and final_wake_ts per run
    wake_df = df.where(F.col("is_sleep") == 0)
    wake_runs = _runs(
        wake_df,
        group_cols=part,
        run_id_col="run_id",
        extra_aggs=[
            F.first("onset_ts").alias("_onset"),
            F.first("final_wake_ts").alias("_final_wake"),
        ],
    )

    # Classify each wake run
    wake_runs = (
        wake_runs
        .withColumn(
            "event_type",
            F.when(
                F.col("start_ts") < F.col("_onset"),
                "pre_sleep_wake",
            ).when(
                F.col("start_ts") > F.col("_final_wake"),
                "morning_wake",
            ).when(
                F.col("duration_s") >= WAKE_BOUT_MIN_SECONDS,
                "awakening",
            ).otherwise("micro_arousal"),
        )
        .drop("_onset", "_final_wake")
    )

    # ── 4. Desaturation events ────────────────────────────────────────
    if has_spo2:
        desat_df = df.where(
            (F.col("desat_flag") == 1) & (F.col("in_sleep").isNotNull())
        )
        # desat_flag run_id (re-derive here to avoid dependency on feats structure)
        desat_df = _add_run_id(desat_df, "desat_flag", part)
        desat_runs = _runs(
            desat_df,
            group_cols=part,
            run_id_col="desat_flag_run_id",
            extra_aggs=[F.min("spo2_pct").alias("spo2_nadir")],
        ).withColumn("event_type", F.lit("desaturation"))
    else:
        desat_runs = None

    # ── 5. Sensor gaps ────────────────────────────────────────────────
    gap_ev = (
        df.where(F.col("is_gap_after") == 1)
          .select(*part, "ts", "dur_s")
          .withColumn("start_ts",   F.col("ts"))
          .withColumn("end_ts",     F.col("ts") + F.col("dur_s").cast("int"))
          .withColumn("duration_s", F.col("dur_s").cast("long"))
          .withColumn("event_type", F.lit("sensor_gap"))
          .drop("ts", "dur_s")
    )

    # ── Union all event frames ────────────────────────────────────────
    # Normalise columns so union works even when some frames lack metadata cols
    def _norm(frame: DataFrame) -> DataFrame:
        for c in ["stage", "spo2_nadir"]:
            if c not in frame.columns:
                frame = frame.withColumn(c, F.lit(None).cast("string"))
        # Ensure duration_s is long
        frame = frame.withColumn("duration_s", F.col("duration_s").cast("long"))
        return frame.select(
            *part, "event_type", "start_ts", "end_ts", "duration_s",
            "stage", "spo2_nadir",
        )

    frames = [
        _norm(lights_off_ev),
        _norm(sleep_onset_ev),
        _norm(final_wake_ev),
        _norm(lights_on_ev),
        _norm(stage_runs),
        _norm(wake_runs),
        _norm(gap_ev),
    ]
    if desat_runs is not None:
        frames.append(_norm(desat_runs))

    events = frames[0]
    for f in frames[1:]:
        events = events.unionByName(f)

    events = events.orderBy(*part, "start_ts")
    return events
