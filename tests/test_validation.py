"""
Tests for Data Validation Module
"""

import sys
from pathlib import Path
import pytest
import pandas as pd

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))
sys.path.insert(0, str(PROJECT_ROOT / "src"))

from ingestion.scinet_loader import load_scinet_data
from ingestion.validation import run_full_validation, ValidationReport


def test_full_validation_on_raw_scinet():
    data = load_scinet_data()
    report = run_full_validation(data)
    assert isinstance(report, ValidationReport)
    assert report.is_valid is True
    assert len(report.errors) == 0

    # Check metrics
    assert report.metrics.get("tasks_count") == 7262
    assert report.metrics.get("dimensions_count") == 7262
    assert report.metrics.get("hours_count") == 26803
    assert report.metrics.get("ratings_count") == 26803
    assert report.metrics.get("task_time_universal_count") == 1020


def test_validation_detects_missing_columns():
    data = load_scinet_data()
    corrupt_data = data.copy()
    # Remove mandatory column from tasks
    corrupt_data["tasks"] = corrupt_data["tasks"].drop(columns=["task"])

    report = run_full_validation(corrupt_data)
    assert report.is_valid is False
    assert any("missing required columns" in err.lower() for err in report.errors)


def test_validation_detects_out_of_range_ratings():
    data = load_scinet_data()
    corrupt_data = data.copy()
    # Add an invalid importance score
    corrupt_ratings = corrupt_data["task_ratings"].copy()
    corrupt_ratings.loc[0, "importance"] = 99.0
    corrupt_data["task_ratings"] = corrupt_ratings

    report = run_full_validation(corrupt_data)
    assert report.is_valid is False
    assert any("importance outside" in err.lower() for err in report.errors)
