"""CLI wrapper: run the full Spark pipeline over the synthetic dataset.

Usage:
    python scripts/run_spark_pipeline.py
    python scripts/run_spark_pipeline.py --input data/synthetic/sleep_observations.csv
    python scripts/run_spark_pipeline.py --input data/raw/ --output data/parquet/
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

# Ensure repo root is on the path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from spark.pipeline import run_pipeline


def main():
    parser = argparse.ArgumentParser(
        description="SleepSense AI: Run the full PySpark analytics pipeline"
    )
    parser.add_argument(
        "--input",
        default="data/synthetic/sleep_observations.csv",
        help="Path to raw CSV input (default: data/synthetic/sleep_observations.csv)",
    )
    parser.add_argument(
        "--output",
        default="data/parquet",
        help="Path to Parquet output directory (default: data/parquet)",
    )
    args = parser.parse_args()

    repo_root = Path(__file__).resolve().parent.parent
    input_path = repo_root / args.input
    output_path = repo_root / args.output

    if not input_path.exists():
        print(f"❌ Input not found: {input_path}")
        print("   Run: python scripts/generate_synthetic_sleep.py  first")
        sys.exit(1)

    print(f"🔥 Starting PySpark pipeline")
    print(f"   Input:  {input_path}")
    print(f"   Output: {output_path}")

    df = run_pipeline(input_path, output_path)

    print(f"\n✅ Pipeline complete!")
    print(f"   Total nights processed: {df.count():,}")
    df.printSchema()
    df.select(
        "user_id", "date", "sleep_score", "sleep_category",
        "risk_level", "sleep_score_7d_avg", "n3_fraction", "rem_fraction",
    ).orderBy("user_id", "date").show(20, truncate=False)


if __name__ == "__main__":
    main()
