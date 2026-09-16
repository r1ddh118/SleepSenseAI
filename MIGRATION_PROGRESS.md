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
- Hardware/MQTT/ESP3s2 code is optional legacy code, not part of the primary run
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

## Step 11: Doctor Report

### What Was Done

- Added `analytics/report_builder.py`.
  - Builds a complete doctor report payload.
  - Renders JSON-ready dictionaries.
  - Renders CSV.
  - Renders HTML using Jinja2.
- Added `api/routers/reports.py`.
  - `GET /api/v1/sessions/{sid}/report?format=json`
  - `GET /api/v1/sessions/{sid}/report?format=csv`
  - `GET /api/v1/sessions/{sid}/report?format=html`
- Registered the reports router in `api/main.py` before the legacy prediction
  CSV report route, so the new multi-format endpoint handles report requests.
- Added `tests/test_report_builder.py`.

### Why It Was Done

Doctors need a consolidated session report rather than raw model output or CSV
prediction rows. This creates a structured report layer that can later be filled
from Spark analytics summary tables, doctor alerts, recommendations, and DB
metadata.

### How It Was Done

The report contains the required sections:

- patient info
- sleep summary
- longitudinal trend
- risk assessment
- lifestyle
- recommendations
- alerts
- model info
- disclaimer

The medical disclaimer text is present verbatim:

```text
SleepSense AI reports are academic analytics summaries only; they are not clinically validated, are not a medical diagnosis, and must not be used to diagnose or rule out any medical condition.
```

The report endpoint currently assembles available DB data from:

- `Session`
- latest `Prediction`
- matching `DoctorAlert` rows

Sections that need the future Spark-to-DB bridge are still rendered with a clear
`Not available in DB yet` message instead of being omitted.

### Verification

Compiled updated files:

```bash
python -m py_compile analytics/report_builder.py api/routers/reports.py api/main.py tests/test_report_builder.py
```

Ran:

```bash
python -m pytest tests/test_report_builder.py -v
```

Observed:

- `3 passed`

Also verified:

```bash
python -c "import api.main; print('api import ok')"
```

Observed:

- `api import ok`

Pending live check:

```bash
curl "http://localhost:8000/api/v1/sessions/1/report?format=json" | jq
curl "http://localhost:8000/api/v1/sessions/1/report?format=html" -o /tmp/report.html
```

This requires the API server to be running and a session row with ID or SID `1`
to exist in the active database.

## Step 12: Manual-Entry API And Frontend

### What Was Done

- Added `ManualSleepSession` ORM model.
- Added `SleepAnalytics` ORM model.
- Added `POST /api/v1/sessions/manual`.
  - Accepts manual sleep fields.
  - Allows `"unknown"`/blank optional values.
  - Saves a raw manual session row.
  - Creates an initial `SleepAnalytics(status="PROCESSING")` row.
  - Enqueues `run_sleep_analytics(session_id)` via Celery.
  - Returns immediately:

```json
{"session_id": "...", "status": "PROCESSING"}
```

- Added `GET /api/v1/sessions/{sid}/analytics`.
  - Resolves either DB session ID or SID.
  - Returns `PROCESSING`, `COMPLETED`, or `FAILED`.
  - Returns sleep score, risk, recommendations, metrics, and Spark job ID when
    complete.
- Added Celery task `run_sleep_analytics(session_id)`.
  - Reads the saved manual row.
  - Builds a small observation-level CSV under `data/raw/manual/`.
  - Runs the Spark chain outside the request thread:
    - ingestion
    - cleaning
    - feature engineering
    - nightly metrics
    - sleep score
    - risk features
    - longitudinal metrics
  - Generates metric-triggered recommendations.
  - Stores the result in `SleepAnalytics`.
- Added frontend page:
  - `frontend/src/app/pages/RecordSleep.tsx`
- Added frontend routes:
  - `/record-sleep`
  - `/doctor`
- Updated patient dashboard CTA to open `/record-sleep`.
- Added `tests/test_manual_sessions.py`.

### Why It Was Done

The primary app path is now manual entry -> DB raw row -> Celery -> Spark
analytics -> polling, instead of hardware/MQTT or inline request processing.

This preserves the architecture rule that FastAPI should save/enqueue and return
quickly, while Celery owns the Spark work.

### How It Was Done

- The manual endpoint is intentionally unauthenticated for the current demo curl
  workflow.
- Unknown values are stored as `None`.
- The Celery task adapts a manual nightly summary into a small observation CSV so
  the same Spark modules are still used.
- The frontend form polls `GET /api/v1/sessions/{id}/analytics` every 2.5
  seconds until the status changes away from `PROCESSING`.

### Verification

Compiled backend files:

```bash
python -m py_compile api/models_db.py api/database.py api/schemas.py api/routers/sessions.py api/tasks.py
```

Ran manual-session tests:

```bash
python -m pytest tests/test_manual_sessions.py -v
```

Observed:

- `2 passed`

Covered cases:

- Manual submission saves `Session`, `ManualSleepSession`, and
  `SleepAnalytics(PROCESSING)`.
- Celery `.delay()` is called with the session ID.
- The response is immediate and returns `PROCESSING`.
- Polling the analytics endpoint returns a processing payload before worker
  completion.

Frontend verification:

```bash
npm run build
```

Could not run because `vite` is not installed in the current frontend
environment:

```text
sh: line 1: vite: command not found
```

Pending live verification:

- Start Redis.
- Start Celery worker.
- Start FastAPI.
- Submit:

```bash
curl -X POST http://localhost:8000/api/v1/sessions/manual \
  -H "Content-Type: application/json" \
  -d '{"user_id":"U034","date":"2026-09-10","sleep_efficiency":0.82,"n3_fraction":0.12,"rem_fraction":0.18,"wake_fraction":0.14,"screen_time":150,"stress_level":7}'
```

- Poll:

```bash
curl http://localhost:8000/api/v1/sessions/<id>/analytics
```

Expected:

- First response: `PROCESSING`.
- Later response: `COMPLETED` with sleep score, risk, recommendations, and
  Spark-derived metrics.

## Step 13: Full Integration Chain Smoke Test

### What Was Done

- Wired completed manual Spark analytics into persistence-based doctor alert
  creation inside `tasks.run_sleep_analytics`.
- Added `_analytics_history_for_patient()` so each completed manual session can
  evaluate the patient's recent nightly history.
- Updated `api/routers/reports.py` so doctor reports prefer `SleepAnalytics`
  and manual-entry data when available.
- Updated `api/routers/frontend_adapter.py` so the dashboard and session detail
  pages expose Spark analytics scores, stage percentages, risk level, and
  recommendations.
- Added `tests/test_full_integration.py`.
- Added `tests/conftest.py` so repo-root and API imports work consistently when
  test files are run alone or in groups.
- Added `data/raw/manual/` to `.gitignore` because manual analytics jobs create
  transient observation CSVs there.

### Why It Was Done

The manual-entry flow already saved raw rows and queued Celery, but the final
application chain needed the downstream consumers to use the new analytics
record:

- alerts should be created after the Celery/Spark job finishes;
- reports should include sleep score, risk, lifestyle, longitudinal, alert, and
  recommendation sections from `SleepAnalytics`;
- the dashboard should show the new analytics result instead of legacy zeros or
  only old `Prediction` rows.

### How It Was Done

- The Celery task now commits `SleepAnalytics(COMPLETED)`, rebuilds the
  patient's completed nightly history, and calls
  `create_alerts_for_history()`.
- The report route now loads:
  - `ManualSleepSession`
  - `SleepAnalytics`
  - legacy `Prediction` only as fallback
- The frontend adapter now converts analytics metrics into the frontend's
  expected dashboard shape.
- The integration test runs this chain synchronously:
  - manual route function saves session rows;
  - Celery task runs synchronously;
  - Spark calls are replaced with a deterministic fake DataFrame pipeline for a
    fast local smoke test;
  - analytics endpoint, doctor alerts, report payload, and dashboard payload are
    checked from the real DB models.

### Verification

Focused integration test:

```bash
pytest tests/test_full_integration.py -v
```

Observed:

- `1 passed`

Focused regression suite:

```bash
pytest tests/test_manual_sessions.py tests/test_alerts.py tests/test_report_builder.py tests/test_full_integration.py -v
```

Observed:

- `10 passed`

Compile check:

```bash
python -m py_compile api/tasks.py api/routers/reports.py api/routers/frontend_adapter.py tests/test_full_integration.py tests/conftest.py
```

Observed:

- no compile errors

### Notes

- The integration test does not start Redis, Uvicorn, or a JVM-backed Spark
  session. It verifies application wiring around the Celery task with a
  deterministic local Spark stand-in.
- Live verification was also run:

```bash
python scripts/generate_synthetic_sleep.py
python scripts/run_spark_pipeline.py
uvicorn api.main:app --reload
```

Observed:

- Synthetic generator wrote `1,259,952` rows.
- Spark pipeline wrote `data/parquet` with `8,400` nightly rows.
- `uvicorn api.main:app --reload --port 8000` could not bind because port
  `8000` was already in use.
- The same app booted cleanly on port `8010`:

```bash
timeout 8s uvicorn api.main:app --reload --port 8010
```

Observed startup:

```text
Application startup complete.
```

## Step 14: Live Redis + Celery + Uvicorn Smoke Test

### What Was Done

- Started Redis locally and confirmed broker connectivity:

```bash
redis-cli ping
```

Observed:

- `PONG`

- Started the Celery worker against the real task module:

```bash
PYTHONPATH=api:. celery -A tasks worker --loglevel=info --concurrency=1
```

Observed:

- worker connected to `redis://localhost:6379/0`;
- task registry included `tasks.run_sleep_analytics`;
- Spark session creation happened inside the worker with no Java/JVM traceback.

- Added `api/celery_app.py` so this equivalent command also has a valid target:

```bash
celery -A api.celery_app worker --loglevel=info
```

- Started FastAPI on port `8010`.
- Confirmed basic routes:

```bash
curl -s http://localhost:8010/docs -o /dev/null -w "%{http_code}\n"
curl -s http://localhost:8010/api/v1/doctor/alerts -o /dev/null -w "%{http_code}\n"
```

Observed:

- both returned `200`.

### One-Session Round Trip

Submitted:

```bash
curl -s -X POST http://localhost:8010/api/v1/sessions/manual \
  -H "Content-Type: application/json" \
  -d '{"user_id":"U034","date":"2026-09-10","sleep_efficiency":0.82,"n3_fraction":0.12,"rem_fraction":0.18,"wake_fraction":0.14,"screen_time":150,"stress_level":7}'
```

Observed:

```json
{"session_id":"10","id":"10","status":"PROCESSING"}
```

First analytics poll returned `PROCESSING`. The Celery worker then completed
the Spark-backed task:

```text
Manual Spark analytics complete
Task tasks.run_sleep_analytics[...] succeeded ... {'session_id': 10, 'status': 'COMPLETED', 'sleep_score': 89.6, 'alerts_created': 0}
```

Later analytics poll returned `COMPLETED` with:

- `sleep_score: 89.6`
- `sleep_category: EXCELLENT`
- `risk_level: LOW`
- metric-triggered recommendations for screen time and stress.

### U034 Declining Demo

Submitted a sequence of worsening nights for `U034`. The completed live scores
were:

| Date | Score | Risk |
| --- | ---: | --- |
| 2026-09-10 | 89.6 | LOW |
| 2026-09-11 | 88.0 | LOW |
| 2026-09-12 | 73.4 | LOW |
| 2026-09-13 | 54.8 | MODERATE |
| 2026-09-14 | 38.2 | HIGH |
| 2026-09-15 | 25.8 | HIGH |
| 2026-09-16 | 15.0 | HIGH |
| 2026-09-17 | 10.3 | HIGH |
| 2026-09-18 | 7.8 | HIGH |
| 2026-09-19 | 5.1 | HIGH |

Doctor alerts endpoint:

```bash
curl -s http://localhost:8010/api/v1/doctor/alerts
```

Observed three `OPEN`, `HIGH` alerts because three persistence rules were
satisfied:

- `persistent_low_sleep_score`
  - evidence: `sleep_score < 50 for >=5 of last 7 nights`
- `persistent_high_risk`
  - evidence: `risk_level == HIGH for >=3 consecutive nights`
- `sustained_elevated_event_rate`
  - evidence: elevated event rate for consecutive/recent nights

Patient report endpoint:

```bash
curl -s http://localhost:8010/api/v1/doctor/patients/U034/report
```

Observed:

- `night_count: 10`
- completed nightly history only;
- all completed scores and risk levels listed;
- `open_alert_count: 3`;
- medical disclaimer present verbatim:

```text
SleepSense AI reports are academic analytics summaries only; they are not clinically validated, are not a medical diagnosis, and must not be used to diagnose or rule out any medical condition.
```

### Fixes From The Live Run

- The previous `404` on `localhost:8000` was from another process already
  bound to port `8000`; the new app had exited with `Address already in use`.
  Port `8010` was used for the live smoke test.
- Patient-level reports now include only `SleepAnalytics(status="COMPLETED")`
  rows, so stale `PROCESSING` rows from interrupted attempts do not pollute the
  doctor report.
- Manual session responses include both `session_id` and `id` for compatibility
  with shell snippets that use `jq -r .id`.

### Verification After Fixes

```bash
python -m py_compile api/celery_app.py api/routers/reports.py
pytest tests/test_report_builder.py tests/test_full_integration.py -v
```

Observed:

- `4 passed`

## Current Status

The PySpark migration now has the main functional pieces in place:

- hardware/MQTT removed from the primary run path;
- synthetic longitudinal data generation;
- Spark ingestion, cleaning, rolling features, nightly analytics, sleep score,
  risk features, longitudinal metrics, SQL helper, Parquet pipeline, and CLI;
- academic sleep score and rule-based risk engines;
- metric-triggered recommendations;
- persistence-based doctor alerts;
- doctor report generation in JSON, CSV, and HTML;
- manual-entry API, Celery analytics task, polling endpoint, and frontend
  screens;
- integration smoke coverage for manual input through dashboard/report/alerts.

## Next Likely Step

Decide the doctor-alert product policy:

- keep all simultaneous persistence alerts, as implemented now; or
- collapse multiple alerts for the same patient/window into one strongest
  doctor-facing alert.

The live smoke currently proves the full stack works, and it also shows why this
UI/product choice matters: one severe sustained decline can satisfy several
rules at once.
