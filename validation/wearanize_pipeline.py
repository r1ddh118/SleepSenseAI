#!/usr/bin/env python3
"""
Wearanize+ (N≈130) validation path — mirror of DREAMT flow.

Place Wearanize+ exports under a directory with the same SleepSense contract:
  - compressed_<SID>_whole_df.csv sensor files
  - participant_info.csv (SleepSense column schema)

Then run:
  python validation/wearanize_pipeline.py --dataset-dir datasets/wearanize/

Or convert from a vendor export folder (implement mapping below for your format).
"""

from __future__ import annotations

import argparse
import logging
import subprocess
import sys
from pathlib import Path

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("wearanize_pipeline")

REPO_ROOT = Path(__file__).resolve().parent.parent


def run_pipeline(dataset_dir: Path, artifacts_dir: Path) -> int:
    participant_csv = dataset_dir / "participant_info.csv"
    if not participant_csv.exists():
        logger.error("Missing %s", participant_csv)
        return 1

    steps = [
        (
            "preprocess",
            [
                sys.executable,
                "-m",
                "src.main",
                "preprocess",
                "--dataset-dir",
                str(dataset_dir),
                "--participant-csv",
                str(participant_csv),
                "--outdir",
                str(artifacts_dir),
            ],
        ),
        (
            "eda",
            [
                sys.executable,
                "-m",
                "src.main",
                "eda",
                "--dataset-dir",
                str(dataset_dir),
                "--participant-csv",
                str(participant_csv),
                "--outdir",
                str(artifacts_dir),
            ],
        ),
        (
            "train",
            [
                sys.executable,
                "-m",
                "src.main",
                "train",
                "--dataset-dir",
                str(dataset_dir),
                "--participant-csv",
                str(participant_csv),
                "--outdir",
                str(artifacts_dir),
            ],
        ),
    ]

    for name, cmd in steps:
        logger.info("Running %s", name)
        r = subprocess.run(cmd, cwd=str(REPO_ROOT), capture_output=True, text=True)
        if r.returncode != 0:
            logger.error("%s failed:\n%s\n%s", name, r.stdout, r.stderr)
            return r.returncode

    logger.info("Wearanize pipeline complete. Leaderboard: %s", artifacts_dir / "model_leaderboard.csv")
    return 0


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument(
        "--dataset-dir",
        type=Path,
        default=REPO_ROOT / "datasets" / "wearanize",
        help="Directory with compressed_*_whole_df.csv + participant_info.csv",
    )
    p.add_argument("--artifacts", type=Path, default=None)
    args = p.parse_args()

    ds = args.dataset_dir.resolve()
    art = (args.artifacts or (REPO_ROOT / "artifacts")).resolve()
    return run_pipeline(ds, art)


if __name__ == "__main__":
    raise SystemExit(main())
