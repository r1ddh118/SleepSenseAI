# SleepSense AI

SleepSense AI is now a PySpark-backed sleep analytics stack. The primary flow is:

```text
Manual sleep input -> FastAPI -> SQLite DB -> Celery -> PySpark -> analytics/risk/recommendations -> alerts/report/dashboard
```

The old hardware/MQTT path is treated as optional legacy support. The main app does not require ESP32, MQTT, HiveMQ, or live sensors.

## Current Architecture

| Area | Path | Purpose |
| --- | --- | --- |
| API | `api/` | FastAPI routes, SQLAlchemy models, Celery tasks |
| Spark | `spark/` | Session, schema, ingestion, cleaning, rolling features, nightly metrics, score/risk/longitudinal transforms |
| Analytics | `analytics/` | Academic sleep score, condition-risk rules, recommendations, persistence alerts, report builder |
| Frontend | `frontend/` | React/Vite patient and doctor UI |
| Synthetic data | `scripts/generate_synthetic_sleep.py` | Generates large longitudinal sleep observation CSV |
| Pipeline CLI | `scripts/run_spark_pipeline.py` | Runs Spark CSV to Parquet analytics pipeline |
| Legacy hardware deps | `requirements-hardware.txt` | Optional hardware/MQTT dependencies only |
| Migration notes | `MIGRATION_PROGRESS.md` | Living implementation and verification report |

## Disclaimer

SleepSense AI analytics are academic/product analytics only. They are not clinically validated, are not a medical diagnosis, and must not be used to diagnose or rule out any medical condition.

## Install

Backend:

```bash
python -m venv .venv
source .venv/bin/activate
pip install -U pip
pip install -r requirements.txt
pip install -r api/requirements_api.txt
```

Frontend:

```bash
cd frontend
npm install
cd ..
```

Optional hardware only:

```bash
pip install -r requirements-hardware.txt
```

## Generate Data And Run Spark Pipeline

Generate longitudinal synthetic observations:

```bash
python scripts/generate_synthetic_sleep.py
```

Expected output:

- `data/synthetic/sleep_observations.csv`
- about `1.2M+` observation rows

Run the Spark analytics pipeline:

```bash
python scripts/run_spark_pipeline.py
```

Expected output:

- `data/parquet/`
- about `8,400` nightly rows for the default synthetic dataset

Inspect Parquet:

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

## Run The Live App

Use four terminals.

### Terminal 1: Redis

```bash
redis-server --daemonize yes
redis-cli ping
```

Expected:

```text
PONG
```

### Terminal 2: Celery Worker

```bash
PYTHONPATH=api:. celery -A api.celery_app worker --loglevel=info --concurrency=1
```

Watch this terminal during manual-session tests. Spark starts inside the Celery task, so Java/JVM errors appear here.

### Terminal 3: FastAPI

Port `8000` may already be occupied on some machines. Use `8010` for the current local workflow:

```bash
uvicorn api.main:app --reload --port 8010
```

Check:

```bash
curl -s http://localhost:8010/docs -o /dev/null -w "%{http_code}\n"
curl -s http://localhost:8010/api/v1/doctor/alerts -o /dev/null -w "%{http_code}\n"
```

Expected:

```text
200
200
```

### Terminal 4: Frontend

```bash
cd frontend
npm run dev -- --host 127.0.0.1 --port 5173
```

Open:

```text
http://localhost:5173
```

The Vite dev server proxies `/api` and `/ws` to `http://localhost:8010`.

## Frontend Smoke Test

1. Open `http://localhost:5173/record-sleep`.
2. Submit a manual sleep row, for example `user_id=U034`, date `2026-09-10`, screen time `150`, stress `7`.
3. Confirm the UI returns quickly with `PROCESSING`.
4. Watch the Celery terminal for `tasks.run_sleep_analytics` and Spark stages.
5. Wait for the UI polling to show `COMPLETED`.
6. Open `http://localhost:5173/dashboard`.
7. Confirm the new session appears with sleep score, risk, stages, and recommendations.
8. Open `http://localhost:5173/doctor`.
9. After several poor nights, confirm doctor alerts/report data appears.

If browser requests to `/api/...` return `404` from `localhost:5173`, restart Vite and confirm `frontend/vite.config.ts` includes the proxy to `localhost:8010`.

## Manual API Smoke Test

Submit one session:

```bash
curl -s -X POST http://localhost:8010/api/v1/sessions/manual \
  -H "Content-Type: application/json" \
  -d '{"user_id":"U034","date":"2026-09-10","sleep_efficiency":0.82,"n3_fraction":0.12,"rem_fraction":0.18,"wake_fraction":0.14,"screen_time":150,"stress_level":7}'
```

Expected:

```json
{"session_id":"...","id":"...","status":"PROCESSING"}
```

Poll:

```bash
curl -s http://localhost:8010/api/v1/sessions/<session_id>/analytics
```

Expected first:

```json
{"status":"PROCESSING"}
```

Expected later:

```json
{"status":"COMPLETED","sleep_score":...,"risk_level":"...","recommendations":[...]}
```

## Doctor Alert Demo

Submit worsening nights for `U034` through the UI or API. A known live smoke produced these completed scores:

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

Check alerts:

```bash
curl -s http://localhost:8010/api/v1/doctor/alerts
```

Expected alert types can include:

- `persistent_low_sleep_score`
- `persistent_high_risk`
- `sustained_elevated_event_rate`

Check patient report:

```bash
curl -s http://localhost:8010/api/v1/doctor/patients/U034/report
```

Expected:

- completed nightly history only;
- alert evidence;
- recommendations;
- model info;
- medical disclaimer.

## Main Routes

| Method | Route | Description |
| --- | --- | --- |
| `POST` | `/api/v1/sessions/manual` | Save manual sleep input, enqueue Celery Spark analytics |
| `GET` | `/api/v1/sessions/{sid}/analytics` | Poll analytics status/result |
| `GET` | `/api/v1/doctor/alerts` | List doctor alerts |
| `POST` | `/api/v1/doctor/alerts/{id}/acknowledge` | Acknowledge alert |
| `POST` | `/api/v1/doctor/alerts/{id}/resolve` | Resolve alert |
| `GET` | `/api/v1/sessions/{sid}/report?format=json\|csv\|html` | Session report |
| `GET` | `/api/v1/doctor/patients/{patient_id}/report` | Patient-level report |
| `GET` | `/api/v1/frontend/dashboard` | Dashboard adapter payload |
| `GET` | `/api/v1/frontend/sessions/{sid}` | Frontend session detail payload |
| `GET` | `/api/v1/health` | Health check |
| `GET` | `/docs` | OpenAPI docs |

## Tests

Focused integration/regression suite:

```bash
pytest tests/test_manual_sessions.py tests/test_alerts.py tests/test_report_builder.py tests/test_full_integration.py -v
```

Other focused suites:

```bash
pytest tests/test_sleep_score.py -v
pytest tests/test_risk_analysis.py -v
pytest tests/ -k recommendations -v
```

Compile check:

```bash
python -m py_compile api/celery_app.py api/routers/reports.py api/tasks.py
```

## Generated Files And Cleanup

Removed during cleanup:

- Python `__pycache__/` folders
- `.pytest_cache/`
- `frontend/dist/`
- `dump.rdb`

Safe-to-delete generated/runtime artifacts:

- `__pycache__/`
- `.pytest_cache/`
- `frontend/dist/`
- `dump.rdb`
- `data/raw/manual/`

Ignored generated analytics outputs:

- `data/synthetic/`
- `data/parquet/`
- `artifacts/`
- `sleepsense.db`
- `frontend/node_modules/`

`frontend/node_modules/` is not source-controlled, but it is useful while testing the frontend. Delete it only if you are okay running `npm install` again.

## Legacy CLI

The older scikit-learn CLI path still exists under `src/` for reference and compatibility:

```bash
python -m src.main preprocess
python -m src.main eda
python -m src.main train
python -m src.main predict \
  --sensor-csv datasets/compressed_S002_whole_df.csv \
  --sid S002
```

The active migration path is the Spark/Celery/manual-entry workflow described above.
