"""
Tests for Data Normalization Module
"""

import sys
from pathlib import Path
import pytest
import pandas as pd

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))
sys.path.insert(0, str(PROJECT_ROOT / "src"))

from ingestion.scinet_loader import load_scinet_data
from ingestion.normalize import (
    generate_task_id,
    normalize_scinet_datasets,
    HIERARCHY_COLUMNS
)


def test_generate_task_id_deterministic():
    row1 = {"task": "Analyze data", "level": "subfield", "domain": "Life Sciences", "field": "Genomics", "subfield": "DNA"}
    row2 = {"task": "Analyze data", "level": "subfield", "domain": "Life Sciences", "field": "Genomics", "subfield": "DNA"}
    row3 = {"task": "Analyze data", "level": "domain", "domain": "Life Sciences", "field": None, "subfield": None}

    id1 = generate_task_id(row1)
    id2 = generate_task_id(row2)
    id3 = generate_task_id(row3)

    assert id1 == id2, "Identical hierarchy rows must generate identical task_id"
    assert id1 != id3, "Different hierarchy levels must generate distinct task_ids"
    assert id1.startswith("t_")
    assert len(id1) == 16


def test_normalize_scinet_preserves_records_and_universal_tasks():
    raw_data = load_scinet_data()
    norm = normalize_scinet_datasets(raw_data)

    assert "tasks" in norm
    assert "task_dimensions" in norm
    assert "task_hours_per_year" in norm
    assert "task_ratings" in norm
    assert "task_time" in norm
    assert "task_activity_assignments" in norm
    assert "tasks_master" in norm

    # Row count preservation
    assert len(norm["tasks"]) == 7262
    assert len(norm["task_dimensions"]) == 7262
    assert len(norm["task_hours_per_year"]) == 26803
    assert len(norm["task_ratings"]) == 26803
    assert len(norm["task_time"]) == 18283
    assert len(norm["task_activity_assignments"]) == 6956

    # Verify 1,020 universal tasks preservation in task_time
    time_df = norm["task_time"]
    assert "is_universal_unmatched" in time_df.columns
    unmatched_count = time_df["is_universal_unmatched"].sum()
    assert unmatched_count == 1020, f"Expected 1,020 unmatched universal tasks, found {unmatched_count}"

    # Verify tasks_master includes both the 26,803 domain/field/subfield tasks AND the 1,020 universal tasks
    assert len(norm["tasks_master"]) == 26803 + 1020
