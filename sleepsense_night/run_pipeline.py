#!/usr/bin/env python3
"""
run_pipeline.py  –  End-to-end pipeline orchestrator
=====================================================

Calls each pipeline stage in order and writes outputs as Parquet + CSV.

Usage
-----
    python -m sleepsense_night.run_pipeline --input data/raw --output outputs

Outputs
-------
    epochs.parquet            – epoch-level data with all features
    events.csv / .parquet     – per-night event timeline
    nightly_metrics.csv / .parquet
    doctor_alerts.csv         – alert streaks (when present)
    quality_report.json
"""

from __future__ import annotations

import argparse
import json
from dataclasses import dataclass
from pathlib import Path

from sleepsense_night.pipeline.spark_utils import get_spark
from sleepsense_night.pipeline.ingest_clean import read_nights, detect_step_seconds, clean
from sleepsense_night.pipeline.features import add_features
from sleepsense_night.pipeline.nightly import aggregate_nights, compute_marks
from sleepsense_night.pipeline.events import build_events
from sleepsense_night.pipeline.scoring import add_score, add_risk_flags
from sleepsense_night.pipeline.trends_alerts import add_trends, doctor_alerts


@dataclass
class PipelineConfig:
    input_dir: str  = "data/raw"
    output_dir: str = "outputs"


def run(cfg: PipelineConfig | None = None) -> dict:
    """Execute the full pipeline and return a summary dict."""
    if cfg is None:
        cfg = PipelineConfig()

    out = Path(cfg.output_dir)
    out.mkdir(parents=True, exist_ok=True)

    spark = get_spark()

    # ── Stage 1: Ingest ───────────────────────────────────────────────
    print("▸ Stage 1 – Ingest …")
    raw  = read_nights(spark, cfg.input_dir)
    step = detect_step_seconds(raw)
    print(f"  sampling step = {step}s")

    # ── Stage 2: Clean ────────────────────────────────────────────────
    print("▸ Stage 2 – Clean …")
    cleaned, quality = clean(raw, step)
    print(f"  rows_raw={quality['rows_raw']}  "
          f"rows_clean={quality['rows_clean']}  "
          f"dups={quality['duplicates_removed']}  "
          f"sensor_gaps={quality['sensor_gaps']}")

    # ── Stage 3: Features ─────────────────────────────────────────────
    print("▸ Stage 3 – Features …")
    feats = add_features(cleaned, step=step)
    feats.cache()

    # ── Stage 4: Marks (onset / wake timestamps) ──────────────────────
    print("▸ Stage 4 – Computing night marks …")
    marks = compute_marks(feats)
    marks.cache()

    # ── Stage 5: Event timeline ───────────────────────────────────────
    print("▸ Stage 5 – Building event timeline …")
    events = build_events(feats, marks, step=step)

    # ── Stage 6: Nightly aggregation ──────────────────────────────────
    print("▸ Stage 6 – Nightly aggregation …")
    nightly = aggregate_nights(feats, step=step, marks=marks)

    # ── Stage 7: Scoring ──────────────────────────────────────────────
    print("▸ Stage 7 – Score & risk flags …")
    nightly = add_risk_flags(add_score(nightly))

    # ── Stage 8: Trends & alerts ──────────────────────────────────────
    print("▸ Stage 8 – Trends & alerts …")
    nightly = add_trends(nightly)
    alerts  = doctor_alerts(nightly)

    # ── Write outputs ─────────────────────────────────────────────────
    print("▸ Writing outputs …")

    # Epoch-level data (Parquet only – can be large)
    feats.write.mode("overwrite").parquet(str(out / "epochs.parquet"))

    # Event timeline
    events.coalesce(1).write.mode("overwrite").parquet(str(out / "events.parquet"))
    events_pd = events.toPandas()
    events_pd.to_csv(str(out / "events.csv"), index=False)

    # Nightly metrics
    nightly.coalesce(1).write.mode("overwrite").parquet(str(out / "nightly_metrics.parquet"))
    nightly_pd = nightly.toPandas()
    nightly_pd.to_csv(str(out / "nightly_metrics.csv"), index=False)

    # Alerts
    alert_count = alerts.count()
    if alert_count > 0:
        alerts.coalesce(1).write.mode("overwrite").parquet(str(out / "alerts.parquet"))
        alerts.toPandas().to_csv(str(out / "doctor_alerts.csv"), index=False)
    else:
        print("  (no alerts)")

    # Quality report
    with open(str(out / "quality_report.json"), "w") as f:
        json.dump(quality, f, indent=2, default=str)

    nights_scored = nightly_pd.shape[0]
    print(f"\n✓ Pipeline complete")
    print(f"  nights_scored={nights_scored}  alerts={alert_count}")
    print(f"  outputs in {out}/")

    summary = {
        "step_seconds": step,
        "nights_scored": nights_scored,
        "users": int(nightly_pd["user_id"].nunique()),
        "alerts": int(alert_count),
        "quality": quality,
    }
    return summary


def main() -> None:
    parser = argparse.ArgumentParser(description="SleepSense Night Pipeline")
    parser.add_argument("--input",  default="data/raw",  help="Input directory with CSVs")
    parser.add_argument("--output", default="outputs",   help="Output directory")
    args = parser.parse_args()

    cfg = PipelineConfig(input_dir=args.input, output_dir=args.output)
    summary = run(cfg)
    print(f"\nSummary: {json.dumps(summary, indent=2, default=str)}")


if __name__ == "__main__":
    main()
