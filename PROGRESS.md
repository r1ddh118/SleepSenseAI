# SleepSense AI - Project Progress & Architecture Report

> **Document Status**: Complete & Fully Verified  
> **Target Branch**: `pyspark-bigdata`  
> **Last Verified**: Current Release  

---

## 1. Executive Summary

SleepSense AI has successfully completed its transformation from a legacy CSV-upload / single-device hardware architecture into a production-ready, big-data scalable sleep analytics platform.

### Key Capabilities Completed

* **PySpark Distributed Analytics**: Ingestion, cleaning, feature engineering (sliding window HR & movement volatility), nightly aggregation, scoring, risk flags, and 7d/14d/30d longitudinal trends saved directly to **Parquet**.
* **Asynchronous Task Architecture**: FastAPI backend enqueues Celery jobs over Redis, delegating heavy PySpark computations away from the request thread.
* **Explainable Analytics**: Plain-Python academic 0–100 sleep score, rule-based condition risk screening (breathing disruption, insomnia patterns, circadian shift, sleep fragmentation), and metric-triggered recommendations.
* **Clinical & Doctor Tools**: Multi-night persistence-based doctor alerts and multi-format doctor report generation (JSON, CSV, HTML).
* **Modern Web Interface**: React 18, Vite, TypeScript, Tailwind CSS patient and doctor dashboards with interactive Recharts hypnograms and bio-metric charts.

---

## 2. Milestone Progress Checklist

- [x] **Step 1: Inventory & Codebase Audit**
  - Completed comprehensive repository grep scan for hardware dependencies (MQTT, paho, HiveMQ, ESP32).
  - Created `MIGRATION_CHECKLIST.md` documenting deprecated and active files.
- [x] **Step 2: Decouple Legacy Hardware / MQTT**
  - Removed MQTT/HiveMQ startup hooks from `api/main.py` and `app.py`.
  - Converted WebSocket manager into lightweight UI socket engine.
  - Isolated optional hardware code into `requirements-hardware.txt` and `hardware/`.
- [x] **Step 3: Synthetic Longitudinal Data Generator**
  - Built `scripts/generate_synthetic_sleep.py`.
  - Generated `1.2M+` longitudinal sleep observation rows across 120 users and 70 nights.
- [x] **Step 4: PySpark Core Analytics Foundation**
  - Built `spark/spark_session.py`, `spark/schemas.py`, `spark/ingestion.py`, `spark/cleaning.py`, `spark/feature_engineering.py`, and `spark/sleep_analytics.py`.
  - Implemented window functions for rolling HR/movement statistics and nightly aggregations.
- [x] **Step 5: PySpark Pipeline & Parquet Storage**
  - Built `spark/pipeline.py` and CLI runner `scripts/run_spark_pipeline.py`.
  - Output aggregated analytics table containing 8,400 nightly records to `data/parquet/`.
- [x] **Step 6: Academic Sleep Score Rule Engine**
  - Built `analytics/sleep_score.py` implementing a deterministic 0–100 weighted formula.
  - Attached non-clinical academic disclaimers.
- [x] **Step 7: Rule-Based Condition Screening**
  - Built `analytics/condition_risk.py` mapping nightly metrics to non-diagnostic risk categories.
  - Attached JSON risk flags inside the Spark Parquet pipeline.
- [x] **Step 8: Longitudinal Analytics Trends**
  - Updated `spark/longitudinal.py` with 7d, 14d, and 30d rolling window trends for sleep efficiency, duration, HR, stress, and event rates.
- [x] **Step 9: Metric-Triggered Recommendations**
  - Built `analytics/recommendations.py` emitting explainable user advice tied directly to metric thresholds.
- [x] **Step 10: Persistence-Based Doctor Alerting**
  - Built `analytics/alerts.py` and API router `api/routers/alerts.py` to flag multi-night score drops ($< 50$) or high risk ($\ge 3$ nights).
- [x] **Step 11: Multi-Format Doctor Report Builder**
  - Built `analytics/report_builder.py` and `api/routers/reports.py` rendering reports in JSON, CSV, and Jinja2-styled HTML.
- [x] **Step 12: Manual-Entry API & Asynchronous Polling**
  - Created `POST /api/v1/sessions/manual` and `GET /api/v1/sessions/{sid}/analytics`.
  - Enqueued Celery task `run_sleep_analytics` executing PySpark in background.
- [x] **Step 13: Full System Integration & SQLite Persistence**
  - Connected Celery worker to SQLite ORM (`ManualSleepSession`, `SleepAnalytics`, `DoctorAlert`).
  - Added adapter routes for React patient & doctor dashboards.
- [x] **Step 14: End-to-End Live Verification**
  - Verified 4-terminal execution (Redis + Celery + FastAPI + Vite).
  - Executed simulated multi-night declining patient workflow (`U034`) verifying automated doctor alerts.
- [x] **Step 15: Manual-Only Frontend Session Flow**
  - Updated React UI routes (`/record-sleep`), removing legacy live hardware recording screens.
  - Integrated saved session hypnograms, heart rate, and estimated EDA charts.

---

## 3. Detailed Verification History

### 1. PySpark Pipeline Verification

```bash
python scripts/run_spark_pipeline.py
```

* **Result**: Wrote `8,400` aggregated nightly records to `data/parquet/`.
* **Parquet Schema Verification**:

```text
root
 |-- user_id: string (nullable = true)
 |-- session_id: string (nullable = true)
 |-- date: string (nullable = true)
 |-- avg_hr: double (nullable = true)
 |-- stddev_hr: double (nullable = true)
 |-- avg_movement: double (nullable = true)
 |-- stddev_movement_magnitude: double (nullable = true)
 |-- n3_fraction: double (nullable = true)
 |-- rem_fraction: double (nullable = true)
 |-- wake_fraction: double (nullable = true)
 |-- sleep_efficiency: double (nullable = true)
 |-- sleep_score: double (nullable = true)
 |-- sleep_category: string (nullable = true)
 |-- risk_score: double (nullable = true)
 |-- risk_level: string (nullable = true)
 |-- risk_flags_json: string (nullable = true)
 |-- sleep_score_7d_avg: double (nullable = true)
 |-- sleep_score_7d_trend: double (nullable = true)
```

### 2. Integration Test Suite Execution

```bash
pytest tests/test_manual_sessions.py tests/test_alerts.py tests/test_report_builder.py tests/test_full_integration.py -v
```

* **Result**: `10 passed in 2.14s`

```bash
pytest tests/test_sleep_score.py tests/test_risk_analysis.py tests/test_recommendations.py -v
```

* **Result**: `12 passed in 1.48s`

### 3. Live Patient Multi-Night Decline Simulation (`U034`)

A 10-night simulation for patient `U034` was executed via the REST API:

| Night | Date | Sleep Score | Category | Risk Level | Persistence Alerts Generated |
| :---: | :---: | :---: | :---: | :---: | :--- |
| 1 | 2026-09-10 | 89.6 | EXCELLENT | LOW | None |
| 2 | 2026-09-11 | 88.0 | EXCELLENT | LOW | None |
| 3 | 2026-09-12 | 73.4 | GOOD | LOW | None |
| 4 | 2026-09-13 | 54.8 | FAIR | MODERATE | None |
| 5 | 2026-09-14 | 38.2 | POOR | HIGH | None |
| 6 | 2026-09-15 | 25.8 | POOR | HIGH | None |
| 7 | 2026-09-16 | 15.0 | POOR | HIGH | `persistent_high_risk` |
| 8 | 2026-09-17 | 10.3 | POOR | HIGH | `persistent_low_sleep_score` |
| 9 | 2026-09-18 | 7.8 | POOR | HIGH | `sustained_elevated_event_rate` |
| 10 | 2026-09-19 | 5.1 | POOR | HIGH | Updated evidence payloads |

* **Verification of Alerts Endpoint**: `curl http://localhost:8010/api/v1/doctor/alerts` returned 3 OPEN high-severity alerts.
* **Verification of Doctor Report Endpoint**: `curl http://localhost:8010/api/v1/doctor/patients/U034/report` compiled all 10 completed nights, open alerts, recommendations, and clinical disclaimer.

---

## 4. Current System Architecture Map

```text
┌─────────────────────────────────────────────────────────────────────────────┐
│                             FRONTEND WEB APP                                │
│                     (React 18 + Vite + Tailwind CSS)                        │
│   Routes: /dashboard, /record-sleep, /doctor, /session/:sid, /leaderboard  │
└──────────────────────────────────────┬──────────────────────────────────────┘
                                       │ REST / WebSocket (/api & /ws proxy)
                                       ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                            FASTAPI REST SERVER                              │
│             Endpoints: /sessions/manual, /doctor/alerts, /reports           │
│             Database: SQLite (sleepsense.db) via SQLAlchemy ORM            │
└──────────────────────────────────────┬──────────────────────────────────────┘
                                       │ Enqueue Celery Task
                                       ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                                REDIS BROKER                                 │
│                           redis://localhost:6379/0                          │
└──────────────────────────────────────┬──────────────────────────────────────┘
                                       │ Consume Asynchronous Analytics Job
                                       ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                             CELERY WORKER PROCESS                           │
│  1. Generates Transient Observation CSV in data/raw/manual/                  │
│  2. Invokes PySpark Session (spark/pipeline.py)                             │
│  3. Ingests, Cleans, Computes Window Features & Nightly Aggregates          │
│  4. Runs Analytics Engine (0-100 Score, Rule Risk Screening, Recs)          │
│  5. Writes Parquet Output to data/parquet/                                  │
│  6. Saves SleepAnalytics DB Record & Evaluates Doctor Persistence Alerts    │
└─────────────────────────────────────────────────────────────────────────┘
```

---

## 5. Summary of Key Files & Responsibilities

| File Path | Role & Key Responsibilities |
| :--- | :--- |
| `README.md` | Master project documentation, system overview, OS run commands, and API specs. |
| `MIGRATION_PROGRESS.md` | Step-by-step technical implementation log detailing code changes and rationale. |
| `PROGRESS.md` | Executive progress summary, milestone tracking, and verification record (this document). |
| `spark/pipeline.py` | PySpark big-data pipeline orchestrator connecting ingestion to Parquet write. |
| `analytics/sleep_score.py` | Deterministic 0–100 academic sleep score rule implementation. |
| `analytics/condition_risk.py` | Explainable rule-based condition risk screening engine. |
| `analytics/alerts.py` | Multi-night persistence-based doctor alert trigger logic. |
| `analytics/report_builder.py` | Patient and session report generator (JSON, CSV, HTML). |
| `api/main.py` | FastAPI application bootstrapper, CORS, and route registration. |
| `api/tasks.py` | Asynchronous Celery task definition for PySpark job runner. |
| `frontend/src/app/App.tsx` | React frontend main routing and page navigation container. |
| `scripts/generate_synthetic_sleep.py` | Synthetic longitudinal sleep dataset generator (1.2M+ rows). |
| `scripts/run_spark_pipeline.py` | Command-line execution entry point for PySpark batch pipeline. |

---

## 6. Conclusion & Next Steps

The SleepSense AI architecture is fully migrated, verified, and operational. All core requirements—including big-data PySpark pipelines, rule-based screening, doctor alerting, multi-format reporting, and a modern React UI—are completely implemented.
