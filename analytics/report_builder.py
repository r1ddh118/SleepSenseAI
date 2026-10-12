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
    h2 { border-bottom: 1px solid #d9dee6; padding-bottom: 4px; margin-top: 24px; }
    table { width: 100%; margin-top: 8px; border: 1px solid #d9dee6; }
    th, td { border: 1px solid #d9dee6; padding: 6px 8px; text-align: left; vertical-align: top; }
    th { background: #f4f6f8; font-weight: bold; width: 35%; }
    .disclaimer { border: 1px solid #c9a227; background: #fff8db; padding: 12px; margin-top: 12px; }
    .muted { color: #667085; }
    .badge { display: inline-block; padding: 2px 8px; border-radius: 4px; background: #eef2f6; }
  </style>
</head>
<body>
  <h1>SleepSense AI Clinical Report</h1>
  <p class="muted">Generated at {{ report.generated_at }} | Session: {{ report.session_id }}</p>

  <h2>Patient Info</h2>
  {{ render_mapping(report.sections.patient_info) }}

  <h2>Sleep Summary</h2>
  {{ render_mapping(report.sections.sleep_summary) }}

  {% if report.sections.eda_assessment %}
  <h2>Electrodermal Activity (EDA) & Autonomic Tone</h2>
  {{ render_mapping(report.sections.eda_assessment) }}
  {% endif %}

  {% if report.sections.sensor_biometrics %}
  <h2>Sensor Biometrics & Events</h2>
  {{ render_mapping(report.sections.sensor_biometrics) }}
  {% endif %}

  <h2>Longitudinal Trend</h2>
  {{ render_mapping(report.sections.longitudinal_trend) }}

  <h2>Risk Assessment</h2>
  {{ render_mapping(report.sections.risk_assessment) }}

  <h2>Lifestyle</h2>
  {{ render_mapping(report.sections.lifestyle) }}

  {% if report.sections.doctor_clinical_notes %}
  <h2>Doctor Clinical Notes & Observations</h2>
  {{ render_mapping(report.sections.doctor_clinical_notes) }}
  {% endif %}

  {% if report.sections.data_quality %}
  <h2>Signal & Data Quality Assessment</h2>
  {{ render_mapping(report.sections.data_quality) }}
  {% endif %}

  {% if report.sections.events %}
  <h2>Physiological & Cardiorespiratory Events</h2>
  {{ render_mapping(report.sections.events) }}
  {% endif %}

  {% if report.sections.stages %}
  <h2>Sleep Stage Distribution Breakdown</h2>
  {{ render_mapping(report.sections.stages) }}
  {% endif %}

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
    if not mapping:
        return Markup('<p class="muted">No data available.</p>')
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
    eda_assessment: Mapping[str, Any] | None = None,
    sensor_biometrics: Mapping[str, Any] | None = None,
    extra_sections: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """Build a complete doctor report payload with all required sections and optional EDA / sensor sections."""
    sections: dict[str, Any] = {
        "patient_info": dict(patient_info),
        "sleep_summary": dict(sleep_summary),
        "longitudinal_trend": dict(longitudinal_trend),
        "risk_assessment": dict(risk_assessment),
        "lifestyle": dict(lifestyle),
        "recommendations": [dict(item) for item in recommendations],
        "alerts": [dict(item) for item in alerts],
        "model_info": dict(model_info),
        "disclaimer": {"text": MEDICAL_DISCLAIMER},
    }
    if eda_assessment is not None:
        sections["eda_assessment"] = dict(eda_assessment)
    if sensor_biometrics is not None:
        sections["sensor_biometrics"] = dict(sensor_biometrics)
    if extra_sections is not None:
        for k, v in extra_sections.items():
            if isinstance(v, Mapping):
                sections[k] = dict(v)
            elif isinstance(v, list):
                sections[k] = list(v)
            else:
                sections[k] = v

    return {
        "report_type": "doctor_sleep_report",
        "session_id": session_id,
        "generated_at": generated_at,
        "sections": sections,
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
    # Output required sections in order, plus any extra sections (like eda_assessment, sensor_biometrics)
    rendered_sections = list(REQUIRED_SECTIONS)
    for extra in ["eda_assessment", "sensor_biometrics"]:
        if extra in sections and extra not in rendered_sections:
            rendered_sections.insert(3, extra)

    for section_name in rendered_sections:
        section = sections.get(section_name)
        if section is None:
            continue
        if isinstance(section, Mapping):
            for key, value in section.items():
                writer.writerow([section_name, key, _format_value(value)])
        elif isinstance(section, list):
            for idx, item in enumerate(section, start=1):
                writer.writerow([section_name, str(idx), _format_value(item)])
        else:
            writer.writerow([section_name, "", _format_value(section)])
    return output.getvalue()


def render_report_pdf(report: Mapping[str, Any]) -> bytes:
    """Render full report as PDF from HTML with graceful fallbacks.
    
    Tries:
    1. xhtml2pdf (pisa)
    2. weasyprint
    3. reportlab fallback
    """
    html_content = render_report_html(report)

    # 1. Try xhtml2pdf
    try:
        from xhtml2pdf import pisa
        from io import BytesIO

        pdf_buffer = BytesIO()
        pisa_status = pisa.CreatePDF(html_content, dest=pdf_buffer)
        if not pisa_status.err:
            pdf_bytes = pdf_buffer.getvalue()
            if len(pdf_bytes) > 0:
                return pdf_bytes
    except Exception:
        pass

    # 2. Try weasyprint
    try:
        import weasyprint

        return weasyprint.HTML(string=html_content).write_pdf()
    except Exception:
        pass

    # 3. ReportLab fallback
    try:
        from reportlab.lib.pagesizes import letter
        from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
        from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle
        from reportlab.lib import colors
        from io import BytesIO

        pdf_buffer = BytesIO()
        doc = SimpleDocTemplate(pdf_buffer, pagesize=letter, leftMargin=36, rightMargin=36, topMargin=36, bottomMargin=36)
        styles = getSampleStyleSheet()
        story = []

        title_style = ParagraphStyle('RptTitle', parent=styles['Heading1'], fontSize=16, leading=20, textColor=colors.HexColor('#0F172A'))
        h2_style = ParagraphStyle('RptH2', parent=styles['Heading2'], fontSize=12, leading=15, textColor=colors.HexColor('#0284C7'))
        body_style = ParagraphStyle('RptBody', parent=styles['Normal'], fontSize=8.5, leading=11, textColor=colors.HexColor('#334155'))

        story.append(Paragraph(f"SleepSense AI Clinical Report - {report.get('session_id')}", title_style))
        story.append(Paragraph(f"Generated at: {report.get('generated_at')}", body_style))
        story.append(Spacer(1, 10))

        sections = report.get("sections", {})
        for sec_name, sec_val in sections.items():
            story.append(Paragraph(sec_name.replace("_", " ").title(), h2_style))
            if isinstance(sec_val, Mapping):
                table_data = [[Paragraph(f"<b>{k}</b>", body_style), Paragraph(_format_value(v), body_style)] for k, v in sec_val.items()]
                if table_data:
                    t = Table(table_data, colWidths=[180, 360])
                    t.setStyle(TableStyle([
                        ('BACKGROUND', (0, 0), (0, -1), colors.HexColor('#F8FAFC')),
                        ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor('#CBD5E1')),
                        ('PADDING', (0, 0), (-1, -1), 3),
                    ]))
                    story.append(t)
            elif isinstance(sec_val, list):
                for item in sec_val:
                    story.append(Paragraph(f"• {_format_value(item)}", body_style))
            else:
                story.append(Paragraph(_format_value(sec_val), body_style))
            story.append(Spacer(1, 8))

        doc.build(story)
        return pdf_buffer.getvalue()
    except Exception as exc:
        raise RuntimeError(f"All PDF generation engines failed: {str(exc)}") from exc

