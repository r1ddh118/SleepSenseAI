# SleepSense AI Migration Checklist

Step 1 inventory only. No application code has been changed.

## Verification Command

Run this from the repository root to confirm the primary MQTT/hardware hits remain accounted for:

```bash
grep -rn "mqtt\|paho\|HIVEMQ\|ESP32\|MPU6050\|withMPU" --include="*.py" --include="*.ino" --include="*.md" .
```

Note: after this file exists, the command also reports `MIGRATION_CHECKLIST.md` because it documents the same search terms. The original application/documentation hits are accounted for in the inventory below.

## Files Touched In Step 1

- [x] `MIGRATION_CHECKLIST.md` added as the migration inventory and checklist.

## Primary Grep Hit Inventory

- [x] `README.md`
  - Hits: launcher MQTT flags, Mosquitto setup, WebSocket/MQTT relay docs, hardware quick check, `hardware/mqtt_publisher.py` reference.
  - Migration action: update after Spark/API path exists; remove primary MQTT/hardware run-path docs and move hardware notes to legacy documentation.
- [x] `api/config.py`
  - Hits: `mqtt_broker_host`, `mqtt_broker_port`, `mqtt_username`, `mqtt_password`.
  - Migration action: remove MQTT settings from the primary API config; hardcoded HiveMQ host, username, and password must be deleted, rotated, and replaced only with optional legacy env vars if hardware is retained.
- [x] `api/main.py`
  - Hits: startup/shutdown calls to `ws_manager.start_mqtt()` and `ws_manager.stop_mqtt()`.
  - Migration action: remove MQTT startup from the primary FastAPI lifecycle; keep FastAPI focused on DB writes, Celery enqueueing, and analytics read endpoints.
- [x] `api/ws_manager.py`
  - Hits: `paho.mqtt.client`, MQTT client state, `esp32/heartrate` subscribe/unsubscribe, HiveMQ auth, broker connect, MQTT message handler.
  - Migration action: archive or split into `legacy/hardware/`; remove from primary API flow and replace live hardware relay assumptions with analytics polling endpoints.
- [x] `app.py`
  - Hits: `--mqtt-port`, `--no-mqtt`, Mosquitto process management, MQTT service status output.
  - Migration action: remove MQTT broker orchestration from the default launcher; if kept, make it legacy/hardware-only and disabled outside the primary run path.
- [x] `frontend/src/imports/pasted_text/sleepsense-roadmap.md`
  - Hits: roadmap references to `paho-mqtt`, MQTT broker, E4-to-MQTT daemon, Mosquitto acquisition.
  - Migration action: keep only as imported historical text or move under legacy docs; do not use as primary architecture documentation.
- [x] `hardware/mqtt_publisher.py`
  - Hits: `paho.mqtt.client`, `MQTTPublisher`, MQTT publish helper.
  - Migration action: archive under `legacy/hardware/`; remove `paho-mqtt` from primary requirements.

## Additional Hardware/MQTT References Found Outside The Requested Grep Scope

- [x] `requirements.txt`
  - Hit: `paho-mqtt`.
  - Migration action: move to `requirements-hardware.txt` or `legacy/hardware/requirements.txt`.
- [x] `api/requirements_api.txt`
  - Hit: `paho-mqtt==1.6.1`.
  - Migration action: remove from API requirements when MQTT relay is removed.
- [x] `hardware/requirements_rpi.txt`
  - Hit: `paho-mqtt>=1.6.1`.
  - Migration action: archive with hardware code.
- [x] `hardware/e4_streamer.py`
  - Hit: docstring says E4 streams to local CSV and MQTT.
  - Migration action: archive with hardware code; primary ingestion should be manual entry, CSV, or synthetic data.
- [x] `docker-compose.yml`
  - Hit: `MQTT_BROKER_HOST=host.docker.internal`.
  - Migration action: remove primary MQTT env once API no longer starts MQTT relay.
- [x] `packaging/docker-compose.prod.yml`
  - Hit: `MQTT_BROKER_HOST=mosquitto`.
  - Migration action: remove from primary production deployment; keep only in optional legacy hardware compose if needed.
- [x] `frontend/src/app/pages/NewSession.tsx`
  - Hit: user-facing copy says data is streamed via MQTT.
  - Migration action: replace with manual/CSV/synthetic session language during frontend migration.

## Search Results With No Current Repo Hit

- [x] `realtime_predictor.py`
  - No matching file or reference found.
- [x] `withMPU`
  - No matching file or reference found.
- [x] `ESP32`
  - Found as `esp32/heartrate` topic references in `api/ws_manager.py`; no standalone ESP32 source file found.
- [x] `MPU6050`
  - No matching file or reference found.

## Hardcoded Credentials And Secrets To Fix

- [x] `api/config.py`
  - Hardcoded `secret_key = "CHANGE_ME_IN_PRODUCTION"` is insecure for any deployed environment.
  - Hardcoded HiveMQ broker host, username, and password are present and must be removed from tracked source, rotated, and replaced with environment-only optional legacy settings if retained.
- [x] `packaging/docker-compose.prod.yml`
  - Uses env-required `POSTGRES_PASSWORD` and `SECRET_KEY`; acceptable pattern, but confirm no real `.env` is committed before deployment cleanup.
- [x] `validation/dreamt_pipeline.py`
  - Accepts PhysioNet username/password as runtime inputs for credentialed download; no literal credential found.

## Pandas-Heavy Analytics And Training Paths To Refactor

- [x] `src/data_processor.py`
  - Current role: pandas CSV ingestion, participant cleaning, feature aggregation, EDA CSV/PNG generation, single prediction row construction.
  - Migration action: extract ingestion, schema enforcement, cleaning, aggregation, stage percentages, event rates, and feature construction into `spark/ingestion.py`, `spark/cleaning.py`, `spark/feature_engineering.py`, `spark/sleep_analytics.py`, and `spark/pipeline.py`.
  - Keep/refactor: preserve useful label heuristics and EDA/report outputs only where they still fit the Spark-backed analytics design.
- [x] `src/trainer.py`
  - Current role: pandas/scikit-learn model training, row-level `train_test_split`, leaderboard generation, pickle bundle persistence, CSV prediction output.
  - Migration action: move training to `ml/train_spark_model.py`, evaluation to `ml/evaluate.py`, persistence to `ml/model_registry.py`, and inference to `ml/inference.py`.
  - Required behavior change: use user-level train/test split for any ML evaluation and avoid claims of clinical validation.
- [x] `api/tasks.py`
  - Current role: Celery invokes old `src/main.py` pipeline, loads pickle models, reads/writes CSVs with pandas, computes risk labels, SHAP, recommendations, and DB prediction rows.
  - Migration action: replace prediction/training tasks with `run_sleep_analytics(session_id)` that calls `spark/pipeline.py`, then plain-Python analytics rules, persistence-based alerts, report generation, and DB summary updates.
- [x] `advanced/recommendations.py`
  - Current role: recommendation generation outside the Spark pipeline.
  - Migration action: refactor into `analytics/recommendations.py` and feed it already-computed Spark aggregate metrics.

## Files To Archive Under `legacy/hardware/`

- [ ] `hardware/mqtt_publisher.py`
- [ ] `hardware/e4_streamer.py`
- [ ] `hardware/session_manager.py`
- [ ] `hardware/sleepsense-recorder.service`
- [ ] `hardware/requirements_rpi.txt`
- [ ] Any future-discovered Arduino/ESP32 assets such as `withMPU/withMPU.ino` if added or recovered.
- [ ] Hardware/MQTT sections from `README.md` and imported roadmap docs, if retained as historical reference.

## Files To Refactor In Later Phases

- [ ] `api/config.py` - remove hardcoded secrets and primary MQTT settings.
- [ ] `api/main.py` - remove MQTT relay lifecycle startup/shutdown.
- [ ] `api/ws_manager.py` - remove from primary run path or archive with hardware.
- [ ] `app.py` - remove default Mosquitto orchestration.
- [ ] `docker-compose.yml` - remove MQTT env from primary services.
- [ ] `packaging/docker-compose.prod.yml` - remove MQTT env from production services.
- [ ] `requirements.txt` and `api/requirements_api.txt` - remove `paho-mqtt` from primary dependencies.
- [ ] `src/data_processor.py` - extract/refactor logic into Spark modules rather than deleting outright.
- [ ] `src/trainer.py` - replace scikit-learn/pickle path with Spark MLlib-oriented modules and user-level evaluation.
- [ ] `api/tasks.py` - make Celery invoke the Spark analytics pipeline.
- [ ] `advanced/recommendations.py` - move/refactor into `analytics/recommendations.py`.
- [ ] `frontend/src/app/pages/NewSession.tsx` - remove MQTT streaming language from primary UI.
- [ ] `README.md` - rewrite primary workflow around manual/CSV/synthetic input, Celery, Spark, analytics, reports, and doctor alerts.

## Step 1 Status

- [x] MQTT, `paho`, HiveMQ, ESP32 topic references, `withMPU`, `MPU6050`, `realtime_predictor.py`, hardcoded credential patterns, and pandas-heavy analytics paths were searched.
- [x] Every hit from the requested grep command is accounted for above.
- [x] No code migration has been performed yet.
