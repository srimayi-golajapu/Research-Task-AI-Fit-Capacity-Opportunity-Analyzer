"""
Tests for Data Ingestion Module
"""

import sys
from pathlib import Path
import pytest
import pandas as pd

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))
sys.path.insert(0, str(PROJECT_ROOT / "src"))

from ingestion.scinet_loader import load_scinet_data, load_organization_data, SCINET_FILES


def test_load_scinet_data_success():
    data = load_scinet_data()
    assert isinstance(data, dict)
    assert set(data.keys()) == set(SCINET_FILES.keys())

    # Verify key dataset row counts
    assert len(data["tasks"]) == 7262
    assert len(data["task_dimensions"]) == 7262
    assert len(data["task_hours_per_year"]) == 26803
    assert len(data["task_ratings"]) == 26803
    assert len(data["task_time"]) == 18283
    assert len(data["task_activity_assignments"]) == 6956


def test_load_scinet_data_missing_dir(tmp_path):
    with pytest.raises(FileNotFoundError):
        load_scinet_data(data_dir=tmp_path / "non_existent_folder")


def test_load_organization_data_success():
    org_path = PROJECT_ROOT / "data/synthetic/organization_task_usage.csv"
    if org_path.exists():
        df = load_organization_data(org_path)
        assert isinstance(df, pd.DataFrame)
        assert len(df) > 0
        expected_cols = ["department", "role", "task", "fte_count", "annual_task_hours"]
        for col in expected_cols:
            assert col in df.columns


def test_load_organization_data_missing_file(tmp_path):
    with pytest.raises(FileNotFoundError):
        load_organization_data(tmp_path / "missing_org_file.csv")
