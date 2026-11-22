"""
Tests for Analytical Scoring Engine
"""

import sys
from pathlib import Path
import pytest
import pandas as pd

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))
sys.path.insert(0, str(PROJECT_ROOT / "src"))

from analytics.scoring_engine import (
    compute_time_exposure_score,
    compute_ai_suitability_score,
    compute_physical_intensity_score,
    compute_regulatory_penalty_score,
    score_tasks,
    ScoringWeights
)


def test_time_exposure_score_bounds():
    assert compute_time_exposure_score(0) == 0.0
    assert compute_time_exposure_score(-50) == 0.0
    assert compute_time_exposure_score(1) == 0.0
    assert compute_time_exposure_score(500) == 100.0
    assert compute_time_exposure_score(2000) == 100.0
    # Log monotonic progression
    s10 = compute_time_exposure_score(10)
    s100 = compute_time_exposure_score(100)
    assert s10 < s100 < 100.0


def test_physical_intensity_score_gating():
    w = ScoringWeights()
    digital_task = pd.Series({"medium_materials": 0.0, "physical_deployment": 0.0})
    wetlab_task = pd.Series({"medium_materials": 90.0, "physical_deployment": 4.5})

    s_digital = compute_physical_intensity_score(digital_task, w)
    s_wetlab = compute_physical_intensity_score(wetlab_task, w)

    assert s_digital == 0.0
    assert s_wetlab > 80.0


def test_score_tasks_end_to_end():
    sample_tasks = pd.DataFrame([
        {
            "task_id": "t_001",
            "task": "Synthesize theoretical literature",
            "hours_per_year": 120.0,
            "medium_information": 95.0,
            "cognitive_complexity": 3.2,
            "medium_materials": 0.0,
            "physical_deployment": 0.0,
            "regulatory_restriction": 0.0,
            "classification": "Supplementary"
        },
        {
            "task_id": "t_002",
            "task": "Perform centrifuge extraction of biological tissue",
            "hours_per_year": 80.0,
            "medium_information": 10.0,
            "cognitive_complexity": 2.0,
            "medium_materials": 95.0,
            "physical_deployment": 4.0,
            "regulatory_restriction": 4.0,
            "classification": "Core"
        }
    ])

    scored = score_tasks(sample_tasks)
    assert len(scored) == 2
    assert "capacity_opportunity_score" in scored.columns
    assert "priority_tier" in scored.columns
    assert "ai_fit_category" in scored.columns

    # Theoretical task should have higher opportunity than wet-lab centrifuge extraction
    opp_digital = scored.loc[scored["task_id"] == "t_001", "capacity_opportunity_score"].values[0]
    opp_wetlab = scored.loc[scored["task_id"] == "t_002", "capacity_opportunity_score"].values[0]
    assert opp_digital > opp_wetlab

    # Wet-lab centrifuge task should be Constrained due to physical materials
    cat_wetlab = scored.loc[scored["task_id"] == "t_002", "ai_fit_category"].values[0]
    assert cat_wetlab == "Constrained"
