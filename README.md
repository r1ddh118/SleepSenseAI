# SleepSense AI

SleepSense AI is a multimodal sleep analysis stack: an **OOP Python CLI pipeline** in `src/`, a **FastAPI + Celery backend** in `api/` (Phase 2 + SHAP hooks), and scaffold folders for hardware, frontend, validation, packaging, and advanced work.

## Target layout

```
sleepsense-ai/
├── src/                 # Phase 0 — CLI pipeline (do not restructure)
├── hardware/            # Phase 1 — RPi / E4 acquisition (stubs)
├── api/                 # Phase 2 — FastAPI, Celery, WebSocket/MQTT relay
├── frontend/            # Phase 3 — React dashboard (scaffold)
├── validation/          # Phase 4 — DREAMT / Wearanize, metrics, IRB, regulatory
├── packaging/           # Phase 5 — RPi systemd, prod compose, nginx, Mosquitto
├── advanced/            # Phase 6 — SHAP CLI, recommendations, FL stub, LSTM
├── datasets/            # raw data (large files gitignored as needed)
├── artifacts/           # models, CSV outputs (gitignored)
├── docker-compose.yml   # dev: Redis + API + worker
└── .env.example
```

## Phase 0 — CLI pipeline

Entrypoint: `src/main.py` (`preprocess`, `eda`, `train`, `predict`). See **CLI Workflow** below for commands.

## Phase 2 — Backend (FastAPI)

Stack: FastAPI, SQLAlchemy (SQLite or Postgres), Celery + Redis, WebSocket + MQTT relay, JWT auth.
## Unified app launcher (single terminal)

If your local stack feels broken because API, worker, broker, and frontend need separate terminals, use the new root `app.py` launcher. It starts the services together and shuts them down together.

```bash
# from repo root
python app.py
```

What it starts by default:
- Redis (`redis-server`)
- Mosquitto MQTT broker (`mosquitto`)
- Celery worker (`celery -A tasks worker --loglevel=info`)
- FastAPI (`uvicorn main:app --reload --port 8000`)
- Frontend Vite dev server (`npm run dev -- --host`)

Useful flags:

```bash
python app.py --no-frontend      # run backend only
python app.py --no-mqtt          # disable MQTT broker
python app.py --no-redis         # disable redis (if you provide an external redis)
python app.py --api-port 8080    # change API port
python app.py --mqtt-port 1884   # change MQTT port
```

Press `Ctrl+C` once to stop all services cleanly.


The API **imports the existing `src/` pipeline** inside Celery workers via `src/main.py` (`SleepSenseApp`) so preprocessing/training logic is not duplicated.

### Run without Docker

Recommended (single terminal):

```bash
python app.py
```

Manual multi-terminal option (legacy):

```bash
# Terminal 1
redis-server

# Terminal 2
mosquitto -p 1883

# Terminal 3
cd api
pip install -r requirements_api.txt
celery -A tasks worker --loglevel=info

# Terminal 4
cd api
uvicorn main:app --reload --port 8000

# Terminal 5
cd frontend && npm install && npm run dev -- --host
```

Open [http://localhost:8000/docs](http://localhost:8000/docs) for backend and [http://localhost:5173](http://localhost:5173) for frontend.

Copy `.env.example` to `.env` at the repo root and adjust variables as needed.

### Run with Docker

```bash
docker compose up --build
```

API and worker share a named volume for SQLite at `/app/db/sleepsense.db`. Mount `./datasets` and `./artifacts` for data and models.

### Main routes

| Method | Route | Auth | Description |
|--------|--------|------|-------------|
| POST | `/api/v1/auth/register` | — | Create user |
| POST | `/api/v1/auth/login` | — | JWT |
| POST | `/api/v1/sessions/` | User | Create session |
| GET | `/api/v1/sessions/` | User | List sessions |
| GET | `/api/v1/sessions/{sid}` | User | Get session |
| PATCH | `/api/v1/sessions/{sid}` | User | Update session |
| POST | `/api/v1/sessions/{sid}/complete` | — | Mark complete (hardware) |
| POST | `/api/v1/sessions/{sid}/predict` | User | Queue prediction |
| GET | `/api/v1/sessions/{sid}/predictions` | User | List results |
| GET | `/api/v1/sessions/{sid}/report` | User | Download CSV |
| GET | `/api/v1/tasks/{task_id}` | User | Poll Celery task |
| GET | `/api/v1/models/leaderboard` | Clinician | Leaderboard JSON |
| POST | `/api/v1/models/train` | Clinician | Queue training |
| GET | `/api/v1/models/clinical-metrics` | Clinician | Rows from `validation/clinical_metrics_report.csv` |
| GET | `/api/v1/sessions/{sid}/trend` | User | Last ≤7 nights with predictions (same user) |
| GET | `/api/v1/health` | — | Health |
| WS | `/ws/live/{sid}` | — | Live stream (MQTT relay) |

Prediction task results and stored rows can include `shap_top_features` (tree models) and `recommendations` (rule-based, from `advanced/recommendations.py`).

## Phase 4 — Clinical validation

1. **DREAMT (PhysioNet, credentialed)** — download the v2.1.0 extract locally, then convert + run the same CLI pipeline:

   ```bash
   pip install -r validation/requirements_validation.txt
   export PHYSIONET_USER=... PHYSIONET_PASS=...   # optional for wget/HTTP helpers
   python validation/dreamt_pipeline.py --dreamt-root /path/to/dreamt/2.1.0 --out datasets/dreamt/ --batch-predictions
   ```

   This writes SleepSense-style `compressed_<SID>_whole_df.csv`, `participant_info.csv`, and `psg_labels.csv` under `--out`, runs `preprocess` → `eda` → `train`, and (with `--batch-predictions`) writes `artifacts/dreamt_batch_predictions.csv` for metrics.

2. **Wearanize+** — place `compressed_*_whole_df.csv` + `participant_info.csv` under `datasets/wearanize/` (or pass `--dataset-dir`), then:

   ```bash
   python validation/wearanize_pipeline.py --dataset-dir datasets/wearanize/
   ```

3. **Clinical metrics** (sensitivity, specificity, PPV, NPV, AUC, kappa, bootstrap CIs):

   ```bash
   python validation/metrics_report.py \
     --predictions artifacts/dreamt_batch_predictions.csv \
     --ground-truth datasets/dreamt/psg_labels.csv \
     --output validation/clinical_metrics_report.csv
   ```

   **Local smoke test** (pilot data only, not peer review): after `preprocess` + `train`, batch-predict from `artifacts/preprocessed_training_data.csv`, build a ground-truth CSV with columns `SID` and `sleep_deprivation_label_gt`, then run `metrics_report.py` as above.

4. **IRB / regulatory** — see `validation/irb_checklist.md` and `validation/regulatory_notes.md`.

## Phase 5 — Packaging

- **Raspberry Pi**: `sudo bash packaging/rpi_setup.sh` (expects repo already cloned at `SLEEPSENSE_HOME` or `/home/pi/sleepsense-ai`; installs venv deps, systemd units `sleepsense-api`, `sleepsense-worker`, `sleepsense-recorder`).
- **Cloud / VPS**: from repo root, set `POSTGRES_PASSWORD` and `SECRET_KEY` in `.env`, build frontend to `frontend/dist`, then:

  ```bash
  docker compose -f packaging/docker-compose.prod.yml --env-file .env up --build
  ```

  Nginx proxies `/api/`, `/docs`, `/openapi.json`, and `/ws/` to the API container; static files from `frontend/dist`.


## Hardware connectivity quick check (MQTT + API relay)

1. Start the stack with `python app.py` (or ensure API + Mosquitto are running).
2. Open a WebSocket client to `ws://localhost:8000/ws/live/S002`.
3. Publish a test message:

```bash
mosquitto_pub -h localhost -p 1883 -t sleepsense/S002/eda -m '{"eda": 2.1, "ts": 1710000000}'
```

If the WebSocket receives that payload, frontend live charts can consume hardware stream data through the backend relay.

For hardware scripts, `hardware/mqtt_publisher.py` now includes a reusable `MQTTPublisher` class plus `publish_sample(topic, payload)` helper.

## Phase 6 — Advanced

```bash
pip install -r advanced/requirements_advanced.txt
python advanced/explainability.py --model artifacts/best_model.pkl --data artifacts/preprocessed_inference_S002.csv --out artifacts/shap/
python advanced/federated_client.py --features artifacts/preprocessed_inference_S002.csv
python advanced/longitudinal_model.py --features artifacts/all_nights_features.csv --out artifacts/
```

`advanced/recommendations.py` is invoked automatically from the Celery prediction task when possible.

## Installation (CLI only)

```bash
python -m venv .venv
source .venv/bin/activate
pip install -U pip
pip install -r requirements.txt
```

## CLI workflow

```bash
python -m src.main preprocess
python -m src.main eda
python -m src.main train
python -m src.main predict \
  --sensor-csv datasets/compressed_S002_whole_df.csv \
  --sid S002
```

### Preprocess

```bash
python -m src.main preprocess \
  --dataset-dir datasets \
  --participant-csv datasets/participant_info.csv \
  --outdir artifacts
```

### Predict

```bash
python -m src.main predict \
  --dataset-dir datasets \
  --participant-csv datasets/participant_info.csv \
  --model-pickle artifacts/best_model.pkl \
  --sensor-csv datasets/compressed_S002_whole_df.csv \
  --sid S002 \
  --output-csv artifacts/predictions.csv
```

## Dataset inputs

- `datasets/participant_info.csv` — participant metadata and clinical fields.
- `datasets/compressed_*_whole_df.csv` — per-participant sensor CSVs; filename must contain a SID like `S002`.

## Models compared (training)

Eight models: logistic regression, random forest, extra trees, AdaBoost, SVC, KNN, MLP, TensorFlow ANN.

## Notes on labels

`sleep_deprivation_label` is built heuristically from clinical fields; tiny datasets may use a severity fallback so training still runs. This is for development, not validated clinical deployment.

## Phase index (spec documents)

Implement details from your phase markdowns: `PHASE_1_HARDWARE.md` … `PHASE_6_ADVANCED_FEATURES.md` (not bundled in this repo unless you add them).

## Common issues

- **`Need at least two target classes`** — inspect `artifacts/preprocessed_training_data.csv` and EDA outputs.
- **TensorFlow / CUDA messages** — often informational; CPU training works.
