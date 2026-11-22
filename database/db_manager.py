"""
DuckDB Database Manager Module
==============================
Handles connection, schema initialization, table ingestion, query execution,
and validation for local analytical DuckDB storage.
"""

import sys
from pathlib import Path

# Auto-detect local virtualenv site-packages if running with system python
_VENV_SITE = Path(__file__).resolve().parent.parent / ".venv" / "Lib" / "site-packages"
if _VENV_SITE.exists() and str(_VENV_SITE) not in sys.path:
    sys.path.insert(0, str(_VENV_SITE))

from typing import Any, Dict, List, Optional, Union
import duckdb
import pandas as pd

DEFAULT_DB_PATH = Path("database/research_task_analyzer.duckdb")
DEFAULT_SCHEMA_PATH = Path("database/schema.sql")
DEFAULT_PROCESSED_PATH = Path("data/processed")
DEFAULT_SYNTHETIC_PATH = Path("data/synthetic/organization_task_usage.csv")


def get_connection(
    db_path: Optional[Union[str, Path]] = None,
    read_only: bool = False
) -> duckdb.DuckDBPyConnection:
    """
    Open and return a DuckDB connection.

    Parameters
    ----------
    db_path : str or Path, optional
        Path to DuckDB database file. Defaults to 'database/research_task_analyzer.duckdb'.
    read_only : bool, default=False
        Whether to open in read-only mode.

    Returns
    -------
    duckdb.DuckDBPyConnection
        Active DuckDB database connection.
    """
    path = Path(db_path) if db_path is not None else DEFAULT_DB_PATH
    path.parent.mkdir(parents=True, exist_ok=True)
    return duckdb.connect(str(path), read_only=read_only)


def initialize_schema(
    conn: duckdb.DuckDBPyConnection,
    schema_path: Optional[Union[str, Path]] = None
) -> None:
    """
    Execute schema.sql DDL to create analytical tables and views.

    Parameters
    ----------
    conn : duckdb.DuckDBPyConnection
        Active database connection.
    schema_path : str or Path, optional
        Path to schema DDL file. Defaults to 'database/schema.sql'.
    """
    path = Path(schema_path) if schema_path is not None else DEFAULT_SCHEMA_PATH
    if not path.exists():
        raise FileNotFoundError(f"Schema file not found at {path}")

    sql_statements = path.read_text(encoding="utf-8")
    conn.execute(sql_statements)


def load_processed_scinet_data(
    conn: duckdb.DuckDBPyConnection,
    processed_dir: Optional[Union[str, Path]] = None
) -> Dict[str, int]:
    """
    Load normalized CSV files from data/processed/ into DuckDB tables.

    Parameters
    ----------
    conn : duckdb.DuckDBPyConnection
        Active database connection.
    processed_dir : str or Path, optional
        Path to processed CSV files. Defaults to 'data/processed/'.

    Returns
    -------
    dict of {str: int}
        Mapping of table name to ingested record count.
    """
    p_dir = Path(processed_dir) if processed_dir is not None else DEFAULT_PROCESSED_PATH

    table_mappings = {
        "scinet_tasks": p_dir / "tasks.csv",
        "scinet_task_dimensions": p_dir / "task_dimensions.csv",
        "scinet_task_hours": p_dir / "task_hours_per_year.csv",
        "scinet_task_ratings": p_dir / "task_ratings.csv",
        "scinet_task_time": p_dir / "task_time.csv",
        "scinet_task_activity_assignments": p_dir / "task_activity_assignments.csv",
        "scinet_tasks_master": p_dir / "tasks_master.csv",
    }

    ingested_counts: Dict[str, int] = {}

    for table_name, csv_path in table_mappings.items():
        if not csv_path.exists():
            raise FileNotFoundError(f"Processed file missing: {csv_path}")

        norm_path = str(csv_path).replace("\\", "/")
        conn.execute(f"""
            CREATE OR REPLACE TABLE {table_name} AS
            SELECT * FROM read_csv('{norm_path}', header=true, auto_detect=true);
        """)
        count = conn.execute(f"SELECT COUNT(*) FROM {table_name};").fetchone()[0]
        ingested_counts[table_name] = count

    return ingested_counts


def load_organization_usage_data(
    conn: duckdb.DuckDBPyConnection,
    usage_csv_path: Optional[Union[str, Path]] = None
) -> int:
    """
    Load organization task usage data and map records to scinet_tasks_master.

    Parameters
    ----------
    conn : duckdb.DuckDBPyConnection
        Active database connection.
    usage_csv_path : str or Path, optional
        Path to organization task usage CSV file. Defaults to synthetic path.

    Returns
    -------
    int
        Number of ingested organization task usage records.
    """
    csv_file = Path(usage_csv_path) if usage_csv_path is not None else DEFAULT_SYNTHETIC_PATH
    if not csv_file.exists():
        raise FileNotFoundError(f"Organization task usage file not found at {csv_file}")

    raw_df = pd.read_csv(csv_file)
    raw_df.columns = [c.strip().lower() for c in raw_df.columns]

    # Generate sequential usage IDs if not present
    if "usage_id" not in raw_df.columns:
        raw_df.insert(0, "usage_id", [f"USE_{i:05d}" for i in range(1, len(raw_df) + 1)])

    if "org_id" not in raw_df.columns:
        raw_df["org_id"] = "ORG_CUSTOM"
    if "organization_name" not in raw_df.columns:
        raw_df["organization_name"] = "Uploaded Organization"
    if "current_ai_usage" not in raw_df.columns:
        raw_df["current_ai_usage"] = "None"

    # Compute annual_task_hours if missing
    if "annual_task_hours" not in raw_df.columns:
        fte = raw_df["fte_count"] if "fte_count" in raw_df.columns else 1.0
        w_hrs = raw_df["weekly_hours_per_fte"] if "weekly_hours_per_fte" in raw_df.columns else 5.0
        weeks = raw_df["weeks_per_year"] if "weeks_per_year" in raw_df.columns else 46.0
        raw_df["annual_task_hours"] = (fte * w_hrs * weeks).round(1)

    for col in ["department", "role", "task"]:
        if col not in raw_df.columns:
            raise ValueError(f"Uploaded CSV must contain '{col}' column.")

    for col in ["fte_count", "weekly_hours_per_fte", "weeks_per_year"]:
        if col not in raw_df.columns:
            raw_df[col] = 1.0

    # Match each organization task against scinet_tasks_master to find matched_task_id
    tasks_master = conn.execute(
        "SELECT task_id, task, level, domain, field, subfield FROM scinet_tasks_master;"
    ).df()

    # Determine which hierarchy keys are present in raw_df
    hierarchy_keys = ["task", "level", "domain", "field", "subfield"]
    available_merge_keys = [k for k in hierarchy_keys if k in raw_df.columns]

    if len(available_merge_keys) > 1:
        matched = raw_df.merge(
            tasks_master[available_merge_keys + ["task_id"]].drop_duplicates(subset=available_merge_keys),
            on=available_merge_keys,
            how="left"
        )
        matched = matched.rename(columns={"task_id": "matched_task_id"})
    else:
        task_lookup = tasks_master[["task", "task_id", "level", "domain", "field", "subfield"]].drop_duplicates(subset=["task"])
        matched = raw_df.merge(
            task_lookup,
            on="task",
            how="left"
        )
        matched = matched.rename(columns={"task_id": "matched_task_id"})

    # Fallback match on task alone if some subfields were unmatched
    unmatched_mask = matched["matched_task_id"].isna()
    if unmatched_mask.any():
        task_only_master = tasks_master[["task", "task_id"]].drop_duplicates(subset=["task"])
        fallback_matched = raw_df[unmatched_mask].merge(
            task_only_master,
            on="task",
            how="left"
        )
        matched.loc[unmatched_mask, "matched_task_id"] = fallback_matched["task_id"].values

    for col in ["level", "domain", "field", "subfield"]:
        if col not in matched.columns:
            matched[col] = None

    conn.execute("DELETE FROM organization_task_usage;")
    conn.register("df_temp_org", matched)
    conn.execute("""
        INSERT INTO organization_task_usage
        SELECT
            usage_id,
            org_id,
            organization_name,
            department,
            role,
            task,
            level,
            domain,
            field,
            subfield,
            fte_count,
            weekly_hours_per_fte,
            weeks_per_year,
            annual_task_hours,
            current_ai_usage,
            matched_task_id
        FROM df_temp_org;
    """)
    conn.unregister("df_temp_org")

    count = conn.execute("SELECT COUNT(*) FROM organization_task_usage;").fetchone()[0]
    return count


def validate_database_records(conn: duckdb.DuckDBPyConnection) -> Dict[str, Any]:
    """
    Validate table counts, non-empty status, and relational joinability.

    Returns
    -------
    dict
        Summary metrics of database tables.
    """
    tables = [
        "scinet_tasks",
        "scinet_task_dimensions",
        "scinet_task_hours",
        "scinet_task_ratings",
        "scinet_task_time",
        "scinet_task_activity_assignments",
        "scinet_tasks_master",
        "organization_task_usage",
    ]

    metrics: Dict[str, Any] = {}
    for tbl in tables:
        count = conn.execute(f"SELECT COUNT(*) FROM {tbl};").fetchone()[0]
        metrics[f"{tbl}_count"] = count

    # Check organization task match rate
    org_total = metrics.get("organization_task_usage_count", 0)
    if org_total > 0:
        matched_count = conn.execute(
            "SELECT COUNT(*) FROM organization_task_usage WHERE matched_task_id IS NOT NULL;"
        ).fetchone()[0]
        metrics["org_matched_count"] = matched_count
        metrics["org_match_rate_pct"] = round((matched_count / org_total) * 100, 2)

    return metrics


def query_df(
    query: str,
    conn: Optional[duckdb.DuckDBPyConnection] = None,
    params: Optional[List[Any]] = None
) -> pd.DataFrame:
    """Execute a query and return result as a pandas DataFrame."""
    should_close = False
    if conn is None:
        conn = get_connection(read_only=True)
        should_close = True

    try:
        if params:
            df = conn.execute(query, params).df()
        else:
            df = conn.execute(query).df()
        return df
    finally:
        if should_close:
            conn.close()


def initialize_complete_database(
    db_path: Optional[Union[str, Path]] = None,
    schema_path: Optional[Union[str, Path]] = None,
    processed_dir: Optional[Union[str, Path]] = None,
    synthetic_org_path: Optional[Union[str, Path]] = None
) -> Dict[str, Any]:
    """
    End-to-end initialization: creates schema, loads SciNet data,
    loads organization data, and validates database status.
    """
    conn = get_connection(db_path=db_path)
    try:
        print("1. Loading normalized SciNet datasets...")
        scinet_counts = load_processed_scinet_data(conn, processed_dir=processed_dir)

        print("2. Initializing analytical tables & schema DDL...")
        initialize_schema(conn, schema_path=schema_path)

        print("3. Loading organization task usage data...")
        org_count = load_organization_usage_data(conn, usage_csv_path=synthetic_org_path)

        print("4. Validating database record integrity...")
        metrics = validate_database_records(conn)

        print("DuckDB database successfully initialized.")
        return metrics
    finally:
        conn.close()


if __name__ == "__main__":
    results = initialize_complete_database()
    print("\nDatabase validation metrics:")
    for k, v in results.items():
        print(f"  {k:<35}: {v}")
