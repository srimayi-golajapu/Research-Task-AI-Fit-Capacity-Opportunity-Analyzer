"""
Synthetic Organization Task Usage Generator
============================================
Generates realistic organization-specific task allocation data representing an
actual research institute ("Nexus Institute for Advanced Research").

Allows users to test the capacity release opportunity analyzer immediately out-of-the-box,
while also serving as a clear template for users replacing it with their own organizational CSV.
"""

import random
from pathlib import Path
from typing import Optional, Union
import pandas as pd

from .scinet_loader import load_scinet_data

DEFAULT_SYNTHETIC_PATH = Path("data/synthetic/organization_task_usage.csv")

DEPARTMENT_MAPPINGS = {
    "Life Sciences": "Department of Biosciences & Genomics",
    "Social Sciences": "Institute for Empirical Social Sciences",
    "Physical Sciences": "Center for Physics & Advanced Materials",
    "Engineering": "School of Computing & Systems Engineering",
    "Arts & Humanities": "Humanities & Spatial Design Center",
    "Mathematics & Statistics": "Department of Mathematical Sciences",
}

ROLES = [
    "Principal Investigator / Professor",
    "Senior Research Scientist",
    "Postdoctoral Fellow",
    "Research Associate / Data Analyst",
    "Graduate Research Assistant",
]

AI_USAGE_LEVELS = ["None", "Minimal (<10%)", "Occasional (10-30%)", "Regular (>30%)"]


def generate_synthetic_organization_data(
    num_task_assignments: int = 150,
    output_path: Optional[Union[str, Path]] = None,
    seed: int = 42
) -> pd.DataFrame:
    """
    Generate synthetic organization task usage data sampled from real SciNet tasks.

    Parameters
    ----------
    num_task_assignments : int, default=150
        Number of task allocations across roles and departments.
    output_path : str or Path, optional
        Destination CSV path. Defaults to 'data/synthetic/organization_task_usage.csv'.
    seed : int, default=42
        Random seed for reproducibility.

    Returns
    -------
    pd.DataFrame
        Synthetic organization task usage DataFrame.
    """
    random.seed(seed)
    scinet = load_scinet_data()
    hours_df = scinet["task_hours_per_year"]

    # Sample tasks stratified by domain to ensure balanced organizational representation
    available_domains = [d for d in hours_df["domain"].dropna().unique() if d in DEPARTMENT_MAPPINGS]
    sampled_rows = []

    tasks_per_domain = max(10, num_task_assignments // len(available_domains))

    for domain in available_domains:
        dom_df = hours_df[hours_df["domain"] == domain]
        sample_count = min(len(dom_df), tasks_per_domain)
        dom_samples = dom_df.sample(n=sample_count, random_state=seed)
        sampled_rows.append(dom_samples)

    sampled_tasks = pd.concat(sampled_rows, ignore_index=True)
    if len(sampled_tasks) < num_task_assignments:
        remaining = num_task_assignments - len(sampled_tasks)
        extra = hours_df.sample(n=remaining, random_state=seed + 1)
        sampled_tasks = pd.concat([sampled_tasks, extra], ignore_index=True)

    records = []
    for idx, row in sampled_tasks.iterrows():
        domain = row.get("domain", "General Research")
        dept = DEPARTMENT_MAPPINGS.get(domain, "Cross-Disciplinary Research Unit")
        role = random.choice(ROLES)

        # Baseline FTE count and allocated weekly hours
        fte_count = random.randint(1, 8)
        weekly_hours_per_fte = round(random.uniform(1.5, 9.5), 1)
        weeks_per_year = random.choice([44, 46, 48, 50])
        total_annual_hours = round(fte_count * weekly_hours_per_fte * weeks_per_year, 1)

        # Current AI tool usage
        curr_ai = random.choices(
            AI_USAGE_LEVELS, weights=[0.40, 0.30, 0.20, 0.10], k=1
        )[0]

        records.append({
            "org_id": "ORG_NEXUS_01",
            "organization_name": "Nexus Institute for Advanced Research",
            "department": dept,
            "role": role,
            "task": row["task"],
            "level": row["level"],
            "domain": domain,
            "field": row["field"],
            "subfield": row["subfield"],
            "fte_count": fte_count,
            "weekly_hours_per_fte": weekly_hours_per_fte,
            "weeks_per_year": weeks_per_year,
            "annual_task_hours": total_annual_hours,
            "current_ai_usage": curr_ai,
        })

    org_df = pd.DataFrame(records)

    out_file = Path(output_path) if output_path is not None else DEFAULT_SYNTHETIC_PATH
    out_file.parent.mkdir(parents=True, exist_ok=True)
    org_df.to_csv(out_file, index=False)
    print(f"Generated {len(org_df)} synthetic task assignments -> {out_file}")

    return org_df


if __name__ == "__main__":
    generate_synthetic_organization_data()
