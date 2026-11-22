"""
Tests for DuckDB Database Manager
"""

import sys
from pathlib import Path
import pytest
import duckdb

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))
sys.path.insert(0, str(PROJECT_ROOT / "database"))

from db_manager import get_connection, query_df, validate_database_records


def test_duckdb_connection():
    conn = get_connection(read_only=True)
    try:
        assert isinstance(conn, duckdb.DuckDBPyConnection)
        val = conn.execute("SELECT 1 + 1;").fetchone()[0]
        assert val == 2
    finally:
        conn.close()


def test_database_table_record_counts():
    conn = get_connection(read_only=True)
    try:
        metrics = validate_database_records(conn)
        assert metrics.get("scinet_tasks_count") == 7262
        assert metrics.get("scinet_task_dimensions_count") == 7262
        assert metrics.get("scinet_task_hours_count") == 26803
        assert metrics.get("scinet_task_ratings_count") == 26803
        assert metrics.get("scinet_task_time_count") == 18283
        assert metrics.get("scinet_task_activity_assignments_count") == 6956
        assert metrics.get("scinet_tasks_master_count") == 27823
        assert metrics.get("organization_task_usage_count") == 150
        assert metrics.get("org_match_rate_pct") == 100.0
    finally:
        conn.close()


def test_analytical_views_exist_and_queryable():
    conn = get_connection(read_only=True)
    try:
        df_domain = query_df("SELECT * FROM vw_domain_opportunity_summary;", conn=conn)
        assert len(df_domain) > 0
        assert "avg_opportunity_score" in df_domain.columns

        df_top = query_df("SELECT * FROM vw_top_capacity_opportunities LIMIT 10;", conn=conn)
        assert len(df_top) <= 10
        assert "opportunity_score" in df_top.columns
    finally:
        conn.close()
