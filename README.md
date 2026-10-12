# SleepSense AI: Scalable Sleep Analytics and Risk Screening

> **Non-Clinical / Academic Disclaimer**  
> SleepSense AI provides academic, research, and product analytics only. It is **not** a medical device, does **not** provide a clinical diagnosis, and must **not** be used to diagnose, treat, or rule out any medical condition (such as obstructive sleep apnea, central sleep apnea, or clinical insomnia). All risk categories and scores are rule-based screening indicators for academic and informational use only.

---

## Table of Contents

1. [Why SleepSense AI? (Project Purpose)](#why-sleepsense-ai-project-purpose)
2. [What Is SleepSense AI? (System Overview)](#what-is-sleepsense-ai-system-overview)
3. [Architecture & Data Flow](#architecture--data-flow)
4. [Exhaustive Codebase File Structure](#exhaustive-codebase-file-structure)
5. [Core Analytics & Feature Breakdown](#core-analytics--feature-breakdown)
6. [Cross-Platform Execution Guide (Linux, macOS, Windows)](#cross-platform-execution-guide-linux-macos-windows)
7. [Running the Synthetic Data & PySpark Pipeline](#running-the-synthetic-data--pyspark-pipeline)
8. [Running the Live Application (4-Terminal Workflow)](#running-the-live-application-4-terminal-workflow)
9. [REST API Endpoint Specifications](#rest-api-endpoint-specifications)
10. [Automated Testing & Quality Verification](#automated-testing--quality-verification)
11. [Generated File & Cache Management](#generated-file--cache-management)
12. [Legacy Components & Future Roadmap](#legacy-components--future-roadmap)

---

## Why SleepSense AI? (Project Purpose)

Sleep disorders such as Obstructive Sleep Apnea (OSA), clinical insomnia, circadian rhythm disruption, and severe sleep fragmentation affect hundreds of millions of individuals globally. Traditional sleep diagnostics rely on Polysomnography (PSG)—an expensive, inconvenient overnight laboratory study requiring dozens of wired sensors and manual scoring by sleep technologists.

**SleepSense AI** was created to address the need for a **scalable, continuous, big-data sleep analytics platform**. Rather than relying on single-night laboratory snapshots, SleepSense AI enables multi-night longitudinal tracking by ingesting sleep observations, stage breakdowns, physiological telemetry (heart rate, SpO2), and lifestyle factors (caffeine, screen time, stress).

### Key Project Objectives

1. **Big-Data Scalability**: Leverage **PySpark** to ingest, clean, and process millions of observation-level telemetry records across hundreds of users and longitudinal timeframes.
2. **Explainable Screening**: Replace black-box machine learning predictions with a deterministic 0–100 academic sleep score and explainable, rule-based condition screening (identifying sleep fragmentation, breathing-disruption patterns, and circadian shifts).
3. **Multi-Night Longitudinal Trends**: Calculate 7-day, 14-day, and 30-day rolling window trends to track sleep efficiency degradation and stress correlations over time.
4. **Physician & Patient Dashboards**: Provide patients with intuitive hypnograms and bio-metric charts while equipping clinicians with multi-night persistence-based alerting and downloadable reports (JSON, CSV, HTML).
5. **Decoupled Architecture**: Provide an asynchronous, production-ready stack using FastAPI, Celery, Redis, and PySpark without hardware vendor lock-in.

---

## What Is SleepSense AI? (System Overview)

SleepSense AI is a full-stack, distributed sleep analytics application. It accepts night-level or observation-level sleep input, processes the data asynchronously via Celery and PySpark, stores aggregates in Parquet and SQLite, and presents actionable analytics through a modern React/Vite web interface.

### Core Stack & Technologies

* **Big-Data Engine**: PySpark 3.5+ (PySpark SQL, Window Functions, Parquet storage)
* **REST API Server**: FastAPI (Uvicorn ASGI runner, Async SQL models, OpenAPI docs)
* **Task Worker Queue**: Celery with Redis broker (`redis://localhost:6379/0`)
* **Relational Storage**: SQLite via SQLAlchemy (`sleepsense.db`)
* **Analytics Engine**: Plain Python rules & mathematical score normalization (academic 0–100 score, condition risk screening, metric-triggered recommendations)
* **Frontend Web Application**: React 18, Vite, TypeScript, Tailwind CSS, Recharts, Lucide Icons
* **CLI & Tooling**: Pytest, Synthetic Data Generator (`scripts/generate_synthetic_sleep.py`), Pipeline Orchestrator (`scripts/run_spark_pipeline.py`)

---

## Architecture & Data Flow

```text
 ┌─────────────────────────────────┐       ┌─────────────────────────────────┐
 │ 1. GENERATE                     │       │ 2. UPLOAD                       │
 │ scripts/generate_night_csv.py   │ ────► │ POST /api/v1/sessions/upload    │
 │ (1 Hz synthetic sensor stream)  │       │ (Validates 13-column contract)  │
 └─────────────────────────────────┘       └────────────────┬────────────────┘
                                                            │
                                                            ▼
 ┌─────────────────────────────────┐       ┌─────────────────────────────────┐
 │ 4. EDA & TIMELINE               │       │ 3. PROCESS                      │
 │ - Tonic/Phasic EDA Filter       │ ◄──── │ spark/night_pipeline.py         │
 │ - Clock-Time Epoching (W/N/R)   │       │ - Streaming Cleaning & Ranges   │
 │ - Cardiorespiratory & SpO2      │       │ - AHI / Desat Event Detection   │
 └────────────────┬────────────────┘       └─────────────────────────────────┘
                  │
                  ▼
 ┌─────────────────────────────────┐       ┌─────────────────────────────────┐
 │ 5. REPORT                       │       │ 6. DOCTOR PORTAL                │
 │ GET /api/v1/sessions/{sid}/report│ ────► │ GET /api/v1/doctor/...          │
 │ (JSON, CSV, HTML, PDF download) │       │ - Assignment-Gated Access (403) │
 │ Split-Action Download Button    │       │ - 9 Clinical Tabs + Triage      │
 └─────────────────────────────────┘       └─────────────────────────────────┘
```

---

## Exhaustive Codebase File Structure

Below is a complete description of every file and directory in the project:

```text
SleepSenseAI/
├── README.md                      # Primary documentation & system overview (this file)
├── MIGRATION_PROGRESS.md          # Living engineering log tracking PySpark migration steps
├── PROGRESS.md                    # Project milestone tracker & verification report
├── MIGRATION_CHECKLIST.md         # File inventory & deprecation tracking list
├── app.py                         # Root launcher script for multi-process development
├── docker-compose.yml             # Docker Compose file for Redis & local infrastructure
├── requirements.txt               # Main Python dependencies (PySpark, FastAPI, Celery, Redis, pytest)
├── requirements-hardware.txt      # Optional legacy hardware dependencies (paho-mqtt)
├── sleepsense.db                  # SQLite database created at runtime for session & alert metadata
│
├── spark/                         # PySpark Big-Data Engine
│   ├── __init__.py                # Package marker
│   ├── spark_session.py           # Creates local PySpark session with UTC timezone & file:/// URIs
│   ├── schemas.py                 # Explicit StructType schemas for raw observation CSVs
│   ├── night_schema.py            # 13-column 1 Hz sensor contract & range validator
│   ├── night_generator.py         # Multi-profile synthetic whole-night sensor CSV generator
│   ├── night_pipeline.py          # PySpark streaming epoching, stage inference & EDA decomposition
│   ├── ingestion.py               # Path-safe loader functions for raw CSVs and processed Parquet
│   ├── cleaning.py                # Spark SQL cleaner: deduping, range checks (HR 45-130), movement calc
│   ├── feature_engineering.py     # Sliding window functions (-5 to 0) for rolling HR & movement stddev/mean
│   ├── sleep_analytics.py         # Nightly groupBy aggregation (stage %, HR stats, sleep efficiency)
│   ├── sleep_score.py             # Batch Spark SQL expressions for 0-100 scoring & categories
│   ├── risk_analysis.py           # Quantitative risk features & JSON risk flags attachment
│   ├── longitudinal.py            # Rolling 7d/14d/30d user-level averages & trend deltas
│   ├── spark_sql.py               # Relational Spark SQL temp view registration and query runner
│   └── pipeline.py                # Main PySpark orchestrator combining ingestion to Parquet write
│
├── analytics/                     # Business Logic & Screening Engine
│   ├── __init__.py                # Package marker
│   ├── sleep_score.py             # Deterministic 0-100 academic sleep score calculator
│   ├── condition_risk.py          # Rule-based risk engine (insomnia, apnea pattern, fragmentation)
│   ├── recommendations.py         # Metric-triggered explainable user guidance generator
│   ├── alerts.py                  # Persistence-based doctor alert manager for multi-night poor sleep
│   └── report_builder.py          # Clinical report generator producing JSON, CSV, HTML, and PDF reports
│
├── api/                           # FastAPI Backend & Celery Task Management
│   ├── main.py                    # FastAPI entry point, CORS configuration, & router inclusion
│   ├── celery_app.py              # Celery instance configuration using Redis broker
│   ├── tasks.py                   # Celery task wrappers executing PySpark & analytics pipelines
│   ├── database.py                # SQLAlchemy engine setup & session factory
│   ├── models_db.py               # SQLAlchemy ORM models (NightSession, SessionEDA, DoctorPatientAssignment)
│   ├── schemas.py                 # Pydantic schemas for API request validation & response serializing
│   ├── config.py                  # Environment settings and application defaults
│   ├── auth.py                    # User authentication, role verification & JWT management
│   ├── ws_manager.py              # WebSocket connection manager for live client updates
│   ├── requirements_api.txt       # Backend-specific Python requirements
│   ├── Dockerfile                 # Container file for API service
│   ├── templates/                 # Jinja2 HTML templates for doctor reports
│   └── routers/                   # API Route Controllers
│       ├── sessions.py            # Whole-night CSV upload, status, timeline, and preserved manual endpoints
│       ├── doctor.py              # Doctor alert triage & patient history
│       ├── frontend.py            # Adapter endpoints for patient dashboard payloads
│       └── reports.py             # Multi-format report builder endpoints & doctor authorization routes
│
├── frontend/                      # React 18 + Vite Web Application
│   ├── package.json               # Frontend dependencies & npm script definitions
│   ├── vite.config.ts             # Vite server config with API proxy (/api -> localhost:8010)
│   ├── index.html                 # HTML application shell
│   ├── ATTRIBUTIONS.md            # Asset attributions
│   └── src/                       # Frontend Source Code
│       ├── main.tsx               # React application entry point
│       ├── app/
│       │   ├── App.tsx            # Main router switch & theme provider
│       │   ├── routes.tsx         # Route path declarations
│       │   ├── pages/             # Page Views
│       │   │   ├── Dashboard.tsx          # General dashboard redirect / summary
│       │   │   ├── RecordSleep.tsx        # 1 Hz sensor CSV upload & streaming pipeline execution
│       │   │   ├── PatientDashboard.tsx   # Detailed patient view (Score, Hypnogram, Sensor Charts)
│       │   │   ├── DoctorDashboard.tsx    # Doctor triage, session selector, & Full Clinical Report
│       │   │   ├── SessionDetail.tsx      # In-depth 6-tab clock-time night visualization & download
│       │   │   ├── ModelLeaderboard.tsx   # Analytics & algorithm performance metrics
│       │   │   ├── Login.tsx              # User authentication view
│       │   │   └── Signup.tsx             # User registration view
│       │   ├── components/        # UI Components
│       │   │   ├── DoctorReportView.tsx   # 9-tab clinical doctor report with doctor-only sections
│       │   │   ├── DownloadReportButton.tsx # Split-action instant multi-format download button
│       │   │   ├── SessionReportView.tsx  # Shared clinical report modal view
│       │   │   ├── SleepHypnogram.tsx     # Recharts hypnogram visualization (W, R, N1, N2, N3)
│       │   │   ├── SensorChart.tsx        # Recharts time-series graphs for HR, EDA, SpO2
│       │   │   ├── RiskBadge.tsx          # Status indicator badge (LOW, MODERATE, HIGH)
│       │   │   ├── SessionCard.tsx        # Night summary card component
│       │   │   ├── ThemeToggle.tsx        # Dark/Light mode switch
│       │   │   └── ui/                # UI Primitives (Button, Card, Dialog, Table, Tabs, etc.)
│       │   ├── context/           # React Context (AuthContext.tsx)
│       │   └── data/              # Data utilities & API adapters (sessionUtils.ts, mockData.ts)
│       └── styles/                # CSS stylesheet bundles (tailwind.css, theme.css)
│
├── scripts/                       # Command-Line Executable Utilities
│   ├── generate_synthetic_sleep.py # Generator for 1.2M+ row longitudinal observation CSV
│   ├── generate_night_csv.py      # CLI generator for 1 Hz whole-night sensor CSVs
│   └── run_spark_pipeline.py      # CLI script executing full PySpark batch pipeline
│
├── tests/                         # Automated Pytest Suite (42 Tests - 100% Passing)
│   ├── conftest.py                # Shared pytest fixtures and test DB setup
│   ├── test_sleep_score.py        # Unit tests for academic sleep score calculation
│   ├── test_risk_analysis.py      # Unit tests for rule-based condition risk screening
│   ├── test_recommendations.py    # Unit tests for explainable recommendation generator
│   ├── test_alerts.py             # Unit tests for doctor alert persistence rules
│   ├── test_report_builder.py     # Unit tests for JSON, CSV, HTML, and PDF report outputs
│   ├── test_report_download.py    # Multi-format report download gate verification
│   ├── test_doctor_full_report.py # Doctor portal authorization & full clinical reporting gate
│   ├── test_night_generator.py    # Synthetic 1 Hz sensor generation unit tests
│   ├── test_night_pipeline.py     # Streaming PySpark epoching and EDA tests
│   ├── test_night_upload.py       # API upload and CSV contract validation tests
│   ├── test_phase4_e2e.py         # End-to-end clock-time hypnogram and EDA verification
│   ├── test_manual_sessions.py    # API integration tests for preserved manual recording
│   └── test_full_integration.py   # End-to-end integration test suite
│
├── data/                          # Data Directories (Created / Managed at Runtime)
│   ├── sample_data/               # Pre-packaged 1 Hz CSVs (healthy_night, apnea_night, fragmented)
│   ├── synthetic/                 # Contains generated sleep_observations.csv
│   ├── raw/                       # Raw session uploads
│   └── parquet/                   # Processed PySpark Parquet output tables
│
├── reports/                       # Generated Clinical Reports
│   └── generated/                 # Export directory for PDF/HTML report artifacts
│
├── hardware/                      # Legacy ESP32 & RPi streaming scripts (Optional)
├── legacy/                        # Legacy hardware docs & scikit-learn models
├── advanced/                      # Legacy federated learning & explainability research code
└── validation/                    # IRB checklist, regulatory notes, and clinical metrics scripts
```

---

## Core Analytics & Feature Breakdown

### 1. Academic Sleep Score (0–100)

The sleep score is computed using a weighted composite formula:

| Parameter | Weight | Description |
| :--- | :---: | :--- |
| **Sleep Efficiency** | **25%** | Percentage of time in bed spent asleep ($\ge 90\%$ ideal) |
| **Total Duration** | **20%** | Total hours slept (target $7.0 - 9.0$ hours) |
| **Deep Sleep (N3)** | **15%** | Fraction of total sleep spent in deep N3 stage ($15-25\%$ ideal) |
| **REM Sleep (R)** | **15%** | Fraction of total sleep spent in REM stage ($20-25\%$ ideal) |
| **Wake Fragmentation** | **10%** | Inverse ratio of nocturnal awakenings and wake fraction |
| **Heart Rate Stability** | **10%** | Standard deviation of heart rate during sleep ($\le 4.0$ bpm ideal) |
| **Movement Stability** | **5%** | Standard deviation of accelerometer movement magnitude |

### 2. Rule-Based Condition Screening

The screening engine evaluates specific metrics against rule thresholds to flag non-diagnostic patterns:

* **Sleep-Disordered Breathing Pattern**: Triggered by elevated nocturnal event counts ($\ge 5$ per night) or SpO2 drops ($\le 90\%$).
* **Insomnia-Like Pattern**: Triggered by low sleep efficiency ($< 75\%$), high wake fraction ($> 20\%$), or elevated awakenings.
* **Circadian Irregularity**: Triggered by high bedtime/wake-time variance across a rolling 7-night window.
* **Sleep Fragmentation**: Triggered by high wake fraction combined with low deep sleep fraction ($< 10\%$).

### 3. Metric-Triggered Recommendations

Recommendations are generated with explicit trigger evidence:

```json
{
  "code": "REC_REDUCE_SCREEN_TIME",
  "area": "LIFESTYLE",
  "severity": "MODERATE",
  "message": "High screen time before bed (150 min) correlates with reduced REM sleep.",
  "trigger": {
    "metric": "screen_time",
    "value": 150,
    "threshold": 60
  }
}
```

### 4. Persistence-Based Doctor Alerting

Alerts are generated when poor sleep criteria persist over multiple consecutive nights:
* `persistent_low_sleep_score`: Triggered when sleep score is $< 55$ for $\ge 3$ consecutive nights.
* `persistent_high_risk`: Triggered when risk category is `HIGH` for $\ge 3$ consecutive nights.
* `sustained_elevated_event_rate`: Triggered when event rate is elevated across $\ge 4$ nights.

---

## Cross-Platform Execution Guide (Linux, macOS, Windows)

### Prerequisites (All Platforms)

1. **Python**: Version `3.10` or higher (`python3 --version` or `python --version`)
2. **Java JDK**: OpenJDK `17` or `21` (Required for PySpark execution). Verify with `java -version`.
3. **Node.js**: Version `18` or higher and `npm 9+` (`node -v`, `npm -v`)
4. **Redis**: Redis server version `6.x` or `7.x` (`redis-cli ping`)

---

### Option A: Linux (Ubuntu / Debian / RHEL)

#### 1. System Dependencies Installation

```bash
# Ubuntu / Debian
sudo apt update
sudo apt install -y python3-venv python3-dev openjdk-17-jre-headless redis-server nodejs npm

# Verify Java
java -version
```

#### 2. Virtual Environment Setup

```bash
cd /path/to/SleepSenseAI
python3 -m venv .venv
source .venv/bin/activate
pip install -U pip
pip install -r requirements.txt
pip install -r api/requirements_api.txt
```

#### 3. Frontend Installation

```bash
cd frontend
npm install
cd ..
```

---

### Option B: macOS (Intel & Apple Silicon M1/M2/M3/M4)

#### 1. System Dependencies Installation via Homebrew

```bash
brew update
brew install openjdk@17 redis node python@3.11

# Set JAVA_HOME for Apple Silicon / Intel macOS
export JAVA_HOME=$(/usr/libexec/java_home -v 17)
echo 'export JAVA_HOME=$(/usr/libexec/java_home -v 17)' >> ~/.zshrc

# Verify Java & Redis
java -version
brew services start redis
redis-cli ping
```

#### 2. Python & Frontend Setup

```bash
cd /path/to/SleepSenseAI
python3 -m venv .venv
source .venv/bin/activate
pip install -U pip
pip install -r requirements.txt
pip install -r api/requirements_api.txt

cd frontend
npm install
cd ..
```

---

### Option C: Windows 10 / 11

> **Recommended Approach**: Use **WSL2 (Ubuntu)** for the smoothest experience with PySpark, Redis, and Celery.

#### Method 1: Windows Subsystem for Linux (WSL2 - Recommended)

1. Open PowerShell as Administrator and run: `wsl --install`
2. Restart your computer and open the **Ubuntu** app.
3. Follow the **Linux (Ubuntu)** instructions above inside your WSL2 terminal.

#### Method 2: Native Windows (PowerShell)

1. **Install Java 17**: Download and install Eclipse Temurin JDK 17 or Oracle JDK 17. Set environment variable `JAVA_HOME=C:\Program Files\Eclipse Adoptium\jdk-17...`.
2. **Install Python 3.10+**: Download from python.org (Ensure "Add Python to PATH" is checked).
3. **Install Node.js LTS**: Download installer from nodejs.org.
4. **Install Redis on Windows**:
   * Use Docker: `docker run -d -p 6379:6379 --name redis-sleepsense redis`
   * Or install Memurai / Redis for Windows binaries.

5. **Setup Virtual Environment in PowerShell**:

```powershell
Set-ExecutionPolicy -ExecutionPolicy RemoteSigned -Scope Process
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -U pip
pip install -r requirements.txt
pip install -r api/requirements_api.txt

cd frontend
npm install
cd ..
```

> **Windows Celery Note**: On native Windows, Celery worker requires the `solo` pool modifier:  
> `celery -A api.celery_app worker --loglevel=info -P solo`

---

## Running the Synthetic Data & PySpark Pipeline

Before launching the web app, generate the synthetic longitudinal dataset and run the offline PySpark analytics pipeline:

### 1. Generate Synthetic Longitudinal Dataset (1.2M+ Rows)

```bash
python scripts/generate_synthetic_sleep.py
```

* **Output File**: `data/synthetic/sleep_observations.csv`
* **Dataset Metrics**: 120 users, 70 nights per user, ~1.26M observation rows.

### 2. Run the PySpark Pipeline

```bash
python scripts/run_spark_pipeline.py
```

* **Output Directory**: `data/parquet/`
* **Output Metrics**: 8,400 aggregated nightly rows containing raw metrics, rolling features, sleep scores, risk flags, and 7d/14d/30d longitudinal trends.

### 3. Verify Parquet Output

```bash
python -c "
from spark.spark_session import create_spark_session
spark = create_spark_session()
df = spark.read.parquet('data/parquet')
df.printSchema()
print('Total nights processed:', df.count())
df.select('user_id', 'date', 'sleep_score', 'risk_level', 'sleep_score_7d_avg').show(5)
spark.stop()
"
```

---

## Running the Live Application (4-Terminal Workflow)

Launch the application using four separate terminal windows:

### Terminal 1: Redis Broker

```bash
redis-server
```

* **Verification**: `redis-cli ping` (Should return `PONG`).

### Terminal 2: Celery Worker (PySpark Analytics Runner)

```bash
# Linux / macOS / WSL2
PYTHONPATH=api:. celery -A api.celery_app worker --loglevel=info --concurrency=1

# Windows PowerShell
$env:PYTHONPATH="api;."
celery -A api.celery_app worker --loglevel=info -P solo
```

> Watch this terminal when submitting sessions from the UI. PySpark runs inside Celery, so task output and JVM logs appear here.

### Terminal 3: FastAPI Backend

```bash
uvicorn api.main:app --reload --port 8010
```

* **API Base URL**: `http://localhost:8010`
* **Interactive Docs**: `http://localhost:8010/docs`
* **Health Check**: `curl http://localhost:8010/api/v1/health`

### Terminal 4: React / Vite Frontend

```bash
cd frontend
npm run dev -- --host 127.0.0.1 --port 5173
```

* **Web UI URL**: `http://localhost:5173`

---

## REST API Endpoint Specifications

| Method | Route | Description | Request Payload / Params | Response |
| :--- | :--- | :--- | :--- | :--- |
| `POST` | `/api/v1/sessions/upload` | Ingest 1 Hz whole-night sensor CSV | `file` (multipart CSV), `user_id`, `session_id`, `notes` | `{"session_id": "...", "status": "processing"}` |
| `GET` | `/api/v1/sessions/{sid}/status` | Poll night pipeline status & score | `sid` (path) | `{"status": "completed", "sleep_score": 87.2, "risk_level": "LOW"}` |
| `GET` | `/api/v1/sessions/{sid}/timeline` | Retrieve clock-time hypnogram & sensor stream | `sid` (path) | Epochs (`stage`, `clock_time`), HR, EDA, SpO2 streams |
| `GET` | `/api/v1/sessions/{sid}/report` | Export patient report as attachment | `format=json\|csv\|html\|pdf` | Downloadable attachment with `Content-Disposition` |
| `GET` | `/api/v1/doctor/patients/{uid}/sessions` | Doctor: list assigned patient sessions | `uid` (path), Bearer Doctor JWT | Array of patient sessions with scores and risk profiles |
| `GET` | `/api/v1/doctor/patients/{uid}/sessions/{sid}/report` | Doctor: full clinical report export | `uid`, `sid`, `format=json\|csv\|html\|pdf` | Clinical report with doctor-only notes, data quality, events |
| `GET` | `/api/v1/doctor/alerts` | List unhandled multi-night alerts | Bearer Doctor JWT | `[{"id": 1, "patient_id": "U034", "alert_type": "...", "severity": "HIGH"}]` |
| `POST` | `/api/v1/doctor/alerts/{id}/acknowledge` | Acknowledge clinical alert | `id` (path) | `{"status": "acknowledged"}` |
| `POST` | `/api/v1/doctor/alerts/{id}/resolve` | Resolve clinical alert | `id` (path) | `{"status": "resolved"}` |
| `POST` | `/api/v1/sessions/manual` | *(Deprecated)* Submit manual metrics | `{user_id, date, sleep_efficiency, ...}` | `{"session_id": "...", "status": "PROCESSING"}` |
| `GET` | `/api/v1/health` | Health status check | None | `{"status": "healthy", "service": "SleepSense AI"}` |

---

## Automated Testing & Quality Verification

SleepSense AI includes an exhaustive test suite built with `pytest` covering units, algorithms, rule engines, API endpoints, whole-night sensor pipelines, multi-format downloads, and doctor role authorization gates.

### Run All Integration & Gate Tests (42 Tests - 100% Green)

```bash
pytest tests/ -v
```

### Run Specialized Test Suites

```bash
# Phase 3 & 4: 1 Hz Synthetic Sensor Generator & Streaming Pipeline
pytest tests/test_night_generator.py tests/test_night_pipeline.py tests/test_night_upload.py -v

# Phase 4: Clock-Time Timeline & Hypnogram Verification
pytest tests/test_phase4_e2e.py -v

# Phase 5: Multi-Format Clinical Report Download Gate (JSON, CSV, HTML, PDF)
pytest tests/test_report_download.py tests/test_report_builder.py -v

# Phase 6: Doctor Portal Full Report & Clinical Authorization Gate
pytest tests/test_doctor_full_report.py tests/test_alerts.py -v

# Algorithm Units: Sleep Scoring, Risk Screening & Recommendations
pytest tests/test_sleep_score.py tests/test_risk_analysis.py tests/test_recommendations.py -v
```

### Python Syntax & Compile Verification

```bash
python -m py_compile api/celery_app.py api/tasks.py api/routers/reports.py api/routers/sessions.py spark/night_pipeline.py analytics/report_builder.py
```

---

## Generated File & Cache Management

### Safe-to-Delete Temporary Artifacts

The following generated caches and runtime files can be safely cleaned up without affecting source code:

* `__pycache__/` directories
* `.pytest_cache/`
* `frontend/dist/`
* `dump.rdb` (Redis dump file)
* `data/raw/manual/` (Raw manual entry temporary files)

### Ignored Data Artifacts (Do Not Commit)

* `data/synthetic/sleep_observations.csv`
* `data/parquet/`
* `sleepsense.db`
* `frontend/node_modules/`
* `.venv/`

---

## Legacy Components & Future Roadmap

* **Legacy Hardware Integration**: Historical MQTT and ESP32 files are preserved under `hardware/` and `legacy/hardware/`. They can be enabled by installing `requirements-hardware.txt`.
* **Legacy CLI Predictor**: The historical scikit-learn workflow is preserved under `src/main.py`.
* **Future Roadmap**:
  1. Integration of real-time streaming via PySpark Structured Streaming.
  2. Integration of HL7 FHIR / EHR patient record exports.
  3. Federated privacy-preserving multi-hospital model training (`advanced/federated_client.py`).
