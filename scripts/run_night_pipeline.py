"""CLI entry point for SleepSense AI 1 Hz Night Sensor Pipeline."""

from __future__ import annotations

import argparse
import json
import sys
from concurrent.futures import ProcessPoolExecutor, as_completed
from pathlib import Path

# Add project root to sys.path
ROOT_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT_DIR))

from spark.night_pipeline import process_night_session


def _pipeline_worker(task_tuple: tuple) -> dict:
    session_id, csv_path_str, out_parquet_str, out_eda_str, user_id = task_tuple
    return process_night_session(
        session_id=session_id,
        csv_path=Path(csv_path_str),
        out_parquet_dir=Path(out_parquet_str),
        out_eda_dir=Path(out_eda_str),
        user_id=user_id,
    )


def run_pipeline(
    input_dir: Path,
    out_parquet_dir: Path,
    out_eda_dir: Path,
    process_all: bool = False,
    single_session: str | None = None,
    workers: int = 4,
) -> list[dict]:
    """Runs night sensor pipeline across dataset or single session."""
    input_dir = Path(input_dir)
    out_parquet_dir = Path(out_parquet_dir)
    out_eda_dir = Path(out_eda_dir)

    out_parquet_dir.mkdir(parents=True, exist_ok=True)
    out_eda_dir.mkdir(parents=True, exist_ok=True)

    csv_files = list(input_dir.rglob("*.csv"))
    csv_files = [f for f in csv_files if f.name != "manifest.csv"]

    if single_session:
        csv_files = [f for f in csv_files if single_session in f.name]
        if not csv_files:
            raise FileNotFoundError(f"No CSV file found matching session '{single_session}' in '{input_dir}'")

    print(f"Found {len(csv_files)} night CSV files to process.")

    tasks = []
    for csv_file in csv_files:
        sid = csv_file.stem
        uid = csv_file.parent.name
        tasks.append((sid, str(csv_file), str(out_parquet_dir), str(out_eda_dir), uid))

    results = []
    if len(tasks) == 1:
        res = _pipeline_worker(tasks[0])
        results.append(res)
        print(f"Processed session {res['session_id']}: Score={res['sleep_score']}, Risk={res['risk_level']}")
    else:
        print(f"Processing {len(tasks)} sessions using {workers} parallel workers...")
        with ProcessPoolExecutor(max_workers=workers) as executor:
            futures = [executor.submit(_pipeline_worker, task) for task in tasks]
            for future in as_completed(futures):
                res = future.result()
                results.append(res)

    summary_file = out_parquet_dir / "night_analytics_summary.json"
    with open(summary_file, "w", encoding="utf-8") as f:
        json.dump(results, f, indent=2)

    print(f"Pipeline complete! Successfully processed {len(results)} nights.")
    print(f"Parquet output written to: {out_parquet_dir}")
    print(f"EDA JSON output written to: {out_eda_dir}")
    return results


def main():
    parser = argparse.ArgumentParser(description="SleepSense AI 1 Hz Night Sensor Pipeline CLI")
    parser.add_argument("--input", type=Path, default=Path("data/raw/nights"), help="Input directory containing night sensor CSVs")
    parser.add_argument("--out-parquet", type=Path, default=Path("data/parquet/epochs"), help="Output directory for 30s epochs Parquet")
    parser.add_argument("--out-eda", type=Path, default=Path("data/eda"), help="Output directory for high-res EDA JSON files")
    parser.add_argument("--all", action="store_true", help="Process all night CSV files in input directory")
    parser.add_argument("--session", type=str, default=None, help="Process single session ID (e.g. S_U001_N01)")
    parser.add_argument("--workers", type=int, default=4, help="Parallel worker count")

    args = parser.parse_args()

    if not args.all and not args.session:
        print("Error: Must specify either --all or --session S123")
        sys.exit(1)

    run_pipeline(
        input_dir=args.input,
        out_parquet_dir=args.out_parquet,
        out_eda_dir=args.out_eda,
        process_all=args.all,
        single_session=args.session,
        workers=args.workers,
    )


if __name__ == "__main__":
    main()
