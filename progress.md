# SleepSense AI — Spark Implementation Progress

## Branch: `spark-implementation`

This document tracks progress of the whole-night sensor pipeline
implemented inside `sleepsense_night/`.

---

## ✅ Completed Steps

### Step 0 — Environment Bootstrap
- Branch `spark-implementation` is active.
- Dependencies: `pyspark>=3.5`, `pyarrow`, `pandas<3`, `numpy`, `matplotlib`, `seaborn`, `tabulate`.
- Directory layout: `sleepsense_night/pipeline/`, `data/`, `outputs/`.

### Step 1 — Input Schema (`config.py`)
- **Before:** 7 required columns including `user_id`, `night_date`, `spo2_pct`, `resp_rate_bpm`.
- **After:** Only 3 required columns: `["timestamp", "hr_bpm", "movement_g"]`.
- `user_id`, `night_date`, `spo2_pct`, `resp_rate_bpm` moved to `OPTIONAL_COLUMNS`.
- Enables HR-only wearables and files without explicit user/date headers.

### Step 2 — Data Generator (`generate_nights.py`)
- Already complete. Generates one CSV per user-night with configurable `--step`.
- Injects NaN gaps, spike artefacts, duplicate rows, and sensor-off stretches.
- Usage: `python generate_nights.py --users 5 --nights 12 --step 10 --out data/raw`

### Steps 3 & 4 — Ingestion + Cleaning (`pipeline/ingest_clean.py`)
- `read_nights()`:
  - Reads entire folder via `spark.read.csv("*.csv")`.
  - Derives `user_id` from file name (pattern `U\d+_`) using `input_file_name()`.
  - Derives `night_date` from `first_timestamp - 12 h` when absent from CSV.
  - Absent optional channels added as `NULL`.
- `clean()`:
  - Deduplicates on `(user_id, night_date, ts)`.
  - Clamps out-of-range values to `NULL`.
  - Snapshots `hr_was_null` and `_{col}_was_null` **before** forward-filling.
  - Adds `is_gap_after` flag (1 where interval > 120 s = sensor-off stretch).
  - Long gaps are excluded from sleep-time accounting via `dur_s` cap.

### Step 5 — Feature Engineering (`pipeline/features.py`)
- Rolling windows (centred 2.5 min): `hr_roll_mean`, `hr_roll_std`, `resp_roll_std`, `mov_roll_mean`.
- Night-level median HR → `hr_rel`.
- Improved stage inference with **HR-only fallbacks** when respiration is absent:
  - `DEEP` when `hr_rel < -4.0` (no resp)
  - `REM` when `hr_rel > 1.5` (no resp)
- Stage run-length encoding (`stage_run_id`) for events timeline.
- `run_id` for wake/sleep bouts.

### Step 6 — Nightly Aggregation (`pipeline/nightly.py`)
- Extracted `compute_marks()` as a standalone function (returns `bedtime_ts`, `onset_ts`, `final_wake_ts`, `last_ts` per night).
- `aggregate_nights()` accepts pre-computed `marks` (avoids recomputing).
- `spo2_samples` column guards ODI and SpO₂ percentages:
  - When `spo2_samples == 0`, ODI and SpO₂ stats are `NULL` not `0`.

### Step 7 — Event Timeline (`pipeline/events.py`) 🆕
- New module, produces one row per event.
- Event types:

| `event_type`      | Description |
|-------------------|-------------|
| `lights_off`      | First timestamp |
| `sleep_onset`     | First qualifying onset epoch |
| `final_wake`      | Last wake epoch inside sleep period |
| `lights_on`       | Last timestamp |
| `stage_segment`   | Every stage transition run |
| `awakening`       | Wake ≥ 120 s after onset, before final_wake |
| `micro_arousal`   | Wake < 120 s inside sleep period |
| `pre_sleep_wake`  | Wake before onset |
| `morning_wake`    | Wake after final_wake |
| `desaturation`    | Low SpO₂ run with nadir value |
| `sensor_gap`      | Missing data stretch |

- Run-length IDs built in two separate steps (avoids nested window functions).

### Step 8 — Scoring (`pipeline/scoring.py`)
- Added `_b(expr)` helper: NULL sensor → never raises a flag (coalesces to `False`).
- Added `sdb_level` column: `no_spo2` / `none` / `mild` / `moderate` / `severe`.
- ODI penalty is 0 when SpO₂ was not recorded (HR-only wearables score fairly).

### Step 9 — Trends & Alerts (`pipeline/trends_alerts.py`)
- No logic change; 7/14/30-night MAs, gaps-and-islands alert streaks unchanged.
- Works correctly with the new optional-channel outputs.

### Step 10 — Pipeline Orchestration (`run_pipeline.py`)
- Wired `compute_marks()` and `build_events()` into the stage ordering.
- Outputs:
  - `epochs.parquet`
  - `events.parquet` + `events.csv` 🆕
  - `nightly_metrics.parquet` + `nightly_metrics.csv`
  - `doctor_alerts.csv` (when alerts exist)
  - `quality_report.json`

### Step 11 — Smoke Tests (`smoke_test.py`)
- Extended with event reconciliation:
  - Awakening counts in `events.csv` match `nightly_metrics.csv`.
  - Desaturation counts match.
  - Stage segment durations sum to within 5 min of TIB.
  - Sensor-gap count matches `quality_report.json`.

### Step 12 — Per-Night EDA (`eda_night.py`) 🆕
- Generates self-contained HTML with embedded base-64 PNG signals figure.
- Includes: key times, hour-by-hour table, event log, stage changes.
- Usage:
  ```bash
  python -m sleepsense_night.eda_night --user U003 --date 2026-09-04
  python -m sleepsense_night.eda_night --all
  ```

### Step 13 — Dataset EDA (`eda.py`)
- Added `plot_events_timing()` — histograms of when events occur relative to bedtime.
- Loads `events.csv` / `events.parquet` automatically.
- Tries `doctor_alerts.csv` then legacy `alerts.csv`.
- Generates per-night HTML for best and worst nights via `eda_night`.

### Step 14 — Real Wearable Adapter (`adapt_sensor_csv.py`) 🆕
- Maps DREAMT / Empatica E4 column aliases to pipeline names.
- Converts ACC X/Y/Z to `movement_g` (std of vector magnitude / scale).
- Anchors relative-second timestamps to a bedtime.
- Maps stage labels (`R→REM`, `P/0→W`, `N1/N2→LIGHT`, `N3/N4→DEEP`).
- Resamples to target epoch length.
- Usage:
  ```bash
  python adapt_sensor_csv.py --input raw_exports/ --output data/raw_adapted/ --target-seconds 10
  python run_pipeline.py --input data/raw_adapted --output outputs
  ```

---

## 🔄 Pending

### Step 15 — App Integration
- Backend: add `POST /api/v1/nights/upload` (validates header, queues Celery job).
- Results: `GET /nights/{user_id}/{night_date}/events` (reads `events.csv`).
- Frontend: replace manual-entry form with CSV multi-upload.
- **Start only after Step 11 passes on your own data.**

---

## Running the Pipeline

```bash
# 1. Generate synthetic data
cd sleepsense_night
python generate_nights.py --users 5 --nights 12 --step 10 --out data/raw

# 2. Run the pipeline
python run_pipeline.py --input data/raw --output outputs

# 3. Verify
python smoke_test.py

# 4. Dataset EDA
python eda.py

# 5. Per-night report
python eda_night.py --user U003 --date 2026-09-04

# 6. Adapt real wearable data
python adapt_sensor_csv.py --input raw_exports/ --output data/raw_adapted/ --target-seconds 10
python run_pipeline.py --input data/raw_adapted --output outputs
```

---

## File Map

```
sleepsense_night/
├── config.py               Step 1  – reduced REQUIRED_COLUMNS
├── generate_nights.py      Step 2  – synthetic data generator
├── run_pipeline.py         Step 10 – orchestrator (wires events.py)
├── smoke_test.py           Step 11 – with event reconciliation
├── eda.py                  Step 13 – dataset EDA + events timing
├── eda_night.py            Step 12 – per-night HTML report  [NEW]
├── adapt_sensor_csv.py     Step 14 – wearable CSV adapter   [NEW]
└── pipeline/
    ├── __init__.py
    ├── spark_utils.py
    ├── ingest_clean.py     Steps 3-4 – read folder, derive IDs, is_gap_after
    ├── features.py         Step 5  – HR-only fallbacks, stage_run_id
    ├── nightly.py          Step 6  – compute_marks(), NULL-guarded SpO₂
    ├── events.py           Step 7  – event timeline          [NEW]
    ├── scoring.py          Step 8  – _b(), sdb_level, NULL-safe ODI
    └── trends_alerts.py    Step 9  – unchanged
```
