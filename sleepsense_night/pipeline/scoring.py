"""
pipeline/scoring.py  –  Sleep score, risk flags, and score drivers
==================================================================

The composite score is a 0-100 number built from six positive components
and one penalty (ODI).  Each component uses ``lin(x, lo, hi)`` –
a linear ramp from 0 at *lo* to 1 at *hi*.

Missing-channel safety
----------------------
* ``_b(expr)`` wraps boolean flag expressions so that a NULL sensor column
  never raises a flag (it coalesces to False).
* When ``odi`` is NULL (no SpO₂ recorded), the SDB level is ``"no_spo2"``
  and the ODI penalty is 0 rather than a false flag.

Risk flags identify specific clinical concerns.
"""

from __future__ import annotations

from pyspark.sql import DataFrame
from pyspark.sql import functions as F

from sleepsense_night.config import SCORE_WEIGHTS as W, FLAG_THRESHOLDS as FT


def _lin(col, lo: float, hi: float):
    """Spark expression: linear ramp from 0 at *lo* to 1 at *hi*, clamped."""
    return F.least(F.lit(1.0), F.greatest(F.lit(0.0),
        (F.col(col) - F.lit(lo)) / F.lit(hi - lo)
    ))


def _b(expr):
    """Safe boolean: a missing/NULL sensor never raises a flag."""
    return F.coalesce(expr, F.lit(False)).cast("int")


def add_score(nightly: DataFrame) -> DataFrame:
    """Add ``sleep_score`` (0-100), ``sdb_level``, and ``score_drivers``."""

    # Individual components (each 0-1, then multiplied by weight)
    comp_eff     = _lin("efficiency_pct", 50, 88) * W["efficiency"]
    comp_tst     = _lin("tst_min",        180, 420) * W["tst"]   # 3h to 7h
    comp_deep    = _lin("deep_pct",       2, 13) * W["deep_pct"]
    comp_rem     = _lin("rem_pct",        5, 18) * W["rem_pct"]
    comp_latency = (F.lit(1) - _lin("sol_min", 20, 60)) * W["latency"]
    comp_waso    = (F.lit(1) - _lin("waso_min", 20, 90)) * W["waso"]

    # ODI penalty – 0 when SpO₂ was never recorded (odi is NULL)
    odi_col      = F.coalesce(F.col("odi"), F.lit(0.0))
    penalty_odi  = (
        F.least(F.lit(1.0), F.greatest(F.lit(0.0),
                (odi_col - F.lit(5.0)) / F.lit(25.0)))
        * W["odi_penalty"]
    )

    score = comp_eff + comp_tst + comp_deep + comp_rem + comp_latency + comp_waso - penalty_odi

    nightly = nightly.withColumn(
        "sleep_score",
        F.greatest(F.lit(0.0), F.least(F.lit(100.0), F.round(score, 1))),
    )

    # SDB severity level (for reporting / alerting)
    odi = F.col("odi")
    nightly = nightly.withColumn(
        "sdb_level",
        F.when(odi.isNull(),  "no_spo2")
         .when(odi >= 30,     "severe")
         .when(odi >= 15,     "moderate")
         .when(odi >= 5,      "mild")
         .otherwise("none"),
    )

    # Score drivers – the two components that cost the most points
    nightly = nightly.withColumn(
        "score_drivers",
        F.array_sort(F.array(
            F.struct(
                (F.lit(W["efficiency"]) - comp_eff).alias("cost"),
                F.lit("efficiency").alias("component"),
            ),
            F.struct(
                (F.lit(W["tst"]) - comp_tst).alias("cost"),
                F.lit("tst").alias("component"),
            ),
            F.struct(
                (F.lit(W["deep_pct"]) - comp_deep).alias("cost"),
                F.lit("deep_pct").alias("component"),
            ),
            F.struct(
                (F.lit(W["rem_pct"]) - comp_rem).alias("cost"),
                F.lit("rem_pct").alias("component"),
            ),
            F.struct(
                (F.lit(W["latency"]) - comp_latency).alias("cost"),
                F.lit("latency").alias("component"),
            ),
            F.struct(
                (F.lit(W["waso"]) - comp_waso).alias("cost"),
                F.lit("waso").alias("component"),
            ),
        )),
    )

    # Keep only the top-2 driver names (sorted ascending → last = highest cost)
    nightly = nightly.withColumn(
        "score_drivers",
        F.concat_ws(", ",
            F.col("score_drivers")[5]["component"],
            F.col("score_drivers")[4]["component"],
        ),
    )

    return nightly


def add_risk_flags(nightly: DataFrame) -> DataFrame:
    """Add boolean risk flags and ``high_risk_night``.

    Uses ``_b()`` so that a NULL sensor column never raises a flag
    (HR-only wearables won't get a false SDB flag).
    """

    nightly = (
        nightly
        .withColumn("flag_sdb",
            _b(F.col("odi") >= FT["odi_sdb"]) |
            (
                _b(F.col("snore_pct") > FT["snore_pct_sdb"]) &
                _b(F.col("spo2_min") < FT["spo2_min_sdb"])
            ))
        .withColumn("flag_insomnia",
            _b(
                (F.col("sol_min") > FT["sol_insomnia"]) &
                (
                    (F.col("efficiency_pct") < FT["efficiency_insomnia"]) |
                    (F.col("waso_min") > FT["waso_insomnia"])
                )
            ))
        .withColumn("flag_fragmentation",
            _b(F.col("awakenings") >= FT["awakenings_frag"]) |
            _b(F.col("micro_arousal_index") >= FT["micro_arousal_frag"]))
        .withColumn("flag_short_sleep",
            _b(F.col("tst_min") < FT["tst_short"]))
    )

    flag_count = (
        F.col("flag_sdb").cast("int") +
        F.col("flag_insomnia").cast("int") +
        F.col("flag_fragmentation").cast("int") +
        F.col("flag_short_sleep").cast("int")
    )
    nightly = nightly.withColumn("flag_count", flag_count)

    nightly = nightly.withColumn(
        "high_risk_night",
        _b(F.col("odi") >= FT["odi_high_risk"]) |
        (F.col("flag_count") >= FT["flag_count_high"]) |
        _b(F.col("sleep_score") < FT["score_high_risk"]),
    )

    return nightly
