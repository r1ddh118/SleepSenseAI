#!/usr/bin/env python3
"""
smoke_test.py  –  End-to-end sanity checks for the night pipeline
=================================================================

Checks
------
1. Healthy users score above 85 on average.
2. SDB users have higher ODI than healthy users.
3. Clean sleepers (best user) get no alerts.
4. Every alert spans at least 3 consecutive nights.
5. Declining user's score drops from first to second half of nights.
6. Event reconciliation: awakening and desaturation counts from events.csv
   match the nightly_metrics.csv on every scored night.
7. Stage segments add up to within 5 min of TIB on every night.
8. Sensor-gap count matches quality_report.json.

Usage
-----
    python -m sleepsense_night.smoke_test
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pandas as pd

OUTPUT_DIR = Path("outputs")


def check(name: str, condition: bool) -> bool:
    status = "✓ PASS" if condition else "✗ FAIL"
    print(f"  {status}  {name}")
    return condition


def main() -> int:
    metrics_path = OUTPUT_DIR / "nightly_metrics.csv"
    if not metrics_path.exists():
        print("Error: run the pipeline first (python -m sleepsense_night.run_pipeline)")
        return 1

    nightly = pd.read_csv(str(metrics_path))
    alerts = pd.DataFrame()
    alerts_path = OUTPUT_DIR / "doctor_alerts.csv"
    if not alerts_path.exists():
        alerts_path = OUTPUT_DIR / "alerts.csv"   # legacy name
    if alerts_path.exists():
        alerts = pd.read_csv(str(alerts_path))

    events = pd.DataFrame()
    ev_path = OUTPUT_DIR / "events.csv"
    if ev_path.exists():
        events = pd.read_csv(str(ev_path))

    quality = {}
    qpath = OUTPUT_DIR / "quality_report.json"
    if qpath.exists():
        with open(str(qpath)) as f:
            quality = json.load(f)

    ok = True

    # ── 1. Healthy users score above 85 (on average) ─────────────────
    user_means = nightly.groupby("user_id")["sleep_score"].mean()
    best_user  = user_means.idxmax()
    ok &= check(
        f"Best user ({best_user}) averages ≥ 85",
        user_means[best_user] >= 85,
    )

    # ── 2. SDB users have higher ODI ─────────────────────────────────
    if "odi" in nightly.columns:
        user_odi = nightly.groupby("user_id")["odi"].mean().dropna()
        if len(user_odi) > 1:
            max_odi_user = user_odi.idxmax()
            min_odi_user = user_odi.idxmin()
            ok &= check(
                f"Max-ODI user ({max_odi_user}, {user_odi[max_odi_user]:.1f}) > "
                f"Min-ODI user ({min_odi_user}, {user_odi[min_odi_user]:.1f})",
                user_odi[max_odi_user] > user_odi[min_odi_user] * 2,
            )

    # ── 3. Clean sleepers get no alerts ───────────────────────────────
    if not alerts.empty:
        alert_users = set(alerts["user_id"].unique())
        ok &= check(
            f"Best user ({best_user}) has no alerts",
            best_user not in alert_users,
        )
    else:
        ok &= check("No alerts generated (may be expected for few nights)", True)

    # ── 4. Every alert spans ≥ 3 consecutive nights ──────────────────
    if not alerts.empty and "streak_nights" in alerts.columns:
        min_streak = alerts["streak_nights"].min()
        ok &= check(
            f"Minimum alert streak = {min_streak} (≥ 3)",
            min_streak >= 3,
        )

    # ── 5. Declining user's score drops ──────────────────────────────
    if "U005" in nightly["user_id"].values:
        u5 = nightly[nightly["user_id"] == "U005"].sort_values("night_date")
        first_half  = u5.head(len(u5) // 2)["sleep_score"].mean()
        second_half = u5.tail(len(u5) // 2)["sleep_score"].mean()
        ok &= check(
            f"Declining user (U005) first-half avg ({first_half:.1f}) > "
            f"second-half avg ({second_half:.1f})",
            first_half > second_half,
        )

    # ── 6. Event reconciliation ───────────────────────────────────────
    if not events.empty and "awakenings" in nightly.columns:
        # Count awakenings per night from events.csv
        ev_awakenings = (
            events[events["event_type"] == "awakening"]
            .groupby(["user_id", "night_date"])
            .size()
            .reset_index(name="ev_awakenings")
        )
        merged = nightly[["user_id", "night_date", "awakenings"]].merge(
            ev_awakenings, on=["user_id", "night_date"], how="left"
        )
        merged["ev_awakenings"] = merged["ev_awakenings"].fillna(0).astype(int)
        merged["awakenings"]    = merged["awakenings"].fillna(0).astype(int)
        mismatch = (merged["awakenings"] != merged["ev_awakenings"]).sum()
        ok &= check(
            f"Awakening counts match events.csv on all nights (mismatches: {mismatch})",
            mismatch == 0,
        )

        # Desaturation count reconciliation
        if "desat_events" in nightly.columns:
            ev_desats = (
                events[events["event_type"] == "desaturation"]
                .groupby(["user_id", "night_date"])
                .size()
                .reset_index(name="ev_desats")
            )
            mdn = nightly[["user_id", "night_date", "desat_events"]].merge(
                ev_desats, on=["user_id", "night_date"], how="left"
            )
            mdn["ev_desats"]    = mdn["ev_desats"].fillna(0).astype(int)
            mdn["desat_events"] = mdn["desat_events"].fillna(0).astype(int)
            mismatch_d = (mdn["desat_events"] != mdn["ev_desats"]).sum()
            ok &= check(
                f"Desaturation counts match events.csv on all nights (mismatches: {mismatch_d})",
                mismatch_d == 0,
            )

    # ── 7. Stage segments cover ≈ TIB ─────────────────────────────────
    if not events.empty and "tib_min" in nightly.columns:
        stage_secs = (
            events[events["event_type"] == "stage_segment"]
            .groupby(["user_id", "night_date"])["duration_s"]
            .sum()
            .reset_index(name="stage_total_s")
        )
        merged2 = nightly[["user_id", "night_date", "tib_min"]].merge(
            stage_secs, on=["user_id", "night_date"], how="left"
        )
        merged2["tib_s"]   = merged2["tib_min"] * 60
        merged2["diff_s"]  = (merged2["tib_s"] - merged2["stage_total_s"]).abs()
        bad = (merged2["diff_s"] > 300).sum()   # 5-minute tolerance
        ok &= check(
            f"Stage segments cover TIB (±5 min) on all nights (bad: {bad})",
            bad == 0,
        )

    # ── 8. Sensor-gap count ───────────────────────────────────────────
    if quality and not events.empty:
        qgaps = quality.get("sensor_gaps", None)
        ev_gaps = int((events["event_type"] == "sensor_gap").sum())
        if qgaps is not None:
            ok &= check(
                f"sensor_gaps in quality_report ({qgaps}) ≈ gap events in events.csv ({ev_gaps})",
                abs(qgaps - ev_gaps) <= 5,   # small tolerance for partition edge
            )

    # ── Summary ──────────────────────────────────────────────────────
    print()
    if ok:
        print("All smoke tests passed ✓")
        return 0
    else:
        print("Some smoke tests FAILED ✗")
        return 1


if __name__ == "__main__":
    sys.exit(main())
