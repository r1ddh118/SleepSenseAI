# SleepSenseAI Big Data Architecture

## Big Data Architecture

The project uses **Apache Spark through PySpark** as its main large-scale processing engine. However, the current implementation is primarily a **single-machine Spark batch system**, not a full Hadoop/Hive cluster.

The central flow is:

```text
Raw CSV files
    ↓
Spark DataFrame ingestion
    ↓
Distributed cleaning
    ↓
Window-based feature engineering
    ↓
Nightly aggregation
    ↓
Sleep score and risk features
    ↓
Longitudinal trends
    ↓
Partitioned Parquet files
    ↓
Spark SQL queries / API / reports
```

The main implementation is in `spark/pipeline.py`.

## 1. Spark Configuration

The Spark session is created in `spark/spark_session.py`.

Important settings include:

```python
SparkSession.builder
    .appName("SleepSenseAI-BigData")
    .master("local[*]")
    .config("spark.sql.shuffle.partitions", "8")
    .config("spark.driver.memory", "2g")
    .config("spark.sql.adaptive.enabled", "true")
```

### Meaning

- `local[*]` tells Spark to run locally using all available CPU cores.
- `spark.sql.shuffle.partitions = 8` controls the number of partitions created after shuffle operations.
- `spark.driver.memory = 2g` limits the Spark driver to approximately 2 GB.
- Adaptive Query Execution is enabled so Spark can optimize some SQL and shuffle operations at runtime.
- The session timezone is forced to UTC.

This is useful for development and moderate datasets, but it is not yet a distributed Spark cluster configuration. There is no:

- Spark master node
- Spark worker cluster
- YARN
- Kubernetes Spark deployment
- Hadoop HDFS
- Hive Metastore

The newer pipeline has a second Spark factory in `sleepsense_night/pipeline/spark_utils.py`. It also uses `local[*]`, but additionally disables ANSI SQL errors and allows a configurable shuffle partition count.

## 2. Input Ingestion

The original Spark pipeline reads raw CSV data using an explicit Spark schema in `spark/ingestion.py`.

```python
spark.read \\
    .option("header", True) \\
    .schema(SLEEP_SCHEMA) \\
    .csv(path)
```

The schema is defined in `spark/schemas.py`.

It describes one row as a sensor observation containing:

- `user_id`
- `session_id`
- `timestamp`
- Heart rate
- Accelerometer coordinates
- Sleep stage
- Bedtime and wake time
- Lifestyle data
- Breathing events
- SpO2

The explicit schema is important for Big Data processing because Spark does not need to infer the type of every column by scanning the input first. This avoids inconsistent type inference and makes the pipeline more predictable.

The ingestion function returns a Spark `DataFrame`, not a pandas DataFrame. Therefore, the raw file can be processed using Spark transformations.

The project also has Parquet readers:

```python
load_processed(...)
load_parquet_analytics(...)
load_user_history(...)
```

These functions use Spark's native Parquet reader rather than converting the data through pandas.

## 3. Distributed Data Cleaning

Cleaning is implemented in `spark/cleaning.py`.

The operations include:

1. Deduplicating observations.
2. Removing impossible heart-rate values.
3. Calculating movement magnitude.
4. Filling missing lifestyle values.
5. Deriving a date from the timestamp.
6. Validating sleep-stage labels.

For example:

```python
df.dropDuplicates(["user_id", "session_id", "timestamp"])
```

and:

```python
df.filter(F.col("heart_rate").between(35, 220))
```

These are Spark DataFrame transformations. Spark does not immediately execute them. It builds a logical execution plan first. Actual execution occurs later when an action such as `count()`, `write.parquet()`, or `show()` is called.

Movement magnitude is computed using Spark SQL functions:

```text
sqrt(acc_x² + acc_y² + acc_z²)
```

The important Big Data characteristic is that the code does not loop over rows in Python. The computation is expressed as Spark column operations, allowing Spark to execute it across partitions.

## 4. Window Functions

A major Spark feature used by this project is the window function API.

The original rolling feature implementation is in `spark/feature_engineering.py`.

```python
Window.partitionBy("user_id", "session_id") \\
      .orderBy("timestamp") \\
      .rowsBetween(-5, 0)
```

This means:

- Separate every user/session.
- Sort observations by timestamp.
- For each observation, look at the current row and five preceding rows.

The pipeline calculates:

- Rolling mean heart rate
- Rolling heart-rate standard deviation
- Rolling minimum and maximum heart rate
- Rolling movement statistics
- Rolling average sleep-stage score

This is preferable to a Python loop because Spark can distribute the calculation by user and session.

The newer pipeline uses similar windows in `sleepsense_night/pipeline/features.py`, but with more advanced processing:

- Rolling HR mean and standard deviation
- Rolling movement mean
- Rolling respiration statistics
- Rolling SpO2 averages
- Nightly median heart rate
- Sleep-stage inference
- Sleep onset detection
- Desaturation detection
- Wake and sleep run-length encoding

## 5. Nightly Aggregation

The original nightly aggregation is in `spark/sleep_analytics.py`.

The raw data is observation-level. The aggregation converts it into one row per:

```text
(user_id, session_id, date)
```

The main operation is:

```python
df.groupBy("user_id", "session_id", "date").agg(...)
```

It calculates:

- Average, minimum, maximum, and standard deviation of heart rate
- Average and standard deviation of movement
- Number of observations
- Counts for N1, N2, N3, REM, and wake stages
- Sleep-stage fractions
- Sleep efficiency
- Estimated sleep duration
- Breathing-event rate
- Average SpO2
- Lifestyle values

For example:

```text
n3_fraction = n3_count / observations
wake_fraction = wake_count / observations
sleep_efficiency = 1 - wake_fraction
```

This is the first major reduction in data volume:

```text
Many sensor observations
        ↓ groupBy
One nightly analytics row
```

The aggregation involves a shuffle because records belonging to the same user/session/date may initially exist in different Spark partitions.

## 6. Sleep Score and Risk Features

After nightly aggregation, the main pipeline adds the sleep score using:

```python
calculate_sleep_score_column(nightly)
```

That logic is in the analytics layer rather than the Spark package, but it operates on Spark DataFrame columns.

Risk features are added in `spark/risk_analysis.py`.

It uses a 30-row window per user:

```python
Window.partitionBy("user_id") \\
      .orderBy("date") \\
      .rowsBetween(-29, 0)
```

The pipeline calculates:

- Bedtime variability
- Wake-time variability
- Duration variability
- High breathing-event-rate flag
- High wake-fraction flag
- Low deep-sleep flag
- Low REM flag
- High heart-rate flag
- High heart-rate-variability flag

The `risk_level` is then derived in `spark/pipeline.py`:

- `HIGH` if at least three risk flags are active
- `MODERATE` if at least one risk flag is active
- `LOW` otherwise

## 7. Longitudinal Processing

The longitudinal stage is implemented in `spark/longitudinal.py`.

It creates per-user rolling statistics over 7, 14, and 30 observations:

- Seven-day average sleep score
- Fourteen-day average sleep score
- Thirty-day average sleep score
- Rolling duration
- Rolling sleep efficiency
- Rolling N3 and REM fractions
- Recent high-risk counts
- Recent poor-score counts
- High-risk count over the last three observations

This provides historical context for each night.

One technical detail is important: the implementation uses `rowsBetween`, not a calendar interval. Therefore, “7-day” means the current row plus the previous six records, assuming there is approximately one record per night. Missing calendar dates are not explicitly accounted for in this original pipeline.

The newer pipeline has similar functionality in `sleepsense_night/pipeline/trends_alerts.py`, including:

- Seven-, fourteen-, and thirty-night moving averages
- Improving, declining, or stable trend labels
- Circadian regularity detection
- Consecutive high-risk-night alerts

The alert logic uses the Spark “gaps and islands” technique to find consecutive date streaks.

## 8. Parquet Storage

The final output is written as Parquet in `spark/pipeline.py`:

```python
longitudinal.write \\
    .mode("overwrite") \\
    .partitionBy("user_id") \\
    .parquet(output_path)
```

The resulting directory generally looks like:

```text
data/parquet/
├── user_id=U001/
│   └── part-....parquet
├── user_id=U002/
│   └── part-....parquet
└── ...
```

Partitioning by `user_id` allows Spark to perform partition pruning. For example, when reading only one user:

```python
spark.read.parquet(path).filter(F.col("user_id") == user_id)
```

Spark may avoid scanning unrelated user partitions.

There is also an intermediate Parquet output under `data/processed/`, containing cleaned and feature-enriched observation data.

Parquet is a good Big Data storage format because it is:

- Columnar
- Compressed
- Schema-aware
- Efficient for analytical queries
- Able to read only the required columns
- Compatible with Spark

The newer night pipeline writes:

- Epoch-level Parquet
- Event Parquet
- Nightly metrics Parquet
- Alert Parquet

This is implemented in `sleepsense_night/run_pipeline.py`.

## 9. Spark SQL

The project uses Spark SQL temporary views in `spark/spark_sql.py`.

A DataFrame is registered as:

```python
nightly_df.createOrReplaceTempView("nightly_sleep")
```

Then SQL queries are executed using:

```python
spark.sql(...)
```

Implemented queries include:

- Users with the worst average sleep score
- Population sleep-stage distribution
- Date-ordered trends for one user
- Users with persistent high risk

For example, the worst-sleeper query groups data by user and calculates:

- Number of nights
- Average sleep score
- Average duration
- Average deep sleep
- Average REM
- Average efficiency
- Average wake fraction
- Average event rate

This is Spark SQL, but it is not Hive SQL backed by a Hive Metastore. It is querying a temporary in-memory Spark view.

## 10. Is Hive Implemented?

Hive is **not actually implemented as a storage or metastore layer** in the current repository.

There is no evidence of:

```python
.enableHiveSupport()
```

There are no calls to:

```python
saveAsTable(...)
```

There are no Hive DDL statements such as:

```sql
CREATE TABLE ...
```

There is no Hive Metastore configuration and no Hive service in either Docker Compose file.

The Docker configurations provide:

- Redis
- FastAPI
- Celery
- SQLite or PostgreSQL
- MQTT
- Nginx

They do not provide Spark, Hadoop, HDFS, or Hive services. Therefore, the accurate description is:

> The project uses Spark DataFrames, Spark SQL temporary views, and Parquet files. It does not currently use Hive tables or a Hive Metastore.

Spark SQL can work with Hive in a larger deployment, but this project has not configured that integration.

## 11. Batch Execution

The command-line entry point is `scripts/run_spark_pipeline.py`.

Typical usage:

```bash
python scripts/run_spark_pipeline.py
```

It defaults to:

```text
Input:  data/synthetic/sleep_observations.csv
Output: data/parquet
```

It can also process a raw directory:

```bash
python scripts/run_spark_pipeline.py \\
  --input data/raw \\
  --output data/parquet
```

The complete original pipeline is:

```text
load_sleep_data
    ↓
clean_sleep_data
    ↓
add_rolling_features
    ↓
nightly_metrics
    ↓
calculate_sleep_score_column
    ↓
calculate_risk_features
    ↓
risk_level
    ↓
add_trends
    ↓
write partitioned Parquet
```

The tests in `tests/test_spark_pipeline.py` verify:

- Spark ingestion
- Invalid heart-rate filtering
- Rolling feature creation
- Nightly aggregation
- Sleep-score creation
- Longitudinal trend columns

## 12. Per-User Processing Through Celery

The pipeline also supports a per-user/per-session path through `run_pipeline_for_user()` in `spark/pipeline.py`.

The intended flow is:

```text
New user CSV
    ↓
Celery worker
    ↓
Spark session
    ↓
Read existing Parquet history
    ↓
Combine historical and new data
    ↓
Recalculate user-level nightly metrics
    ↓
Write the user's Parquet partition
    ↓
Return latest result to the application
```

This allows the API to submit analytics work asynchronously rather than blocking an HTTP request.

The application-level database is separate from the Spark analytics store:

```text
PostgreSQL/SQLite → users, sessions, application records
Parquet           → analytical sensor and nightly data
Redis             → Celery broker/result backend
```

Redis is an asynchronous task queue component, not a Big Data storage engine.

## 13. The Newer `sleepsense_night` Pipeline

There are effectively two Spark-based analytical paths.

### Original `spark/` path

Focused on:

- Generic sleep observations
- Session-level aggregation
- Sleep score
- Rule-based risk
- Longitudinal statistics
- Partitioned analytics Parquet

### `sleepsense_night/` path

Focused on:

- Per-night wearable CSV files
- Sensor-quality metrics
- Sampling-step detection
- Forward-filling short sensor gaps
- Sleep-stage inference
- Sleep onset
- Desaturation events
- Wake bouts and micro-arousals
- Time-weighted nightly metrics
- Doctor alert streaks
- Quality reports

Its flow is:

```text
read_nights
    ↓
detect_step_seconds
    ↓
clean
    ↓
add_features
    ↓
compute_marks
    ↓
build_events
    ↓
aggregate_nights
    ↓
add_score
    ↓
add_risk_flags
    ↓
add_trends
    ↓
doctor_alerts
```

This pipeline is more detailed at the epoch and sensor-quality level. It also writes CSV files by calling `toPandas()` after Spark processing. That is acceptable for small reporting outputs, but it creates a scalability boundary: collecting large event or nightly datasets into the driver would not be appropriate for truly large data.

## 14. Big Data Technologies Present

### Actually implemented

- PySpark
- Spark DataFrames
- Spark SQL temporary views
- Spark window functions
- Spark aggregations
- Spark Parquet input/output
- Local multi-core execution with `local[*]`
- Celery-based asynchronous execution around processing
- Redis as a task broker
- Partitioned Parquet by user

### Not currently implemented

- Hive Metastore
- Hive managed or external tables
- HDFS
- YARN
- Spark standalone cluster
- Kubernetes Spark jobs
- Kafka streaming
- Structured Streaming
- Delta Lake
- Apache Iceberg
- Apache Hudi
- Distributed object storage such as S3
- Production Spark cluster deployment

## Overall Assessment

The project has a solid Spark-oriented analytical design:

- It avoids Python row-by-row loops in the core transformations.
- It uses DataFrames and column expressions.
- It uses window functions for temporal analytics.
- It reduces sensor-level data into nightly analytical records.
- It stores analytical results in partitioned Parquet.
- It exposes Spark SQL reporting queries.
- It supports both bulk batch processing and a per-user processing concept.

The accurate architectural description is:

> A local, multi-core PySpark batch analytics pipeline using Parquet as its analytical data store, with Spark SQL temporary views and Celery for asynchronous orchestration.

It should not currently be described as a Hive or Hadoop-based Big Data platform, because those components are not configured or running in the repository.
