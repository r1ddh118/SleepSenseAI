from __future__ import annotations

import csv
import json
from io import StringIO
from typing import Any, Mapping

from jinja2 import Environment, select_autoescape
from markupsafe import Markup


MEDICAL_DISCLAIMER = (
    "SleepSense AI reports are academic analytics summaries only; they are not clinically validated, "
    "are not a medical diagnosis, and must not be used to diagnose or rule out any medical condition."
)

REQUIRED_SECTIONS = [
    "patient_info",
    "sleep_summary",
    "longitudinal_trend",
    "risk_assessment",
    "lifestyle",
    "recommendations",
    "alerts",
    "model_info",
    "disclaimer",
]

HTML_TEMPLATE = """
<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <title>SleepSense AI Doctor Report - {{ report.session_id }}</title>
  <style>
    body { font-family: Arial, sans-serif; color: #18202a; margin: 32px; line-height: 1.45; }
    h1 { margin-bottom: 4px; }
    h2 { border-bottom: 1px solid #d9dee6; padding-bottom: 4px; margin-top: 28px; }
    table { border-collapse: collapse; width: 100%; margin-top: 8px; }
    th, td { border: 1px solid #d9dee6; padding: 8px; text-align: left; vertical-align: top; }
    th { background: #f4f6f8; }
    .disclaimer { border: 1px solid #c9a227; background: #fff8db; padding: 12px; }
    .muted { color: #667085; }
    .badge { display: inline-block; padding: 2px 8px; border-radius: 4px; background: #eef2f6; }
  </style>
</head>
<body>
  <h1>SleepSense AI Doctor Report</h1>
  <p class="muted">Generated at {{ report.generated_at }}</p>

  <h2>Patient Info</h2>
  {{ render_mapping(report.sections.patient_info) }}

  <h2>Sleep Summary</h2>
  {{ render_mapping(report.sections.sleep_summary) }}

  <h2>Longitudinal Trend</h2>
  {{ render_mapping(report.sections.longitudinal_trend) }}

  <h2>Risk Assessment</h2>
  {{ render_mapping(report.sections.risk_assessment) }}

  <h2>Lifestyle</h2>
  {{ render_mapping(report.sections.lifestyle) }}

  <h2>Recommendations</h2>
  {{ render_list(report.sections.recommendations) }}

  <h2>Alerts</h2>
  {{ render_list(report.sections.alerts) }}

  <h2>Model Info</h2>
  {{ render_mapping(report.sections.model_info) }}

  <h2>Disclaimer</h2>
  <p class="disclaimer">{{ report.sections.disclaimer.text }}</p>
</body>
</html>
"""


def _json_default(value: Any) -> str:
    return str(value)


def _format_value(value: Any) -> str:
    if value is None:
        return "Not available"
    if isinstance(value, (dict, list)):
        return json.dumps(value, default=_json_default, sort_keys=True)
    return str(value)


def _render_mapping(mapping: Mapping[str, Any]) -> str:
    rows = []
    for key, value in mapping.items():
        rows.append(f"<tr><th>{key}</th><td>{_format_value(value)}</td></tr>")
    return Markup("<table>" + "".join(rows) + "</table>")


def _render_list(items: list[Any]) -> str:
    if not items:
        return Markup('<p class="muted">No items available.</p>')
    if all(isinstance(item, Mapping) for item in items):
        keys: list[str] = []
        for item in items:
            for key in item.keys():
                if key not in keys:
                    keys.append(str(key))
        header = "".join(f"<th>{key}</th>" for key in keys)
        body = []
        for item in items:
            body.append("<tr>" + "".join(f"<td>{_format_value(item.get(key))}</td>" for key in keys) + "</tr>")
        return Markup(f"<table><thead><tr>{header}</tr></thead><tbody>{''.join(body)}</tbody></table>")
    return Markup("<ul>" + "".join(f"<li>{_format_value(item)}</li>" for item in items) + "</ul>")


def build_report_payload(
    *,
    session_id: str,
    generated_at: str,
    patient_info: Mapping[str, Any],
    sleep_summary: Mapping[str, Any],
    longitudinal_trend: Mapping[str, Any],
    risk_assessment: Mapping[str, Any],
    lifestyle: Mapping[str, Any],
    recommendations: list[Mapping[str, Any]],
    alerts: list[Mapping[str, Any]],
    model_info: Mapping[str, Any],
) -> dict[str, Any]:
    """Build a complete doctor report payload with all required sections."""
    return {
        "report_type": "doctor_sleep_report",
        "session_id": session_id,
        "generated_at": generated_at,
        "sections": {
            "patient_info": dict(patient_info),
            "sleep_summary": dict(sleep_summary),
            "longitudinal_trend": dict(longitudinal_trend),
            "risk_assessment": dict(risk_assessment),
            "lifestyle": dict(lifestyle),
            "recommendations": [dict(item) for item in recommendations],
            "alerts": [dict(item) for item in alerts],
            "model_info": dict(model_info),
            "disclaimer": {"text": MEDICAL_DISCLAIMER},
        },
    }


def render_report_html(report: Mapping[str, Any]) -> str:
    env = Environment(autoescape=select_autoescape(["html", "xml"]))
    env.globals["render_mapping"] = _render_mapping
    env.globals["render_list"] = _render_list
    template = env.from_string(HTML_TEMPLATE)
    return template.render(report=report)


def render_report_csv(report: Mapping[str, Any]) -> str:
    output = StringIO()
    writer = csv.writer(output)
    writer.writerow(["section", "field", "value"])

    sections = report.get("sections", {})
    for section_name in REQUIRED_SECTIONS:
        section = sections.get(section_name)
        if isinstance(section, Mapping):
            for key, value in section.items():
                writer.writerow([section_name, key, _format_value(value)])
        elif isinstance(section, list):
            for idx, item in enumerate(section, start=1):
                writer.writerow([section_name, str(idx), _format_value(item)])
        else:
            writer.writerow([section_name, "", _format_value(section)])
    return output.getvalue()
