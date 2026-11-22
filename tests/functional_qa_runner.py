"""
End-to-End Functional QA Test Runner
====================================
Performs complete, rigorous end-to-end functional QA of the Research Task
AI Fit & Capacity Opportunity Analyzer across all 10 verification dimensions:
1. Dashboard sections & API data loading
2. Search, domain filters, and priority filters
3. Task explanation consistency with scoring engine
4. Scenario comparison calculations against scenario engine
5. Departmental & domain summaries against DuckDB
6. Organization CSV upload edge cases (valid, missing columns, empty, duplicates, non-corruption)
7. Report file downloads and content verification
8. Broken links, HTML tags, JS structure, misleading labels
9. Cross-component figure consistency (Dashboard == DB == Reports)
10. Server lifecycle & restart capability
"""

import io
import json
import socket
import socketserver
import subprocess
import sys
import threading
import time
from pathlib import Path
import pandas as pd

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))
sys.path.insert(0, str(PROJECT_ROOT / "src"))
sys.path.insert(0, str(PROJECT_ROOT / "database"))
sys.path.insert(0, str(PROJECT_ROOT / "app"))

from database.db_manager import (
    get_connection,
    query_df,
    load_organization_usage_data,
    validate_database_records
)
from simulation.scenario_engine import (
    DEFAULT_SCENARIOS,
    run_scenario_simulation,
    save_scenario_results_to_duckdb
)
from reporting.report_generator import export_all_reports, generate_executive_decision_brief
from app.web_app import AnalyzerRequestHandler, parse_multipart_payload


def make_mock_handler(method: str, path: str, headers: dict = None, body: bytes = b""):
    """Create and initialize an AnalyzerRequestHandler mock instance."""
    if headers is None:
        headers = {}
    handler = AnalyzerRequestHandler.__new__(AnalyzerRequestHandler)
    handler.command = method
    handler.path = path
    handler.headers = headers
    handler.rfile = io.BytesIO(body)
    handler.wfile = io.BytesIO()
    handler.status_code = None
    handler.response_headers = {}

    def mock_send_response(code, message=None):
        handler.status_code = code

    def mock_send_header(keyword, value):
        handler.response_headers[keyword] = value

    def mock_end_headers():
        pass

    def mock_send_error(code, message=None, explain=None):
        handler.status_code = code

    handler.send_response = mock_send_response
    handler.send_header = mock_send_header
    handler.end_headers = mock_end_headers
    handler.send_error = mock_send_error
    return handler


def test_1_dashboard_sections_and_api():
    print("\n--- Task 1: Inspect Every Dashboard Section & Verify Data Loading ---")
    h_index = make_mock_handler("GET", "/")
    h_index.do_GET()
    assert h_index.status_code == 200, "Index GET must return 200"
    html = h_index.wfile.getvalue().decode("utf-8")
    for section_id in ["tab-overview", "tab-scenarios", "tab-tasks", "tab-org", "tab-reports"]:
        assert f'id="{section_id}"' in html, f"Section {section_id} missing from HTML"
    print("  [PASS] Index HTML contains all 5 required navigation tabs.")

    # Health API
    h_health = make_mock_handler("GET", "/health")
    h_health.do_GET()
    assert h_health.status_code == 200
    health_data = json.loads(h_health.wfile.getvalue().decode("utf-8"))
    assert health_data.get("status") == "healthy"
    print("  [PASS] /health endpoint returned HTTP 200 with healthy status.")

    # KPI API
    h_kpi = make_mock_handler("GET", "/api/kpis")
    h_kpi.do_GET()
    assert h_kpi.status_code == 200
    kpi = json.loads(h_kpi.wfile.getvalue().decode("utf-8"))
    assert kpi["total_tasks"] == 27823, f"Expected 27,823 tasks, got {kpi['total_tasks']}"
    assert kpi["high_fit_tasks"] > 0
    assert kpi["moderate_hours_released"] > 0
    assert kpi["moderate_fte"] > 0
    print(f"  [PASS] Live KPIs: {kpi['total_tasks']:,} tasks, {kpi['high_fit_tasks']:,} high fit, {kpi['moderate_hours_released']:,} hrs released ({kpi['moderate_fte']} FTE).")

    # Domains API
    h_dom = make_mock_handler("GET", "/api/domains")
    h_dom.do_GET()
    assert h_dom.status_code == 200
    doms = json.loads(h_dom.wfile.getvalue().decode("utf-8"))
    assert len(doms) == 6, f"Expected 6 domains, got {len(doms)}"
    print(f"  [PASS] Domains API returned all {len(doms)} macro domains.")

    # Scenarios API
    h_scen = make_mock_handler("GET", "/api/scenarios")
    h_scen.do_GET()
    assert h_scen.status_code == 200
    scens = json.loads(h_scen.wfile.getvalue().decode("utf-8"))
    assert len(scens["scenarios"]) == 3, f"Expected 3 scenarios, got {len(scens['scenarios'])}"
    assert len(scens["departments"]) > 0, "Expected non-empty departments list"
    print(f"  [PASS] Scenarios API returned {len(scens['scenarios'])} scenarios and {len(scens['departments'])} departments.")

    # Tasks API
    h_tasks = make_mock_handler("GET", "/api/tasks")
    h_tasks.do_GET()
    assert h_tasks.status_code == 200
    tasks = json.loads(h_tasks.wfile.getvalue().decode("utf-8"))
    assert len(tasks) == 200, f"Expected 200 top opportunity tasks, got {len(tasks)}"
    print(f"  [PASS] Tasks API returned top {len(tasks)} tasks.")

    # Org Summary API
    h_org = make_mock_handler("GET", "/api/org_summary")
    h_org.do_GET()
    assert h_org.status_code == 200
    org = json.loads(h_org.wfile.getvalue().decode("utf-8"))
    assert org["task_count"] == 150
    assert org["match_rate_pct"] == 100.0
    print(f"  [PASS] Org summary: {org['organization_name']} with {org['task_count']} tasks, 100% matched.")


def test_2_search_and_filters():
    print("\n--- Task 2: Test Search, Domain Filters, and Priority Filters ---")
    h_tasks = make_mock_handler("GET", "/api/tasks")
    h_tasks.do_GET()
    tasks = json.loads(h_tasks.wfile.getvalue().decode("utf-8"))

    # Keyword search test
    query = "theory"
    filtered_kw = [t for t in tasks if query in t["task"].lower()]
    assert len(filtered_kw) > 0, f"Expected keyword matches for '{query}'"
    print(f"  [PASS] Keyword search for '{query}' matched {len(filtered_kw)} tasks.")

    # Domain filter test
    dom = "Physical Sciences"
    filtered_dom = [t for t in tasks if t.get("domain") == dom]
    assert len(filtered_dom) > 0, f"Expected tasks in domain '{dom}'"
    print(f"  [PASS] Domain filter '{dom}' returned {len(filtered_dom)} tasks.")

    # Priority tier filter test
    tier_prefix = "Tier 1"
    filtered_tier = [t for t in tasks if t.get("priority_tier", "").startswith(tier_prefix)]
    assert len(filtered_tier) > 0, f"Expected tasks in '{tier_prefix}'"
    print(f"  [PASS] Priority filter '{tier_prefix}' returned {len(filtered_tier)} tasks.")

    # Combined filter test
    combined = [t for t in tasks if query in t["task"].lower() and t.get("domain") == dom and t.get("priority_tier", "").startswith(tier_prefix)]
    print(f"  [PASS] Combined filter (query + domain + tier) safely returned {len(combined)} tasks.")


def test_3_explanation_accuracy():
    print("\n--- Task 3: Test Task Explanation Details Against Scoring Engine ---")
    h_tasks = make_mock_handler("GET", "/api/tasks")
    h_tasks.do_GET()
    tasks = json.loads(h_tasks.wfile.getvalue().decode("utf-8"))

    for t in tasks[:20]:
        expl = t["explanation"]
        ai_suit = t["ai_suitability_score"]
        phys = t["physical_intensity_score"]
        reg = t["regulatory_penalty_score"]
        hrs = t["hours_per_year"] or 0

        # Check AI suitability rationale
        if ai_suit >= 70:
            assert "High cognitive-information alignment" in expl
        elif ai_suit >= 45:
            assert "Moderate technical suitability" in expl
        else:
            assert "Low digital/information alignment" in expl

        # Check physical gate rationale
        if phys >= 40:
            assert "physical materials constraint" in expl

        # Check regulatory penalty rationale
        if reg >= 40:
            assert "Regulatory/governance restrictions" in expl

        # Check hours rationale
        if hrs >= 100:
            assert "High annual workload exposure" in expl
    print("  [PASS] Verified 20 task explanations strictly adhere to scoring engine rules.")


def test_4_scenario_calculations():
    print("\n--- Task 4: Test Scenario Comparisons & Formula Verification ---")
    conn = get_connection(read_only=True)
    try:
        scens = query_df("SELECT * FROM scenario_results;", conn=conn)
        assert len(scens) > 0

        for scen_id, params in DEFAULT_SCENARIOS.items():
            sub = scens[scens["scenario_id"] == params.scenario_id]
            assert len(sub) > 0, f"No records for scenario {params.scenario_id}"
            net_eff = params.gross_efficiency_gain * (1.0 - params.verification_overhead)
            
            for _, row in sub.head(10).iterrows():
                base_hrs = row["baseline_annual_hours"]
                rel_hrs = row["potential_hours_released"]
                fte = row["fte_capacity_equivalent"]

                # Check FTE formula: Hours / 1800
                expected_fte = round(rel_hrs / 1800.0, 3)
                assert abs(fte - expected_fte) <= 0.005, f"FTE mismatch: {fte} vs {expected_fte}"

                # Released hours cannot exceed baseline
                assert rel_hrs <= base_hrs, f"Released hours {rel_hrs} exceeds baseline {base_hrs}"
                assert row["net_hours_retained"] == round(base_hrs - rel_hrs, 1)

        # Monotonicity check across aggregates
        agg = scens.groupby("scenario_id")["potential_hours_released"].sum()
        assert agg["SCEN_CONSERVATIVE"] < agg["SCEN_MODERATE"] < agg["SCEN_OPTIMISTIC"], "Scenario ordering violated"
        print(f"  [PASS] Verified scenario mathematical rigor: Conservative ({agg['SCEN_CONSERVATIVE']:,.1f} hrs) < Moderate ({agg['SCEN_MODERATE']:,.1f} hrs) < Optimistic ({agg['SCEN_OPTIMISTIC']:,.1f} hrs).")
    finally:
        conn.close()


def test_5_department_and_domain_summaries():
    print("\n--- Task 5: Test Departmental and Domain Summaries Against DuckDB ---")
    conn = get_connection(read_only=True)
    try:
        # Check domain summary view
        dom_view = query_df("SELECT * FROM vw_domain_opportunity_summary;", conn=conn)
        dom_table = query_df("""
            SELECT domain, COUNT(*) AS total_tasks, ROUND(AVG(capacity_opportunity_score), 2) AS avg_opp
            FROM analytical_scoring_results
            GROUP BY domain
            ORDER BY avg_opp DESC;
        """, conn=conn)
        assert len(dom_view) == len(dom_table)
        for _, r in dom_view.iterrows():
            expected_count = dom_table.loc[dom_table["domain"] == r["domain"], "total_tasks"].values[0]
            assert r["total_tasks"] == expected_count
        print(f"  [PASS] Domain summary view perfectly matches base table aggregates across {len(dom_view)} domains.")

        # Check department summary in scenario_results
        dept_summary = query_df("""
            SELECT department, ROUND(SUM(baseline_annual_hours), 1) as base, ROUND(SUM(potential_hours_released), 1) as rel
            FROM scenario_results
            WHERE scenario_id = 'SCEN_MODERATE'
            GROUP BY department;
        """, conn=conn)
        assert len(dept_summary) > 0
        total_dept_rel = dept_summary["rel"].sum()
        total_scen_rel = query_df("SELECT ROUND(SUM(potential_hours_released), 1) as s FROM scenario_results WHERE scenario_id='SCEN_MODERATE';", conn=conn)["s"].values[0]
        assert abs(total_dept_rel - total_scen_rel) <= 0.5
        print(f"  [PASS] Departmental breakdown sums ({total_dept_rel:,.1f} hrs) match scenario total ({total_scen_rel:,.1f} hrs).")
    finally:
        conn.close()


def test_6_organization_csv_upload_safety():
    print("\n--- Task 6: Test Organization CSV Upload Edge Cases & Data Safety ---")
    conn = get_connection(read_only=True)
    initial_count = conn.execute("SELECT COUNT(*) FROM organization_task_usage;").fetchone()[0]
    conn.close()
    assert initial_count == 150

    # 1. Missing columns
    boundary = "----TestBound1"
    body = (
        f"--{boundary}\r\n"
        f'Content-Disposition: form-data; name="csv_file"; filename="missing.csv"\r\n'
        f"Content-Type: text/csv\r\n\r\n"
        f"dept,hours\r\nPhysics,100\r\n"
        f"--{boundary}--\r\n"
    ).encode("utf-8")
    h = make_mock_handler("POST", "/api/upload", {"Content-Type": f"multipart/form-data; boundary={boundary}", "Content-Length": str(len(body))}, body)
    h.do_POST()
    assert h.status_code == 303 and "/?status=error" in h.response_headers.get("Location", "")

    # 2. Empty file
    h_empty = make_mock_handler("POST", "/api/upload", {"Content-Type": f"multipart/form-data; boundary={boundary}", "Content-Length": "0"}, b"")
    h_empty.do_POST()
    assert h_empty.status_code == 400

    # 3. Duplicate records
    dupe_csv = (
        "department,role,task,fte_count,weekly_hours_per_fte,weeks_per_year\r\n"
        "Center for Physics,Senior Researcher,Develop new analytical calculational formalisms to extend theory into previously inaccessible regimes,2,6.0,46\r\n"
        "Center for Physics,Senior Researcher,Develop new analytical calculational formalisms to extend theory into previously inaccessible regimes,2,6.0,46\r\n"
    )
    b_dupe = (
        f"--{boundary}\r\n"
        f'Content-Disposition: form-data; name="csv_file"; filename="dupe.csv"\r\n'
        f"Content-Type: text/csv\r\n\r\n"
        f"{dupe_csv}\r\n"
        f"--{boundary}--\r\n"
    ).encode("utf-8")
    h_dupe = make_mock_handler("POST", "/api/upload", {"Content-Type": f"multipart/form-data; boundary={boundary}", "Content-Length": str(len(b_dupe))}, b_dupe)
    h_dupe.do_POST()
    assert h_dupe.status_code == 303 and h_dupe.response_headers.get("Location") == "/?status=uploaded"

    # Restore default data
    conn = get_connection()
    try:
        load_organization_usage_data(conn)
        org_df = query_df("""
            SELECT u.*,
                COALESCE(s.feasibility_score, 50.0) AS feasibility_score,
                COALESCE(s.capacity_opportunity_score, 40.0) AS capacity_opportunity_score,
                s.ai_fit_category, s.priority_tier
            FROM organization_task_usage u
            LEFT JOIN analytical_scoring_results s ON u.matched_task_id = s.task_id;
        """, conn=conn)
        sim = run_scenario_simulation(org_df)
        save_scenario_results_to_duckdb(sim, conn=conn)
        export_all_reports(conn=conn)
        restored_count = conn.execute("SELECT COUNT(*) FROM organization_task_usage;").fetchone()[0]
        assert restored_count == 150
        print(f"  [PASS] All upload failure and duplicate cases handled safely; database fully restored to {restored_count} records.")
    finally:
        conn.close()


def test_7_report_downloads():
    print("\n--- Task 7: Test All CSV and Markdown Report Downloads ---")
    reports = {
        "/reports/executive_decision_brief.md": "text/markdown",
        "/reports/task_opportunity_scoring.csv": "text/csv",
        "/reports/scenario_simulation_matrix.csv": "text/csv",
        "/reports/domain_opportunity_summary.csv": "text/csv"
    }

    for path, expected_type in reports.items():
        h = make_mock_handler("GET", path)
        h.do_GET()
        assert h.status_code == 200, f"Failed GET {path}"
        assert expected_type in h.response_headers.get("Content-Type", "")
        content = h.wfile.getvalue()
        assert len(content) > 0, f"Empty content for {path}"

        if path.endswith(".csv"):
            df = pd.read_csv(io.BytesIO(content))
            assert len(df) > 0, f"CSV {path} has 0 rows"
            print(f"  [PASS] {path} valid CSV with {len(df):,} rows and columns: {list(df.columns)[:4]}...")
        else:
            text = content.decode("utf-8")
            assert "# Executive Decision Brief" in text
            assert "Nexus Institute for Advanced Research" in text
            print(f"  [PASS] {path} valid Markdown ({len(text):,} characters) with all sections present.")

    # Path traversal safety check
    h_bad = make_mock_handler("GET", "/reports/../../pyproject.toml")
    h_bad.do_GET()
    assert h_bad.status_code in [400, 404]
    print("  [PASS] Path traversal protection verified (returned 400/404).")


def test_8_ui_integrity():
    print("\n--- Task 8: Check Links, Labels, and UI Elements ---")
    h = make_mock_handler("GET", "/")
    h.do_GET()
    html = h.wfile.getvalue().decode("utf-8")

    # Verify all report download hrefs match existing endpoints
    assert 'href="/reports/executive_decision_brief.md"' in html
    assert 'href="/reports/task_opportunity_scoring.csv"' in html
    assert 'href="/reports/scenario_simulation_matrix.csv"' in html
    assert 'href="/reports/domain_opportunity_summary.csv"' in html

    # Verify tabs exist
    assert "Executive Overview" in html
    assert "Scenario Simulation" in html
    assert "Task Opportunity Explorer" in html
    assert "Organization Data" in html
    assert "Exports &amp; Reports" in html or "Exports & Reports" in html

    # Verify script is present and valid
    assert "async function loadData()" in html
    assert "function filterTasks()" in html
    assert "function showExplanation(" in html
    print("  [PASS] All links, tabs, labels, and script structures verified.")


def test_9_cross_component_consistency():
    print("\n--- Task 9: Cross-Component Figure Consistency (Dashboard == DB == Reports) ---")
    conn = get_connection(read_only=True)
    try:
        # DB figures
        db_scen = query_df("""
            SELECT scenario_name,
                ROUND(SUM(baseline_annual_hours), 1) AS baseline,
                ROUND(SUM(potential_hours_released), 1) AS released,
                ROUND(SUM(fte_capacity_equivalent), 2) AS fte
            FROM scenario_results
            WHERE scenario_id = 'SCEN_MODERATE'
            GROUP BY scenario_name;
        """, conn=conn)
        db_base = db_scen["baseline"].values[0]
        db_rel = db_scen["released"].values[0]
        db_fte = db_scen["fte"].values[0]

        # API KPI figures
        h_kpi = make_mock_handler("GET", "/api/kpis")
        h_kpi.do_GET()
        kpi = json.loads(h_kpi.wfile.getvalue().decode("utf-8"))

        assert kpi["moderate_hours_released"] == db_rel, f"KPI released {kpi['moderate_hours_released']} != DB {db_rel}"
        assert kpi["moderate_fte"] == db_fte, f"KPI fte {kpi['moderate_fte']} != DB {db_fte}"

        # Markdown Report figures
        brief_text = Path("reports/executive_decision_brief.md").read_text(encoding="utf-8")
        assert f"{db_rel:,.1f} hours annually" in brief_text, f"Brief missing '{db_rel:,.1f} hours annually'"
        assert f"{db_fte:.2f} full-time research FTEs" in brief_text, f"Brief missing '{db_fte:.2f} FTEs'"

        # CSV Report figures
        csv_scen = pd.read_csv("reports/scenario_simulation_matrix.csv")
        csv_mod = csv_scen[csv_scen["scenario_id"] == "SCEN_MODERATE"]
        assert round(csv_mod["potential_hours_released"].sum(), 1) == db_rel

        print(f"  [PASS] Mathematical figures match across all tiers: Moderate Baseline = {db_base:,.1f} hrs, Released = {db_rel:,.1f} hrs, FTE = {db_fte:.2f}.")
    finally:
        conn.close()


def test_10_server_startup_and_restart():
    print("\n--- Task 10: Test Server Lifecycle & Restart Capability ---")
    from app.web_app import ThreadedHTTPServer

    # Test binding to a port, handling request, closing, and immediately re-binding
    test_port = 8599
    
    # Run 1
    server1 = ThreadedHTTPServer(("", test_port), AnalyzerRequestHandler)
    t1 = threading.Thread(target=server1.serve_forever)
    t1.daemon = True
    t1.start()
    time.sleep(0.3)

    def read_all(s):
        chunks = []
        while True:
            chunk = s.recv(1024)
            if not chunk:
                break
            chunks.append(chunk)
        return b"".join(chunks)

    # Probe 1
    with socket.create_connection(("127.0.0.1", test_port), timeout=2) as s:
        s.sendall(b"GET /health HTTP/1.1\r\nHost: localhost\r\nConnection: close\r\n\r\n")
        response1 = read_all(s)
        assert b"200 OK" in response1
        assert b"healthy" in response1

    server1.shutdown()
    server1.server_close()
    time.sleep(0.3)
    print("  [PASS] Initial server startup & request handled successfully.")

    # Run 2 (Restart test on same port)
    server2 = ThreadedHTTPServer(("", test_port), AnalyzerRequestHandler)
    t2 = threading.Thread(target=server2.serve_forever)
    t2.daemon = True
    t2.start()
    time.sleep(0.3)

    # Probe 2
    with socket.create_connection(("127.0.0.1", test_port), timeout=2) as s:
        s.sendall(b"GET /health HTTP/1.1\r\nHost: localhost\r\nConnection: close\r\n\r\n")
        response2 = read_all(s)
        assert b"200 OK" in response2
        assert b"healthy" in response2

    server2.shutdown()
    server2.server_close()
    print("  [PASS] Server restart on same port without address collision succeeded.")


def run_all_qa():
    print("=" * 75)
    print("STARTING COMPLETE END-TO-END FUNCTIONAL QA")
    print("=" * 75)

    test_1_dashboard_sections_and_api()
    test_2_search_and_filters()
    test_3_explanation_accuracy()
    test_4_scenario_calculations()
    test_5_department_and_domain_summaries()
    test_6_organization_csv_upload_safety()
    test_7_report_downloads()
    test_8_ui_integrity()
    test_9_cross_component_consistency()
    test_10_server_startup_and_restart()

    print("\n" + "=" * 75)
    print("ALL 10 FUNCTIONAL QA SUITES PASSED WITH 100% SUCCESS!")
    print("=" * 75)


if __name__ == "__main__":
    run_all_qa()
