"""
SleepSense Night Pipeline – Configuration
==========================================
Defines the input schema (required and optional columns), valid sensor
ranges, and scoring / flag thresholds used throughout the pipeline.
"""

# ── Column definitions ────────────────────────────────────────────────
# Only three columns are truly mandatory; everything else is derived or
# filled with NULL when absent.
REQUIRED_COLUMNS = ["timestamp", "hr_bpm", "movement_g"]

OPTIONAL_COLUMNS = [
    "user_id", "night_date", "spo2_pct", "resp_rate_bpm", "skin_temp_c",
    "eda_us", "snore_db", "ambient_lux", "device_stage",
]

# Numeric columns that should be cast to double
NUMERIC_COLUMNS = [
    "hr_bpm", "spo2_pct", "resp_rate_bpm", "movement_g",
    "skin_temp_c", "eda_us", "snore_db", "ambient_lux",
]

# ── Valid sensor ranges ───────────────────────────────────────────────
# Values outside these ranges are treated as sensor glitches (set to NULL).
VALID_RANGES = {
    "hr_bpm":        (30, 200),
    "spo2_pct":      (70, 100),
    "resp_rate_bpm": (0,  40),
    "movement_g":    (0,  8),
    "skin_temp_c":   (28, 40),
    "eda_us":        (0,  60),
    "snore_db":      (20, 100),
    "ambient_lux":   (0,  5000),
}

# ── Sleep-stage inference thresholds ──────────────────────────────────
STAGE_THRESHOLDS = {
    "wake_movement":   0.05,   # movement_g above this → wake candidate
    "wake_hr_rel":     7.0,    # HR relative to night median above this → wake
    "deep_hr_rel":    -3.5,    # HR relative below this → deep candidate
    "deep_resp_std":   0.45,   # resp std below this confirms deep
    "rem_resp_std":    0.9,    # resp std above this → REM candidate
    "rem_hr_rel":     -1.0,    # HR relative above this confirms REM
}

# ── Onset detection ──────────────────────────────────────────────────
ONSET_SLEEP_FRACTION = 0.90   # 90 % of next 10 min must be sleep
ONSET_WINDOW_MINUTES = 10

# ── Desaturation event detection ─────────────────────────────────────
DESAT_THRESHOLD_PCT  = 3      # SpO₂ must drop ≥3 points from rolling max
DESAT_BASELINE_MINUTES = 5    # rolling-max window

# ── Scoring weights ──────────────────────────────────────────────────
SCORE_WEIGHTS = {
    "efficiency":    30,
    "tst":           25,
    "deep_pct":      15,
    "rem_pct":       10,
    "latency":       10,
    "waso":          10,
    "odi_penalty":   15,
}

# ── Risk-flag thresholds ─────────────────────────────────────────────
FLAG_THRESHOLDS = {
    "odi_sdb":              5,
    "snore_pct_sdb":       25,
    "spo2_min_sdb":        90,
    "sol_insomnia":        30,
    "efficiency_insomnia": 85,
    "waso_insomnia":       45,
    "awakenings_frag":      4,
    "micro_arousal_frag":   2.0,
    "tst_short":          360,   # minutes
    "odi_high_risk":       15,
    "flag_count_high":      2,
    "score_high_risk":     50,
}

# ── Trend / alert thresholds ─────────────────────────────────────────
TREND_DECLINE_POINTS   = 5     # 7-night MA vs prior 7 nights
CIRCADIAN_STD_MINUTES  = 90    # bedtime σ over 7 nights
ALERT_CONSECUTIVE_NIGHTS = 3   # doctor-alert streak threshold

# ── Pipeline defaults ────────────────────────────────────────────────
DEFAULT_PARTITIONS = 8
MAX_GAP_FILL_SECONDS = 60
MAX_EPOCH_SECONDS = 120        # longer gap → epoch gets default step duration
WAKE_BOUT_MIN_SECONDS = 120    # wake bout ≥ this counts as an awakening
