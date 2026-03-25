# SleepSenseAI

> An AI-powered sleep quality scoring system using heart rate and accelerometer data collected from an ESP32-based wearable device.

---

## Table of Contents

- [Overview](#overview)
- [How It Works](#how-it-works)
- [Hardware Setup](#hardware-setup)
- [Dataset](#dataset)
- [Project Structure](#project-structure)
- [Getting Started](#getting-started)
- [Model & Methodology](#model--methodology)
- [Results](#results)
- [Contributing](#contributing)
- [License](#license)

---

## Overview

SleepSenseAI is a machine learning project that automatically scores the quality of a person's sleep. The system captures physiological and motion signals overnight using an **ESP32** microcontroller equipped with:

- **Heart Rate Sensor** – tracks pulse variations associated with different sleep stages.
- **Accelerometer Sensor** – monitors body movement to detect restlessness and transitions between sleep stages.

The recorded signals are fed into an AI model that analyses patterns and produces a **sleep quality score**, helping users and clinicians better understand sleep health.

---

## How It Works

```
ESP32 Device (Heart Rate + Accelerometer)
          │
          ▼
  Raw Sensor Data Collection
  (timestamped HR & accelerometer readings)
          │
          ▼
  Data Pre-processing & Feature Extraction
  (filtering, windowing, statistical features)
          │
          ▼
  AI / ML Model
  (classifies sleep stages & computes sleep score)
          │
          ▼
  Sleep Quality Score & Report
```

1. **Data Collection** – The ESP32 samples heart rate and acceleration at regular intervals throughout the night.
2. **Pre-processing** – Raw signals are cleaned (noise removal, normalisation) and segmented into fixed time windows.
3. **Feature Extraction** – Statistical and frequency-domain features are extracted from each window.
4. **Model Inference** – A trained machine learning model predicts sleep stages (e.g., Awake, Light, Deep, REM) and aggregates them into an overall sleep quality score.
5. **Scoring** – The final score summarises sleep efficiency, stage distribution, and disturbance frequency.

---

## Hardware Setup

| Component | Details |
|-----------|---------|
| Microcontroller | ESP32 (Wi-Fi/BLE capable) |
| Heart Rate Sensor | Pulse oximeter / optical HR sensor (e.g., MAX30102) |
| Accelerometer | 3-axis MEMS accelerometer (e.g., MPU-6050) |
| Power Supply | Rechargeable LiPo battery |
| Communication | Wi-Fi / BLE for data transfer to host system |

**Wiring overview:**

- Heart rate sensor connected to ESP32 via I²C (SDA/SCL pins).
- Accelerometer connected to ESP32 via I²C (shared bus or separate).
- Data logged locally to flash or streamed to a host for offline analysis.

---

## Dataset

The project uses polysomnography (PSG) annotated datasets to train and validate the model. Sample participant metadata is stored in `datasets/participant_info.csv`.

| Column | Description |
|--------|-------------|
| `SID` | Participant ID |
| `AGE` | Age in years |
| `GENDER` | M / F |
| `BMI` | Body Mass Index |
| `OAHI` | Obstructive Apnea-Hypopnea Index |
| `AHI` | Apnea-Hypopnea Index |
| `Mean_SaO2` | Mean blood oxygen saturation |
| `Arousal Index` | Number of arousals per hour |
| `MEDICAL_HISTORY` | Pre-existing conditions |
| `Sleep_Disorders` | Diagnosed sleep disorders |

Raw sensor recordings per participant are stored as compressed archives (`.zip`) inside the `datasets/` directory.

---

## Project Structure

```
SleepSenseAI/
├── datasets/
│   ├── participant_info.csv          # Participant metadata
│   ├── S002_whole_df_compressed_v2.zip
│   ├── S006_whole_df_compressed_v2.zip
│   └── Data.zip
├── README.md
└── ...                               # Model training & inference scripts (coming soon)
```

---

## Getting Started

### Prerequisites

- Python 3.8+
- pip

### Installation

```bash
# Clone the repository
git clone https://github.com/r1ddh118/SleepSenseAI.git
cd SleepSenseAI

# (Optional) Create and activate a virtual environment
python -m venv venv
source venv/bin/activate   # Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt
```

### Running the Model

```bash
# Pre-process the raw dataset
python src/preprocess.py --data datasets/

# Train the model
python src/train.py

# Score a new recording
python src/predict.py --input <path_to_recording>
```

> **Note:** Training scripts and full pipeline code are actively being developed.

---

## Model & Methodology

| Step | Technique |
|------|-----------|
| Signal Filtering | Butterworth bandpass filter |
| Segmentation | 30-second overlapping windows |
| Feature Extraction | Mean, std, skewness, FFT peaks, HRV metrics |
| Classification | Random Forest / LSTM neural network |
| Scoring | Weighted average of sleep stage proportions |

Sleep stages targeted:

- **Awake**
- **Light Sleep (N1/N2)**
- **Deep Sleep (N3)**
- **REM Sleep**

---

## Results

> Results and benchmarks will be updated as model development progresses.

---

## Contributing

Contributions are welcome! Please follow these steps:

1. Fork the repository.
2. Create a feature branch: `git checkout -b feature/your-feature`.
3. Commit your changes: `git commit -m "Add your feature"`.
4. Push to the branch: `git push origin feature/your-feature`.
5. Open a Pull Request.

---

## License

This project is licensed under the [MIT License](LICENSE).
