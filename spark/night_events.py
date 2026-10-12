"""Event detection engine for 1 Hz night sensor streams."""

from __future__ import annotations

import pandas as pd
import numpy as np


def detect_night_events(df_cleaned: pd.DataFrame, tst_hours: float) -> dict:
    """Detects micro-arousals, breathing desaturation events, and snoring episodes."""
    spo2 = df_cleaned["spo2_pct"].values
    hr = df_cleaned["hr_bpm"].values
    mov = df_cleaned["movement_magnitude"].values
    snore = df_cleaned["snore_decibels"].values
    n = len(df_cleaned)

    # 1. Micro-arousals: movement spikes > 0.4 or HR jump > 12 bpm within 5 seconds
    hr_diff = np.abs(np.diff(hr, prepend=hr[0]))
    arousal_mask = (mov > 0.35) | (hr_diff > 12.0)
    arousal_count = int(np.sum(arousal_mask))

    # 2. Oxygen desaturation episodes (SpO2 drop >= 3% below rolling 60s median)
    rolling_median_spo2 = pd.Series(spo2).rolling(window=60, min_periods=1, center=True).median().values
    desat_mask = (rolling_median_spo2 - spo2) >= 3.0

    # Group contiguous desat seconds into distinct episodes (>= 10 seconds duration)
    desat_episodes = 0
    in_episode = False
    episode_length = 0

    for i in range(n):
        if desat_mask[i]:
            if not in_episode:
                in_episode = True
                episode_length = 1
            else:
                episode_length += 1
        else:
            if in_episode:
                if episode_length >= 10:
                    desat_episodes += 1
                in_episode = False
                episode_length = 0

    if in_episode and episode_length >= 10:
        desat_episodes += 1

    # 3. Snoring duration (seconds with snore > 45 dB)
    snore_seconds = int(np.sum(snore > 45.0))
    snore_minutes = round(snore_seconds / 60.0, 1)

    tst = max(0.5, tst_hours)
    desaturation_index = round(desat_episodes / tst, 2)
    total_events = desat_episodes + arousal_count
    event_rate = round(total_events / (n / 3600.0), 3)

    return {
        "micro_arousals_count": arousal_count,
        "desaturation_episodes_count": desat_episodes,
        "desaturation_index": desaturation_index,
        "snore_minutes": snore_minutes,
        "event_count": total_events,
        "event_rate": event_rate,
    }
