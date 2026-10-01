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
                               ┌───────────────────────────┐
                               │  Manual Sleep Entry / UI  │
                               │   or Synthetic CSV Input  │
                               └─────────────┬─────────────┘
                                             │
                                             ▼
                               ┌───────────────────────────┐
                               │   FastAPI Backend (8010)  │
                               │   Stores Raw DB Record    │
                               └─────────────┬─────────────┘
                                             │
                                             ▼
                               ┌───────────────────────────┐
                               │   Redis Broker (6379)     │
                               │   Celery Task Dispatch    │
                               └─────────────┬─────────────┘
                                             │
                                             ▼
                               ┌───────────────────────────┐
                               │   Celery PySpark Worker   │
                               │  Ingestion ➔ Cleaning ➔   │
                               │  Rolling Features ➔ Aggs  │
                               └─────────────┬─────────────┘
                                             │
                        ┌────────────────────┴────────────────────┐
                        ▼                                         ▼
         ┌──────────────────────────────┐          ┌──────────────────────────────┐
         │ Parquet Storage              │          │ Analytics Layer              │
         │ (data/parquet/)              │          │ - Academic 0-100 Score       │
         └──────────────────────────────┘          │ - Rule-Based Risk Screening  │
                                                   │ - Metric Recommendations     │
                                                   │ - Multi-Night Alerts         │
                                                   └──────────────┬───────────────┘
                                                                  │
                                                                  ▼
                                                   ┌──────────────────────────────┐
                                                   │ React Patient/Doctor UI      │
                                                   │ (http://localhost:5173)      │
                                                   └──────────────────────────────┘
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
│   └── report_builder.py          # Clinical report generator producing JSON, CSV, and HTML reports
│
├── api/                           # FastAPI Backend & Celery Task Management
│   ├── main.py                    # FastAPI entry point, CORS configuration, & router inclusion
│   ├── celery_app.py              # Celery instance configuration using Redis broker
│   ├── tasks.py                   # Celery task wrappers executing PySpark & analytics pipelines
│   ├── database.py                # SQLAlchemy engine setup & session factory
│   ├── models_db.py               # SQLAlchemy ORM models (ManualSleepSession, DoctorAlert, DoctorReport)
│   ├── schemas.py                 # Pydantic schemas for API request validation & response serializing
│   ├── config.py                  # Environment settings and application defaults
│   ├── auth.py                    # User authentication stubs & context management
│   ├── ws_manager.py              # WebSocket connection manager for live client updates
│   ├── requirements_api.txt       # Backend-specific Python requirements
│   ├── Dockerfile                 # Container file for API service
│   ├── templates/                 # Jinja2 HTML templates for doctor reports
│   └── routers/                   # API Route Controllers
│       ├── sessions.py            # POST manual sleep session & GET polling endpoints
│       ├── doctor.py              # GET/POST doctor alert triage & patient history
│       ├── frontend.py            # Adapter endpoints for patient dashboard payloads
│       └── reports.py             # Multi-format report builder endpoints (JSON/CSV/HTML)
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
│       │   │   ├── RecordSleep.tsx        # Manual sleep session input form
│       │   │   ├── PatientDashboard.tsx   # Detailed patient view (Score, Hypnogram, Sensor Charts)
│       │   │   ├── DoctorDashboard.tsx    # Doctor alert triage, patient list & report preview
│       │   │   ├── SessionDetail.tsx      # In-depth single night visualization
│       │   │   ├── ModelLeaderboard.tsx   # Analytics & algorithm performance metrics
│       │   │   ├── Login.tsx              # User authentication view
│       │   │   └── Signup.tsx             # User registration view
│       │   ├── components/        # UI Components
│       │   │   ├── SleepHypnogram.tsx     # Recharts hypnogram visualization (W, R, N1, N2, N3)
│       │   │   ├── SensorChart.tsx        # Recharts time-series graphs for HR and EDA
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
│   └── run_spark_pipeline.py      # CLI script executing full PySpark batch pipeline
│
├── tests/                         # Automated Pytest Suite
│   ├── conftest.py                # Shared pytest fixtures and test DB setup
│   ├── test_sleep_score.py        # Unit tests for academic sleep score calculation
│   ├── test_risk_analysis.py      # Unit tests for rule-based condition risk screening
│   ├── test_recommendations.py    # Unit tests for explainable recommendation generator
│   ├── test_alerts.py             # Unit tests for doctor alert persistence rules
│   ├── test_report_builder.py     # Unit tests for JSON, CSV, and HTML report outputs
│   ├── test_manual_sessions.py    # API integration tests for manual sleep recording
│   └── test_full_integration.py   # End-to-end integration test suite
│
├── data/                          # Data Directories (Created / Managed at Runtime)
│   ├── synthetic/                 # Contains generated sleep_observations.csv
│   ├── raw/                       # Raw session payloads (data/raw/manual/)
│   └── parquet/                   # Processed PySpark Parquet output tables
│
├── reports/                       # Generated Doctor Reports
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
| `POST` | `/api/v1/sessions/manual` | Submit manual sleep session | `{user_id, date, sleep_efficiency, n3_fraction, rem_fraction, wake_fraction, screen_time, stress_level}` | `{"session_id": "...", "status": "PROCESSING"}` |
| `GET` | `/api/v1/sessions/{sid}/analytics` | Poll session analytics result | `sid` (path) | `{"status": "COMPLETED", "sleep_score": 88.5, ...}` |
| `GET` | `/api/v1/doctor/alerts` | List unhandled doctor alerts | None | `[{"id": 1, "patient_id": "U034", "alert_type": "...", "severity": "HIGH"}]` |
| `POST` | `/api/v1/doctor/alerts/{id}/acknowledge` | Acknowledge alert | `id` (path) | `{"status": "acknowledged"}` |
| `POST` | `/api/v1/doctor/alerts/{id}/resolve` | Resolve alert | `id` (path) | `{"status": "resolved"}` |
| `GET` | `/api/v1/doctor/patients/{id}/report` | Generate patient summary | `patient_id` (path) | `{"patient_id": "U034", "nightly_history": [...], "alerts": [...]}` |
| `GET` | `/api/v1/sessions/{sid}/report` | Export session report | `format=json\|csv\|html` | JSON object, CSV file, or rendered HTML page |
| `GET` | `/api/v1/frontend/dashboard` | Dashboard summary payload | None | Dashboard stats, recent sessions, alert counters |
| `GET` | `/api/v1/frontend/sessions/{sid}` | Frontend session detail | `sid` (path) | Detail metrics, hypnogram stages, HR/EDA series |
| `GET` | `/api/v1/health` | Health status check | None | `{"status": "healthy", "service": "SleepSense AI"}` |

---

## Automated Testing & Quality Verification

SleepSense AI includes a test suite built with `pytest` covering units, algorithms, rule engines, API endpoints, and end-to-end integration workflows.

### Run All Integration & Unit Tests

```bash
pytest tests/test_manual_sessions.py tests/test_alerts.py tests/test_report_builder.py tests/test_full_integration.py -v
```

### Run Specialized Test Suites

```bash
# Test Sleep Scoring Formula
pytest tests/test_sleep_score.py -v

# Test Rule-Based Condition Risk Screening
pytest tests/test_risk_analysis.py -v

# Test Recommendation Engine
pytest tests/test_recommendations.py -v
```

### Python Syntax & Compile Verification

```bash
python -m py_compile api/celery_app.py api/tasks.py api/routers/reports.py spark/pipeline.py analytics/sleep_score.py
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
