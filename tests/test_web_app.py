"""
Tests for Python 3.13-Compatible Web Application & Multipart Upload Handler
"""

import io
import json
import sys
from pathlib import Path
from unittest.mock import MagicMock
import pytest

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))
sys.path.insert(0, str(PROJECT_ROOT / "src"))
sys.path.insert(0, str(PROJECT_ROOT / "database"))
sys.path.insert(0, str(PROJECT_ROOT / "app"))

from app.web_app import parse_multipart_payload, AnalyzerRequestHandler


# =============================================================================
# Unit Tests: parse_multipart_payload
# =============================================================================

def test_parse_multipart_payload_valid_csv():
    boundary = "----WebKitFormBoundary7MA4YWxkTrZu0gW"
    content_type = f"multipart/form-data; boundary={boundary}"

    body = (
        f"--{boundary}\r\n"
        f'Content-Disposition: form-data; name="csv_file"; filename="organization_tasks.csv"\r\n'
        f"Content-Type: text/csv\r\n\r\n"
        f"department,role,task,fte_count,weekly_hours_per_fte,weeks_per_year\r\n"
        f"Genomics,Postdoc,Sequence DNA,2,5.0,48\r\n"
        f"--{boundary}--\r\n"
    ).encode("utf-8")

    fields = parse_multipart_payload(content_type, body)
    assert "csv_file" in fields
    assert fields["csv_file"]["filename"] == "organization_tasks.csv"
    assert b"Sequence DNA" in fields["csv_file"]["payload"]


def test_parse_multipart_payload_empty_body():
    boundary = "----WebKitFormBoundaryEmpty"
    content_type = f"multipart/form-data; boundary={boundary}"
    fields = parse_multipart_payload(content_type, b"")
    assert fields == {}


def test_parse_multipart_payload_missing_content_type():
    fields = parse_multipart_payload("", b"dummy data")
    assert fields == {}


def test_parse_multipart_payload_multiple_fields():
    boundary = "----WebKitFormBoundaryMulti"
    content_type = f"multipart/form-data; boundary={boundary}"

    body = (
        f"--{boundary}\r\n"
        f'Content-Disposition: form-data; name="org_name"\r\n\r\n'
        f"Global Science Lab\r\n"
        f"--{boundary}\r\n"
        f'Content-Disposition: form-data; name="csv_file"; filename="tasks.csv"\r\n'
        f"Content-Type: text/csv\r\n\r\n"
        f"task,hours\r\n"
        f"--{boundary}--\r\n"
    ).encode("utf-8")

    fields = parse_multipart_payload(content_type, body)
    assert "org_name" in fields
    assert fields["org_name"]["payload"] == b"Global Science Lab"
    assert "csv_file" in fields
    assert fields["csv_file"]["filename"] == "tasks.csv"


# =============================================================================
# Integration Tests: AnalyzerRequestHandler (Mocked Socket)
# =============================================================================

def make_handler(method: str, path: str, headers: dict = None, body: bytes = b""):
    """Create a mock-initialized instance of AnalyzerRequestHandler."""
    if headers is None:
        headers = {}

    handler = AnalyzerRequestHandler.__new__(AnalyzerRequestHandler)
    handler.command = method
    handler.path = path
    handler.headers = headers
    handler.rfile = io.BytesIO(body)
    handler.wfile = io.BytesIO()

    # Mock response tracking
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


def test_http_get_index():
    handler = make_handler("GET", "/")
    handler.do_GET()
    assert handler.status_code == 200
    assert "text/html" in handler.response_headers.get("Content-Type", "")
    output = handler.wfile.getvalue().decode("utf-8")
    assert "Research Task AI Fit & Capacity Opportunity Analyzer" in output


def test_http_get_api_domains():
    handler = make_handler("GET", "/api/domains")
    handler.do_GET()
    assert handler.status_code == 200
    assert handler.response_headers.get("Content-Type") == "application/json"
    data = json.loads(handler.wfile.getvalue().decode("utf-8"))
    assert isinstance(data, list)
    assert len(data) > 0


def test_http_get_api_scenarios():
    handler = make_handler("GET", "/api/scenarios")
    handler.do_GET()
    assert handler.status_code == 200
    data = json.loads(handler.wfile.getvalue().decode("utf-8"))
    assert "scenarios" in data
    assert "departments" in data
    assert len(data["scenarios"]) == 3


def test_http_get_api_tasks():
    handler = make_handler("GET", "/api/tasks")
    handler.do_GET()
    assert handler.status_code == 200
    data = json.loads(handler.wfile.getvalue().decode("utf-8"))
    assert isinstance(data, list)
    assert len(data) > 0


def test_http_get_reports_file():
    handler = make_handler("GET", "/reports/executive_decision_brief.md")
    handler.do_GET()
    assert handler.status_code == 200
    assert "text/markdown" in handler.response_headers.get("Content-Type", "")


def test_http_post_upload_invalid_content_type():
    handler = make_handler("POST", "/api/upload", headers={"Content-Type": "application/json"}, body=b"{}")
    handler.do_POST()
    assert handler.status_code == 400


def test_http_post_upload_empty_body():
    boundary = "----BoundaryEmpty"
    headers = {
        "Content-Type": f"multipart/form-data; boundary={boundary}",
        "Content-Length": "0"
    }
    handler = make_handler("POST", "/api/upload", headers=headers, body=b"")
    handler.do_POST()
    assert handler.status_code == 400


def test_http_post_upload_missing_file_field():
    boundary = "----BoundaryNoFile"
    body = (
        f"--{boundary}\r\n"
        f'Content-Disposition: form-data; name="notes"\r\n\r\n'
        f"Some notes\r\n"
        f"--{boundary}--\r\n"
    ).encode("utf-8")

    headers = {
        "Content-Type": f"multipart/form-data; boundary={boundary}",
        "Content-Length": str(len(body))
    }
    handler = make_handler("POST", "/api/upload", headers=headers, body=body)
    handler.do_POST()
    assert handler.status_code == 400


def test_http_post_upload_valid_csv_redirects():
    boundary = "----BoundaryValid"
    csv_content = (
        "department,role,task,fte_count,weekly_hours_per_fte,weeks_per_year\r\n"
        "Center for Physics,Senior Researcher,Develop new analytical calculational formalisms to extend theory into previously inaccessible regimes,2,6.0,46\r\n"
    )
    body = (
        f"--{boundary}\r\n"
        f'Content-Disposition: form-data; name="csv_file"; filename="upload_test.csv"\r\n'
        f"Content-Type: text/csv\r\n\r\n"
        f"{csv_content}\r\n"
        f"--{boundary}--\r\n"
    ).encode("utf-8")

    headers = {
        "Content-Type": f"multipart/form-data; boundary={boundary}",
        "Content-Length": str(len(body))
    }
    handler = make_handler("POST", "/api/upload", headers=headers, body=body)
    handler.do_POST()
    assert handler.status_code == 303
    assert handler.response_headers.get("Location") == "/?status=uploaded"

    # Restore default synthetic organization data and scenario results for test isolation
    from database.db_manager import get_connection, load_organization_usage_data, query_df
    from simulation.scenario_engine import run_scenario_simulation, save_scenario_results_to_duckdb
    from reporting.report_generator import export_all_reports

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
        sim_results = run_scenario_simulation(org_df)
        save_scenario_results_to_duckdb(sim_results, conn=conn)
        export_all_reports(conn=conn)
    finally:
        conn.close()


def test_http_get_api_kpis():
    handler = make_handler("GET", "/api/kpis")
    handler.do_GET()
    assert handler.status_code == 200
    assert handler.response_headers.get("Content-Type") == "application/json"
    data = json.loads(handler.wfile.getvalue().decode("utf-8"))
    assert "total_tasks" in data
    assert "high_fit_tasks" in data
    assert "moderate_hours_released" in data
    assert "moderate_fte" in data
    assert "constrained_tasks" in data
    assert data["total_tasks"] == 27823
    assert data["moderate_hours_released"] > 0


def test_http_get_api_org_summary():
    handler = make_handler("GET", "/api/org_summary")
    handler.do_GET()
    assert handler.status_code == 200
    data = json.loads(handler.wfile.getvalue().decode("utf-8"))
    assert "organization_name" in data
    assert "task_count" in data
    assert "matched_count" in data
    assert data["task_count"] == 150
    assert data["matched_count"] == 150


def test_http_post_upload_missing_required_columns_does_not_corrupt_data():
    boundary = "----BoundaryMissingCol"
    csv_content = (
        "wrong_col1,wrong_col2\r\n"
        "Value 1,Value 2\r\n"
    )
    body = (
        f"--{boundary}\r\n"
        f'Content-Disposition: form-data; name="csv_file"; filename="bad_cols.csv"\r\n'
        f"Content-Type: text/csv\r\n\r\n"
        f"{csv_content}\r\n"
        f"--{boundary}--\r\n"
    ).encode("utf-8")

    headers = {
        "Content-Type": f"multipart/form-data; boundary={boundary}",
        "Content-Length": str(len(body))
    }
    handler = make_handler("POST", "/api/upload", headers=headers, body=body)
    handler.do_POST()
    assert handler.status_code == 303
    assert "/?status=error" in handler.response_headers.get("Location", "")
    assert "Missing+required+columns" in handler.response_headers.get("Location", "") or "Missing%20required%20columns" in handler.response_headers.get("Location", "")

    # Ensure DB was NOT corrupted
    from database.db_manager import get_connection
    conn = get_connection(read_only=True)
    try:
        count = conn.execute("SELECT COUNT(*) FROM organization_task_usage;").fetchone()[0]
        assert count == 150, f"Expected 150 records preserved, found {count}"
    finally:
        conn.close()


def test_http_post_upload_empty_csv_file():
    boundary = "----BoundaryEmptyFile"
    body = (
        f"--{boundary}\r\n"
        f'Content-Disposition: form-data; name="csv_file"; filename="empty.csv"\r\n'
        f"Content-Type: text/csv\r\n\r\n"
        f"\r\n"
        f"--{boundary}--\r\n"
    ).encode("utf-8")

    headers = {
        "Content-Type": f"multipart/form-data; boundary={boundary}",
        "Content-Length": str(len(body))
    }
    handler = make_handler("POST", "/api/upload", headers=headers, body=body)
    handler.do_POST()
    assert handler.status_code == 400

    # Ensure DB preserved
    from database.db_manager import get_connection
    conn = get_connection(read_only=True)
    try:
        count = conn.execute("SELECT COUNT(*) FROM organization_task_usage;").fetchone()[0]
        assert count == 150
    finally:
        conn.close()


def test_http_post_upload_duplicate_records():
    boundary = "----BoundaryDupes"
    csv_content = (
        "department,role,task,fte_count,weekly_hours_per_fte,weeks_per_year\r\n"
        "Center for Physics,Senior Researcher,Develop new analytical calculational formalisms to extend theory into previously inaccessible regimes,2,6.0,46\r\n"
        "Center for Physics,Senior Researcher,Develop new analytical calculational formalisms to extend theory into previously inaccessible regimes,2,6.0,46\r\n"
    )
    body = (
        f"--{boundary}\r\n"
        f'Content-Disposition: form-data; name="csv_file"; filename="dupes.csv"\r\n'
        f"Content-Type: text/csv\r\n\r\n"
        f"{csv_content}\r\n"
        f"--{boundary}--\r\n"
    ).encode("utf-8")

    headers = {
        "Content-Type": f"multipart/form-data; boundary={boundary}",
        "Content-Length": str(len(body))
    }
    handler = make_handler("POST", "/api/upload", headers=headers, body=body)
    handler.do_POST()
    assert handler.status_code == 303
    assert handler.response_headers.get("Location") == "/?status=uploaded"

    # Restore default synthetic data
    from database.db_manager import get_connection, load_organization_usage_data, query_df
    from simulation.scenario_engine import run_scenario_simulation, save_scenario_results_to_duckdb
    from reporting.report_generator import export_all_reports

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
        sim_results = run_scenario_simulation(org_df)
        save_scenario_results_to_duckdb(sim_results, conn=conn)
        export_all_reports(conn=conn)
    finally:
        conn.close()


def test_http_get_reports_file_path_traversal_blocked():
    handler = make_handler("GET", "/reports/../app/web_app.py")
    handler.do_GET()
    assert handler.status_code == 400


def test_http_get_reports_nonexistent_returns_404():
    handler = make_handler("GET", "/reports/non_existent_file.csv")
    handler.do_GET()
    assert handler.status_code == 404


def test_http_get_health_endpoint():
    handler = make_handler("GET", "/health")
    handler.do_GET()
    assert handler.status_code == 200
    assert handler.response_headers.get("Content-Type") == "application/json"
    data = json.loads(handler.wfile.getvalue().decode("utf-8"))
    assert data["status"] == "healthy"
    assert "service" in data


def test_port_environment_variable_configuration(monkeypatch):
    import os
    monkeypatch.setenv("PORT", "9999")
    port = int(os.environ.get("PORT", 8501))
    assert port == 9999

    monkeypatch.delenv("PORT", raising=False)
    default_port = int(os.environ.get("PORT", 8501))
    assert default_port == 8501


def test_threaded_http_server_concurrent_requests():
    import socket
    import threading
    import time
    from app.web_app import ThreadedHTTPServer, AnalyzerRequestHandler

    test_port = 8598
    server = ThreadedHTTPServer(("", test_port), AnalyzerRequestHandler)
    server_thread = threading.Thread(target=server.serve_forever)
    server_thread.daemon = True
    server_thread.start()
    time.sleep(0.3)

    results = []

    def make_req():
        try:
            with socket.create_connection(("127.0.0.1", test_port), timeout=3) as s:
                s.sendall(b"GET /health HTTP/1.1\r\nHost: localhost\r\nConnection: close\r\n\r\n")
                chunks = []
                while True:
                    part = s.recv(1024)
                    if not part:
                        break
                    chunks.append(part)
                resp = b"".join(chunks)
                if b"200 OK" in resp and b"healthy" in resp:
                    results.append(True)
                else:
                    results.append(False)
        except Exception:
            results.append(False)

    threads = [threading.Thread(target=make_req) for _ in range(4)]
    for t in threads:
        t.start()
    for t in threads:
        t.join(timeout=3)

    server.shutdown()
    server.server_close()

    assert len(results) == 4
    assert all(results)


