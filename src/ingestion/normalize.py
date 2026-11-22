"""
SciNet Data Normalization Module
================================
Transforms raw SciNet datasets into consistent, normalized tables:
- Generates deterministic composite task IDs (SHA-256 based prefix).
- Preserves all original records and row counts.
- Explicitly flags and preserves the 1,020 unmatched universal-level task_time records.
- Builds an unified master view for rapid analytical scoring.
- Exports processed tables to parquet and CSV.
"""

import hashlib
from pathlib import Path
from typing import Dict, Optional, Union
import numpy as np
import pandas as pd

from .scinet_loader import load_scinet_data


HIERARCHY_COLUMNS = ["task", "level", "domain", "field", "subfield"]
DEFAULT_PROCESSED_DIR = Path("data/processed/")


def generate_task_id(row: Union[pd.Series, dict]) -> str:
    """
    Generate a deterministic, 16-character unique identifier for a task
    based on its composite hierarchy key: (task, level, domain, field, subfield).

    Parameters
    ----------
    row : pd.Series or dict
        Row containing hierarchy columns.

    Returns
    -------
    str
        Deterministic string identifier, e.g., 't_a3f8c129e04b7d'.
    """
    t = str(row.get("task", "")).strip()
    lvl = str(row.get("level", "")).strip()
    d = "" if pd.isna(row.get("domain")) else str(row.get("domain")).strip()
    f = "" if pd.isna(row.get("field")) else str(row.get("field")).strip()
    s = "" if pd.isna(row.get("subfield")) else str(row.get("subfield")).strip()

    raw_key = f"{t}|{lvl}|{d}|{f}|{s}"
    digest = hashlib.sha256(raw_key.encode("utf-8")).hexdigest()[:14]
    return f"t_{digest}"


def add_task_id(df: pd.DataFrame) -> pd.DataFrame:
    """Add deterministic task_id column to DataFrame."""
    df_out = df.copy()
    df_out["task_id"] = [
        generate_task_id(row) for row in df_out[HIERARCHY_COLUMNS].to_dict("records")
    ]
    # Reorder task_id to first position
    cols = ["task_id"] + [c for c in df_out.columns if c != "task_id"]
    return df_out[cols]


def normalize_scinet_datasets(
    raw_data: Optional[Dict[str, pd.DataFrame]] = None
) -> Dict[str, pd.DataFrame]:
    """
    Normalize all six SciNet raw datasets and generate the unified master table.

    Parameters
    ----------
    raw_data : dict of {str: pd.DataFrame}, optional
        Raw SciNet datasets dictionary. If None, loaded automatically.

    Returns
    -------
    dict of {str: pd.DataFrame}
        Dictionary of normalized DataFrames:
        - 'tasks'
        - 'task_dimensions'
        - 'task_time' (with 'is_universal_unmatched' flag)
        - 'task_hours_per_year'
        - 'task_ratings'
        - 'task_activity_assignments'
        - 'tasks_master' (unified enriched analytical catalog)
    """
    if raw_data is None:
        raw_data = load_scinet_data()

    normalized: Dict[str, pd.DataFrame] = {}

    # 1. Normalize tasks
    tasks = add_task_id(raw_data["tasks"])
    normalized["tasks"] = tasks

    # 2. Normalize task_dimensions
    dims = add_task_id(raw_data["task_dimensions"])
    normalized["task_dimensions"] = dims

    # 3. Normalize task_hours_per_year
    hours = add_task_id(raw_data["task_hours_per_year"])
    normalized["task_hours_per_year"] = hours

    # 4. Normalize task_ratings
    ratings = add_task_id(raw_data["task_ratings"])
    normalized["task_ratings"] = ratings

    # 5. Normalize task_time & flag 1,020 unmatched universal tasks
    time_df = add_task_id(raw_data["task_time"])
    # Check if task_id exists in task_hours_per_year
    hours_ids = set(hours["task_id"])
    time_df["is_universal_unmatched"] = (
        (time_df["level"] == "universal") & (~time_df["task_id"].isin(hours_ids))
    )
    normalized["task_time"] = time_df

    # 6. Normalize task_activity_assignments
    act_df = raw_data["task_activity_assignments"].copy()
    act_df["task_id"] = [
        generate_task_id(row) for row in act_df.to_dict("records")
    ]
    cols = ["task_id"] + [c for c in act_df.columns if c != "task_id"]
    normalized["task_activity_assignments"] = act_df[cols]

    # 7. Build unified tasks_master table
    # Base: task_hours_per_year (26,803 rows with domain/field/subfield and hourly metrics)
    master = hours.copy()

    # Join ratings (1:1 with hours)
    rating_cols = [
        "task_id", "importance", "pct_researchers", "frequency", "classification"
    ]
    master = master.merge(ratings[rating_cols], on="task_id", how="left")

    # Join dimensions (tasks.csv and task_dimensions have 7,262 rows)
    dim_cols = [
        "task_id", "cognitive_complexity", "physical_deployment", "regulatory_restriction",
        "medium_information", "medium_materials", "medium_people",
        "mode_theoretical", "mode_quantitative", "mode_qualitative", "mode_design",
        "rl_index", "elo_opus5", "pasteur_quadrant"
    ]
    dim_subset = dims[[c for c in dim_cols if c in dims.columns]]
    master = master.merge(dim_subset, on="task_id", how="left")

    # Join category from tasks.csv
    task_cat_map = tasks[["task_id", "category"]].drop_duplicates(subset=["task_id"])
    master = master.merge(task_cat_map, on="task_id", how="left")

    # Join task_time metrics
    time_metrics = time_df[["task_id", "n_substeps", "researcher_hours", "elapsed_hours", "confidence"]].drop_duplicates(subset=["task_id"])
    master = master.merge(time_metrics, on="task_id", how="left")

    # Now append the 1,020 universal tasks from task_time that do not exist in task_hours
    unmatched_time = time_df[time_df["is_universal_unmatched"]].copy()
    if len(unmatched_time) > 0:
        # Create matching columns for unmatched universal tasks
        unmatched_master = pd.DataFrame(index=unmatched_time.index)
        for col in master.columns:
            if col in unmatched_time.columns:
                unmatched_master[col] = unmatched_time[col]
            else:
                unmatched_master[col] = np.nan

        # Enrich unmatched universal tasks with dimensions & category
        unmatched_master = unmatched_master.drop(
            columns=[c for c in dim_subset.columns if c != "task_id"] + ["category"],
            errors="ignore"
        )
        unmatched_master = unmatched_master.merge(dim_subset, on="task_id", how="left")
        unmatched_master = unmatched_master.merge(task_cat_map, on="task_id", how="left")

        # Combine
        master = pd.concat([master, unmatched_master], ignore_index=True)

    normalized["tasks_master"] = master

    return normalized


def save_processed_data(
    normalized_data: Dict[str, pd.DataFrame],
    output_dir: Optional[Union[str, Path]] = None
) -> Dict[str, Path]:
    """
    Save normalized tables to CSV (and parquet if pyarrow is available) in data/processed/.

    Parameters
    ----------
    normalized_data : dict of {str: pd.DataFrame}
        Normalized tables dictionary.
    output_dir : str or Path, optional
        Output directory. Defaults to 'data/processed/'.

    Returns
    -------
    dict of {str: Path}
        Mapping of table name to saved file path.
    """
    out_path = Path(output_dir) if output_dir is not None else DEFAULT_PROCESSED_DIR
    out_path.mkdir(parents=True, exist_ok=True)

    saved_paths: Dict[str, Path] = {}
    for name, df in normalized_data.items():
        csv_file = out_path / f"{name}.csv"
        df.to_csv(csv_file, index=False)
        saved_paths[name] = csv_file

        # Try saving parquet if pyarrow/fastparquet engine is installed
        try:
            parquet_file = out_path / f"{name}.parquet"
            df.to_parquet(parquet_file, index=False)
            saved_paths[f"{name}_parquet"] = parquet_file
        except (ImportError, Exception):
            pass

    return saved_paths


if __name__ == "__main__":
    print("Executing normalize_scinet_datasets()...")
    norm_data = normalize_scinet_datasets()
    for name, df in norm_data.items():
        print(f"  {name:<28}: {len(df):>6} rows × {len(df.columns):>2} cols")

    paths = save_processed_data(norm_data)
    print("\nSaved processed datasets:")
    for name, path in paths.items():
        print(f"  {name:<28} -> {path}")
