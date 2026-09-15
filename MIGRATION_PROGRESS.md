# SleepSense AI PySpark Migration Progress

This is the living migration report. Update it after each implementation step so
the project has a clear record of what changed, why it changed, how it was done,
and how it was verified.

## Current Branch

- `pyspark-bigdata`

## Migration Goal

Convert the app from a CSV upload -> Celery -> scikit-learn prediction workflow
into **SleepSense AI: Scalable Sleep Analytics and Risk Screening Using
PySpark**.

The intended architecture is:

- FastAPI receives requests and stores metadata/raw session rows.
- Celery runs asynchronous analytics jobs.
- PySpark owns ingestion, cleaning, feature engineering, aggregation, and
  longitudinal analytics.
- Plain Python analytics modules turn Spark-computed aggregates into scores,
  risk levels, recommendations, reports, and persistence-based alerts.
- Hardware/MQTT/ESP32 code is optional legacy code, not part of the primary run
  path.

## Step 1: Repository Inventory And Migration Checklist

### What Was Done

- Added `MIGRATION_CHECKLIST.md`.
- Searched the repo for MQTT, `paho`, HiveMQ, ESP32, MPU6050, `withMPU`,
  `realtime_predictor.py`, hardcoded credential patterns, and pandas-heavy
  analytics/training paths.
- Recorded files to archive, files to refactor, files to update, and files with
  credentials or hardware assumptions.
- Committed the checklist as:
  - `52fca90 Add migration checklist`

### Why It Was Done

The blueprint explicitly requires an inventory before code changes. This reduces
the risk of doing a cosmetic Spark migration while accidentally leaving the old
hardware, MQTT, pandas, and scikit-learn prediction flow as the real app path.

### How It Was Done

- Used repo-wide search for hardware/MQTT terms and credential-like strings.
- Read the old analytics and task files:
  - `src/data_processor.py`
  - `src/trainer.py`
  - `api/tasks.py`
  - `advanced/recommendations.py`
- Wrote a markdown checklist mapping each hit to a future migration action.

### Verification

- Ran the requested grep command:

```bash
grep -rn "mqtt\|paho\|HIVEMQ\|ESP32\|MPU6050\|withMPU" --include="*.py" --include="*.ino" --include="*.md" .
```

- Confirmed every original hit was accounted for in `MIGRATION_CHECKLIST.md`.
- No application code was changed in this step.

## Step 2: Remove MQTT/ESP32 From Primary Run Path

### What Was Done

- Created and switched to branch `pyspark-bigdata`.
- Removed MQTT startup/shutdown from `api/main.py`.
- Removed `paho.mqtt.client`, HiveMQ connection logic, broker state, and
  ESP32 topic handling from `api/ws_manager.py`.
- Removed hardcoded HiveMQ settings from `api/config.py`.
- Removed Mosquitto orchestration from the root launcher `app.py`.
- Removed MQTT environment variables from:
  - `docker-compose.yml`
  - `packaging/docker-compose.prod.yml`
- Removed `paho-mqtt` from primary dependency files:
  - `requirements.txt`
  - `api/requirements_api.txt`
- Added optional hardware dependency file:
  - `requirements-hardware.txt`
- Added placeholder packages for upcoming phases:
  - `spark/`
  - `analytics/`
  - `ml/`
- Added `legacy/hardware/README.md`.

### Why It Was Done

The primary workflow should not require ESP32, MQTT, Mosquitto, HiveMQ, or
hardware streaming. FastAPI should boot without broker connection attempts, and
the new pipeline should be centered on manual entry, CSV/synthetic data, Celery,
and PySpark analytics.

This also removed tracked HiveMQ credentials from the primary config.

### How It Was Done

- Converted `api/ws_manager.py` into a WebSocket-only manager.
- Kept `set_recording_session()` as a lightweight state hook so existing session
  routes still import and run.
- Left hardware dependency support in `requirements-hardware.txt` rather than
  primary runtime requirements.
- Updated README language so MQTT is no longer described as required.

### Verification

- Confirmed no `paho` imports in hot-path packages:

```bash
grep -rn "import paho" api/ src/ spark/ analytics/ ml/
```

- Result: no output.
- Also searched primary app files for MQTT/ESP32 hot-path terms; no relevant
  primary references remained.
- Tried the requested boot command on port `8000`, but that port was already in
  use.
- Verified startup on alternate port `8010`:

```bash
timeout 8s uvicorn api.main:app --reload --port 8010
```

- Result: app started and shut down cleanly with no MQTT connection attempts or
  MQTT-related errors.

### Notes

- `withMPU/withMPU.ino` was not present in the repository, so there was no file
  to move. `legacy/hardware/README.md` records the intended destination if the
  asset is recovered later.

## Step 3: Synthetic Longitudinal Sleep Data Generator

### What Was Done

- Added `scripts/generate_synthetic_sleep.py`.
- Generated:
  - `data/synthetic/sleep_observations.csv`
- The generator creates longitudinal observation-level sleep data with:
  - `120` users by default
  - `70` nights per user by default
  - `100-200` observations per user-night
  - More than `1.2M` generated observation rows
- Included required columns:
  - `user_id`
  - `session_id`
  - `timestamp`
  - `date`
  - `heart_rate`
  - `acc_x`
  - `acc_y`
  - `acc_z`
  - `sleep_stage`
  - `bed_time`
  - `sleep_onset`
  - `wake_time`
  - `caffeine`
  - `screen_time`
  - `exercise_minutes`
  - `stress_level`
  - `nap_minutes`
  - `awakenings`
  - `event_count`
  - `spo2`

### Why It Was Done

The upcoming Spark pipeline needs enough longitudinal data to make distributed
ingestion, aggregation, window functions, and trend calculations meaningful.
The original sample dataset is small, so synthetic data gives the migration a
realistic big-data-style development and demo input.

### How It Was Done

- Used `datasets/participant_info.csv` as seed profiles where possible.
- Synthesized additional users until the default population reached `120`.
- Assigned some users persistent poor-sleeper traits and some elevated event
  rates.
- Generated night-level lifestyle and sleep-context fields such as caffeine,
  screen time, exercise, stress, naps, awakenings, bed time, sleep onset, and
  wake time.
- Generated observation-level physiology and motion:
  - N3 has lower movement and lower heart rate.
  - Wake has higher movement and higher heart rate.
  - REM and event-heavy users can show more events and SpO2 dips.
  - Poor sleepers have more wake/N1, fewer N3 periods, and more awakenings.

### Verification

Commands run:

```bash
python scripts/generate_synthetic_sleep.py
wc -l data/synthetic/sleep_observations.csv
python -c "import pandas as pd; df=pd.read_csv('data/synthetic/sleep_observations.csv', nrows=5); print(df.columns.tolist()); print(df.head())"
python -m py_compile scripts/generate_synthetic_sleep.py
```

Observed results:

- CSV line count: `1,259,953`, including header.
- Data rows: `1,259,952`.
- Users: `120`.
- Nights per user: `70`.
- Observations per user-night: `100-200`.
- Heart-rate range: `42.0` to `100.1`.
- SpO2 range: `82.0` to `100.0`.
- Sleep stages: `N1`, `N2`, `N3`, `R`, `W`.
- Event count range: `0` to `2`.

## Step 4: Spark Core Analytics Foundation

### What Was Done

- Added `spark/spark_session.py`.
  - Provides `create_spark_session()`.
  - Uses `local[*]`.
  - Sets `spark.sql.shuffle.partitions=8`.
  - Sets the Spark SQL session timezone to UTC.
  - Forces local file resolution with `spark.hadoop.fs.defaultFS=file:///`.
- Added `spark/schemas.py`.
  - Defines an explicit `StructType` for raw synthetic sleep observations.
  - Defines the accepted sleep-stage set: `W`, `N1`, `N2`, `N3`, `R`.
- Added `spark/ingestion.py`.
  - Adds `load_sleep_data(spark, path)` using the explicit schema.
  - Adds `load_processed_data(spark, path)` for Parquet reads.
  - Converts local relative paths to `file:///...` URIs so Spark does not try to
    resolve repo files as HDFS paths.
- Added `spark/cleaning.py`.
  - Adds `clean_sleep_data(df)`.
  - Drops duplicates by `user_id`, `session_id`, and `timestamp`.
  - Filters invalid required keys and heart rates outside `45-130`.
  - Keeps only valid sleep stages.
  - Fills null lifestyle fields.
  - Adds `movement_magnitude`.
- Added `spark/feature_engineering.py`.
  - Adds `add_rolling_features(df)`.
  - Uses a Spark `Window.partitionBy("user_id", "session_id").orderBy("timestamp").rowsBetween(-5, 0)`.
  - Adds rolling HR mean/std and movement mean/std.
- Added `spark/sleep_analytics.py`.
  - Adds `nightly_metrics(df)`.
  - Aggregates one row per `user_id`, `session_id`, and `date`.
  - Computes HR aggregates, movement average, observation counts, event totals,
    SpO2 aggregates, lifestyle nightly values, per-stage counts, per-stage
    percentages, sleep efficiency, and a `stage_pct_total` check column.
- Added `pyspark` to `requirements.txt`.

### Why It Was Done

This is the first real PySpark data path. Spark now owns the beginning of the
analytics workflow: schema-based ingestion, cleaning, feature engineering, and
nightly aggregation.

This directly addresses the blueprint requirement that Spark must be the actual
analytics engine rather than a decorative import.

### How It Was Done

- Used explicit Spark schemas instead of schema inference.
- Used Spark SQL functions for all cleaning and feature calculations.
- Used Spark window functions for short rolling features.
- Used `groupBy(...).agg(...)` for nightly metrics and derived percentages.
- Kept the functions small and composable so the future `spark/pipeline.py` can
  orchestrate them for both batch and per-session runs.

### Verification

Compiled the Spark modules:

```bash
python -m py_compile spark/spark_session.py spark/schemas.py spark/ingestion.py spark/cleaning.py spark/feature_engineering.py spark/sleep_analytics.py
```

Ran the requested pipeline stub:

```bash
python -c "
from spark.spark_session import create_spark_session
from spark.ingestion import load_sleep_data
from spark.cleaning import clean_sleep_data
from spark.feature_engineering import add_rolling_features
from spark.sleep_analytics import nightly_metrics

spark = create_spark_session()
raw = load_sleep_data(spark, 'data/synthetic/sleep_observations.csv')
print('raw rows:', raw.count())
clean = clean_sleep_data(raw)
print('clean rows:', clean.count())
featured = add_rolling_features(clean)
featured.select('user_id','timestamp','hr_rolling_mean','movement_rolling_mean').show(5)
nightly = nightly_metrics(featured)
nightly.show(5)
spark.stop()
"
```

Observed results:

- Raw rows: `1,259,952`.
- Clean rows: `1,231,804`.
- Cleaning reduced row count because the HR validation filter removed rows below
  the configured valid range.
- Rolling feature columns were populated.
- Nightly metrics produced rows with per-stage percentages.
- Example `stage_pct_total` values were `100.0` or floating-point equivalents
  such as `100.00000000000001`.

Ran an additional invariant check:

- Nightly rows: `8,400`.
- Distinct `(user_id, session_id, date)` keys: `8,400`.
- Stage percentage total min: `99.99999999999997`.
- Stage percentage total max: `100.00000000000003`.
- Rows with `stage_pct_total` between `99.99` and `100.01`: `8,400`.
- Rows with non-null rolling HR and movement means: `1,231,804`.

## Current Uncommitted Work

The following work is currently present in the working tree on
`pyspark-bigdata`:

- MQTT/hardware primary-path removal.
- Optional hardware dependency split.
- Initial `spark/`, `analytics/`, and `ml/` package placeholders.
- Synthetic data generator.
- Generated synthetic CSV.
- Spark session, schema, ingestion, cleaning, rolling feature, and nightly
  analytics modules.
- This progress report.

## Next Likely Step

Build the Spark pipeline orchestration and storage layer:

- `spark/pipeline.py`
- write cleaned/processed Parquet under `data/processed/`
- write nightly analytics Parquet under `data/parquet/`
- add a script such as `scripts/run_spark_pipeline.py`
- add focused tests for cleaning, rolling windows, and nightly metrics

This will turn the individual Spark functions into a repeatable batch/per-session
pipeline.
