# SleepSense AI → PySpark Migration Checklist

Generated: 2026-09-15  
Branch: `spark-implementation`

---

## MQTT / paho-mqtt References (to remove from hot path)

| File | Line | Reference | Action |
|------|------|-----------|--------|
| `api/ws_manager.py` | 12 | `import paho.mqtt.client as mqtt` | Guard with `try/except ImportError` |
| `api/ws_manager.py` | 24, 51-57, 60-82, 84 | `mqtt.Client`, `start_mqtt()`, `stop_mqtt()`, `_on_mqtt_message()` | Make no-op when paho not installed |
| `api/main.py` | 24, 31 | `ws_manager.start_mqtt(loop)`, `ws_manager.stop_mqtt()` | Already wrapped in try/except; keep as-is |
| `api/config.py` | 30-33 | `mqtt_broker_host`, `mqtt_broker_port`, `mqtt_username`, `mqtt_password` | Change defaults to empty strings |
| `api/requirements_api.txt` | 13 | `paho-mqtt==1.6.1` | Move to `requirements-hardware.txt` |
| `requirements.txt` | 15 | `paho-mqtt` | Move to `requirements-hardware.txt` |
| `app.py` | 99-127, 204-219 | `--mqtt-port`, `--no-mqtt`, mosquitto process | Keep as legacy; add note in README that hardware flags are deprecated |

## HiveMQ Credentials (to remove/anonymize)

| File | Setting | Action |
|------|---------|--------|
| `api/config.py` | `mqtt_broker_host`, `mqtt_username`, `mqtt_password` | Set defaults to empty string `""` |

## ESP32 / Hardware References

| File | Reference | Action |
|------|-----------|--------|
| `api/ws_manager.py` | `"esp32/heartrate"` topic subscription | Stays inside guarded paho block |
| `hardware/mqtt_publisher.py` | Entire file | Move to `legacy/hardware/` |
| `hardware/e4_streamer.py` | Entire file | Move to `legacy/hardware/` |
| `hardware/session_manager.py` | Entire file | Move to `legacy/hardware/` |
| `hardware/sleepsense-recorder.service` | Entire file | Move to `legacy/hardware/` |
| `hardware/requirements_rpi.txt` | Entire file | Move to `legacy/hardware/` |
| `README.md` | MQTT/ESP32 sections | Update to reflect PySpark-primary workflow |

## Pandas-Heavy Analytics Paths (to replace with Spark)

| File | Role | New Home |
|------|------|----------|
| `src/data_processor.py` | CSV feature extraction (pandas) | Logic refactored into `spark/cleaning.py` + `spark/feature_engineering.py` + `spark/sleep_analytics.py` |
| `src/trainer.py` | scikit-learn model training | Logic preserved; new `ml/train_spark_model.py` adds MLlib path |
| `advanced/recommendations.py` | Rule-based recs | Refactored into `analytics/recommendations.py` with expanded signature |
| `api/tasks.py` | pandas + sklearn Celery tasks | Extended with `run_sleep_analytics()` Spark task; old tasks preserved for legacy datasets |

## Old ML Model References

| File | Reference | Action |
|------|-----------|--------|
| `api/tasks.py` | `best_model.pkl`, `shap`, `pickle.load` | Keep for old sklearn path; new Spark MLlib model in `ml/` |
| `api/routers/predictions.py` | sklearn predictions router | Keep as-is (backward compatibility) |

---

## Module Boundary Checklist (post-implementation)

- [ ] `spark/` — only PySpark DataFrame operations, no pandas
- [ ] `analytics/` — plain Python business logic reading aggregated Parquet results, no Spark jobs
- [ ] `ml/` — MLlib training, evaluation, inference
- [ ] `api/` — FastAPI routes, DB models, Celery task dispatch only (no inline Spark)
- [ ] `scripts/` — CLI wrappers, synthetic data generation, seeding

## Final Verification Commands

```bash
# 1. No paho on hot path
grep -rn "import paho" api/ spark/ analytics/ ml/ 2>/dev/null   # expect nothing

# 2. Spark pipeline runs
python scripts/run_spark_pipeline.py

# 3. API boots clean
uvicorn api.main:app --reload --port 8000

# 4. Full test suite
pytest -v
```
