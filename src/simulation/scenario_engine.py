"""
Scenario Modelling & Capacity Release Simulation Engine
========================================================
Implements configurable scenario analysis (Conservative, Moderate, Optimistic)
to model organizational capacity release opportunities under varying AI adoption
and efficiency assumptions.

Key Principles:
- Transparent formulas: explicitly accounts for adoption rate, gross efficiency,
  verification friction overhead, and physical/regulatory gating.
- Never presents capacity release as guaranteed productivity.
- Calculates both annual hours released and Full-Time Equivalent (FTE) capacity equivalents.
- Stores outputs directly into DuckDB scenario_results table.
"""

from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Union
import numpy as np
import pandas as pd


@dataclass
class ScenarioParameters:
    """Configurable assumptions for an AI adoption scenario."""
    scenario_id: str
    scenario_name: str
    description: str
    # Parameters
    adoption_rate: float            # Fraction of workforce adopting (0.0 to 1.0)
    gross_efficiency_gain: float    # Theoretical time reduction on augmented tasks (0.0 to 1.0)
    verification_overhead: float    # Fraction of savings lost to review/prompting (0.0 to 1.0)
    annual_hours_per_fte: float = 1800.0  # Standard annual working hours per full-time researcher


DEFAULT_SCENARIOS = {
    "conservative": ScenarioParameters(
        scenario_id="SCEN_CONSERVATIVE",
        scenario_name="Conservative Scenario",
        description="Cautious rollout, 35% adoption, 20% gross efficiency, high verification oversight (30%).",
        adoption_rate=0.35,
        gross_efficiency_gain=0.20,
        verification_overhead=0.30,
        annual_hours_per_fte=1800.0
    ),
    "moderate": ScenarioParameters(
        scenario_id="SCEN_MODERATE",
        scenario_name="Moderate Scenario",
        description="Institutional standard, 60% adoption, 35% gross efficiency, moderate oversight (20%).",
        adoption_rate=0.60,
        gross_efficiency_gain=0.35,
        verification_overhead=0.20,
        annual_hours_per_fte=1800.0
    ),
    "optimistic": ScenarioParameters(
        scenario_id="SCEN_OPTIMISTIC",
        scenario_name="Optimistic Scenario",
        description="Pervasive adoption, 85% adoption, 50% gross efficiency, streamlined workflows (10%).",
        adoption_rate=0.85,
        gross_efficiency_gain=0.50,
        verification_overhead=0.10,
        annual_hours_per_fte=1800.0
    ),
}


def simulate_task_capacity_release(
    row: pd.Series,
    params: ScenarioParameters
) -> Dict[str, Any]:
    """
    Simulate capacity release for a single task row using transparent formula:
    Hours_Released = Baseline_Hours * Adoption_Rate * Net_Efficiency_Rate * Feasibility_Factor
    """
    # Baseline hours
    base_hours = float(row.get("annual_task_hours", row.get("hours_per_year", 0.0)))
    if pd.isna(base_hours) or base_hours <= 0:
        base_hours = 0.0

    # Feasibility factor from scoring (0 to 1.0 scale)
    feas_score = float(row.get("feasibility_score", 50.0))
    if pd.isna(feas_score):
        feas_score = 50.0
    feas_factor = max(0.0, min(1.0, feas_score / 100.0))

    # Net efficiency accounting for verification overhead
    net_eff = params.gross_efficiency_gain * (1.0 - params.verification_overhead)
    effective_pct = params.adoption_rate * net_eff * feas_factor

    # Released hours and retained hours
    released_hours = round(base_hours * effective_pct, 1)
    retained_hours = round(base_hours - released_hours, 1)
    fte_equiv = round(released_hours / params.annual_hours_per_fte, 3)

    return {
        "scenario_id": params.scenario_id,
        "scenario_name": params.scenario_name,
        "task_id": str(row.get("matched_task_id", row.get("task_id", "UNKNOWN"))),
        "department": str(row.get("department", "Cross-Disciplinary")),
        "role": str(row.get("role", "Researcher")),
        "baseline_annual_hours": round(base_hours, 1),
        "potential_hours_released": released_hours,
        "effective_capacity_released_pct": round(effective_pct * 100.0, 2),
        "net_hours_retained": retained_hours,
        "fte_capacity_equivalent": fte_equiv,
    }


def run_scenario_simulation(
    df: pd.DataFrame,
    scenarios: Optional[Dict[str, ScenarioParameters]] = None
) -> pd.DataFrame:
    """
    Run scenario simulations across all provided tasks for each scenario.

    Parameters
    ----------
    df : pd.DataFrame
        DataFrame of tasks with feasibility scores and baseline hours.
    scenarios : dict of {str: ScenarioParameters}, optional
        Scenarios to simulate. Defaults to Conservative, Moderate, Optimistic.

    Returns
    -------
    pd.DataFrame
        Simulation outputs with all scenario comparisons.
    """
    scen_dict = scenarios if scenarios is not None else DEFAULT_SCENARIOS
    all_results: List[Dict[str, Any]] = []

    for scen_key, params in scen_dict.items():
        for _, row in df.iterrows():
            sim_res = simulate_task_capacity_release(row, params)
            all_results.append(sim_res)

    return pd.DataFrame(all_results)


def save_scenario_results_to_duckdb(
    sim_df: pd.DataFrame,
    conn: Optional[Any] = None
) -> int:
    """Save simulation outputs to DuckDB scenario_results table."""
    from database.db_manager import get_connection

    should_close = False
    if conn is None:
        conn = get_connection()
        should_close = True

    try:
        conn.execute("DELETE FROM scenario_results;")
        conn.register("df_temp_scen", sim_df)
        conn.execute("""
            INSERT INTO scenario_results
            SELECT
                scenario_id,
                MAX(scenario_name) AS scenario_name,
                task_id,
                department,
                role,
                ROUND(SUM(baseline_annual_hours), 1) AS baseline_annual_hours,
                ROUND(SUM(potential_hours_released), 1) AS potential_hours_released,
                ROUND(AVG(effective_capacity_released_pct), 2) AS effective_capacity_released_pct,
                ROUND(SUM(net_hours_retained), 1) AS net_hours_retained,
                ROUND(SUM(fte_capacity_equivalent), 3) AS fte_capacity_equivalent
            FROM df_temp_scen
            GROUP BY scenario_id, task_id, department, role;
        """)
        conn.unregister("df_temp_scen")
        count = conn.execute("SELECT COUNT(*) FROM scenario_results;").fetchone()[0]
        return count
    finally:
        if should_close:
            conn.close()


def generate_scenario_comparison_summary(sim_df: pd.DataFrame) -> pd.DataFrame:
    """
    Generate an executive comparison table summarizing capacity released
    across scenarios.
    """
    summary = sim_df.groupby(["scenario_id", "scenario_name"]).agg(
        total_baseline_hours=("baseline_annual_hours", "sum"),
        total_hours_released=("potential_hours_released", "sum"),
        total_fte_equivalent=("fte_capacity_equivalent", "sum"),
        avg_effective_release_pct=("effective_capacity_released_pct", "mean"),
    ).reset_index()

    summary["overall_hours_released_pct"] = round(
        (summary["total_hours_released"] / summary["total_baseline_hours"]) * 100.0, 2
    )
    summary["total_hours_released"] = summary["total_hours_released"].round(1)
    summary["total_fte_equivalent"] = summary["total_fte_equivalent"].round(2)
    summary["total_baseline_hours"] = summary["total_baseline_hours"].round(1)
    return summary


if __name__ == "__main__":
    from database.db_manager import get_connection, query_df
    print("Testing Scenario Engine against organization_task_usage in DuckDB...")
    conn = get_connection()

    # Join organization task usage with analytical scores
    org_tasks_query = """
    SELECT
        u.*,
        COALESCE(s.feasibility_score, 50.0) AS feasibility_score,
        COALESCE(s.capacity_opportunity_score, 40.0) AS capacity_opportunity_score,
        s.ai_fit_category,
        s.priority_tier
    FROM organization_task_usage u
    LEFT JOIN analytical_scoring_results s
        ON u.matched_task_id = s.task_id;
    """
    org_df = query_df(org_tasks_query, conn=conn)
    print(f"Loaded {len(org_df)} organization task allocations.")

    sim_results = run_scenario_simulation(org_df)
    saved_count = save_scenario_results_to_duckdb(sim_results, conn=conn)
    print(f"Simulated and saved {saved_count} scenario records.")

    comp = generate_scenario_comparison_summary(sim_results)
    print("\nExecutive Scenario Comparison Summary:")
    print(comp.to_string(index=False))

    # Department breakdown for Moderate scenario
    mod_df = sim_results[sim_results["scenario_id"] == "SCEN_MODERATE"]
    dept_summary = mod_df.groupby("department").agg(
        baseline_hours=("baseline_annual_hours", "sum"),
        released_hours=("potential_hours_released", "sum"),
        fte_equiv=("fte_capacity_equivalent", "sum")
    ).round(1).sort_values(by="released_hours", ascending=False)
    print("\nDepartment-level Capacity Release (Moderate Scenario):")
    print(dept_summary)

    conn.close()
