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

## Step 5: Spark SQL, Parquet Output, And Pipeline Orchestrator

### What Was Done

- Added `spark/sleep_score.py`.
  - Adds a Spark-native `sleep_score` from nightly metrics.
  - Adds `sleep_category` values: `EXCELLENT`, `GOOD`, `FAIR`, `POOR`.
- Added `spark/risk_analysis.py`.
  - Adds non-diagnostic risk-screening features:
    - `event_rate`
    - `wake_fraction`
    - `deep_sleep_fraction`
    - `rem_fraction`
    - `risk_score`
    - `risk_level`
- Added `spark/longitudinal.py`.
  - Adds rolling 7-night, 14-night, and 30-night user-level trend metrics:
    - sleep score average
    - sleep efficiency average
    - risk score average
    - event rate average
    - nights included in each rolling window
- Added `spark/spark_sql.py`.
  - Registers the nightly analytics DataFrame as `nightly_sleep`.
  - Runs a representative Spark SQL query: average sleep score and risk score
    per user, ordered by lowest average sleep score.
- Added `spark/pipeline.py`.
  - Orchestrates ingestion -> cleaning -> rolling features -> nightly metrics
    -> sleep score -> risk features -> longitudinal metrics -> Parquet write.
- Added `scripts/run_spark_pipeline.py`.
  - CLI entry point for the Spark pipeline.
- Updated `spark/sleep_analytics.py`.
  - Added `stddev_movement_magnitude` to nightly metrics.
- Produced the analytics table at:
  - `data/parquet/`

### Why It Was Done

This turns the separate Spark functions into an executable analytics pipeline.
The output is now a queryable Parquet table, which is the intended storage shape
for high-volume analytics data. The relational database can later store summary
rows and paths/references instead of raw observation-level Spark output.

### How It Was Done

- Kept orchestration in `spark/pipeline.py`.
- Kept scoring, risk features, longitudinal windows, SQL helpers, and raw
  nightly aggregation in separate modules.
- Used Spark SQL temp views for representative analytical querying.
- Wrote the final enriched nightly table with:

```python
analytics.write.mode("overwrite").parquet(output_path)
```

- Used local `file:///` path normalization from `spark.ingestion` so Spark reads
  and writes repository paths locally instead of attempting HDFS resolution.

### Verification

Compiled the new modules:

```bash
python -m py_compile spark/sleep_score.py spark/risk_analysis.py spark/longitudinal.py spark/spark_sql.py spark/pipeline.py scripts/run_spark_pipeline.py
```

Ran the pipeline CLI:

```bash
python scripts/run_spark_pipeline.py
```

Observed SQL query sample:

```text
+-------+---------------+--------------+------+
|user_id|avg_sleep_score|avg_risk_score|nights|
+-------+---------------+--------------+------+
|S004   |56.14          |41.97         |70    |
|U0064  |60.94          |28.64         |70    |
|U0061  |62.07          |27.9          |70    |
|U0030  |67.82          |20.34         |70    |
|U0096  |68.54          |18.5          |70    |
+-------+---------------+--------------+------+
```

Observed pipeline result:

- Wrote nightly analytics Parquet to `data/parquet`.
- Total nights: `8,400`.

Read the Parquet output back with Spark:

```bash
python -c "
from spark.spark_session import create_spark_session
spark = create_spark_session()
df = spark.read.parquet('data/parquet')
df.printSchema()
df.show(5)
print('total nights:', df.count())
spark.stop()
"
```

Confirmed schema includes:

- Sleep score columns:
  - `sleep_score`
  - `sleep_category`
- Risk feature columns:
  - `event_rate`
  - `wake_fraction`
  - `deep_sleep_fraction`
  - `rem_fraction`
  - `risk_score`
  - `risk_level`
- Longitudinal columns:
  - `sleep_score_7d_avg`, `sleep_score_14d_avg`, `sleep_score_30d_avg`
  - `sleep_efficiency_7d_avg`, `sleep_efficiency_14d_avg`, `sleep_efficiency_30d_avg`
  - `risk_score_7d_avg`, `risk_score_14d_avg`, `risk_score_30d_avg`
  - `event_rate_7d_avg`, `event_rate_14d_avg`, `event_rate_30d_avg`
  - `nights_in_7d_window`, `nights_in_14d_window`, `nights_in_30d_window`

Confirmed row count:

- Total nights: `8,400`.

## Step 6: Academic Sleep Score Rule

### What Was Done

- Added `analytics/sleep_score.py`.
- Added `tests/test_sleep_score.py`.
- Added `pytest` to `requirements.txt`.

### Why It Was Done

The Spark pipeline produces nightly metrics, but the application also needs a
plain-Python business-rule layer that can explain user-facing scores without
running another Spark job. This step adds a deterministic 0-100 sleep score that
can be used by API/report code after Spark has already computed nightly
aggregates.

The score is explicitly labeled as academic analytics only. It is not clinically
validated and must not be presented as a medical diagnosis.

### How It Was Done

The score uses the requested weights:

- Efficiency: `25%`
- Duration: `20%`
- Deep sleep: `15%`
- REM sleep: `15%`
- Low wake fragmentation: `10%`
- HR stability: `10%`
- Movement stability: `5%`

`calculate_sleep_score(metrics)` returns:

- `score`
- `category`
- `score_type`
- `clinically_validated`
- `disclaimer`
- `metrics`
  - normalized inputs
  - component scores
  - component weights

The response disclaimer is:

```text
Academic analytics score only; not clinically validated and not a medical diagnosis.
```

### Verification

Compiled the module and tests:

```bash
python -m py_compile analytics/sleep_score.py tests/test_sleep_score.py
```

Ran the direct score check:

```bash
python -c "
from analytics.sleep_score import calculate_sleep_score
good = {'sleep_efficiency':0.92,'sleep_duration_hours':7.6,'n3_fraction':0.20,'rem_fraction':0.22,'wake_fraction':0.05,'hr_std':3.0,'movement_std':0.1}
poor = {'sleep_efficiency':0.60,'sleep_duration_hours':5.0,'n3_fraction':0.05,'rem_fraction':0.08,'wake_fraction':0.30,'hr_std':10.0,'movement_std':0.5}
print(calculate_sleep_score(good))
print(calculate_sleep_score(poor))
"
```

Observed results:

- Good synthetic input: score `91.7`, category `EXCELLENT`.
- Poor synthetic input: score `39.2`, category `POOR`.
- Both responses include `clinically_validated: False` and the academic
  analytics disclaimer.

Attempted the requested pytest command:

```bash
pytest tests/test_sleep_score.py -v
python -m pytest tests/test_sleep_score.py -v
```

Both could not run because `pytest` is not installed in the current environment.
`pytest` has been added to `requirements.txt` so this check will run after
dependencies are installed.

## Step 7: Rule-Based Risk Screening

### What Was Done

- Added `analytics/condition_risk.py`.
  - Implements a deterministic, non-diagnostic rule engine.
  - Returns `risk_flags` with:
    - `condition`
    - `risk`
    - `confidence`
    - `reasons`
    - academic/non-clinical disclaimer
- Added `tests/test_risk_analysis.py`.
  - Covers high wake fragmentation.
  - Covers a good sleeper with no material risk flags.
  - Covers elevated event/SpO2 breathing-pattern risk.
  - Covers circadian irregularity from timing variability.
- Updated `spark/risk_analysis.py`.
  - Computes requested risk features per nightly session:
    - `event_rate`
    - `wake_fraction`
    - `n3_fraction`
    - `rem_fraction`
    - `sleep_efficiency_fraction`
    - `avg_hr`
    - `hr_std`
    - `movement_std`
    - `bedtime_variability`
    - `wake_time_variability`
    - `duration_variability`
    - `sleep_duration_hours`
  - Preserves previous compatibility columns such as `deep_sleep_fraction`,
    `risk_score`, and `risk_level`.
  - Adds `risk_flags_json` to the Spark analytics output using the verified
    plain-Python rule engine.
- Updated `spark/sleep_analytics.py`.
  - Carries nightly `bed_time`, `sleep_onset`, and `wake_time` through
    aggregation so timing variability can be computed.
- Re-ran `scripts/run_spark_pipeline.py`.
  - Regenerated `data/parquet/` with the new risk feature columns and
    `risk_flags_json`.

### Why It Was Done

The project needs explainable risk screening before any ML model. This follows
the blueprint constraint: do not diagnose disease, and do not jump to Spark
MLlib until rule-based behavior is verified and labeled data exists.

The risk engine is explicitly labeled as academic screening only, not clinically
validated, and not a medical diagnosis.

### How It Was Done

- Spark computes quantitative risk features from nightly metrics.
- The Python rule engine maps those features to condition-like screening
  categories:
  - Sleep-disordered breathing pattern
  - Insomnia-like pattern
  - Circadian irregularity
  - Sleep fragmentation
  - Sleep architecture strain
- Each flag includes confidence and human-readable reasons.
- Spark stores the rule output per row as `risk_flags_json`.
- Timing variability uses a 7-night rolling user window over normalized
  bedtime, wake time, and derived sleep duration.

### Verification

Compiled updated files:

```bash
python -m py_compile analytics/condition_risk.py spark/risk_analysis.py spark/sleep_analytics.py tests/test_risk_analysis.py
```

Direct rule-engine check:

- High-wake synthetic sleeper returned:
  - `Insomnia-like pattern: HIGH`
  - `Sleep fragmentation: HIGH`
- Good synthetic sleeper returned:
  - `[]`

Test functions were invoked directly because `pytest` is still not installed in
the current environment:

```bash
python -c "import importlib.util; spec=importlib.util.spec_from_file_location('risk_tests','tests/test_risk_analysis.py'); mod=importlib.util.module_from_spec(spec); spec.loader.exec_module(mod); mod.test_high_wake_fraction_flags_sleep_fragmentation(); mod.test_good_sleeper_has_no_material_risk_flags(); mod.test_breathing_pattern_uses_events_and_spo2_without_diagnosis(); mod.test_circadian_irregularity_uses_timing_variability(); print('risk analysis test functions passed')"
```

Observed:

- `risk analysis test functions passed`

Attempted the requested command:

```bash
python -m pytest tests/test_risk_analysis.py -v
```

It could not run because `pytest` is not installed in the current environment.
`pytest` is already listed in `requirements.txt`.

Pipeline verification:

```bash
python scripts/run_spark_pipeline.py
```

Observed:

- Wrote nightly analytics Parquet to `data/parquet`.
- Total nights: `8,400`.

Manual synthetic user inspection:

- Bad sleepers:
  - `S004`: average score `56.14`, average risk `41.97`, flags included
    `Sleep-disordered breathing pattern: HIGH` and `Sleep fragmentation: HIGH`.
  - `U0064`: average score `60.94`, average risk `28.64`, flags included
    breathing pattern, fragmentation, and insomnia-like pattern.
  - `U0061`: average score `62.07`, average risk `27.90`, flags included
    breathing pattern and fragmentation.
- Good sleepers:
  - `U0054`: average score `91.40`, average risk `4.15`, representative
    `risk_flags_json` was `[]`.
  - `U0015`: average score `91.07`, average risk `4.34`, representative row was
    LOW overall with one moderate circadian timing variability flag.
  - `U0109`: average score `90.88`, average risk `4.27`, representative
    `risk_flags_json` was `[]`.

Confirmed the Parquet schema includes all requested risk feature columns and
`risk_flags_json`.

## Step 8: Longitudinal Analytics Trends

### What Was Done

- Updated `spark/longitudinal.py`.
- The module now computes rolling per-user averages and trend deltas for:
  - sleep score
  - sleep efficiency
  - duration
  - REM fraction
  - N3 fraction
  - wake fraction
  - average HR
  - stress level
  - risk score
  - event rate
- The primary demo/dashboard windows are:
  - 7-day window: `Window.partitionBy("user_id").orderBy("date").rowsBetween(-6, 0)`
  - 14-day window: `Window.partitionBy("user_id").orderBy("date").rowsBetween(-13, 0)`
- Existing 30-day window output is retained for compatibility with prior
  pipeline output.
- For each signal/window pair, the module emits:
  - `{signal}_{window}d_avg`
  - `{signal}_{window}d_trend`
- It also emits:
  - `nights_in_7d_window`
  - `nights_in_14d_window`
  - `nights_in_30d_window`

### Why It Was Done

The analytics dashboard needs longitudinal context, not just one-night metrics.
Rolling averages and trend deltas make it possible to show whether sleep score,
duration, REM, N3, wake, HR, and stress are improving or deteriorating over
recent nights.

### How It Was Done

- Centralized longitudinal signals in a `signals` mapping inside
  `add_longitudinal_metrics(df)`.
- Used Spark window functions over each user's ordered nightly rows.
- Defined trend as:

```text
current_value - rolling_average
```

This means negative score/duration/REM/N3 trends indicate the current night is
below the recent rolling average, while positive wake/HR/stress trends indicate
the current night is above the recent rolling average.

### Verification

Compiled the module:

```bash
python -m py_compile spark/longitudinal.py
```

Before this edit, the existing generated Parquet was inspected for the Phase-9
demo patient `U034`:

```bash
python -c "
from spark.spark_session import create_spark_session
spark = create_spark_session()
df = spark.read.parquet('data/parquet')
df.filter(df.user_id=='U034').select('date','sleep_score','sleep_score_7d_avg').orderBy('date').show()
spark.stop()
"
```

The final visible demo segment already showed the expected downward 7-day score
trend:

- `2026-03-05`: `sleep_score_7d_avg` about `90.64`
- `2026-03-07`: `sleep_score_7d_avg` about `87.61`
- `2026-03-09`: `sleep_score_7d_avg` about `79.27`
- `2026-03-11`: `sleep_score_7d_avg` about `66.19`

Pending verification:

- Re-run `python scripts/run_spark_pipeline.py` after Spark execution approval is
  available so `data/parquet/` is regenerated from the updated
  `spark/longitudinal.py`.
- Re-run the U034 check against the regenerated Parquet table.

## Step 9: Metric-Triggered Recommendations

### What Was Done

- Added `analytics/recommendations.py`.
- Refactored `advanced/recommendations.py` into a compatibility wrapper around
  the new analytics module.
- Added `tests/test_recommendations.py`.

### Why It Was Done

The old recommendation function accepted a single feature row and could return
generic advice. The migration requires recommendations to sit on top of
Spark-computed analytics and to be explainable: every recommendation must point
to the exact metric that triggered it.

### How It Was Done

- New signature:

```python
generate_recommendations(
    sleep_metrics,
    risk_metrics,
    lifestyle_metrics,
    longitudinal_metrics,
)
```

- Each recommendation includes:
  - `code`
  - `area`
  - `severity`
  - `trigger.metric`
  - `trigger.value`
  - `trigger.threshold`
  - `message`
- Missing metrics do not trigger recommendations.
- Good metrics do not produce generic "keep it up" advice.
- Legacy callers importing `advanced.recommendations.generate_recommendations`
  still work through a thin adapter, but the old generic rule body was removed.

### Verification

Ran the requested check:

```bash
python -m pytest tests/ -k recommendations -v
```

Observed:

- `3 passed`
- `8 deselected`

Manual bad-sleep input:

- `screen_time=185`
- `stress_level=8`
- `n3_fraction=0.06`
- `caffeine=90`

Observed recommendation areas:

- `deep_sleep`
- `fragmentation`
- `efficiency`
- `duration`
- `screen_time`
- `stress`

No caffeine recommendation was emitted because caffeine was below the configured
threshold.

## Step 10: Doctor Alerts

### What Was Done

- Added `analytics/alerts.py`.
  - Evaluates persistence-based doctor alert rules.
  - A single noisy night does not create an alert.
- Added `DoctorAlert` ORM model in `api/models_db.py`.
- Updated `api/database.py` so `DoctorAlert` is included in DB initialization.
- Added `api/routers/alerts.py`.
  - `GET /api/v1/doctor/alerts`
  - `POST /api/v1/doctor/alerts/{id}/acknowledge`
  - `POST /api/v1/doctor/alerts/{id}/resolve`
  - Helper: `create_alerts_for_history(db, nightly_rows, doctor_id=None)`
- Registered the alerts router in `api/main.py`.
- Added `DoctorAlertOut` schema in `api/schemas.py`.
- Added `tests/test_alerts.py`.

### Why It Was Done

Doctor alerts must be persistence-based, not triggered by one noisy night. This
implements the blueprint guardrail that alerts require sustained evidence before
appearing in a doctor workflow.

### How It Was Done

The alert rules currently include:

- `risk_level == HIGH` for at least 3 consecutive nights.
- `sleep_score < 50` for at least 5 of the last 7 nights.
- `event_rate >= 0.025` for at least 4 of the last 7 nights, or at least 3
  consecutive nights.

Each alert stores:

- patient ID
- session ID
- alert type
- severity
- reason
- evidence JSON
- lifecycle status: `OPEN`, `ACKNOWLEDGED`, or `RESOLVED`

The API lifecycle can acknowledge and resolve alerts without deleting evidence.

### Verification

Compiled updated files:

```bash
python -m py_compile analytics/alerts.py api/routers/alerts.py api/models_db.py api/database.py api/schemas.py api/main.py tests/test_alerts.py
```

Ran:

```bash
python -m pytest tests/test_alerts.py -v
```

Observed:

- `4 passed`

Covered cases:

- Sustained-decline patient `U034` creates expected HIGH persistent alert(s)
  with evidence.
- A control user with one bad/noisy night creates no alert.
- `POST /doctor/alerts/{id}/acknowledge` behavior flips status to
  `ACKNOWLEDGED`.
- Re-evaluating the same persisted alert is idempotent and does not duplicate an
  existing OPEN alert.

Attempted an in-process route smoke check with FastAPI `TestClient`, but it did
not return promptly in this environment and was stopped. The router/model logic
is covered by direct tests, and `api.main` imports successfully with the new
router registered.

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
- Spark SQL helper, sleep score transform, risk feature transform, longitudinal
  transform, pipeline orchestrator, and pipeline CLI.
- Generated analytics Parquet table under `data/parquet/`.
- Plain-Python academic sleep score module and tests.
- Rule-based condition risk engine and risk-analysis tests.
- Regenerated analytics Parquet with risk feature columns and `risk_flags_json`.
- Expanded Spark longitudinal averages and trend deltas.
- Metric-triggered recommendation engine and tests.
- Persistence-based doctor alert engine, ORM model, router, and tests.
- This progress report.

## Next Likely Step

Build the plain-Python analytics/reporting layer and persistence bridge:

- `analytics/condition_risk.py`
- `analytics/alerts.py`
- `analytics/recommendations.py`
- `analytics/report_builder.py`
- API/Celery task updates to call `spark/pipeline.py` and store summary rows.

This will connect the Spark-computed table to non-diagnostic business rules,
persistence-based alerts, and user/doctor-facing artifacts.
