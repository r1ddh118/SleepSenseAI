"""
pipeline/nightly.py  –  Collapse per-epoch data to one row per night
====================================================================

Two-pass aggregation:
    Pass 1 (compute_marks) – find bedtime, onset, and final-wake timestamps;
                              mark ``in_sleep``.
    Pass 2 (aggregate_nights) – time-weighted aggregation of all nightly metrics.

``compute_marks`` is also consumed by ``events.py`` so it is separated out.
"""

from __future__ import annotations

from pyspark.sql import DataFrame
from pyspark.sql import functions as F
from pyspark.sql.window import Window

from sleepsense_night.config import WAKE_BOUT_MIN_SECONDS


# ── Pass 1: key time-points ───────────────────────────────────────────

def compute_marks(df: DataFrame) -> DataFrame:
    """Return a per-(user_id, night_date) DataFrame with:

    * ``bedtime_ts``    – first timestamp of the recording.
    * ``onset_ts``      – first epoch where onset_candidate == 1.
    * ``final_wake_ts`` – last wake epoch after onset (or last ts).
    * ``last_ts``       – last timestamp of the recording.
    """
    part = ["user_id", "night_date"]
    wo   = Window.partitionBy(*part).orderBy("ts")
    w_all = Window.partitionBy(*part).orderBy("ts") \
                  .rowsBetween(Window.unboundedPreceding, Window.unboundedFollowing)

    bedtime_df = (
        df.groupBy(*part)
          .agg(F.min("ts").alias("bedtime_ts"),
               F.max("ts").alias("last_ts"))
    )

    onset_df = (
        df.where("onset_candidate = 1")
          .groupBy(*part)
          .agg(F.min("ts").alias("onset_ts"))
    )

    marks = bedtime_df.join(onset_df, on=part, how="left")

    # final_wake: last wake epoch after onset, within the sleep period
    fw_df = (
        df.join(marks.select(*part, "onset_ts"), on=part, how="left")
          .where(
              (F.col("is_sleep") == 0) &
              (F.col("ts") > F.col("onset_ts"))
          )
          .groupBy(*part)
          .agg(F.max("ts").alias("final_wake_ts"))
    )
    marks = marks.join(fw_df, on=part, how="left")

    # Fall back: if no wake after onset → last_ts
    marks = marks.withColumn(
        "final_wake_ts",
        F.coalesce(F.col("final_wake_ts"), F.col("last_ts")),
    )

    return marks


# ── Pass 2: time-weighted aggregation ─────────────────────────────────

def aggregate_nights(
    df: DataFrame,
    cfg=None,
    step: int = 10,
    marks: DataFrame | None = None,
) -> DataFrame:
    """Produce one row per (user_id, night_date) with all nightly metrics.

    Parameters
    ----------
    df    : epoch-level DataFrame from features.py.
    cfg   : PipelineConfig (unused, kept for forward compat).
    step  : sampling step in seconds.
    marks : pre-computed marks DataFrame (from compute_marks). If None,
            compute_marks() is called internally.
    """
    part = ["user_id", "night_date"]

    if marks is None:
        marks = compute_marks(df)

    # Join marks back to epoch data so every row has onset_ts etc.
    df = df.join(marks, on=part, how="left")

    # in_sleep flag
    df = df.withColumn(
        "in_sleep",
        (
            (F.col("ts") >= F.col("onset_ts")) &
            (F.col("ts") <= F.col("final_wake_ts"))
        ).cast("int"),
    )

    # ── Helper ────────────────────────────────────────────────────────
    def secs(cond):
        """Sum dur_s where cond is True."""
        return F.sum(F.when(cond, F.col("dur_s")).otherwise(0))

    is_in  = F.col("in_sleep") == 1
    asleep = (F.col("is_sleep") == 1) & is_in
    awake  = (F.col("is_sleep") == 0) & is_in

    # ── Wake / micro-arousal bouts ────────────────────────────────────
    bout_df = (
        df.where(is_in)
          .groupBy(*part, "run_id")
          .agg(
              F.first("is_sleep").alias("bout_is_sleep"),
              F.sum("dur_s").alias("bout_dur_s"),
              F.min("ts").alias("bout_start"),
          )
    )
    awakenings_df = (
        bout_df
        .where(
            (F.col("bout_is_sleep") == 0) &
            (F.col("bout_dur_s") >= WAKE_BOUT_MIN_SECONDS)
        )
        .groupBy(*part)
        .agg(F.count("*").alias("awakenings"))
    )
    micro_bouts_df = (
        bout_df
        .where(
            (F.col("bout_is_sleep") == 0) &
            (F.col("bout_dur_s") < WAKE_BOUT_MIN_SECONDS) &
            (F.col("bout_dur_s") > 0)
        )
        .groupBy(*part)
        .agg(F.count("*").alias("micro_arousals"))
    )

    # ── How many SpO₂ samples were recorded? ──────────────────────────
    # Used later to NULL-guard breathing metrics when the channel is absent.
    has_spo2 = "spo2_pct" in df.columns

    # ── Main aggregation ──────────────────────────────────────────────
    agg_exprs = [
        # Key timestamps
        F.first("bedtime_ts").alias("bedtime_ts"),
        F.first("onset_ts").alias("onset_ts"),
        F.first("final_wake_ts").alias("final_wake_ts"),

        # TST, WASO, TIB
        (secs(asleep) / 60).alias("tst_min"),
        (secs(awake)  / 60).alias("waso_min"),
        (secs(is_in)  / 60).alias("tib_min"),

        # Stage minutes
        (secs(asleep & (F.col("stage") == "DEEP"))  / 60).alias("deep_min"),
        (secs(asleep & (F.col("stage") == "LIGHT")) / 60).alias("light_min"),
        (secs(asleep & (F.col("stage") == "REM"))   / 60).alias("rem_min"),

        # HR stats
        F.avg(F.when(asleep, F.col("hr_bpm"))).alias("hr_mean_sleep"),
        F.min(F.when(asleep, F.col("hr_bpm"))).alias("hr_min_sleep"),
        F.max(F.when(asleep, F.col("hr_bpm"))).alias("hr_max_sleep"),

        # Completeness
        F.count("*").alias("total_epochs"),
        F.sum(F.when(F.col("hr_bpm").isNotNull(), 1).otherwise(0)).alias("hr_epochs"),
    ]

    # SpO₂ metrics — only when channel exists
    if has_spo2:
        agg_exprs += [
            F.sum(F.when(is_in, F.col("desat_event_start")).otherwise(0)).alias("desat_events"),
            F.min(F.when(is_in, F.col("spo2_pct"))).alias("spo2_min"),
            secs(is_in & (F.col("spo2_pct") < 90)).alias("_spo2_below90_s"),
            secs(is_in & (F.col("spo2_pct") < 94)).alias("_spo2_below94_s"),
            F.sum(F.when(is_in & F.col("spo2_pct").isNotNull(), 1).otherwise(0))
             .alias("spo2_samples"),
        ]
    else:
        agg_exprs += [
            F.lit(0).alias("desat_events"),
            F.lit(None).cast("double").alias("spo2_min"),
            F.lit(0).alias("_spo2_below90_s"),
            F.lit(0).alias("_spo2_below94_s"),
            F.lit(0).alias("spo2_samples"),
        ]

    # Respiration
    if "resp_rate_bpm" in df.columns:
        agg_exprs += [
            F.avg(F.when(asleep, F.col("resp_rate_bpm"))).alias("resp_mean_sleep"),
            F.stddev(F.when(asleep, F.col("resp_rate_bpm"))).alias("resp_std_sleep"),
        ]
    else:
        agg_exprs += [
            F.lit(None).cast("double").alias("resp_mean_sleep"),
            F.lit(None).cast("double").alias("resp_std_sleep"),
        ]

    # Snoring
    if "snore_db" in df.columns:
        agg_exprs.append(secs(is_in & (F.col("snore_db") > 40)).alias("_snore_s"))
    else:
        agg_exprs.append(F.lit(0).alias("_snore_s"))

    # EDA / temp
    agg_exprs.append(
        F.avg(F.when(asleep, F.col("eda_us"))).alias("eda_mean_sleep")
        if "eda_us" in df.columns
        else F.lit(None).cast("double").alias("eda_mean_sleep")
    )
    agg_exprs.append(
        F.avg(F.when(asleep, F.col("skin_temp_c"))).alias("temp_mean_sleep")
        if "skin_temp_c" in df.columns
        else F.lit(None).cast("double").alias("temp_mean_sleep")
    )

    nightly = df.groupBy(*part).agg(*agg_exprs)

    # ── Derived percentages ───────────────────────────────────────────
    nightly = (
        nightly
        .withColumn("sol_min",
                    (F.unix_timestamp("onset_ts") - F.unix_timestamp("bedtime_ts")) / 60)
        .withColumn("efficiency_pct",
                    F.when(F.col("tib_min") > 0,
                           F.col("tst_min") / F.col("tib_min") * 100)
                     .otherwise(0))
        .withColumn("deep_pct",
                    F.when(F.col("tst_min") > 0,
                           F.col("deep_min") / F.col("tst_min") * 100)
                     .otherwise(0))
        .withColumn("light_pct",
                    F.when(F.col("tst_min") > 0,
                           F.col("light_min") / F.col("tst_min") * 100)
                     .otherwise(0))
        .withColumn("rem_pct",
                    F.when(F.col("tst_min") > 0,
                           F.col("rem_min") / F.col("tst_min") * 100)
                     .otherwise(0))
        # ODI: NULL-guarded (set to NULL when no SpO₂ data)
        .withColumn("odi",
                    F.when(
                        (F.col("spo2_samples") > 0) & (F.col("tst_min") > 0),
                        F.col("desat_events") / (F.col("tst_min") / 60),
                    ))
        .withColumn("pct_time_spo2_lt90",
                    F.when(F.col("spo2_samples") > 0,
                           F.col("_spo2_below90_s") / (F.col("tib_min") * 60) * 100))
        .withColumn("pct_time_spo2_lt94",
                    F.when(F.col("spo2_samples") > 0,
                           F.col("_spo2_below94_s") / (F.col("tib_min") * 60) * 100))
        .withColumn("snore_pct",
                    F.when(F.col("tib_min") > 0,
                           F.col("_snore_s") / (F.col("tib_min") * 60) * 100)
                     .otherwise(0))
        .withColumn("completeness_pct",
                    F.when(F.col("total_epochs") > 0,
                           F.col("hr_epochs") / F.col("total_epochs") * 100)
                     .otherwise(0))
        .drop("_spo2_below90_s", "_spo2_below94_s", "_snore_s")
    )

    # ── Join awakenings / micro-arousals ──────────────────────────────
    nightly = nightly.join(awakenings_df, on=part, how="left")
    nightly = nightly.join(micro_bouts_df, on=part, how="left")
    nightly = (
        nightly
        .fillna({"awakenings": 0, "micro_arousals": 0})
        .withColumn("micro_arousal_index",
                    F.when(F.col("tst_min") > 0,
                           F.col("micro_arousals") / (F.col("tst_min") / 60))
                     .otherwise(0))
    )

    return nightly
