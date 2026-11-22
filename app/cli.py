"""
Research Task AI Fit & Capacity Opportunity Analyzer - CLI Application
=====================================================================
Unified Command-Line Interface providing full operational control:
- Ingestion & validation
- DuckDB initialization
- Analytical scoring
- Scenario simulation
- Report generation
- Web dashboard launch
"""

import argparse
import sys
from pathlib import Path

# Ensure project root, src, and database are on Python path
PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))
sys.path.insert(0, str(PROJECT_ROOT / "src"))
sys.path.insert(0, str(PROJECT_ROOT / "database"))

from ingestion.scinet_loader import load_scinet_data
from ingestion.validation import run_full_validation
from ingestion.normalize import normalize_scinet_datasets, save_processed_data
from ingestion.synthetic_generator import generate_synthetic_organization_data
from database.db_manager import (
    initialize_complete_database,
    get_connection,
    query_df,
    load_organization_usage_data
)
from analytics.scoring_engine import score_tasks, save_scoring_results_to_duckdb
from simulation.scenario_engine import (
    run_scenario_simulation,
    save_scenario_results_to_duckdb,
    generate_scenario_comparison_summary
)
from reporting.report_generator import export_all_reports


def cmd_run_pipeline(args):
    """Run full end-to-end data pipeline, scoring, simulation, and report generation."""
    print("=" * 70)
    print("STARTING FULL END-TO-END ANALYTICAL PIPELINE")
    print("=" * 70)

    # 1. Validation
    print("\n[Step 1/6] Validating raw SciNet datasets...")
    rep = run_full_validation()
    print(rep.summary())
    if not rep.is_valid:
        print("[ERROR] Validation failed. Aborting pipeline.", file=sys.stderr)
        sys.exit(1)

    # 2. Normalization
    print("\n[Step 2/6] Normalizing datasets & generating composite task IDs...")
    norm_data = normalize_scinet_datasets()
    save_processed_data(norm_data)
    print(f"  Unified tasks_master catalog: {len(norm_data['tasks_master'])} records.")

    # 3. Synthetic Org Data
    print("\n[Step 3/6] Ensuring organization task usage baseline...")
    generate_synthetic_organization_data()

    # 4. Database Setup
    print("\n[Step 4/6] Initializing DuckDB database & loading tables...")
    metrics = initialize_complete_database()
    print(f"  Database records: {metrics.get('scinet_tasks_master_count')} master tasks, {metrics.get('organization_task_usage_count')} org tasks.")

    # 5. Scoring & Simulation
    print("\n[Step 5/6] Executing multi-factor analytical scoring & scenario simulation...")
    conn = get_connection()
    tasks_df = query_df("SELECT * FROM scinet_tasks_master;", conn=conn)
    scored = score_tasks(tasks_df)
    save_scoring_results_to_duckdb(scored, conn=conn)

    org_df = query_df("""
        SELECT
            u.*,
            COALESCE(s.feasibility_score, 50.0) AS feasibility_score,
            COALESCE(s.capacity_opportunity_score, 40.0) AS capacity_opportunity_score,
            s.ai_fit_category,
            s.priority_tier
        FROM organization_task_usage u
        LEFT JOIN analytical_scoring_results s ON u.matched_task_id = s.task_id;
    """, conn=conn)
    sim_results = run_scenario_simulation(org_df)
    save_scenario_results_to_duckdb(sim_results, conn=conn)
    conn.close()

    # 6. Reports
    print("\n[Step 6/6] Generating executive decision brief & CSV exports...")
    reports = export_all_reports()
    for name, path in reports.items():
        print(f"  {name:<28} -> {path}")

    print("\n" + "=" * 70)
    print("PIPELINE EXECUTION COMPLETED SUCCESSFULLY!")
    print("=" * 70)


def cmd_summary(args):
    """Display an executive terminal summary of analytical and scenario results."""
    conn = get_connection(read_only=True)
    try:
        print("\n" + "=" * 75)
        print("EXECUTIVE ANALYTICAL SUMMARY & SCENARIO RESULTS")
        print("=" * 75)

        # Scenarios
        scen_df = query_df("""
            SELECT
                scenario_name,
                ROUND(SUM(baseline_annual_hours), 1) AS baseline_hours,
                ROUND(SUM(potential_hours_released), 1) AS hours_released,
                ROUND(SUM(fte_capacity_equivalent), 2) AS fte_equivalent,
                ROUND((SUM(potential_hours_released) / SUM(baseline_annual_hours)) * 100.0, 2) AS release_pct
            FROM scenario_results
            GROUP BY scenario_name
            ORDER BY hours_released ASC;
        """, conn=conn)
        print("\n[Capacity Release Scenario Comparison]:")
        print(scen_df.to_string(index=False))

        # Top 5 tasks
        top_df = query_df("""
            SELECT
                task,
                domain,
                hours_per_year,
                capacity_opportunity_score AS opp_score,
                ai_fit_category,
                priority_tier
            FROM analytical_scoring_results
            ORDER BY capacity_opportunity_score DESC
            LIMIT 5;
        """, conn=conn)
        print("\n[Top 5 Prioritized Opportunity Tasks]:")
        print(top_df.to_string(index=False))

        # Department breakdown
        dept_df = query_df("""
            SELECT
                department,
                ROUND(SUM(potential_hours_released), 1) AS hours_released,
                ROUND(SUM(fte_capacity_equivalent), 2) AS fte_equivalent
            FROM scenario_results
            WHERE scenario_id = 'SCEN_MODERATE'
            GROUP BY department
            ORDER BY hours_released DESC;
        """, conn=conn)
        print("\n[Department Potential Under Moderate Scenario]:")
        print(dept_df.to_string(index=False))
        print("=" * 75 + "\n")
    finally:
        conn.close()


def cmd_load_org(args):
    """Load or update organization-specific task usage CSV file."""
    csv_path = Path(args.csv_file)
    if not csv_path.exists():
        print(f"[ERROR] Specified file does not exist: {csv_path}", file=sys.stderr)
        sys.exit(1)

    print(f"Loading organization task usage from: {csv_path}")
    conn = get_connection()
    try:
        count = load_organization_usage_data(conn, usage_csv_path=csv_path)
        print(f"Successfully loaded {count} organization task records into DuckDB.")

        # Re-run simulation
        print("Re-evaluating capacity release scenarios...")
        org_df = query_df("""
            SELECT
                u.*,
                COALESCE(s.feasibility_score, 50.0) AS feasibility_score,
                COALESCE(s.capacity_opportunity_score, 40.0) AS capacity_opportunity_score,
                s.ai_fit_category,
                s.priority_tier
            FROM organization_task_usage u
            LEFT JOIN analytical_scoring_results s ON u.matched_task_id = s.task_id;
        """, conn=conn)
        sim_results = run_scenario_simulation(org_df)
        save_scenario_results_to_duckdb(sim_results, conn=conn)

        # Re-generate reports
        export_all_reports(conn=conn)
        print("Scenarios updated and reports regenerated successfully.")
    finally:
        conn.close()


def cmd_export(args):
    """Regenerate decision brief and CSV reports."""
    print("Exporting decision briefs and reports to reports/ ...")
    reports = export_all_reports()
    for name, path in reports.items():
        print(f"  {name:<28} -> {path} ({path.stat().st_size:,} bytes)")
    print("Reports export complete.")


def cmd_serve(args):
    """Launch local-first interactive web application."""
    from app.web_app import run_server
    print(f"Launching Research Task AI Fit Analyzer Dashboard on port {args.port}...")
    run_server(port=args.port)


def main():
    parser = argparse.ArgumentParser(
        description="Research Task AI Fit & Capacity Opportunity Analyzer - CLI",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    subparsers = parser.add_subparsers(dest="command", help="Available subcommands")

    # run-pipeline
    p_run = subparsers.add_parser("run-pipeline", help="Execute complete end-to-end analytical pipeline")
    p_run.set_defaults(func=cmd_run_pipeline)

    # summary
    p_sum = subparsers.add_parser("summary", help="Display executive terminal analytical summary")
    p_sum.set_defaults(func=cmd_summary)

    # load-org
    p_org = subparsers.add_parser("load-org", help="Load and evaluate organization task usage CSV")
    p_org.add_argument("csv_file", help="Path to organization task usage CSV file")
    p_org.set_defaults(func=cmd_load_org)

    # export
    p_exp = subparsers.add_parser("export", help="Regenerate all Markdown and CSV reports")
    p_exp.set_defaults(func=cmd_export)

    # serve
    import os
    default_port = int(os.environ.get("PORT", 8501))
    p_srv = subparsers.add_parser("serve", help="Start local web dashboard")
    p_srv.add_argument("--port", type=int, default=default_port, help=f"Port to bind dashboard server (default: {default_port})")
    p_srv.set_defaults(func=cmd_serve)

    if len(sys.argv) == 1:
        parser.print_help()
        sys.exit(0)

    args = parser.parse_args()
    if hasattr(args, "func"):
        args.func(args)
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
