from __future__ import annotations

import csv
from io import StringIO

from analytics.report_builder import (
    MEDICAL_DISCLAIMER,
    REQUIRED_SECTIONS,
    build_report_payload,
    render_report_csv,
    render_report_html,
)


def _sample_report():
    return build_report_payload(
        session_id="S001",
        generated_at="2026-01-01T00:00:00",
        patient_info={"patient_id": 1, "session_id": "S001"},
        sleep_summary={"sleep_score": 82.1, "sleep_efficiency": 0.88},
        longitudinal_trend={"sleep_score_7d_avg": 79.4},
        risk_assessment={"risk_level": "LOW", "risk_flags": []},
        lifestyle={"screen_time": 45, "stress_level": 3},
        recommendations=[{"area": "screen_time", "message": "screen_time was high"}],
        alerts=[{"severity": "HIGH", "reason": "Persistent HIGH risk"}],
        model_info={"model_name": "rules"},
    )


def test_report_payload_has_all_required_sections_and_disclaimer():
    report = _sample_report()

    assert list(report["sections"].keys()) == REQUIRED_SECTIONS
    assert report["sections"]["disclaimer"]["text"] == MEDICAL_DISCLAIMER


def test_html_report_contains_all_section_headings_and_disclaimer():
    html = render_report_html(_sample_report())

    for heading in [
        "Patient Info",
        "Sleep Summary",
        "Longitudinal Trend",
        "Risk Assessment",
        "Lifestyle",
        "Recommendations",
        "Alerts",
        "Model Info",
        "Disclaimer",
    ]:
        assert heading in html
    assert MEDICAL_DISCLAIMER in html


def test_csv_report_contains_sections():
    rows = list(csv.reader(StringIO(render_report_csv(_sample_report()))))
    sections = {row[0] for row in rows[1:]}

    assert set(REQUIRED_SECTIONS).issubset(sections)
