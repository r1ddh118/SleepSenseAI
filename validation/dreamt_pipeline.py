#!/usr/bin/env python3
"""
Download / convert DREAMT v2.1.0 (PhysioNet) and run the existing src/ pipeline.

DREAMT layout (typical after credentialled download):
  <dreamt_root>/data_64Hz/*.csv
  <dreamt_root>/participant_info.csv

This script writes SleepSense-compatible files under --out:
  compressed_<SID>_whole_df.csv
  participant_info.csv
  psg_labels.csv          # SID + sleep_deprivation_label_gt (AHI/OAHI-based proxy for metrics_report)

Optional download (requires wget + PhysioNet credentials):
  export PHYSIONET_USER and PHYSIONET_PASS

Usage:
  python validation/dreamt_pipeline.py --dreamt-root /path/to/dreamt/2.1.0 --out datasets/dreamt/
  python validation/dreamt_pipeline.py --skip-convert --out datasets/dreamt/   # data already converted
"""

from __future__ import annotations

import argparse
import logging
import os
import re
import shutil
import subprocess
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import requests

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("dreamt_pipeline")

REPO_ROOT = Path(__file__).resolve().parent.parent

# PhysioNet base (files require credentialed access; wget often works better than raw URLs)
DREAMT_FILES_BASE = "https://physionet.org/files/dreamt/2.1.0/"

DREAMT_STAGE_ONEHOT = [
    "Sleep_Stage_W",
    "Sleep_Stage_N1",
    "Sleep_Stage_N2",
    "Sleep_Stage_N3",
    "Sleep_Stage_R",
]


def _safe_download_file(session: requests.Session, url: str, dest: Path) -> bool:
    dest.parent.mkdir(parents=True, exist_ok=True)
    if dest.exists() and dest.stat().st_size > 0:
        logger.info("Already present: %s", dest.name)
        return True
    logger.info("GET %s", url)
    r = session.get(url, stream=True, timeout=120)
    if r.status_code != 200:
        logger.warning("Failed %s: HTTP %s", dest.name, r.status_code)
        return False
    with open(dest, "wb") as f:
        for chunk in r.iter_content(chunk_size=8192):
            f.write(chunk)
    return True


def download_dreamt_artifacts(out_dir: Path, username: str, password: str) -> bool:
    """Best-effort fetch of participant_info + a small subset via HTTP (may 403 without DUA)."""
    out_dir.mkdir(parents=True, exist_ok=True)
    session = requests.Session()
    session.auth = (username, password)
    ok = True
    for rel in ("participant_info.csv",):
        url = f"{DREAMT_FILES_BASE}{rel}"
        dest = out_dir / rel
        if not _safe_download_file(session, url, dest):
            ok = False
    return ok


def download_dreamt_wget(out_dir: Path, username: str, password: str) -> bool:
    """Mirror DREAMT 2.1.0 with wget (recommended for full data)."""
    if not shutil.which("wget"):
        logger.error("wget not found. Install wget or pass --dreamt-root with a local extract.")
        return False
    out_dir.mkdir(parents=True, exist_ok=True)
    url = DREAMT_FILES_BASE
    cmd = [
        "wget",
        "-r",
        "-N",
        "-c",
        "-np",
        "-nH",
        "--cut-dirs=3",
        "--user",
        username,
        "--password",
        password,
        url,
    ]
    logger.info("Running wget mirror into %s", out_dir)
    r = subprocess.run(cmd, cwd=str(out_dir))
    return r.returncode == 0


def _normalize_columns(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    df.columns = [str(c).strip().replace(" ", "_") for c in df.columns]
    lower = {c.lower(): c for c in df.columns}
    renames = {}
    for old, new in [
        ("acc_x", "ACC_X"),
        ("acc_y", "ACC_Y"),
        ("acc_z", "ACC_Z"),
        ("timestamp", "TIMESTAMP"),
    ]:
        if old in lower and lower[old] != new:
            renames[lower[old]] = new
    df = df.rename(columns=renames)
    return df


def _derive_sleep_stage(df: pd.DataFrame) -> pd.DataFrame:
    if "Sleep_Stage" in df.columns:
        return df
    present = [c for c in DREAMT_STAGE_ONEHOT if c in df.columns]
    if len(present) < 2:
        return df
    sub = df[present].apply(pd.to_numeric, errors="coerce").fillna(0)
    labels = sub.idxmax(axis=1)
    mapping = {
        "Sleep_Stage_W": "W",
        "Sleep_Stage_N1": "N1",
        "Sleep_Stage_N2": "N2",
        "Sleep_Stage_N3": "N3",
        "Sleep_Stage_R": "R",
    }
    df = df.copy()
    df["Sleep_Stage"] = labels.map(mapping).fillna("Unknown")
    return df


def _ensure_event_placeholders(df: pd.DataFrame) -> pd.DataFrame:
    event_cols = ["Obstructive_Apnea", "Central_Apnea", "Hypopnea", "Multiple_Events"]
    df = df.copy()
    for col in event_cols:
        if col not in df.columns:
            df[col] = np.nan
    return df


def _participant_id_from_stem(stem: str) -> str:
    s = stem.strip()
    m = re.search(r"(S\d{3})", s, re.I)
    if m:
        return m.group(1).upper()
    return s


def convert_dreamt_to_sleepsense(dreamt_root: Path, out_dir: Path) -> Path:
    """
    Read DREAMT CSVs from data_64Hz (or flat csv folder), emit compressed_<SID>_whole_df.csv + participant_info.csv.
    """
    data_dir = dreamt_root / "data_64Hz"
    if not data_dir.is_dir():
        data_dir = dreamt_root

    csv_files = sorted(
        p
        for p in data_dir.glob("*.csv")
        if p.name.lower() not in ("participant_info.csv", "psg_labels.csv")
    )
    if not csv_files:
        raise FileNotFoundError(f"No sensor CSV files under {data_dir}")

    p_info_src = dreamt_root / "participant_info.csv"
    if not p_info_src.exists():
        p_info_src = out_dir / "participant_info.csv"
    if not p_info_src.exists():
        raise FileNotFoundError(
            f"Missing participant_info.csv under {dreamt_root}. "
            "Download DREAMT or place participant_info.csv next to data_64Hz."
        )

    raw_info = pd.read_csv(p_info_src)
    raw_info.columns = [str(c).strip() for c in raw_info.columns]

    out_dir.mkdir(parents=True, exist_ok=True)

    id_candidates = [
        c
        for c in raw_info.columns
        if re.search(r"participant|subject|id|pid|record", c, re.I) and c.lower() not in ("age", "bmi")
    ]
    id_col = id_candidates[0] if id_candidates else raw_info.columns[0]
    logger.info("Using participant ID column: %s", id_col)

    rows = []
    for path in csv_files:
        stem_id = _participant_id_from_stem(path.stem)
        df = pd.read_csv(path)
        df = _normalize_columns(df)
        df = _derive_sleep_stage(df)
        df = _ensure_event_placeholders(df)
        required = ["BVP", "ACC_X", "ACC_Y", "ACC_Z", "EDA", "TEMP", "HR", "IBI", "Sleep_Stage"]
        missing = [c for c in required if c not in df.columns]
        if missing:
            logger.warning("Skipping %s — missing columns %s", path.name, missing)
            continue
        out_name = f"compressed_{stem_id}_whole_df.csv"
        dest = out_dir / out_name
        df.to_csv(dest, index=False)
        rows.append({"file_sid": stem_id, "source_file": path.name})

    if not rows:
        raise RuntimeError("No valid DREAMT sensor files converted — check columns vs SleepSense schema.")

    # Map DREAMT demographics → SleepSense participant_info schema
    info = raw_info.copy()
    info["SID"] = info[id_col].astype(str).str.strip()

    def pick(*names: str) -> pd.Series | None:
        for n in names:
            for c in info.columns:
                if c.lower() == n.lower():
                    return info[c]
        return None

    age = pick("AGE", "Age")
    sex = pick("GENDER", "Gender", "Sex", "SEX")
    bmi = pick("BMI", "Bmi")
    oahi = pick("OAHI", "oahi")
    ahi = pick("AHI", "ahi")
    sao2 = pick("Mean_SaO2", "SaO2", "SpO2", "MEAN_SAO2")
    arousal = pick("Arousal Index", "AROUSAL_INDEX", "arousal_index")
    history = pick("MEDICAL_HISTORY", "medical_history", "history")
    disorders = pick("Sleep_Disorders", "sleep_disorders", "diagnosis")

    out_info = pd.DataFrame({"SID": info["SID"]})
    out_info["AGE"] = age if age is not None else np.nan
    out_info["GENDER"] = sex if sex is not None else "Unknown"
    out_info["BMI"] = bmi if bmi is not None else np.nan
    out_info["OAHI"] = oahi if oahi is not None else np.nan
    out_info["AHI"] = ahi if ahi is not None else np.nan
    out_info["Mean_SaO2"] = sao2 if sao2 is not None else np.nan
    out_info["Arousal Index"] = arousal if arousal is not None else np.nan
    out_info["MEDICAL_HISTORY"] = history if history is not None else ""
    out_info["Sleep_Disorders"] = disorders if disorders is not None else ""

    out_path = out_dir / "participant_info.csv"
    out_info.to_csv(out_path, index=False)
    logger.info("Wrote %s participant rows → %s", len(out_info), out_path)

    # Proxy PSG-related binary label for metrics_report (AHI / OAHI rule)
    y = (out_info["AHI"].fillna(out_info["AHI"].median()) >= 15) | (
        out_info["OAHI"].fillna(out_info["OAHI"].median()) >= 15
    )
    label_path = out_dir / "psg_labels.csv"
    pd.DataFrame({"SID": out_info["SID"], "sleep_deprivation_label_gt": y.astype(int)}).to_csv(
        label_path, index=False
    )
    logger.info("Wrote %s", label_path)
    return out_path


def run_pipeline_on_dreamt(dreamt_dir: Path, artifacts_dir: Path) -> int:
    """Run preprocess → eda → train using repo src.main."""
    participant_csv = dreamt_dir / "participant_info.csv"
    if not participant_csv.exists():
        logger.error("Missing %s", participant_csv)
        return 1

    cmds = [
        (
            "preprocess",
            [
                sys.executable,
                "-m",
                "src.main",
                "preprocess",
                "--dataset-dir",
                str(dreamt_dir),
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
                str(dreamt_dir),
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
                str(dreamt_dir),
                "--participant-csv",
                str(participant_csv),
                "--outdir",
                str(artifacts_dir),
            ],
        ),
    ]

    for name, cmd in cmds:
        logger.info("Running: %s", name)
        r = subprocess.run(cmd, cwd=str(REPO_ROOT), capture_output=True, text=True)
        if r.returncode != 0:
            logger.error("%s failed:\n%s\n%s", name, r.stdout, r.stderr)
            return r.returncode
    logger.info("Pipeline complete. See %s", artifacts_dir / "model_leaderboard.csv")
    logger.info(
        "Next: build batch predictions CSV (or run predict per SID), then "
        "python validation/metrics_report.py --predictions <csv> --ground-truth %s",
        dreamt_dir / "psg_labels.csv",
    )
    return 0


def build_batch_predictions_from_training(
    dreamt_dir: Path, artifacts_dir: Path, out_csv: Path
) -> int:
    """Use preprocessed training rows + best_model.pkl to emit predictions with SID for metrics_report."""
    sys.path.insert(0, str(REPO_ROOT / "src"))
    from trainer import SleepModelTrainer

    proc = artifacts_dir / "preprocessed_training_data.csv"
    if not proc.exists():
        logger.error("Missing %s — run preprocess first", proc)
        return 1
    model_pkl = artifacts_dir / "best_model.pkl"
    if not model_pkl.exists():
        logger.error("Missing %s — run train first", model_pkl)
        return 1
    df = pd.read_csv(proc)
    SleepModelTrainer.predict_to_csv(model_pkl, df, out_csv)
    logger.info("Wrote batch predictions: %s", out_csv)
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description="DREAMT → SleepSense pipeline")
    parser.add_argument("--out", default="datasets/dreamt", help="SleepSense dataset directory")
    parser.add_argument(
        "--dreamt-root",
        type=Path,
        default=None,
        help="Local path to extracted DREAMT 2.1.0 (contains data_64Hz/ and participant_info.csv)",
    )
    parser.add_argument("--skip-convert", action="store_true", help="Skip DREAMT→SleepSense conversion")
    parser.add_argument(
        "--download-wget",
        action="store_true",
        help="Attempt full wget mirror (needs PHYSIONET_USER/PASS and signed DUA)",
    )
    parser.add_argument(
        "--download-http",
        action="store_true",
        help="Attempt small HTTP fetch (participant_info only; may fail if restricted)",
    )
    parser.add_argument(
        "--artifacts",
        type=Path,
        default=None,
        help="Artifacts directory (default: repo artifacts/)",
    )
    parser.add_argument(
        "--batch-predictions",
        action="store_true",
        help="After train, write artifacts/dreamt_batch_predictions.csv for metrics_report",
    )
    args = parser.parse_args()

    out_dir = (REPO_ROOT / args.out).resolve()
    artifacts_dir = (args.artifacts or (REPO_ROOT / "artifacts")).resolve()

    if args.download_http:
        user = os.getenv("PHYSIONET_USER", "")
        pwd = os.getenv("PHYSIONET_PASS", "")
        if not user or not pwd:
            logger.error("Set PHYSIONET_USER and PHYSIONET_PASS for download")
            return 1
        download_dreamt_artifacts(out_dir, user, pwd)

    if args.download_wget:
        user = os.getenv("PHYSIONET_USER", "")
        pwd = os.getenv("PHYSIONET_PASS", "")
        if not user or not pwd:
            logger.error("Set PHYSIONET_USER and PHYSIONET_PASS for wget download")
            return 1
        if not download_dreamt_wget(out_dir, user, pwd):
            return 1
        args.dreamt_root = out_dir

    if not args.skip_convert:
        if args.dreamt_root is None:
            logger.error("Pass --dreamt-root /path/to/dreamt/2.1.0 or use --download-wget / --skip-convert")
            return 1
        dreamt_root = Path(args.dreamt_root).resolve()
        convert_dreamt_to_sleepsense(dreamt_root, out_dir)

    rc = run_pipeline_on_dreamt(out_dir, artifacts_dir)
    if rc != 0:
        return rc

    if args.batch_predictions:
        bp = artifacts_dir / "dreamt_batch_predictions.csv"
        return build_batch_predictions_from_training(out_dir, artifacts_dir, bp)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
