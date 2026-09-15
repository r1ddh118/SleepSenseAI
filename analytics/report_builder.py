"""Report assembler — JSON, CSV, and HTML (Jinja2) report generation.

All reports include the mandatory medical disclaimer verbatim.
Sections: patient info, sleep summary, longitudinal trend, risk assessment,
          lifestyle, recommendations, alerts, model info, disclaimer.
"""

from __future__ import annotations

import csv
import io
import json
import os
from datetime import datetime
from pathlib import Path
from typing import Any

try:
    from jinja2 import Environment, FileSystemLoader, select_autoescape
    _JINJA2_AVAILABLE = True
except ImportError:
    _JINJA2_AVAILABLE = False

MEDICAL_DISCLAIMER = (
    "This report is an analytical screening tool and does not constitute a medical diagnosis. "
    "Clinical interpretation should be performed by a qualified healthcare professional."
)

_TEMPLATE_DIR = Path(__file__).resolve().parent.parent / "templates"


def _build_report_data(
    session_id: str,
    user_id: str,
    sleep_metrics: dict[str, Any],
    risk_assessment: dict[str, Any] | None = None,
    recommendations: list[dict] | None = None,
    longitudinal: dict[str, Any] | None = None,
    alerts: list[dict] | None = None,
    patient_info: dict[str, Any] | None = None,
    period_start: str | None = None,
    period_end: str | None = None,
) -> dict[str, Any]:
    """Assemble the full report data structure."""
    return {
        "meta": {
            "report_generated_at": datetime.utcnow().isoformat() + "Z",
            "session_id": session_id,
            "user_id": user_id,
            "period_start": period_start,
            "period_end": period_end or sleep_metrics.get("date"),
            "report_type": "SleepSense AI Analytical Screening Report",
        },
        "patient_info": patient_info or {"user_id": user_id},
        "sleep_summary": {
            "sleep_score": sleep_metrics.get("sleep_score"),
            "sleep_category": sleep_metrics.get("sleep_category"),
            "sleep_efficiency": sleep_metrics.get("sleep_efficiency"),
            "sleep_duration_hours": sleep_metrics.get("sleep_duration_hours"),
            "n3_fraction": sleep_metrics.get("n3_fraction"),
            "rem_fraction": sleep_metrics.get("rem_fraction"),
            "wake_fraction": sleep_metrics.get("wake_fraction"),
            "avg_hr": sleep_metrics.get("avg_hr"),
            "hr_std": sleep_metrics.get("hr_std"),
            "avg_movement": sleep_metrics.get("avg_movement"),
            "event_rate": sleep_metrics.get("event_rate"),
            "awakenings": sleep_metrics.get("awakenings"),
            "score_disclaimer": (
                "Sleep score is an academic analytics metric only — NOT clinically validated."
            ),
        },
        "longitudinal_trend": longitudinal or {
            "sleep_score_7d_avg": sleep_metrics.get("sleep_score_7d_avg"),
            "sleep_score_14d_avg": sleep_metrics.get("sleep_score_14d_avg"),
            "duration_7d_avg": sleep_metrics.get("duration_7d_avg"),
            "efficiency_7d_avg": sleep_metrics.get("efficiency_7d_avg"),
        },
        "risk_assessment": risk_assessment or {},
        "lifestyle": {
            "caffeine_mg": sleep_metrics.get("caffeine"),
            "screen_time_min": sleep_metrics.get("screen_time"),
            "exercise_min": sleep_metrics.get("exercise_minutes"),
            "stress_level": sleep_metrics.get("stress_level"),
            "nap_minutes": sleep_metrics.get("nap_minutes"),
        },
        "recommendations": recommendations or [],
        "alerts": alerts or [],
        "model_info": {
            "scoring_model": "SleepSense AI Rule-Based Analytics (v2.0, PySpark)",
            "evaluation_note": (
                "Any ML model metrics reported use a user-level train/test split "
                "(no user appears in both training and test sets). "
                "This methodology is described explicitly to prevent data-leakage inflation."
            ),
            "not_clinically_validated": True,
        },
        "disclaimer": MEDICAL_DISCLAIMER,
    }


def build_json_report(
    session_id: str,
    user_id: str,
    sleep_metrics: dict[str, Any],
    **kwargs,
) -> str:
    """Return a JSON string report."""
    data = _build_report_data(session_id, user_id, sleep_metrics, **kwargs)
    return json.dumps(data, indent=2, default=str)


def build_csv_report(
    session_id: str,
    user_id: str,
    sleep_metrics: dict[str, Any],
    **kwargs,
) -> str:
    """Return a CSV string report (flat key-value format)."""
    data = _build_report_data(session_id, user_id, sleep_metrics, **kwargs)
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(["section", "field", "value"])

    def flatten(section: str, d: Any, prefix: str = ""):
        if isinstance(d, dict):
            for k, v in d.items():
                flatten(section, v, f"{prefix}{k}.")
        elif isinstance(d, list):
            writer.writerow([section, prefix.rstrip("."), json.dumps(d, default=str)])
        else:
            writer.writerow([section, prefix.rstrip("."), str(d) if d is not None else ""])

    for section, content in data.items():
        flatten(section, content)

    writer.writerow(["disclaimer", "text", MEDICAL_DISCLAIMER])
    return output.getvalue()


def build_html_report(
    session_id: str,
    user_id: str,
    sleep_metrics: dict[str, Any],
    **kwargs,
) -> str:
    """Return an HTML string report using Jinja2 template (or fallback HTML)."""
    data = _build_report_data(session_id, user_id, sleep_metrics, **kwargs)

    if _JINJA2_AVAILABLE and (_TEMPLATE_DIR / "report.html.j2").exists():
        env = Environment(
            loader=FileSystemLoader(str(_TEMPLATE_DIR)),
            autoescape=select_autoescape(["html"]),
        )
        template = env.get_template("report.html.j2")
        return template.render(**data)

    # Fallback: minimal inline HTML
    return _fallback_html(data)


def _fallback_html(data: dict[str, Any]) -> str:
    ss = data.get("sleep_summary", {})
    lt = data.get("longitudinal_trend", {})
    ra = data.get("risk_assessment", {})
    recs = data.get("recommendations", [])

    rows = ""
    for k, v in ss.items():
        if v is not None:
            rows += f"<tr><td><b>{k}</b></td><td>{v}</td></tr>"

    risk_rows = ""
    for flag in ra.get("risk_flags", []):
        risk_rows += (
            f"<tr><td>{flag.get('label','')}</td>"
            f"<td><b>{flag.get('risk','')}</b></td>"
            f"<td>{'; '.join(flag.get('reasons',[]))}</td></tr>"
        )

    rec_rows = ""
    for r in recs:
        rec_rows += f"<tr><td>{r.get('area','')}</td><td>{r.get('message','')}</td></tr>"

    return f"""<!DOCTYPE html>
<html lang="en">
<head><meta charset="UTF-8"><title>SleepSense AI Report — {data['meta']['session_id']}</title>
<style>
  body{{font-family:system-ui,sans-serif;max-width:900px;margin:2rem auto;color:#1a1a2e}}
  h1{{color:#16213e}} h2{{color:#0f3460;border-bottom:2px solid #e94560;padding-bottom:4px}}
  table{{border-collapse:collapse;width:100%;margin:1rem 0}}
  th,td{{border:1px solid #ddd;padding:8px 12px;text-align:left}}
  th{{background:#16213e;color:#fff}} tr:nth-child(even){{background:#f8f9fa}}
  .disclaimer{{background:#fff3cd;border:1px solid #ffc107;padding:1rem;border-radius:6px;margin:1.5rem 0}}
  .score-box{{font-size:3rem;font-weight:700;color:#e94560;text-align:center;padding:1rem}}
  .badge{{display:inline-block;padding:2px 10px;border-radius:12px;font-size:0.85rem;font-weight:600}}
  .HIGH{{background:#dc3545;color:#fff}} .MODERATE{{background:#fd7e14;color:#fff}} .LOW{{background:#198754;color:#fff}}
</style></head>
<body>
<h1>🌙 SleepSense AI Screening Report</h1>
<p><b>Session:</b> {data['meta']['session_id']} &nbsp;|&nbsp;
   <b>Patient:</b> {data['meta']['user_id']} &nbsp;|&nbsp;
   <b>Generated:</b> {data['meta']['report_generated_at']}</p>

<div class="disclaimer">⚠️ <b>DISCLAIMER:</b> {data['disclaimer']}</div>

<h2>Sleep Summary</h2>
<div class="score-box">{ss.get('sleep_score', 'N/A')} <span style="font-size:1.2rem;color:#555">{ss.get('sleep_category','')}</span></div>
<p><i>{ss.get('score_disclaimer','')}</i></p>
<table><tr><th>Metric</th><th>Value</th></tr>{rows}</table>

<h2>Longitudinal Trend (7-day)</h2>
<table><tr><th>Metric</th><th>7-day Average</th></tr>
<tr><td>Sleep Score</td><td>{lt.get('sleep_score_7d_avg','N/A')}</td></tr>
<tr><td>Duration (h)</td><td>{lt.get('duration_7d_avg','N/A')}</td></tr>
<tr><td>Efficiency</td><td>{lt.get('efficiency_7d_avg','N/A')}</td></tr>
</table>

<h2>Risk Screening Indicators</h2>
<p><b>Overall Risk Level:</b> <span class="badge {ra.get('overall_risk_level','LOW')}">{ra.get('overall_risk_level','LOW')}</span></p>
<table><tr><th>Category</th><th>Risk</th><th>Evidence</th></tr>{risk_rows}</table>

<h2>Recommendations</h2>
<table><tr><th>Area</th><th>Recommendation</th></tr>{rec_rows}</table>

<h2>Model Information</h2>
<p>{data['model_info']['evaluation_note']}</p>

<div class="disclaimer">⚠️ {data['disclaimer']}</div>
</body></html>"""


def save_report(
    format: str,
    content: str,
    output_dir: str | Path,
    session_id: str,
) -> str:
    """Write report to disk and return the file path."""
    ext_map = {"json": ".json", "csv": ".csv", "html": ".html"}
    ext = ext_map.get(format.lower(), ".txt")
    out = Path(output_dir)
    out.mkdir(parents=True, exist_ok=True)
    filename = f"report_{session_id}_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}{ext}"
    path = out / filename
    path.write_text(content, encoding="utf-8")
    return str(path)
