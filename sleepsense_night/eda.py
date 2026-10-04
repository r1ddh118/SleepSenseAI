#!/usr/bin/env python3
"""
eda.py  –  Exploratory Data Analysis for SleepSense Night pipeline
==================================================================

Reads Spark outputs with pandas and saves matplotlib/seaborn figures.
Also generates per-night HTML reports for the best and worst nights
using eda_night.build_night_report.

Usage
-----
    python -m sleepsense_night.eda --output outputs
"""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
from textwrap import dedent

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
import numpy as np
import pandas as pd
import seaborn as sns
from matplotlib.gridspec import GridSpec

# ── Style defaults ────────────────────────────────────────────────────
sns.set_theme(style="whitegrid", font_scale=0.9)
PALETTE = sns.color_palette("Set2")
STAGE_COLORS = {"W": "#e74c3c", "LIGHT": "#3498db", "DEEP": "#2c3e50", "REM": "#27ae60"}


def _save(fig: plt.Figure, path: Path, dpi: int = 150) -> None:
    fig.savefig(str(path), dpi=dpi, bbox_inches="tight")
    plt.close(fig)
    print(f"  saved {path.name}")


# ──────────────────────────────────────────────────────────────────────
# 1. Data-quality chart
# ──────────────────────────────────────────────────────────────────────

def plot_quality(quality: dict, out: Path) -> None:
    fig, axes = plt.subplots(1, 2, figsize=(12, 4))

    # Cleaning funnel
    labels = ["Raw rows", "After dedup", "After clean"]
    values = [quality["rows_raw"], quality["rows_after_dedup"], quality["rows_clean"]]
    axes[0].barh(labels, values, color=PALETTE[:3])
    axes[0].set_title("Cleaning Funnel")
    axes[0].set_xlabel("Rows")

    # Artifacts per signal
    art = quality.get("artifacts_per_signal", {})
    if art:
        axes[1].barh(list(art.keys()), list(art.values()), color=PALETTE[3])
        axes[1].set_title("Out-of-Range Artefacts per Signal")
        axes[1].set_xlabel("Count")
    else:
        axes[1].text(0.5, 0.5, "No artefact data", ha="center", va="center",
                     transform=axes[1].transAxes)

    fig.suptitle("Data Quality Report", fontsize=14, y=1.02)
    _save(fig, out / "01_quality.png")


# ──────────────────────────────────────────────────────────────────────
# 2. Whole-night multi-panel plot (one user-night)
# ──────────────────────────────────────────────────────────────────────

def plot_whole_night(epochs: pd.DataFrame, out: Path) -> None:
    # Pick one interesting night (preferably an SDB-profile user)
    if epochs.empty:
        return
    user_night = epochs.groupby(["user_id", "night_date"]).size().idxmax()
    sub = epochs[(epochs["user_id"] == user_night[0]) &
                 (epochs["night_date"] == user_night[1])].copy()
    sub = sub.sort_values("ts")
    t = pd.to_datetime(sub["ts"])

    fig = plt.figure(figsize=(16, 14))
    gs = GridSpec(7, 1, hspace=0.3, figure=fig)
    panels = [
        ("stage",         "Hypnogram",      None),
        ("hr_bpm",        "Heart Rate (bpm)", None),
        ("spo2_pct",      "SpO₂ (%)",        None),
        ("resp_rate_bpm", "Respiration",      None),
        ("movement_g",    "Movement (g)",     None),
        ("snore_db",      "Snore (dB)",       None),
        ("eda_us",        "EDA (μS)",         None),
    ]

    for i, (col, title, _) in enumerate(panels):
        ax = fig.add_subplot(gs[i, 0])
        if col == "stage":
            stage_map = {"W": 3, "REM": 2, "LIGHT": 1, "DEEP": 0}
            y = sub["stage"].map(stage_map).fillna(1)
            ax.step(t, y, where="post", color="#2c3e50", linewidth=0.8)
            ax.set_yticks([0, 1, 2, 3])
            ax.set_yticklabels(["DEEP", "LIGHT", "REM", "WAKE"])
        elif col == "spo2_pct":
            ax.plot(t, sub[col], color="#3498db", linewidth=0.6)
            # Red dots for desaturation starts
            if "desat_event_start" in sub.columns:
                desat = sub[sub["desat_event_start"] == 1]
                ax.scatter(pd.to_datetime(desat["ts"]), desat["spo2_pct"],
                           color="red", s=12, zorder=5, label="desat event")
                ax.legend(loc="lower left", fontsize=7)
        else:
            ax.plot(t, sub[col], linewidth=0.6, color=PALETTE[i % len(PALETTE)])
        ax.set_ylabel(title, fontsize=8)
        ax.tick_params(labelsize=7)
        if i < len(panels) - 1:
            ax.set_xticklabels([])

    fig.suptitle(f"Whole-Night Plot — {user_night[0]} / {user_night[1]}",
                 fontsize=13, y=0.95)
    _save(fig, out / "02_whole_night.png")


# ──────────────────────────────────────────────────────────────────────
# 3. Stage composition per user
# ──────────────────────────────────────────────────────────────────────

def plot_stage_composition(nightly: pd.DataFrame, out: Path) -> None:
    cols = ["deep_pct", "light_pct", "rem_pct"]
    agg = nightly.groupby("user_id")[cols].mean()
    fig, ax = plt.subplots(figsize=(10, 5))
    agg.plot(kind="bar", stacked=True, ax=ax,
             color=[STAGE_COLORS["DEEP"], STAGE_COLORS["LIGHT"], STAGE_COLORS["REM"]])
    ax.set_ylabel("% of TST")
    ax.set_title("Average Stage Composition per User")
    ax.legend(["Deep", "Light", "REM"], loc="upper right")
    plt.xticks(rotation=0)
    _save(fig, out / "03_stage_composition.png")


# ──────────────────────────────────────────────────────────────────────
# 4. Boxplots of nightly metrics
# ──────────────────────────────────────────────────────────────────────

def plot_metric_boxes(nightly: pd.DataFrame, out: Path) -> None:
    metrics = ["tst_min", "efficiency_pct", "sol_min", "waso_min",
               "deep_pct", "rem_pct", "odi", "sleep_score"]
    avail = [m for m in metrics if m in nightly.columns]
    fig, axes = plt.subplots(2, 4, figsize=(16, 7))
    for i, m in enumerate(avail):
        ax = axes.flat[i]
        sns.boxplot(data=nightly, x="user_id", y=m, ax=ax, palette="Set2")
        ax.set_title(m, fontsize=9)
        ax.tick_params(labelsize=7)
        ax.set_xlabel("")
    for j in range(len(avail), 8):
        axes.flat[j].set_visible(False)
    fig.suptitle("Nightly Metric Distributions", fontsize=13, y=1.02)
    fig.tight_layout()
    _save(fig, out / "04_metric_boxes.png")


# ──────────────────────────────────────────────────────────────────────
# 5. Correlation heatmap
# ──────────────────────────────────────────────────────────────────────

def plot_corr_heatmap(nightly: pd.DataFrame, out: Path) -> None:
    num_cols = nightly.select_dtypes(include=[np.number]).columns.tolist()
    # Exclude internal columns
    skip = {"total_epochs", "hr_epochs", "flag_count"}
    num_cols = [c for c in num_cols if c not in skip]
    corr = nightly[num_cols].corr()

    fig, ax = plt.subplots(figsize=(14, 12))
    sns.heatmap(corr, annot=True, fmt=".2f", cmap="RdBu_r", center=0,
                ax=ax, annot_kws={"size": 6}, linewidths=0.5)
    ax.set_title("Nightly Metric Correlations", fontsize=13)
    ax.tick_params(labelsize=7)
    _save(fig, out / "05_correlation.png")


# ──────────────────────────────────────────────────────────────────────
# 6. Overnight profile (mean by half-hour since lights-off)
# ──────────────────────────────────────────────────────────────────────

def plot_overnight_profile(epochs: pd.DataFrame, out: Path) -> None:
    if epochs.empty:
        return
    ep = epochs.copy()
    ep["ts"] = pd.to_datetime(ep["ts"])

    # Compute minutes since bedtime for each user-night
    bedtimes = ep.groupby(["user_id", "night_date"])["ts"].min().rename("bedtime")
    ep = ep.merge(bedtimes, on=["user_id", "night_date"])
    ep["min_since_bed"] = (ep["ts"] - ep["bedtime"]).dt.total_seconds() / 60
    ep["half_hour"] = (ep["min_since_bed"] // 30).astype(int)
    ep = ep[ep["half_hour"].between(0, 16)]  # up to 8 hours

    fig, axes = plt.subplots(2, 2, figsize=(14, 8))
    for ax, col, label in zip(
        axes.flat,
        ["hr_bpm", "spo2_pct", "resp_rate_bpm", "movement_g"],
        ["HR (bpm)", "SpO₂ (%)", "Resp Rate", "Movement (g)"],
    ):
        grp = ep.groupby("half_hour")[col].agg(["mean", "std"]).reset_index()
        ax.fill_between(grp["half_hour"] * 0.5, grp["mean"] - grp["std"],
                        grp["mean"] + grp["std"], alpha=0.2)
        ax.plot(grp["half_hour"] * 0.5, grp["mean"], linewidth=1.5)
        ax.set_xlabel("Hours since bedtime")
        ax.set_ylabel(label)
        ax.set_title(label)
    fig.suptitle("Overnight Profile (all users)", fontsize=13, y=1.02)
    fig.tight_layout()
    _save(fig, out / "06_overnight_profile.png")


# ──────────────────────────────────────────────────────────────────────
# 7. Score trends with moving averages and alert bands
# ──────────────────────────────────────────────────────────────────────

def plot_score_trends(nightly: pd.DataFrame, alerts: pd.DataFrame | None, out: Path) -> None:
    users = sorted(nightly["user_id"].unique())
    n_users = len(users)
    fig, axes = plt.subplots(n_users, 1, figsize=(14, 3 * n_users), sharex=True)
    if n_users == 1:
        axes = [axes]

    for ax, uid in zip(axes, users):
        u = nightly[nightly["user_id"] == uid].sort_values("night_date")
        nd = pd.to_datetime(u["night_date"])
        ax.plot(nd, u["sleep_score"], "o-", markersize=3, label="Score")
        if "sleep_score_ma7" in u.columns:
            ax.plot(nd, u["sleep_score_ma7"], "--", label="7-night MA")
        if "sleep_score_ma14" in u.columns:
            ax.plot(nd, u["sleep_score_ma14"], ":", label="14-night MA")

        # Red bands for alert streaks
        if alerts is not None and not alerts.empty:
            ua = alerts[alerts["user_id"] == uid]
            for _, row in ua.iterrows():
                ax.axvspan(pd.Timestamp(row["streak_start"]),
                           pd.Timestamp(row["streak_end"]),
                           alpha=0.15, color="red")

        ax.set_ylabel("Score")
        ax.set_title(uid, fontsize=10)
        ax.legend(fontsize=7, loc="lower left")
        ax.set_ylim(0, 105)

    fig.suptitle("Sleep Score Trends", fontsize=13, y=1.01)
    fig.tight_layout()
    _save(fig, out / "07_score_trends.png")


# ──────────────────────────────────────────────────────────────────────
# 8. Inferred vs device stage confusion matrix
# ──────────────────────────────────────────────────────────────────────

def plot_stage_confusion(epochs: pd.DataFrame, out: Path) -> None:
    if "device_stage" not in epochs.columns or "stage" not in epochs.columns:
        return
    valid = epochs.dropna(subset=["device_stage", "stage"])
    if valid.empty:
        return

    labels = ["W", "LIGHT", "DEEP", "REM"]
    from sklearn.metrics import confusion_matrix as cm_func
    try:
        mat = cm_func(valid["device_stage"], valid["stage"], labels=labels)
    except Exception:
        # sklearn might not be installed
        return

    fig, ax = plt.subplots(figsize=(6, 5))
    sns.heatmap(mat, annot=True, fmt="d", xticklabels=labels, yticklabels=labels,
                cmap="Blues", ax=ax)
    ax.set_xlabel("Inferred Stage")
    ax.set_ylabel("Device Stage")
    ax.set_title("Stage Classification: Device vs Inferred")
    _save(fig, out / "08_stage_confusion.png")


# ──────────────────────────────────────────────────────────────────────
# 9. When do events happen? (from events.parquet / events.csv)
# ──────────────────────────────────────────────────────────────────────

def plot_events_timing(events: pd.DataFrame, nightly: pd.DataFrame, out: Path) -> None:
    if events.empty:
        return

    # Build minutes-since-bedtime for each event start
    if nightly.empty or "bedtime_ts" not in nightly.columns:
        return

    bedtimes = nightly[["user_id", "night_date", "bedtime_ts"]].copy()
    ev = events.merge(bedtimes, on=["user_id", "night_date"], how="left")
    ev["start_ts"]   = pd.to_datetime(ev["start_ts"])
    ev["bedtime_ts"] = pd.to_datetime(ev["bedtime_ts"])
    ev["min_since_bed"] = (ev["start_ts"] - ev["bedtime_ts"]).dt.total_seconds() / 60

    plot_types = ["awakening", "micro_arousal", "desaturation", "sensor_gap"]
    available  = [t for t in plot_types if t in ev["event_type"].values]
    if not available:
        return

    fig, axes = plt.subplots(1, len(available), figsize=(5 * len(available), 4),
                             sharey=False)
    if len(available) == 1:
        axes = [axes]

    palette = {"awakening": "#e74c3c", "micro_arousal": "#e67e22",
               "desaturation": "#9b59b6", "sensor_gap": "#7f8c8d"}

    for ax, etype in zip(axes, available):
        sub = ev[ev["event_type"] == etype]["min_since_bed"].dropna()
        ax.hist(sub, bins=24, color=palette.get(etype, "steelblue"), edgecolor="white")
        ax.set_title(etype.replace("_", " ").title(), fontsize=10)
        ax.set_xlabel("Minutes since bedtime")
        ax.set_ylabel("Count")

    fig.suptitle("When Do Events Occur?", fontsize=13, y=1.02)
    fig.tight_layout()
    _save(fig, out / "09_event_timing.png")


# ──────────────────────────────────────────────────────────────────────
# HTML report
# ──────────────────────────────────────────────────────────────────────

def build_html_report(out: Path) -> None:
    pngs = sorted(out.glob("*.png"))
    imgs = "\n".join(
        f'<div class="chart"><h3>{p.stem}</h3><img src="{p.name}"></div>'
        for p in pngs
    )
    html = dedent(f"""\
    <!DOCTYPE html>
    <html lang="en">
    <head>
        <meta charset="utf-8">
        <title>SleepSense Night – EDA Report</title>
        <style>
            body {{ font-family: Inter, system-ui, sans-serif; margin: 2em; background: #fafafa; }}
            h1 {{ color: #2c3e50; }}
            .chart {{ margin: 1.5em 0; }}
            .chart img {{ max-width: 100%; border: 1px solid #ddd; border-radius: 6px; }}
            .chart h3 {{ color: #555; font-size: 0.95em; }}
        </style>
    </head>
    <body>
        <h1>🛏️ SleepSense Night – EDA Report</h1>
        {imgs}
    </body>
    </html>
    """)
    (out / "eda_report.html").write_text(html)
    print(f"  saved eda_report.html")


# ──────────────────────────────────────────────────────────────────────
# Main
# ──────────────────────────────────────────────────────────────────────

def main() -> None:
    parser = argparse.ArgumentParser(description="SleepSense Night EDA")
    parser.add_argument("--output", default="outputs", help="Pipeline output directory")
    args = parser.parse_args()

    out = Path(args.output)
    if not out.exists():
        print(f"Error: output directory {out} not found. Run the pipeline first.")
        return

    # Load data
    nightly = pd.read_csv(str(out / "nightly_metrics.csv"))
    alerts = None
    for aname in ("doctor_alerts.csv", "alerts.csv"):
        if (out / aname).exists():
            alerts = pd.read_csv(str(out / aname))
            break

    # Try to load epoch data (Parquet)
    epochs = pd.DataFrame()
    epoch_path = out / "epochs.parquet"
    if epoch_path.exists():
        try:
            epochs = pd.read_parquet(str(epoch_path))
        except Exception as e:
            print(f"  Warning: could not read epochs parquet: {e}")

    # Event timeline
    events = pd.DataFrame()
    for ename in ("events.csv", "events.parquet"):
        ep = out / ename
        if ep.exists():
            try:
                if ename.endswith(".csv"):
                    events = pd.read_csv(str(ep))
                else:
                    events = pd.read_parquet(str(ep))
                break
            except Exception as e:
                print(f"  Warning: could not read {ename}: {e}")

    quality = {}
    qpath = out / "quality_report.json"
    if qpath.exists():
        with open(str(qpath)) as f:
            quality = json.load(f)

    print("Generating EDA plots …")
    plot_quality(quality, out)
    plot_whole_night(epochs, out)
    plot_stage_composition(nightly, out)
    plot_metric_boxes(nightly, out)
    plot_corr_heatmap(nightly, out)
    plot_overnight_profile(epochs, out)
    plot_score_trends(nightly, alerts, out)
    plot_stage_confusion(epochs, out)
    plot_events_timing(events, nightly, out)
    build_html_report(out)

    # Per-night HTML for best and worst nights
    if not nightly.empty and not epochs.empty:
        try:
            from sleepsense_night.eda_night import build_night_report
            night_score = nightly.set_index(["user_id", "night_date"])["sleep_score"]
            best_idx  = night_score.idxmax()
            worst_idx = night_score.idxmin()
            for uid, nd in [best_idx, worst_idx]:
                build_night_report(uid, nd, epochs, events, nightly, out)
        except Exception as e:
            print(f"  Warning: per-night report failed: {e}")

    print(f"\n✓ EDA complete – open {out}/eda_report.html")


if __name__ == "__main__":
    main()
