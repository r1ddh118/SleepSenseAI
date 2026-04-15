# SleepSense AI — Product Roadmap & Next Steps

> From research pipeline to a sellable sleep health platform

---

## Current State (v0.1 — Research Pipeline)

You have a working Python CLI that:
- Ingests raw Empatica E4 sensor CSVs + participant metadata
- Engineers 40+ physiological features per participant
- Trains and benchmarks 8 ML models competitively
- Saves the best model and generates predictions
- Produces EDA visualisations and leaderboard CSVs

**What's missing to make this a product:** real-time data acquisition, a user interface, a backend API, clinical validation, packaging, and a go-to-market strategy.

---

## Phase 1 — Real-Time Data Pipeline (Weeks 1–4)

### Goal: Close the hardware → software loop on Raspberry Pi

### 1.1 Empatica E4 → RPi Live Streaming

The E4 exposes a BLE + TCP streaming server. Set up a daemon on the RPi:

```python
# e4_streamer.py (pseudo-code)
import socket, json, csv, datetime

E4_HOST = "127.0.0.1"
E4_PORT = 28000

def connect_e4():
    s = socket.socket()
    s.connect((E4_HOST, E4_PORT))
    s.send(b"device_connect\r\n")
    # Subscribe to streams
    for stream in ["acc", "bvp", "gsr", "tmp", "hr", "ibi"]:
        s.send(f"device_subscribe {stream} ON\r\n".encode())
    return s

def stream_to_csv(session_id: str, duration_seconds: int = 28800):
    sock = connect_e4()
    outfile = open(f"datasets/live_{session_id}.csv", "w")
    writer = csv.writer(outfile)
    writer.writerow(["timestamp", "stream", "value"])
    start = datetime.datetime.now()
    while (datetime.datetime.now() - start).seconds < duration_seconds:
        line = sock.recv(1024).decode().strip()
        if line:
            parts = line.split()
            writer.writerow([parts[1], parts[0], parts[2]])
    outfile.close()
    sock.close()
```

**Packages needed:** `python-e4` or raw socket; `paho-mqtt` for MQTT relay

### 1.2 MQTT Message Broker

Run Mosquitto on the RPi to decouple acquisition from processing:

```bash
sudo apt install mosquitto mosquitto-clients
# Publish each sensor tick to topic: sleepsense/{session_id}/{stream}
```

This lets your web dashboard subscribe to live data without polling files.

### 1.3 Session Management CLI Command

Add a `record` command to `main.py`:

```bash
python -m src.main record --sid S010 --duration 28800 --outdir datasets
# Streams E4 → CSV for 8 hours, then auto-triggers preprocess + predict
```

---

## Phase 2 — Backend REST API (Weeks 3–6)

### Goal: Expose SleepSense as a service that any frontend can consume

### Technology Stack

| Component | Recommendation |
|-----------|---------------|
| Framework | **FastAPI** (async, auto-docs, Python-native) |
| Database | **SQLite** (dev) → PostgreSQL (prod) |
| Auth | JWT via `python-jose` |
| Task Queue | **Celery + Redis** for async training jobs |
| Deployment | Docker + Nginx on RPi or cloud VM |

### Core API Endpoints

```
POST   /api/v1/sessions           → Create new recording session
GET    /api/v1/sessions/{id}      → Get session status + metadata
POST   /api/v1/sessions/{id}/predict  → Trigger prediction on session CSV
GET    /api/v1/sessions/{id}/report   → Download prediction report as PDF/CSV
GET    /api/v1/models/leaderboard     → Get model comparison leaderboard
POST   /api/v1/train              → Trigger full retraining job (async)
GET    /api/v1/health             → System health check
WS     /ws/live/{session_id}      → WebSocket for real-time sensor stream
```

### FastAPI Skeleton

```python
# api/main.py
from fastapi import FastAPI, BackgroundTasks
from pydantic import BaseModel
from pathlib import Path
import sys; sys.path.insert(0, "src")
from preprocessing import SleepPreprocessor
from trainer import SleepModelTrainer

app = FastAPI(title="SleepSense AI", version="1.0")

class PredictRequest(BaseModel):
    sid: str
    sensor_csv: str
    model_pickle: str = "artifacts/best_model.pkl"

@app.post("/api/v1/predict")
async def predict(req: PredictRequest, bg: BackgroundTasks):
    # Offload to Celery task in production
    bg.add_task(run_prediction, req)
    return {"status": "queued", "sid": req.sid}

@app.get("/api/v1/health")
def health():
    return {"status": "ok", "edge_device": "raspberry_pi_5"}
```

---

## Phase 3 — Frontend Dashboard (Weeks 5–10)

### Goal: A clinically usable React web app for patients and clinicians

### Technology Stack

| Layer | Technology |
|-------|-----------|
| Framework | **React 18 + TypeScript** |
| Styling | **Tailwind CSS** |
| Charts | **Recharts** or **Chart.js** |
| State | **Zustand** |
| API client | **React Query (TanStack Query)** |
| Auth | **Clerk** or **Auth.js** |

### Pages / Views

```
/                    → Landing page (product pitch, "Start Free Trial")
/dashboard           → Patient home: recent sessions, risk score trend
/session/new         → Start new recording (pair E4, enter SID)
/session/{id}        → Session detail: hypnogram, sensor charts, risk badge
/session/{id}/report → Downloadable clinical PDF report
/admin/models        → Model leaderboard, retrain button
/admin/patients      → Patient list (clinician view)
/settings            → Account, device pairing, notification prefs
```

### Key Components to Build

```tsx
// RiskBadge.tsx
type RiskLevel = "low" | "moderate" | "high";
const RiskBadge = ({ probability }: { probability: number }) => {
  const level: RiskLevel = probability < 0.3 ? "low" : probability < 0.65 ? "moderate" : "high";
  const colors = { low: "green", moderate: "amber", high: "red" };
  return <span className={`badge badge-${colors[level]}`}>{level.toUpperCase()} RISK ({(probability * 100).toFixed(0)}%)</span>;
};

// SleepHypnogram.tsx — renders W/N1/N2/N3/REM timeline using Recharts AreaChart
// SensorChart.tsx    — renders live/historic EDA, BVP, TEMP, HR over time
// ModelLeaderboard.tsx — sortable table of model metrics
// ReportDownload.tsx — triggers PDF generation via API
```

### Mock API for Frontend Development

Use **MSW (Mock Service Worker)** to develop the frontend without a live backend:

```bash
npm install msw --save-dev
npx msw init public/ --save
```

---

## Phase 4 — Clinical Validation & Regulatory Path (Months 3–6)

### Goal: Evidence base for commercial/clinical credibility

### Validation Study Design

1. **Dataset expansion**: Download and process DREAMT v2.1.0 (physionet.org/content/dreamt/2.1.0) and Wearanize+ — these give you N=150+ labelled participants with PSG ground truth.
2. **IRB protocol**: Submit institutional review protocol for a prospective study comparing SleepSense AI predictions against in-lab PSG (target N=50).
3. **Metrics to report**: Sensitivity, Specificity, AUC-ROC, Cohen's Kappa vs PSG staging.
4. **Target publication**: Sleep Medicine Reviews, Sensors (MDPI), or npj Digital Medicine.

### Regulatory Considerations

| Market | Pathway | Notes |
|--------|---------|-------|
| India | CDSCO Class B/C SaMD | Software as Medical Device; file with Central Drugs Standard Control Organisation |
| USA | FDA 510(k) or De Novo | SaMD for sleep disorder screening; predicate: WatchPAT |
| EU | MDR Class IIa | CE marking required; clinical evidence file needed |

**Start with**: "wellness/screening" positioning (no regulatory approval needed) → collect real-world evidence → upgrade to medical device claim.

---

## Phase 5 — Packaging & Monetisation (Months 4–8)

### Hardware Bundle

```
SleepSense AI Kit:
├── Empatica E4 wristband (or equivalent open-source alternative)
├── Raspberry Pi 5 (4GB) with SleepSense OS image pre-flashed
├── USB-C power adapter
├── Micro SD card (64GB, SleepSense image)
└── Quick-start card → QR code → onboarding wizard
```

**Manufacturing cost estimate:** ~$250 BOM  
**Suggested retail price:** $499–$799

### SaaS Subscription Tiers

| Tier | Price | Features |
|------|-------|---------|
| **Personal** | $9.99/mo | 1 device, unlimited sessions, mobile app, 12-month history |
| **Clinic** | $99/mo | 10 devices, clinician dashboard, EHR export (HL7/FHIR), priority support |
| **Research** | $299/mo | Unlimited devices, raw CSV export, API access, custom model training |
| **Enterprise** | Custom | On-premise deployment, white-labelling, SLA |

### B2B2C Distribution Channels

1. **Sleep clinics** — sell Clinic tier as a PSG triage tool (reduces unnecessary overnight studies)
2. **Corporate wellness** — bulk Personal tier subscriptions
3. **Health insurance** — risk stratification for policy pricing
4. **Telehealth platforms** — API integration for remote sleep monitoring

---

## Phase 6 — Advanced Features (Months 6–12)

### 6.1 Multi-night Longitudinal Tracking

- Store nightly feature vectors per participant in PostgreSQL
- Train a time-series model (LSTM or Transformer) on rolling 7-night windows
- Surface weekly trend scores: "Your sleep quality has improved 12% this week"

### 6.2 Personalised Recommendations Engine

```python
# recommendations.py (pseudo-code)
def generate_recommendations(session_data: dict) -> list[str]:
    recs = []
    if session_data["sleep_stage_pct_N3"] < 0.10:
        recs.append("Reduce evening caffeine intake — deep sleep (N3) was below 10%")
    if session_data["event_rate"] > 0.05:
        recs.append("Consider a sleep clinic referral — apnea event rate is elevated")
    if session_data["HR_mean"] > 75:
        recs.append("Evening relaxation exercises may reduce resting heart rate during sleep")
    return recs
```

### 6.3 Federated Learning

Allow opt-in model improvement without sharing raw data:
- Each device trains a local delta on its own data
- Deltas are aggregated server-side (FedAvg) to improve the global model
- Raw sensor data never leaves the device

### 6.4 Explainability Layer (SHAP)

```python
import shap
explainer = shap.TreeExplainer(bundle["pipeline"]["model"])
shap_values = explainer.shap_values(X_test)
# Surface top 3 features driving each prediction in the app UI
```

### 6.5 Mobile App (iOS / Android)

- React Native app pairs with RPi over local WiFi
- Shows real-time sensor stream during recording
- Displays morning sleep report with risk badge and recommendations
- Syncs historical data to cloud when on WiFi

---

## Immediate Next 5 Tasks (Start Here)

| # | Task | Effort | Impact |
|---|------|--------|--------|
| 1 | Download DREAMT v2.1.0 and run full pipeline end-to-end | 1 day | Validate pipeline on real clinical data |
| 2 | Add `record` CLI command with E4 socket streaming | 2 days | Close hardware loop |
| 3 | Build FastAPI backend skeleton with `/predict` endpoint | 2 days | Unblock frontend development |
| 4 | Create React app with mock API: dashboard + session detail pages | 3 days | Demonstrate product to investors/users |
| 5 | Add SHAP explainability to prediction output CSV | 0.5 days | Clinical credibility; low effort high value |

---

## Project File Structure (Target State)

```
sleepsense-ai/
├── hardware/
│   ├── e4_streamer.py          # E4 → MQTT live data daemon
│   ├── session_manager.py      # Session lifecycle on RPi
│   └── requirements_rpi.txt
├── src/                        # Existing pipeline (keep as-is)
│   ├── main.py
│   ├── data_processor.py
│   ├── preprocessing.py
│   ├── trainer.py
│   └── models/
├── api/
│   ├── main.py                 # FastAPI app
│   ├── routers/
│   │   ├── sessions.py
│   │   ├── predictions.py
│   │   └── models.py
│   ├── tasks.py                # Celery async tasks
│   └── schemas.py              # Pydantic models
├── frontend/
│   ├── src/
│   │   ├── pages/
│   │   ├── components/
│   │   └── api/
│   └── package.json
├── datasets/                   # gitignored
├── artifacts/                  # gitignored
├── docs/
│   ├── SleepSenseAI_Report.docx
│   ├── SleepSenseAI_Slides.pptx
│   └── SleepSenseAI_ProductRoadmap.md
└── docker-compose.yml          # API + Redis + Postgres
```

---

## Tech Stack Summary

```
Hardware:     Empatica E4 + Raspberry Pi 5
Acquisition:  Python socket daemon → MQTT (Mosquitto)
Pipeline:     Python 3.11, scikit-learn, TensorFlow 2.x, pandas
API:          FastAPI + Celery + Redis + PostgreSQL
Frontend:     React 18 + TypeScript + Tailwind CSS + Recharts
Mobile:       React Native (Phase 5)
DevOps:       Docker, GitHub Actions CI/CD, Nginx
Cloud:        AWS/GCP (optional) or fully on-premise RPi cluster
```

---

*SleepSense AI — Making clinical sleep analysis accessible, affordable, and embedded.*