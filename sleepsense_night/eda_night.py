#!/usr/bin/env python3
"""
eda_night.py  –  Per-night HTML EDA report
==========================================

Writes one self-contained HTML file per night with:
  - A clock-time figure of all sensor signals + event strip
  - Key-time summary (bedtime, onset, final wake, duration)
  - Hour-by-hour table
  - Full event log
  - Every stage-change

Usage
-----
    python -m sleepsense_night.eda_night --user U003 --date 2026-09-04
    python -m sleepsense_night.eda_night --all     # process every night
"""

from __future__ import annotations

import argparse
import base64
import io
from pathlib import Path
from textwrap import dedent

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
import numpy as np
import pandas as pd
from matplotlib.gridspec import GridSpec

# ── Style ────────────────────────────────────────────────────────────
STAGE_COLORS  = {"W": "#e74c3c", "LIGHT": "#3498db", "DEEP": "#2c3e50", "REM": "#27ae60"}
EVENT_COLORS  = {
    "awakening": "#e74c3c",
    "micro_arousal": "#e67e22",
    "desaturation": "#9b59b6",
    "sensor_gap": "#7f8c8d",
    "pre_sleep_wake": "#f39c12",
    "morning_wake": "#c0392b",
}
SIGNAL_COLORS = ["#2980b9", "#16a085", "#8e44ad", "#c0392b", "#f39c12", "#27ae60"]


def _fig_to_b64(fig: plt.Figure) -> str:
    buf = io.BytesIO()
    fig.savefig(buf, format="png", dpi=120, bbox_inches="tight")
    plt.close(fig)
    buf.seek(0)
    return base64.b64encode(buf.read()).decode()


def _plot_signals(sub: pd.DataFrame, events: pd.DataFrame) -> str:
    """Build a multi-panel signal figure; return as base-64 PNG."""
    signals = [
        ("stage",         "Hypnogram"),
        ("hr_bpm",        "HR (bpm)"),
        ("spo2_pct",      "SpO₂ (%)"),
        ("resp_rate_bpm", "Resp (bpm)"),
        ("movement_g",    "Movement (g)"),
        ("snore_db",      "Snore (dB)"),
        ("eda_us",        "EDA (μS)"),
    ]
    avail = [(c, t) for c, t in signals if c in sub.columns or c == "stage"]

    n_panels = len(avail) + 1  # +1 for event strip
    fig = plt.figure(figsize=(16, 2.2 * n_panels))
    gs  = GridSpec(n_panels, 1, hspace=0.35, figure=fig)
    t   = pd.to_datetime(sub["ts"])

    fmt = mdates.DateFormatter("%H:%M")

    for i, (col, title) in enumerate(avail):
        ax = fig.add_subplot(gs[i, 0])
        if col == "stage":
            stage_map = {"W": 3, "REM": 2, "LIGHT": 1, "DEEP": 0}
            y = sub["stage"].map(stage_map).fillna(1)
            ax.step(t, y, where="post", color="#2c3e50", linewidth=0.9)
            ax.set_yticks([0, 1, 2, 3])
            ax.set_yticklabels(["DEEP", "LIGHT", "REM", "WAKE"], fontsize=7)
            # Shade by stage
            for s, c_ in STAGE_COLORS.items():
                mask = sub["stage"] == s
                if mask.any():
                    for seg in _mask_to_spans(t[mask]):
                        ax.axvspan(*seg, alpha=0.10, color=c_)
        elif col == "spo2_pct":
            ax.plot(t, sub[col], color="#3498db", linewidth=0.7)
            if "desat_event_start" in sub.columns:
                ds = sub[sub["desat_event_start"] == 1]
                ax.scatter(pd.to_datetime(ds["ts"]), ds[col],
                           color="red", s=12, zorder=5, label="desat")
                ax.legend(loc="lower left", fontsize=7)
        else:
            color = SIGNAL_COLORS[i % len(SIGNAL_COLORS)]
            ax.plot(t, sub[col], linewidth=0.7, color=color)
        ax.set_ylabel(title, fontsize=8)
        ax.tick_params(labelsize=7)
        ax.xaxis.set_major_formatter(fmt)
        if i < len(avail) - 1:
            ax.set_xticklabels([])

    # Event strip
    ax_ev = fig.add_subplot(gs[n_panels - 1, 0])
    y_map = {
        "awakening": 0.6, "micro_arousal": 0.4,
        "desaturation": 0.2, "sensor_gap": 0.8,
        "pre_sleep_wake": 0.5, "morning_wake": 0.5,
    }
    for _, ev in events.iterrows():
        et = ev["event_type"]
        if et not in y_map:
            continue
        y_  = y_map[et]
        x0  = pd.Timestamp(ev["start_ts"])
        x1  = pd.Timestamp(ev["end_ts"])
        col = EVENT_COLORS.get(et, "gray")
        if x0 == x1:
            ax_ev.axvline(x0, color=col, linewidth=1.5, alpha=0.9)
        else:
            ax_ev.barh(y_, (x1 - x0).total_seconds() / 3600,
                       left=(x0 - t.iloc[0]).total_seconds() / 3600,
                       height=0.15, color=col, alpha=0.8)
    ax_ev.set_xlim(t.iloc[0], t.iloc[-1])
    ax_ev.set_yticks([0.2, 0.4, 0.6, 0.8])
    ax_ev.set_yticklabels(["Desat", "Micro", "Awake", "Gap"], fontsize=7)
    ax_ev.xaxis.set_major_formatter(fmt)
    ax_ev.set_ylabel("Events", fontsize=8)
    ax_ev.tick_params(labelsize=7)

    fig.suptitle(f"Night signals – {sub['user_id'].iloc[0]} / {sub['night_date'].iloc[0]}",
                 fontsize=12, y=1.01)
    return _fig_to_b64(fig)


def _mask_to_spans(t_series: pd.Series) -> list[tuple]:
    """Convert a boolean time-series to contiguous (start, end) spans."""
    spans, in_span, start = [], False, None
    for ts in t_series:
        if not in_span:
            in_span = True
            start   = ts
        prev = ts
    if in_span:
        spans.append((start, prev))
    return spans


def _hour_table(sub: pd.DataFrame) -> str:
    sub = sub.copy()
    sub["ts"] = pd.to_datetime(sub["ts"])
    sub["hour"] = sub["ts"].dt.floor("1h")
    rows = []
    for hr, g in sub.groupby("hour"):
        stage_mode = g["stage"].mode().iloc[0] if "stage" in g.columns else "?"
        hr_mean    = f"{g['hr_bpm'].mean():.1f}" if "hr_bpm" in g.columns and g["hr_bpm"].notna().any() else "—"
        spo2_mean  = f"{g['spo2_pct'].mean():.1f}" if "spo2_pct" in g.columns and g["spo2_pct"].notna().any() else "—"
        mov_mean   = f"{g['movement_g'].mean():.3f}" if "movement_g" in g.columns and g["movement_g"].notna().any() else "—"
        rows.append(f"<tr><td>{hr.strftime('%H:%M')}</td>"
                    f"<td>{stage_mode}</td><td>{hr_mean}</td>"
                    f"<td>{spo2_mean}</td><td>{mov_mean}</td></tr>")
    return (
        "<table><thead><tr>"
        "<th>Hour</th><th>Stage</th><th>HR</th><th>SpO₂</th><th>Mov</th>"
        "</tr></thead><tbody>"
        + "".join(rows)
        + "</tbody></table>"
    )


def _event_table(events: pd.DataFrame) -> str:
    if events.empty:
        return "<p>No events</p>"
    rows = []
    for _, ev in events.sort_values("start_ts").iterrows():
        rows.append(
            f"<tr><td>{ev['event_type']}</td>"
            f"<td>{pd.Timestamp(ev['start_ts']).strftime('%H:%M:%S') if pd.notna(ev['start_ts']) else '—'}</td>"
            f"<td>{pd.Timestamp(ev['end_ts']).strftime('%H:%M:%S') if pd.notna(ev['end_ts']) else '—'}</td>"
            f"<td>{int(ev['duration_s']) if pd.notna(ev['duration_s']) else 0}s</td>"
            f"<td>{ev.get('stage', '') or ''}</td>"
            f"<td>{ev.get('spo2_nadir', '') or ''}</td>"
            f"</tr>"
        )
    return (
        "<table><thead><tr>"
        "<th>Event</th><th>Start</th><th>End</th><th>Duration</th><th>Stage</th><th>SpO₂ nadir</th>"
        "</tr></thead><tbody>"
        + "".join(rows)
        + "</tbody></table>"
    )


def build_night_report(
    uid: str,
    date: str,
    epochs: pd.DataFrame,
    events: pd.DataFrame,
    nightly: pd.DataFrame,
    out: Path,
) -> Path:
    sub = epochs[(epochs["user_id"] == uid) & (epochs["night_date"] == date)].copy()
    if sub.empty:
        print(f"  No epoch data for {uid}/{date}")
        return None

    sub_ev = pd.DataFrame()
    if not events.empty:
        sub_ev = events[(events["user_id"] == uid) & (events["night_date"] == date)].copy()

    sub_n = pd.DataFrame()
    if not nightly.empty:
        sub_n = nightly[(nightly["user_id"] == uid) & (nightly["night_date"] == date)]

    # Key-time summary
    kt_rows = ""
    if not sub_n.empty:
        r = sub_n.iloc[0]
        for label, col in [
            ("Bedtime",    "bedtime_ts"),
            ("Sleep onset","onset_ts"),
            ("Final wake", "final_wake_ts"),
            ("TST",        "tst_min"),
            ("Efficiency", "efficiency_pct"),
            ("Sleep score","sleep_score"),
        ]:
            val = r.get(col, "—")
            if col.endswith("_ts") and pd.notna(val):
                val = pd.Timestamp(val).strftime("%H:%M:%S")
            elif col == "tst_min" and pd.notna(val):
                val = f"{float(val):.0f} min"
            elif col == "efficiency_pct" and pd.notna(val):
                val = f"{float(val):.1f}%"
            kt_rows += f"<tr><td>{label}</td><td>{val}</td></tr>"

    img_b64 = _plot_signals(sub, sub_ev)
    hour_tbl = _hour_table(sub)
    ev_tbl   = _event_table(sub_ev)

    # Stage changes
    stage_changes = ""
    if not sub_ev.empty:
        segs = sub_ev[sub_ev["event_type"] == "stage_segment"].sort_values("start_ts")
        for _, s in segs.iterrows():
            t0 = pd.Timestamp(s["start_ts"]).strftime("%H:%M:%S") if pd.notna(s["start_ts"]) else "—"
            stage_changes += f"<li>{t0} → <b>{s.get('stage','?')}</b></li>"

    html = dedent(f"""\
    <!DOCTYPE html>
    <html lang="en">
    <head>
        <meta charset="utf-8">
        <title>SleepSense – {uid} {date}</title>
        <style>
            body {{ font-family: Inter, system-ui, sans-serif; margin: 2em;
                    background: #f5f6fa; color: #2c3e50; }}
            h1   {{ color: #2c3e50; margin-bottom: 0.3em; }}
            h2   {{ color: #34495e; border-bottom: 2px solid #ddd;
                    padding-bottom: 0.3em; margin-top: 1.8em; }}
            table{{ border-collapse: collapse; width: 100%; margin: 1em 0; }}
            th,td{{ border: 1px solid #ddd; padding: 6px 10px; font-size: 0.85em; }}
            th   {{ background: #2c3e50; color: #fff; }}
            tr:nth-child(even) {{ background: #ecf0f1; }}
            .img-box img {{ max-width: 100%; border: 1px solid #ccc;
                            border-radius: 6px; }}
            ul {{ font-size: 0.85em; }}
        </style>
    </head>
    <body>
        <h1>🛏️ Night Report — {uid} &middot; {date}</h1>

        <h2>Key Times</h2>
        <table style="width:auto"><tbody>{kt_rows}</tbody></table>

        <h2>Signal Overview</h2>
        <div class="img-box">
            <img src="data:image/png;base64,{img_b64}" alt="signals">
        </div>

        <h2>Hour-by-Hour Summary</h2>
        {hour_tbl}

        <h2>Event Log</h2>
        {ev_tbl}

        <h2>Stage Changes</h2>
        <ul>{stage_changes}</ul>
    </body>
    </html>
    """)

    night_dir = out / "night_reports"
    night_dir.mkdir(parents=True, exist_ok=True)
    report_path = night_dir / f"{uid}_{date}.html"
    report_path.write_text(html, encoding="utf-8")
    print(f"  wrote {report_path}")
    return report_path


def main() -> None:
    parser = argparse.ArgumentParser(description="SleepSense per-night EDA")
    parser.add_argument("--user",   help="User ID (e.g. U003)")
    parser.add_argument("--date",   help="Night date (e.g. 2026-09-04)")
    parser.add_argument("--all",    action="store_true", help="Process all nights")
    parser.add_argument("--output", default="outputs", help="Pipeline output directory")
    args = parser.parse_args()

    out = Path(args.output)

    nightly = pd.read_csv(str(out / "nightly_metrics.csv")) \
        if (out / "nightly_metrics.csv").exists() else pd.DataFrame()

    events = pd.DataFrame()
    if (out / "events.csv").exists():
        events = pd.read_csv(str(out / "events.csv"))

    epochs = pd.DataFrame()
    ep_path = out / "epochs.parquet"
    if ep_path.exists():
        try:
            epochs = pd.read_parquet(str(ep_path))
        except Exception as e:
            print(f"Warning: could not read epochs: {e}")

    if args.all:
        if nightly.empty:
            print("No nightly_metrics.csv found.")
            return
        for _, row in nightly[["user_id", "night_date"]].drop_duplicates().iterrows():
            build_night_report(
                row["user_id"], row["night_date"],
                epochs, events, nightly, out,
            )
    elif args.user and args.date:
        build_night_report(args.user, args.date, epochs, events, nightly, out)
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
