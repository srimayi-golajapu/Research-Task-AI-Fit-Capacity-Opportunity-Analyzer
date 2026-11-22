"""
Tests for Reporting and Decision Brief Export Module
"""

import sys
from pathlib import Path
import pytest

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))
sys.path.insert(0, str(PROJECT_ROOT / "src"))
sys.path.insert(0, str(PROJECT_ROOT / "database"))

from reporting.report_generator import generate_executive_decision_brief, export_all_reports


def test_generate_decision_brief_content():
    brief = generate_executive_decision_brief()
    assert isinstance(brief, str)
    assert "# Executive Decision Brief" in brief
    assert "Conservative" in brief
    assert "Moderate" in brief
    assert "Optimistic" in brief
    assert "FTE" in brief


def test_export_all_reports(tmp_path):
    reports = export_all_reports(output_dir=tmp_path)
    assert "executive_brief_markdown" in reports
    assert "task_scoring_csv" in reports
    assert "scenario_matrix_csv" in reports
    assert "domain_summary_csv" in reports

    for name, path in reports.items():
        assert path.exists()
        assert path.stat().st_size > 0
