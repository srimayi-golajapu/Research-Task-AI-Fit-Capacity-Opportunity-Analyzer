"""
SciNet Data Validation Module
=============================
Provides comprehensive schema, nullability, uniqueness, range, and cross-dataset
relationship validation for SciNet datasets and organization task usage inputs.
"""

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional
import pandas as pd

from .scinet_loader import load_scinet_data


@dataclass
class ValidationReport:
    """Structured report containing data validation results."""
    is_valid: bool = True
    errors: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)
    metrics: Dict[str, Any] = field(default_factory=dict)

    def summary(self) -> str:
        status = "PASSED" if self.is_valid else "FAILED"
        lines = [
            f"=== Validation Summary: {status} ===",
            f"Errors:   {len(self.errors)}",
            f"Warnings: {len(self.warnings)}",
        ]
        if self.errors:
            lines.append("\nErrors encountered:")
            for err in self.errors:
                lines.append(f"  [ERROR] {err}")
        if self.warnings:
            lines.append("\nWarnings:")
            for warn in self.warnings:
                lines.append(f"  [WARN]  {warn}")
        return "\n".join(lines)


REQUIRED_COLUMNS = {
    "tasks": ["task", "category", "level", "domain", "field", "subfield"],
    "task_dimensions": [
        "task", "level", "domain", "field", "subfield",
        "cognitive_complexity", "physical_deployment", "regulatory_restriction"
    ],
    "task_time": ["task", "level", "domain", "field", "subfield", "researcher_hours"],
    "task_hours_per_year": ["task", "level", "domain", "field", "subfield", "hours_per_year"],
    "task_ratings": ["task", "level", "domain", "field", "subfield", "importance", "pct_researchers", "classification"],
    "task_activity_assignments": ["task", "level", "activity_id", "universal_task_id"],
}

KEY_HIERARCHY_COLUMNS = ["task", "level", "domain", "field", "subfield"]


def validate_required_columns(data: Dict[str, pd.DataFrame], report: ValidationReport) -> None:
    """Validate that every dataset contains its required columns."""
    for dataset_name, req_cols in REQUIRED_COLUMNS.items():
        if dataset_name not in data:
            report.errors.append(f"Dataset '{dataset_name}' missing from input data dictionary.")
            report.is_valid = False
            continue

        df = data[dataset_name]
        missing_cols = [c for c in req_cols if c not in df.columns]
        if missing_cols:
            report.errors.append(
                f"Dataset '{dataset_name}' is missing required columns: {missing_cols}"
            )
            report.is_valid = False


def validate_duplicates(data: Dict[str, pd.DataFrame], report: ValidationReport) -> None:
    """Check for duplicate rows across primary composite keys."""
    for dataset_name in ["tasks", "task_dimensions", "task_hours_per_year", "task_ratings"]:
        if dataset_name in data:
            df = data[dataset_name]
            available_keys = [c for c in KEY_HIERARCHY_COLUMNS if c in df.columns]
            dupes = df.duplicated(subset=available_keys).sum()
            report.metrics[f"{dataset_name}_duplicate_keys"] = int(dupes)
            if dupes > 0:
                report.errors.append(
                    f"Dataset '{dataset_name}' contains {dupes} duplicate composite hierarchy keys."
                )
                report.is_valid = False

    if "task_activity_assignments" in data:
        act_df = data["task_activity_assignments"]
        act_dupes = act_df.duplicated(subset=["task", "level", "activity_id"]).sum()
        report.metrics["task_activity_assignments_duplicate_keys"] = int(act_dupes)
        if act_dupes > 0:
            report.warnings.append(
                f"task_activity_assignments contains {act_dupes} duplicate task-activity pairs."
            )


def validate_missing_values(data: Dict[str, pd.DataFrame], report: ValidationReport) -> None:
    """Check for missing values in non-nullable essential columns."""
    mandatory_fields = {
        "tasks": ["task", "level"],
        "task_dimensions": ["task", "level"],
        "task_time": ["task", "level"],
        "task_hours_per_year": ["task", "level", "hours_per_year"],
        "task_ratings": ["task", "level", "importance", "pct_researchers"],
        "task_activity_assignments": ["task", "level", "activity_id", "universal_task_id"],
    }

    for dataset_name, cols in mandatory_fields.items():
        if dataset_name in data:
            df = data[dataset_name]
            for col in cols:
                if col in df.columns:
                    null_count = int(df[col].isnull().sum())
                    report.metrics[f"{dataset_name}_{col}_nulls"] = null_count
                    if null_count > 0:
                        report.errors.append(
                            f"Mandatory column '{col}' in '{dataset_name}' contains {null_count} nulls."
                        )
                        report.is_valid = False


def validate_numeric_ranges(data: Dict[str, pd.DataFrame], report: ValidationReport) -> None:
    """Validate that numerical measurements fall within valid physical/domain ranges."""
    if "task_ratings" in data:
        r_df = data["task_ratings"]
        # importance 1 to 5
        imp_invalid = (~r_df["importance"].between(1, 5)).sum()
        if imp_invalid > 0:
            report.errors.append(f"task_ratings: {imp_invalid} rows have importance outside [1, 5].")
            report.is_valid = False

        # pct_researchers 0 to 100
        pct_invalid = (~r_df["pct_researchers"].between(0, 100)).sum()
        if pct_invalid > 0:
            report.errors.append(f"task_ratings: {pct_invalid} rows have pct_researchers outside [0, 100].")
            report.is_valid = False

    if "task_hours_per_year" in data:
        h_df = data["task_hours_per_year"]
        neg_hours = (h_df["hours_per_year"] < 0).sum()
        if neg_hours > 0:
            report.errors.append(f"task_hours_per_year: {neg_hours} rows have negative hours_per_year.")
            report.is_valid = False

    if "task_dimensions" in data:
        dim_df = data["task_dimensions"]
        if "cognitive_complexity" in dim_df.columns:
            neg_cog = (dim_df["cognitive_complexity"] < 0).sum()
            if neg_cog > 0:
                report.errors.append(f"task_dimensions: {neg_cog} rows have negative cognitive_complexity.")
                report.is_valid = False


def validate_cross_dataset_integrity(data: Dict[str, pd.DataFrame], report: ValidationReport) -> None:
    """Validate key relationships across the SciNet data model."""
    # 1. tasks vs task_dimensions 1:1 match
    if "tasks" in data and "task_dimensions" in data:
        tasks = data["tasks"]
        dims = data["task_dimensions"]
        report.metrics["tasks_count"] = len(tasks)
        report.metrics["dimensions_count"] = len(dims)

        if len(tasks) != len(dims):
            report.errors.append(
                f"Row count mismatch: tasks has {len(tasks)} rows, task_dimensions has {len(dims)} rows."
            )
            report.is_valid = False

    # 2. task_hours_per_year vs task_ratings 1:1 match
    if "task_hours_per_year" in data and "task_ratings" in data:
        hours = data["task_hours_per_year"]
        ratings = data["task_ratings"]
        report.metrics["hours_count"] = len(hours)
        report.metrics["ratings_count"] = len(ratings)

        if len(hours) != len(ratings):
            report.errors.append(
                f"Row count mismatch: task_hours_per_year ({len(hours)}) vs task_ratings ({len(ratings)})."
            )
            report.is_valid = False

    # 3. task_time 1,020 universal tasks preservation check
    if "task_time" in data:
        time_df = data["task_time"]
        univ_time_count = int((time_df["level"] == "universal").sum())
        report.metrics["task_time_universal_count"] = univ_time_count
        if univ_time_count != 1020:
            report.warnings.append(
                f"Expected 1,020 universal tasks in task_time, found {univ_time_count}."
            )


def run_full_validation(data: Optional[Dict[str, pd.DataFrame]] = None) -> ValidationReport:
    """
    Execute all validation rules on the loaded SciNet data.

    Parameters
    ----------
    data : dict of {str: pd.DataFrame}, optional
        Loaded SciNet datasets. If None, datasets are loaded using load_scinet_data().

    Returns
    -------
    ValidationReport
        Structured report containing all error, warning, and metric outputs.
    """
    if data is None:
        data = load_scinet_data()

    report = ValidationReport()
    validate_required_columns(data, report)
    validate_duplicates(data, report)
    validate_missing_values(data, report)
    validate_numeric_ranges(data, report)
    validate_cross_dataset_integrity(data, report)

    return report


if __name__ == "__main__":
    rep = run_full_validation()
    print(rep.summary())
    print("\nMetrics:", rep.metrics)
