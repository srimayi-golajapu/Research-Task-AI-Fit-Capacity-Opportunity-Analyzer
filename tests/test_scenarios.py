"""
Tests for Scenario Simulation Engine
"""

import sys
from pathlib import Path
import pytest
import pandas as pd

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))
sys.path.insert(0, str(PROJECT_ROOT / "src"))

from simulation.scenario_engine import (
    DEFAULT_SCENARIOS,
    run_scenario_simulation,
    generate_scenario_comparison_summary
)


def test_scenario_simulation_monotonicity():
    sample_tasks = pd.DataFrame([
        {
            "task_id": "t_001",
            "department": "Department of Biosciences",
            "role": "Postdoctoral Fellow",
            "annual_task_hours": 1000.0,
            "feasibility_score": 80.0
        }
    ])

    sim_df = run_scenario_simulation(sample_tasks)
    assert len(sim_df) == 3

    cons = sim_df.loc[sim_df["scenario_id"] == "SCEN_CONSERVATIVE", "potential_hours_released"].values[0]
    mod = sim_df.loc[sim_df["scenario_id"] == "SCEN_MODERATE", "potential_hours_released"].values[0]
    opt = sim_df.loc[sim_df["scenario_id"] == "SCEN_OPTIMISTIC", "potential_hours_released"].values[0]

    # Monotonicity test: Optimistic > Moderate > Conservative
    assert cons < mod < opt
    assert cons > 0.0

    # FTE check: Hours / 1800
    fte_mod = sim_df.loc[sim_df["scenario_id"] == "SCEN_MODERATE", "fte_capacity_equivalent"].values[0]
    assert abs(fte_mod - (mod / 1800.0)) < 1e-3


def test_scenario_comparison_summary_structure():
    sample_tasks = pd.DataFrame([
        {
            "task_id": "t_001",
            "department": "Biosciences",
            "role": "Postdoc",
            "annual_task_hours": 500.0,
            "feasibility_score": 60.0
        },
        {
            "task_id": "t_002",
            "department": "Engineering",
            "role": "Analyst",
            "annual_task_hours": 800.0,
            "feasibility_score": 75.0
        }
    ])

    sim_df = run_scenario_simulation(sample_tasks)
    summary = generate_scenario_comparison_summary(sim_df)

    assert len(summary) == 3
    assert "total_baseline_hours" in summary.columns
    assert "total_hours_released" in summary.columns
    assert "total_fte_equivalent" in summary.columns
    assert "overall_hours_released_pct" in summary.columns
