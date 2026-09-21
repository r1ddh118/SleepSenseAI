from __future__ import annotations

import argparse
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from spark.pipeline import run_pipeline


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run the SleepSense Spark analytics pipeline.")
    parser.add_argument("--input", default="data/synthetic/sleep_observations.csv")
    parser.add_argument("--output", default="data/parquet")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    result = run_pipeline(args.input, args.output)
    try:
        print(f"Wrote nightly analytics Parquet to {args.output}")
        print(f"Total nights: {result.count()}")
        return 0
    finally:
        result.sparkSession.stop()


if __name__ == "__main__":
    raise SystemExit(main())
