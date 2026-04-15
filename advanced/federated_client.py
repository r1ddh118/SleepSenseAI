#!/usr/bin/env python3
"""
On-device federated learning stub: compute a pseudo-update vector from local features.

This does not implement a full FL protocol (Flower / FedAvg). It provides a hook for
future integration with Phase 2 (e.g. POST /api/v1/models/federated-update).

Usage:
  python advanced/federated_client.py --features artifacts/preprocessed_inference_S002.csv
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np
import pandas as pd


def compute_local_summary(features_csv: Path) -> dict:
    df = pd.read_csv(features_csv)
    numeric = df.select_dtypes(include=[np.number])
    return {
        "n_rows": int(len(df)),
        "mean": {k: float(v) for k, v in numeric.mean(numeric_only=True).items()},
        "std": {k: float(v) for k, v in numeric.std(numeric_only=True).items()},
    }


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--features", type=Path, required=True)
    p.add_argument("--out", type=Path, default=None, help="Optional JSON output path")
    args = p.parse_args()

    summary = compute_local_summary(args.features)
    text = json.dumps(summary, indent=2)
    print(text)
    if args.out:
        args.out.write_text(text, encoding="utf-8")


if __name__ == "__main__":
    main()
