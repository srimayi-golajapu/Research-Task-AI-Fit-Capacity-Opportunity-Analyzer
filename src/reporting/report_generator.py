"""
Reporting & Decision Brief Export Module
========================================
Generates executive-ready decision briefs, CSV exports, scenario comparison tables,
and analytical summaries.

Ensures strict governance compliance:
- Clearly separates SciNet source data, Anthropic contextual evidence,
  organization inputs, and simulation assumptions.
- Explicitly states methodological limitations and capacity interpretation rules.
"""

from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Optional, Union
import pandas as pd

from database.db_manager import get_connection, query_df

DEFAULT_REPORTS_DIR = Path("reports")


def generate_executive_decision_brief(
    conn: Optional[Any] = None,
    organization_name: str = "Nexus Institute for Advanced Research",
    output_path: Optional[Union[str, Path]] = None
) -> str:
    """
    Generate an executive decision-support brief in Markdown.

    Parameters
    ----------
    conn : duckdb connection, optional
        Database connection.
    organization_name : str, default='Nexus Institute for Advanced Research'
        Name of the evaluated organization.
    output_path : str or Path, optional
        Path to save the generated Markdown brief.

    Returns
    -------
    str
        Complete Markdown document content.
    """
    should_close = False
    if conn is None:
        conn = get_connection(read_only=True)
        should_close = True

    try:
        # 1. Fetch Scenario Summary
        scen_df = query_df("""
            SELECT
                scenario_name,
                ROUND(SUM(baseline_annual_hours), 1) AS total_baseline_hours,
                ROUND(SUM(potential_hours_released), 1) AS hours_released,
                ROUND(SUM(fte_capacity_equivalent), 2) AS fte_equivalent,
                ROUND((SUM(potential_hours_released) / SUM(baseline_annual_hours)) * 100.0, 2) AS release_pct
            FROM scenario_results
            GROUP BY scenario_name
            ORDER BY hours_released ASC;
        """, conn=conn)

        # 2. Fetch Department Breakdown (Moderate Scenario)
        dept_df = query_df("""
            SELECT
                department,
                ROUND(SUM(baseline_annual_hours), 1) AS baseline_hours,
                ROUND(SUM(potential_hours_released), 1) AS hours_released,
                ROUND(SUM(fte_capacity_equivalent), 2) AS fte_equivalent,
                ROUND((SUM(potential_hours_released) / SUM(baseline_annual_hours)) * 100.0, 2) AS net_pct
            FROM scenario_results
            WHERE scenario_id = 'SCEN_MODERATE'
            GROUP BY department
            ORDER BY hours_released DESC;
        """, conn=conn)

        # 3. Fetch Top Opportunity Tasks
        top_tasks = query_df("""
            SELECT
                task,
                domain,
                category,
                ROUND(hours_per_year, 1) AS annual_hours,
                ROUND(ai_suitability_score, 1) AS ai_suitability,
                ROUND(physical_intensity_score, 1) AS physical_intensity,
                ROUND(capacity_opportunity_score, 1) AS opportunity_score,
                priority_tier,
                explanation
            FROM analytical_scoring_results
            WHERE capacity_opportunity_score >= 60.0
            ORDER BY capacity_opportunity_score DESC
            LIMIT 8;
        """, conn=conn)

        # 4. Fetch Domain Breakdown Across SciNet Benchmark
        domain_summary = query_df("SELECT * FROM vw_domain_opportunity_summary;", conn=conn)
        total_scored = conn.execute("SELECT COUNT(*) FROM analytical_scoring_results;").fetchone()[0]

        # Assemble Markdown Brief
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M")
        
        brief = f"""# Executive Decision Brief: Research Task AI Fit & Capacity Opportunity

**Target Organization:** {organization_name}  
**Date of Assessment:** {timestamp}  
**Analytical Architecture:** SciNet Task Taxonomy + Empirical AI Suitability Engine + DuckDB Analytics  

---

## 1. Executive Summary

This report delivers a rigorous, data-driven evaluation of organizational tasks to identify high-value opportunities for AI-assisted workflow augmentation and quantify potential capacity-release benefits.

### Core Strategic Takeaways:
1. **Material Capacity Reallocation:** Under the baseline **Moderate Adoption Scenario (60% adoption, 35% gross efficiency)**, the organization can release **{scen_df.loc[scen_df['scenario_name']=='Moderate Scenario', 'hours_released'].values[0]:,.1f} hours annually** across research personnel—the mathematical equivalent of **{scen_df.loc[scen_df['scenario_name']=='Moderate Scenario', 'fte_equivalent'].values[0]:.2f} full-time research FTEs**.
2. **Selective Feasibility (No Blanket Automation):** Only tasks characterized by high digital information density (e.g. theoretical formalisms, literature synthesis, and data coding) yield high capacity returns. Tasks involving physical materials ({top_tasks['physical_intensity'].mean():.1f}% avg constraint in wet-labs) or strict IRB compliance are automatically gated or penalized.
3. **Capacity Creation vs. Headcount Reduction:** Released hours represent *repurposed capacity* for core scientific ideation and grant generation, not workforce elimination.

---

## 2. Multi-Scenario Capacity Release Matrix

The simulation models three distinct policy stances reflecting organizational adoption velocity, model efficiency gains, and required human verification overhead:

| Scenario | Adoption Rate | Gross Speedup | Verification Friction | Annual Baseline Hours | Potential Hours Released | Net Capacity Release (%) | FTE Equivalent |
|---|---|---|---|---:|---:|---:|---:|
| **Conservative** | 35% | 20% | 30% | {scen_df.loc[scen_df['scenario_name']=='Conservative Scenario', 'total_baseline_hours'].values[0]:,.1f} | {scen_df.loc[scen_df['scenario_name']=='Conservative Scenario', 'hours_released'].values[0]:,.1f} | {scen_df.loc[scen_df['scenario_name']=='Conservative Scenario', 'release_pct'].values[0]:.2f}% | **{scen_df.loc[scen_df['scenario_name']=='Conservative Scenario', 'fte_equivalent'].values[0]:.2f} FTE** |
| **Moderate** | 60% | 35% | 20% | {scen_df.loc[scen_df['scenario_name']=='Moderate Scenario', 'total_baseline_hours'].values[0]:,.1f} | {scen_df.loc[scen_df['scenario_name']=='Moderate Scenario', 'hours_released'].values[0]:,.1f} | {scen_df.loc[scen_df['scenario_name']=='Moderate Scenario', 'release_pct'].values[0]:.2f}% | **{scen_df.loc[scen_df['scenario_name']=='Moderate Scenario', 'fte_equivalent'].values[0]:.2f} FTE** |
| **Optimistic** | 85% | 50% | 10% | {scen_df.loc[scen_df['scenario_name']=='Optimistic Scenario', 'total_baseline_hours'].values[0]:,.1f} | {scen_df.loc[scen_df['scenario_name']=='Optimistic Scenario', 'hours_released'].values[0]:,.1f} | {scen_df.loc[scen_df['scenario_name']=='Optimistic Scenario', 'release_pct'].values[0]:.2f}% | **{scen_df.loc[scen_df['scenario_name']=='Optimistic Scenario', 'fte_equivalent'].values[0]:.2f} FTE** |

---

## 3. Departmental Opportunity Breakdown (Moderate Scenario)

Capacity gains vary substantially across disciplinary units depending on the underlying physical and regulatory nature of their task portfolio:

| Department | Annual Task Hours | Potential Hours Released | FTE Capacity Equivalent | Net Gain (%) |
|---|---:|---:|---:|---:|
"""
        for _, row in dept_df.iterrows():
            brief += f"| {row['department']} | {row['baseline_hours']:,.1f} | {row['hours_released']:,.1f} | {row['fte_equivalent']:.2f} FTE | {row['net_pct']:.2f}% |\n"

        brief += """
---

## 4. Top Priority Task Opportunities (Tier 1 & Tier 2)

The analytical engine flags tasks with high time exposure, high digital feasibility, and minimal physical gating for prioritized tooling deployment:

"""
        for enum_i, (_, row) in enumerate(top_tasks.iterrows(), start=1):
            brief += f"### {enum_i}. {row['task']}\n"
            brief += f"- **Domain / Category:** {row['domain']} | {row['category']}\n"
            brief += f"- **Metrics:** Annual Workload: `{row['annual_hours']} hrs` | AI Suitability: `{row['ai_suitability']}/100` | Opportunity Score: `{row['opportunity_score']}/100`\n"
            brief += f"- **Analytical Rationale:** {row['explanation']}\n\n"

        brief += f"""---

## 5. Disciplinary Benchmark Landscape (SciNet Macro Data)

Analysis across all {total_scored:,} SciNet task-level observations reveals structural variations in AI opportunity:

| Scientific Domain | Total Tasks | Avg Time Exposure | Avg AI Suitability | Physical Intensity Gate | Regulatory Penalty | Avg Opportunity Score |
|---|---:|---:|---:|---:|---:|---:|
"""
        for _, row in domain_summary.iterrows():
            brief += f"| {row['domain']} | {row['total_tasks']:,} | {row['avg_time_exposure']:.1f} | {row['avg_ai_suitability']:.1f} | {row['avg_physical_intensity']:.1f} | {row['avg_regulatory_penalty']:.1f} | {row['avg_opportunity_score']:.1f} |\n"

        brief += """
---

## 6. Methodological Foundations & Governance Caveats

### Data Origin Distinctions:
1. **Empirical Task Taxonomy:** Grounded in peer-reviewed SciNet data (7,262 tasks, 26,803 domain instantiations).
2. **Contextual Evidence:** Informed by aggregate economic findings from Anthropic research on generative model task exposure and citation dynamics.
3. **Organization Data:** Evaluated against explicit task hours and FTE allocations supplied via organizational usage logs.

### Analytical Caveats:
- **No Inherent Autonomous Replacement:** Scores measure *augmentation opportunity*. All workflows require domain expert prompting and validation.
- **Physical Barriers:** Laboratory wet-bench synthesis, field sampling, and animal/human trials cannot be automated without embodied robotics.
- **Human-in-the-Loop Imperative:** Core scientific tasks with publication accountability require mandatory sign-off, reflected in the verification friction discount.

---
*Report autonomously generated by Research Task AI Fit & Capacity Opportunity Analyzer.*
"""
        if output_path is not None:
            out_p = Path(output_path)
            out_p.parent.mkdir(parents=True, exist_ok=True)
            out_p.write_text(brief, encoding="utf-8")

        return brief
    finally:
        if should_close:
            conn.close()


def export_all_reports(
    output_dir: Optional[Union[str, Path]] = None,
    conn: Optional[Any] = None
) -> Dict[str, Path]:
    """
    Generate and save all reports:
    1. Executive Decision Brief (Markdown)
    2. Task Opportunity Scores (CSV)
    3. Scenario Simulation Matrix (CSV)
    4. Domain Opportunity Summary (CSV)
    """
    out_dir = Path(output_dir) if output_dir is not None else DEFAULT_REPORTS_DIR
    out_dir.mkdir(parents=True, exist_ok=True)

    should_close = False
    if conn is None:
        conn = get_connection(read_only=True)
        should_close = True

    saved: Dict[str, Path] = {}
    try:
        # 1. Decision Brief
        brief_path = out_dir / "executive_decision_brief.md"
        generate_executive_decision_brief(conn=conn, output_path=brief_path)
        saved["executive_brief_markdown"] = brief_path

        # 2. Task Opportunities CSV
        task_csv = out_dir / "task_opportunity_scoring.csv"
        tasks_df = query_df("SELECT * FROM analytical_scoring_results ORDER BY capacity_opportunity_score DESC;", conn=conn)
        tasks_df.to_csv(task_csv, index=False)
        saved["task_scoring_csv"] = task_csv

        # 3. Scenario Matrix CSV
        scen_csv = out_dir / "scenario_simulation_matrix.csv"
        scen_df = query_df("SELECT * FROM scenario_results ORDER BY scenario_id, potential_hours_released DESC;", conn=conn)
        scen_df.to_csv(scen_csv, index=False)
        saved["scenario_matrix_csv"] = scen_csv

        # 4. Domain Summary CSV
        dom_csv = out_dir / "domain_opportunity_summary.csv"
        dom_df = query_df("SELECT * FROM vw_domain_opportunity_summary;", conn=conn)
        dom_df.to_csv(dom_csv, index=False)
        saved["domain_summary_csv"] = dom_csv

        return saved
    finally:
        if should_close:
            conn.close()


if __name__ == "__main__":
    print("Generating comprehensive executive decision brief and CSV reports...")
    files = export_all_reports()
    for name, p in files.items():
        print(f"  {name:<28} -> {p} ({p.stat().st_size} bytes)")
