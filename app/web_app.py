"""
Interactive Local-First Web Dashboard & Analytical Server
=========================================================
Provides a local, zero-dependency web interface for:
- Viewing executive KPI cards (live from DuckDB)
- Interactive scenario comparisons (Conservative / Moderate / Optimistic)
- Task opportunity exploration with search, domain filtering, and scoring explanations
- Uploading organization CSV data
- Exporting decision briefs and reports
"""

import email
from email import policy
from http.cookies import SimpleCookie
import http.server
import io
import json
import os
import re
import socketserver
import sys
import threading
import time
import urllib.parse
import uuid
from pathlib import Path
from typing import Any, Dict, Optional, Tuple
import duckdb

# Ensure project root, src, and database are on Python path
PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))
sys.path.insert(0, str(PROJECT_ROOT / "src"))
sys.path.insert(0, str(PROJECT_ROOT / "database"))

from database.db_manager import (
    get_connection,
    query_df,
    load_organization_usage_data,
)
from simulation.scenario_engine import (
    run_scenario_simulation,
    save_scenario_results_to_duckdb,
)
from reporting.report_generator import export_all_reports

# Resolve reports directory to absolute path so it works regardless of CWD
REPORTS_DIR = PROJECT_ROOT / "reports"

HTML_TEMPLATE = """<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Research Task AI Fit & Capacity Opportunity Analyzer</title>
    <style>
        :root {
            --primary: #2563eb;
            --primary-dark: #1d4ed8;
            --bg: #f8fafc;
            --card-bg: #ffffff;
            --text-main: #0f172a;
            --text-muted: #64748b;
            --border: #e2e8f0;
            --success: #10b981;
            --warning: #f59e0b;
            --danger: #ef4444;
        }
        * { box-sizing: border-box; margin: 0; padding: 0; }
        body { font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif; background: var(--bg); color: var(--text-main); line-height: 1.5; }
        .container { max-width: 1300px; margin: 0 auto; padding: 24px; }
        header { background: #ffffff; border-bottom: 1px solid var(--border); padding: 18px 24px; margin-bottom: 24px; }
        .header-content { max-width: 1300px; margin: 0 auto; display: flex; justify-content: space-between; align-items: center; }
        .brand { font-size: 1.25rem; font-weight: 700; color: #1e293b; display: flex; align-items: center; gap: 8px; }
        .badge { background: #dbeafe; color: #1e40af; font-size: 0.75rem; padding: 4px 10px; border-radius: 9999px; font-weight: 600; }
        .nav-tabs { display: flex; gap: 8px; margin-bottom: 24px; border-bottom: 1px solid var(--border); padding-bottom: 8px; }
        .tab-btn { background: none; border: none; padding: 10px 18px; font-size: 0.95rem; font-weight: 600; color: var(--text-muted); cursor: pointer; border-radius: 6px; transition: all 0.2s; }
        .tab-btn:hover { background: #e2e8f0; color: var(--text-main); }
        .tab-btn.active { background: var(--primary); color: #ffffff; }
        .tab-pane { display: none; }
        .tab-pane.active { display: block; }
        .kpi-grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(220px, 1fr)); gap: 16px; margin-bottom: 24px; }
        .card { background: var(--card-bg); border: 1px solid var(--border); border-radius: 8px; padding: 20px; box-shadow: 0 1px 3px rgba(0,0,0,0.05); }
        .card h3 { font-size: 0.85rem; color: var(--text-muted); text-transform: uppercase; letter-spacing: 0.05em; margin-bottom: 8px; }
        .card .value { font-size: 1.85rem; font-weight: 700; color: var(--text-main); }
        .card .sub { font-size: 0.8rem; color: var(--text-muted); margin-top: 4px; }
        table { width: 100%; border-collapse: collapse; margin-top: 12px; font-size: 0.9rem; }
        th, td { padding: 12px 14px; text-align: left; border-bottom: 1px solid var(--border); }
        th { background: #f1f5f9; font-weight: 600; color: #475569; position: sticky; top: 0; }
        tr:hover { background: #f8fafc; }
        .btn { display: inline-block; background: var(--primary); color: #ffffff; padding: 8px 16px; border-radius: 6px; text-decoration: none; font-weight: 600; font-size: 0.875rem; border: none; cursor: pointer; }
        .btn:hover { background: var(--primary-dark); }
        .btn-outline { background: transparent; border: 1px solid var(--border); color: var(--text-main); }
        .btn-outline:hover { background: #f1f5f9; }
        .search-bar { display: flex; gap: 12px; margin-bottom: 16px; flex-wrap: wrap; }
        .search-input { flex: 1; min-width: 260px; padding: 8px 12px; border: 1px solid var(--border); border-radius: 6px; font-size: 0.9rem; }
        select.filter-select { padding: 8px 12px; border: 1px solid var(--border); border-radius: 6px; font-size: 0.9rem; background: #fff; }
        .tier-pill { display: inline-block; padding: 3px 8px; border-radius: 4px; font-size: 0.75rem; font-weight: 700; }
        .tier-1 { background: #dcfce7; color: #166534; }
        .tier-2 { background: #e0f2fe; color: #075985; }
        .tier-3 { background: #fef3c7; color: #92400e; }
        .tier-4 { background: #f1f5f9; color: #64748b; }
        .upload-box { border: 2px dashed var(--border); border-radius: 8px; padding: 32px; text-align: center; background: #fff; margin-bottom: 24px; }
        .modal { display: none; position: fixed; top: 0; left: 0; width: 100%; height: 100%; background: rgba(0,0,0,0.5); align-items: center; justify-content: center; z-index: 1000; }
        .modal-content { background: #fff; padding: 24px; border-radius: 8px; max-width: 600px; width: 90%; max-height: 80vh; overflow-y: auto; }
        .modal-header { display: flex; justify-content: space-between; align-items: center; margin-bottom: 16px; }
        .close-btn { background: none; border: none; font-size: 1.5rem; cursor: pointer; }
        .alert { padding: 12px 16px; border-radius: 6px; margin-bottom: 16px; font-size: 0.9rem; }
        .alert-success { background: #dcfce7; color: #166534; border: 1px solid #bbf7d0; }
        .alert-error { background: #fee2e2; color: #991b1b; border: 1px solid #fecaca; }
        .loading { color: var(--text-muted); font-style: italic; }
    </style>
</head>
<body>
    <header>
        <div class="header-content">
            <div class="brand">
                <span>⚡ Research Task AI Fit & Capacity Opportunity Analyzer</span>
                <span id="session-badge" class="badge">DuckDB Local-First</span>
            </div>
            <div style="display: flex; align-items: center; gap: 8px;">
                <a id="header-reset-btn" href="/api/reset" class="btn btn-outline" style="display: none; font-size: 0.8rem; padding: 6px 12px;">Reset to Baseline</a>
                <a href="/reports/executive_decision_brief.md" target="_blank" class="btn btn-outline">View Decision Brief</a>
            </div>
        </div>
    </header>

    <div class="container">
        <div id="status-banner"></div>

        <div class="nav-tabs">
            <button class="tab-btn active" onclick="openTab('tab-overview', this)">Executive Overview</button>
            <button class="tab-btn" onclick="openTab('tab-scenarios', this)">Scenario Simulation</button>
            <button class="tab-btn" onclick="openTab('tab-tasks', this)">Task Opportunity Explorer</button>
            <button class="tab-btn" onclick="openTab('tab-org', this)">Organization Data</button>
            <button class="tab-btn" onclick="openTab('tab-reports', this)">Exports &amp; Reports</button>
        </div>

        <!-- TAB 1: OVERVIEW -->
        <div id="tab-overview" class="tab-pane active">
            <div class="kpi-grid">
                <div class="card">
                    <h3>Evaluated Task Catalog</h3>
                    <div class="value" id="kpi-tasks"><span class="loading">...</span></div>
                    <div class="sub">SciNet peer-reviewed tasks</div>
                </div>
                <div class="card">
                    <h3>High-Fit Opportunities</h3>
                    <div class="value" style="color: var(--primary);" id="kpi-high-fit"><span class="loading">...</span></div>
                    <div class="sub">Tasks with feasibility score &ge; 60</div>
                </div>
                <div class="card">
                    <h3>Moderate Capacity Release</h3>
                    <div class="value" style="color: var(--success);" id="kpi-released-hrs"><span class="loading">...</span></div>
                    <div class="sub">Annual capacity unlocked (Moderate scenario)</div>
                </div>
                <div class="card">
                    <h3>FTE Capacity Equivalent</h3>
                    <div class="value" style="color: var(--success);" id="kpi-fte"><span class="loading">...</span></div>
                    <div class="sub">Repurposed to core research</div>
                </div>
                <div class="card">
                    <h3>Constrained / Gated Tasks</h3>
                    <div class="value" style="color: var(--danger);" id="kpi-constrained"><span class="loading">...</span></div>
                    <div class="sub">Physical lab or strict IRB gates</div>
                </div>
            </div>

            <div class="card">
                <h2>Macro Domain Opportunity Landscape (SciNet Benchmark)</h2>
                <div id="domain-table-container" class="loading">Loading domain landscape...</div>
            </div>
        </div>

        <!-- TAB 2: SCENARIOS -->
        <div id="tab-scenarios" class="tab-pane">
            <div class="card" style="margin-bottom: 24px;">
                <h2>Capacity Release Scenario Comparison Matrix</h2>
                <p style="color: var(--text-muted); margin-bottom: 16px;" id="scenario-description" class="loading">
                    Loading scenario parameters...
                </p>
                <div id="scenario-matrix-container" class="loading">Loading scenarios...</div>
            </div>

            <div class="card">
                <h2>Department-Level Capacity Release (Moderate Scenario)</h2>
                <div id="dept-table-container" class="loading">Loading departments...</div>
            </div>
        </div>

        <!-- TAB 3: TASKS EXPLORER -->
        <div id="tab-tasks" class="tab-pane">
            <div class="card">
                <h2>Task-Level Opportunity Explorer</h2>
                <p style="color: var(--text-muted); margin-bottom: 16px;">
                    Inspect multi-factor scores, physical gates, and transparent natural-language justifications for all tasks.
                </p>
                <div class="search-bar">
                    <input type="text" id="task-search" class="search-input"
                           placeholder="Search tasks by keyword (e.g. hypothesis, model, data, synthesis)..."
                           oninput="filterTasks()">
                    <select id="domain-filter" class="filter-select" onchange="filterTasks()">
                        <option value="">All Domains</option>
                    </select>
                    <select id="tier-filter" class="filter-select" onchange="filterTasks()">
                        <option value="">All Priority Tiers</option>
                        <option value="Tier 1">Tier 1: Immediate Opportunity</option>
                        <option value="Tier 2">Tier 2: Targeted Augmentation</option>
                        <option value="Tier 3">Tier 3: Exploratory / Minor</option>
                        <option value="Tier 4">Tier 4: Deprioritized / Blocked</option>
                    </select>
                </div>
                <div id="task-count-label" style="font-size: 0.85rem; color: var(--text-muted); margin-bottom: 8px;"></div>
                <div id="tasks-table-container" style="max-height: 550px; overflow-y: auto;" class="loading">
                    Loading task catalog...
                </div>
            </div>
        </div>

        <!-- TAB 4: ORGANIZATION DATA -->
        <div id="tab-org" class="tab-pane">
            <div class="card">
                <h2>Organization Task Usage Management</h2>
                <p style="color: var(--text-muted); margin-bottom: 20px;">
                    Currently loaded: <strong id="org-name" class="loading">Loading...</strong>.
                    You can upload your own organization's CSV task usage file below to re-evaluate capacity release immediately.
                </p>
                <div class="upload-box">
                    <form action="/api/upload" method="post" enctype="multipart/form-data">
                        <input type="file" name="csv_file" accept=".csv" required style="margin-bottom: 16px;"><br>
                        <button type="submit" class="btn">Upload &amp; Run Analysis</button>
                    </form>
                </div>
                <p style="font-size: 0.85rem; color: var(--text-muted);">
                    CSV Format Requirement: Columns must include
                    <code>department, role, task, fte_count, weekly_hours_per_fte, weeks_per_year</code>.
                </p>
                <div id="org-stats-container" style="margin-top: 20px;"></div>
            </div>
        </div>

        <!-- TAB 5: REPORTS & EXPORTS -->
        <div id="tab-reports" class="tab-pane">
            <div class="card">
                <h2>Decision Brief &amp; Data Exports</h2>
                <p style="color: var(--text-muted); margin-bottom: 24px;">
                    Download ready-to-use executive briefs and analytical CSVs directly:
                </p>
                <div style="display: grid; grid-template-columns: repeat(auto-fit, minmax(280px, 1fr)); gap: 16px;">
                    <div class="card" style="background: #f8fafc;">
                        <h3>Executive Decision Brief</h3>
                        <p style="font-size: 0.85rem; color: var(--text-muted); margin: 8px 0 16px 0;">Complete C-level strategic evaluation with scenario tables and recommendations.</p>
                        <a href="/reports/executive_decision_brief.md" download class="btn">Download Markdown (.md)</a>
                    </div>
                    <div class="card" style="background: #f8fafc;">
                        <h3>Task Opportunity Scoring</h3>
                        <p style="font-size: 0.85rem; color: var(--text-muted); margin: 8px 0 16px 0;">All scored tasks with dimensional scores, physical gates, and explanations.</p>
                        <a href="/reports/task_opportunity_scoring.csv" download class="btn">Download CSV (.csv)</a>
                    </div>
                    <div class="card" style="background: #f8fafc;">
                        <h3>Scenario Simulation Matrix</h3>
                        <p style="font-size: 0.85rem; color: var(--text-muted); margin: 8px 0 16px 0;">Department and task-level hours released across all three scenarios.</p>
                        <a href="/reports/scenario_simulation_matrix.csv" download class="btn">Download CSV (.csv)</a>
                    </div>
                    <div class="card" style="background: #f8fafc;">
                        <h3>Domain Summary Benchmark</h3>
                        <p style="font-size: 0.85rem; color: var(--text-muted); margin: 8px 0 16px 0;">High-level macro capacity statistics by scientific domain.</p>
                        <a href="/reports/domain_opportunity_summary.csv" download class="btn">Download CSV (.csv)</a>
                    </div>
                </div>
            </div>
        </div>
    </div>

    <!-- EXPLANATION MODAL -->
    <div id="modal" class="modal">
        <div class="modal-content">
            <div class="modal-header">
                <h3 id="modal-title">Task Scoring Explanation</h3>
                <button class="close-btn" onclick="closeModal()">&times;</button>
            </div>
            <div id="modal-body" style="font-size: 0.95rem; line-height: 1.6; color: #334155;"></div>
        </div>
    </div>

    <script>
        let allTasks = [];
        let filteredTasks = [];

        function openTab(tabId, btn) {
            document.querySelectorAll('.tab-pane').forEach(el => el.classList.remove('active'));
            document.querySelectorAll('.tab-btn').forEach(el => el.classList.remove('active'));
            document.getElementById(tabId).classList.add('active');
            if (btn) btn.classList.add('active');
        }

        function escapeHtml(str) {
            if (str === null || str === undefined) return '';
            return String(str)
                .replace(/&/g, '&amp;')
                .replace(/</g, '&lt;')
                .replace(/>/g, '&gt;')
                .replace(/"/g, '&quot;');
        }

        async function loadData() {
            try {
                // 1. Live KPIs from DuckDB
                const resKpi = await fetch('/api/kpis');
                if (!resKpi.ok) throw new Error('KPI endpoint returned ' + resKpi.status);
                const kpi = await resKpi.json();
                document.getElementById('kpi-tasks').textContent = kpi.total_tasks.toLocaleString();
                document.getElementById('kpi-high-fit').textContent = kpi.high_fit_tasks.toLocaleString();
                document.getElementById('kpi-released-hrs').textContent = kpi.moderate_hours_released.toLocaleString() + ' hrs';
                document.getElementById('kpi-fte').textContent = kpi.moderate_fte + ' FTE';
                document.getElementById('kpi-constrained').textContent = kpi.constrained_tasks.toLocaleString();

                // 2. Domain overview
                const resDom = await fetch('/api/domains');
                const domains = await resDom.json();

                // Populate domain filter dynamically from live data
                const domSelect = document.getElementById('domain-filter');
                // Clear existing options (keep "All Domains")
                while (domSelect.options.length > 1) domSelect.remove(1);
                domains.forEach(d => {
                    const opt = document.createElement('option');
                    opt.value = d.domain;
                    opt.textContent = d.domain;
                    domSelect.appendChild(opt);
                });

                let domHtml = '<table><thead><tr><th>Domain</th><th>Total Tasks</th><th>Avg Time Exposure</th><th>Avg AI Suitability</th><th>Physical Intensity Gate</th><th>Regulatory Penalty</th><th>Avg Opportunity Score</th></tr></thead><tbody>';
                domains.forEach(d => {
                    domHtml += `<tr><td><strong>${escapeHtml(d.domain)}</strong></td><td>${Number(d.total_tasks).toLocaleString()}</td><td>${d.avg_time_exposure}</td><td>${d.avg_ai_suitability}</td><td>${d.avg_physical_intensity}</td><td>${d.avg_regulatory_penalty}</td><td><strong>${d.avg_opportunity_score}</strong></td></tr>`;
                });
                domHtml += '</tbody></table>';
                document.getElementById('domain-table-container').innerHTML = domHtml;

                // 3. Scenarios
                const resScen = await fetch('/api/scenarios');
                const scenData = await resScen.json();

                let scenHtml = '<table><thead><tr><th>Scenario</th><th>Adoption Rate</th><th>Gross Efficiency</th><th>Verification Friction</th><th>Baseline Annual Hours</th><th>Potential Hours Released</th><th>FTE Equivalent</th><th>Net Capacity Release (%)</th></tr></thead><tbody>';
                scenData.scenarios.forEach(s => {
                    scenHtml += `<tr>
                        <td><strong>${escapeHtml(s.scenario_name)}</strong></td>
                        <td>${escapeHtml(String(s.adoption_rate_pct))}%</td>
                        <td>${escapeHtml(String(s.gross_efficiency_pct))}%</td>
                        <td>${escapeHtml(String(s.verification_overhead_pct))}%</td>
                        <td>${Number(s.total_baseline_hours).toLocaleString()} hrs</td>
                        <td style="color: var(--success); font-weight:700;">${Number(s.total_hours_released).toLocaleString()} hrs</td>
                        <td><strong>${s.total_fte_equivalent} FTE</strong></td>
                        <td>${s.overall_hours_released_pct}%</td>
                    </tr>`;
                });
                scenHtml += '</tbody></table>';
                document.getElementById('scenario-matrix-container').innerHTML = scenHtml;
                document.getElementById('scenario-description').textContent =
                    'Compares potential workload capacity release across ' +
                    scenData.scenarios.map(s => s.scenario_name).join(', ') +
                    '. Adoption rates, efficiency gains, and verification overhead are sourced live from the scenario engine.';

                let deptHtml = '<table><thead><tr><th>Department</th><th>Baseline Annual Hours</th><th>Potential Hours Released</th><th>FTE Equivalent</th></tr></thead><tbody>';
                if (scenData.departments.length === 0) {
                    deptHtml += '<tr><td colspan="4" style="color: var(--text-muted);">No departmental data available. Upload an organization CSV to see department-level breakdowns.</td></tr>';
                } else {
                    scenData.departments.forEach(d => {
                        deptHtml += `<tr><td>${escapeHtml(d.department)}</td><td>${Number(d.baseline_hours).toLocaleString()} hrs</td><td style="color: var(--success); font-weight:600;">${Number(d.hours_released).toLocaleString()} hrs</td><td>${d.fte_equivalent} FTE</td></tr>`;
                    });
                }
                deptHtml += '</tbody></table>';
                document.getElementById('dept-table-container').innerHTML = deptHtml;

                // 4. Top tasks
                const resTasks = await fetch('/api/tasks');
                allTasks = await resTasks.json();
                filteredTasks = allTasks.map((t, idx) => ({ ...t, _orig_idx: idx }));
                renderTasks(filteredTasks);

                // 5. Org summary
                const resOrg = await fetch('/api/org_summary');
                const orgData = await resOrg.json();
                document.getElementById('org-name').textContent =
                    escapeHtml(orgData.organization_name) + ' (' + orgData.task_count + ' task allocations)';

                // Update session indicator badge in header
                const sessionBadge = document.getElementById('session-badge');
                const resetBtn = document.getElementById('header-reset-btn');
                if (orgData.is_custom_upload) {
                    sessionBadge.textContent = 'Custom Session Active';
                    sessionBadge.style.background = '#fef3c7';
                    sessionBadge.style.color = '#92400e';
                    resetBtn.style.display = 'inline-block';
                } else {
                    sessionBadge.textContent = 'Nexus Baseline Dataset';
                    sessionBadge.style.background = '#dbeafe';
                    sessionBadge.style.color = '#1e40af';
                    resetBtn.style.display = 'none';
                }

                let orgStats = '';
                if (orgData.is_custom_upload) {
                    orgStats += '<div style="margin-bottom: 16px; padding: 12px 16px; background: #eff6ff; border: 1px solid #bfdbfe; border-radius: 6px; display: flex; justify-content: space-between; align-items: center;">' +
                        '<div><strong>Isolated Visitor Session:</strong> Viewing custom uploaded organizational data. Changes and downloads are private to your browser session.</div>' +
                        '<a href="/api/reset" class="btn btn-outline" style="font-size: 0.8rem; background: #fff; padding: 4px 10px;">Reset to Baseline</a>' +
                        '</div>';
                }
                orgStats += '<table><thead><tr><th>Metric</th><th>Value</th></tr></thead><tbody>';
                orgStats += `<tr><td>Total task allocations</td><td>${orgData.task_count}</td></tr>`;
                orgStats += `<tr><td>Matched to SciNet catalog</td><td>${orgData.matched_count} (${orgData.match_rate_pct}%)</td></tr>`;
                orgStats += `<tr><td>Total annual task hours</td><td>${Number(orgData.total_annual_hours).toLocaleString()} hrs</td></tr>`;
                orgStats += '</tbody></table>';
                document.getElementById('org-stats-container').innerHTML = orgStats;

            } catch (err) {
                console.error('Error loading dashboard data:', err);
                document.getElementById('status-banner').innerHTML =
                    '<div class="alert alert-error">&#10007; Dashboard data error: ' + escapeHtml(err.message) + '</div>';
            }

            // Show upload status from URL param
            const params = new URLSearchParams(window.location.search);
            if (params.get('status') === 'uploaded') {
                document.getElementById('status-banner').innerHTML =
                    '<div class="alert alert-success">&#10003; Organization CSV uploaded and analyzed in isolated session.</div>';
                window.history.replaceState({}, '', '/');
            } else if (params.get('status') === 'reset') {
                document.getElementById('status-banner').innerHTML =
                    '<div class="alert alert-success">&#10003; Session reset to default baseline demonstration dataset (Nexus Institute).</div>';
                window.history.replaceState({}, '', '/');
            } else if (params.get('status') === 'error') {
                document.getElementById('status-banner').innerHTML =
                    '<div class="alert alert-error">&#10007; Upload failed: ' + escapeHtml(params.get('msg') || 'Unknown error') + '</div>';
                window.history.replaceState({}, '', '/');
            }
        }

        function renderTasks(tasks) {
            const display = tasks.slice(0, 100);
            document.getElementById('task-count-label').textContent =
                'Showing ' + display.length + ' of ' + tasks.length +
                ' matching tasks (top 200 loaded by opportunity score)';

            let html = '<table><thead><tr><th>Priority Tier</th><th>Task Description</th><th>Domain</th><th>Annual Hours</th><th>AI Fit Category</th><th>Opportunity Score</th><th>Action</th></tr></thead><tbody>';
            display.forEach((t) => {
                let tierClass = 'tier-4';
                if (t.priority_tier.includes('Tier 1')) tierClass = 'tier-1';
                else if (t.priority_tier.includes('Tier 2')) tierClass = 'tier-2';
                else if (t.priority_tier.includes('Tier 3')) tierClass = 'tier-3';

                const origIdx = t._orig_idx !== undefined ? t._orig_idx : 0;

                html += `<tr>
                    <td><span class="tier-pill ${tierClass}">${escapeHtml(t.priority_tier.split(':')[0])}</span></td>
                    <td style="max-width: 450px;">${escapeHtml(t.task)}</td>
                    <td>${escapeHtml(t.domain || '-')}</td>
                    <td>${t.hours_per_year != null ? Number(t.hours_per_year).toFixed(1) : '-'}</td>
                    <td>${escapeHtml(t.ai_fit_category)}</td>
                    <td><strong>${t.capacity_opportunity_score}</strong></td>
                    <td><button class="btn btn-outline" style="padding: 4px 8px; font-size: 0.75rem;"
                        onclick="showExplanation(${origIdx})">Explain</button></td>
                </tr>`;
            });
            html += '</tbody></table>';
            document.getElementById('tasks-table-container').innerHTML = html;
        }

        function filterTasks() {
            const query = document.getElementById('task-search').value.toLowerCase();
            const dom = document.getElementById('domain-filter').value;
            const tier = document.getElementById('tier-filter').value;

            filteredTasks = allTasks
                .map((t, idx) => ({ ...t, _orig_idx: idx }))
                .filter(t => {
                    const matchQ = !query || (t.task && t.task.toLowerCase().includes(query));
                    const matchDom = !dom || (t.domain && t.domain === dom);
                    const matchTier = !tier || (t.priority_tier && t.priority_tier.startsWith(tier));
                    return matchQ && matchDom && matchTier;
                });
            renderTasks(filteredTasks);
        }

        function showExplanation(idx) {
            const t = allTasks[idx];
            if (!t) { console.error('No task at index', idx); return; }
            document.getElementById('modal-title').textContent = t.task;
            document.getElementById('modal-body').innerHTML = `
                <p style="margin-bottom: 12px;">
                    <strong>Domain:</strong> ${escapeHtml(t.domain || 'N/A')} |
                    <strong>Classification:</strong> ${escapeHtml(t.classification || 'N/A')}
                </p>
                <div style="background: #f1f5f9; padding: 12px; border-radius: 6px; margin-bottom: 14px;">
                    <div><strong>Time Exposure Score:</strong> ${t.time_exposure_score}/100</div>
                    <div><strong>AI Suitability Score:</strong> ${t.ai_suitability_score}/100</div>
                    <div><strong>Physical Intensity Gate:</strong> ${t.physical_intensity_score}/100</div>
                    <div><strong>Regulatory Penalty:</strong> ${t.regulatory_penalty_score}/100</div>
                    <div><strong>Feasibility Score:</strong> ${t.feasibility_score}/100</div>
                    <div><strong>Capacity Opportunity Score:</strong>
                        <strong>${t.capacity_opportunity_score}/100</strong>
                        (${escapeHtml(t.priority_tier)})
                    </div>
                </div>
                <p><strong>Methodological Justification:</strong><br>${escapeHtml(t.explanation)}</p>
            `;
            document.getElementById('modal').style.display = 'flex';
        }

        function closeModal() {
            document.getElementById('modal').style.display = 'none';
        }

        window.onclick = function(event) {
            if (event.target === document.getElementById('modal')) closeModal();
        };

        window.addEventListener('keydown', function(e) {
            if (e.key === 'Escape') closeModal();
        });

        loadData();
    </script>
</body>
</html>
"""


def parse_multipart_payload(content_type_header: str, body_bytes: bytes) -> Dict[str, Dict[str, Any]]:
    """
    Parse multipart/form-data payload in a Python 3.13-compatible manner
    using the standard library email module without deprecated cgi.

    Parameters
    ----------
    content_type_header : str
        The raw Content-Type header string, e.g. 'multipart/form-data; boundary=...'.
    body_bytes : bytes
        The raw request body bytes.

    Returns
    -------
    dict
        Dictionary mapping field names to dictionaries with 'filename' and 'payload'.
    """
    if not content_type_header:
        return {}

    raw_mime = b"Content-Type: " + content_type_header.encode("utf-8") + b"\r\n\r\n" + body_bytes
    msg = email.message_from_bytes(raw_mime, policy=policy.default)

    fields: Dict[str, Dict[str, Any]] = {}
    if msg.is_multipart():
        for part in msg.iter_parts():
            name = part.get_param("name", header="content-disposition")
            if name:
                payload = part.get_payload(decode=True)
                filename = part.get_filename()
                fields[name] = {
                    "filename": filename,
                    "payload": payload,
                }
    return fields


MAX_UPLOAD_BYTES = 2 * 1024 * 1024  # 2 MB upload ceiling
SESSION_TTL_SECONDS = 1800           # 30-minute visitor session timeout
MAX_SESSIONS = 50                    # Cap concurrent active in-memory sessions
BASELINE_DB_PATH = PROJECT_ROOT / "database" / "research_task_analyzer.duckdb"
ALLOWED_REPORT_FILES = {
    "executive_decision_brief.md",
    "task_opportunity_scoring.csv",
    "scenario_simulation_matrix.csv",
    "domain_opportunity_summary.csv",
}


def sanitize_error_message(msg: str) -> str:
    """Strip server filesystem paths and truncate error messages for safe display."""
    # Strip Windows drive paths (e.g. C:\... or c:/...)
    cleaned = re.sub(r"[A-Za-z]:[\\/][^ \t\n\r\"']+", "[path]", str(msg))
    # Strip Linux root paths (e.g. /opt/render/... or /home/...)
    cleaned = re.sub(r"/(?:opt|home|usr|var|tmp|etc|app)/[^ \t\n\r\"']+", "[path]", cleaned)
    return cleaned[:200]


class SessionState:
    """Encapsulates an isolated in-memory DuckDB analytical session for a visitor."""

    def __init__(self, session_id: str, baseline_db_path: Path):
        self.session_id = session_id
        self.created_at = time.time()
        self.last_accessed = time.time()
        self.organization_name = "Uploaded Organization"
        self.baseline_db_path = baseline_db_path
        self.lock = threading.Lock()

        # Connect to in-memory DuckDB and initialize schema from baseline
        self.conn = duckdb.connect(":memory:")
        self.attach_baseline()
        try:
            self.conn.execute("CREATE TABLE organization_task_usage AS SELECT * FROM baseline.organization_task_usage WHERE 1=0;")
            self.conn.execute("CREATE TABLE scenario_results AS SELECT * FROM baseline.scenario_results WHERE 1=0;")
        finally:
            self.detach_baseline()

    def attach_baseline(self) -> None:
        """Attach baseline database read-only for catalog lookups."""
        norm_path = str(self.baseline_db_path).replace("\\", "/")
        try:
            self.conn.execute(f"ATTACH '{norm_path}' AS baseline (READ_ONLY);")
            self.conn.execute("PRAGMA search_path='main,baseline';")
        except Exception:
            pass

    def detach_baseline(self) -> None:
        """Detach baseline database to immediately release file handles."""
        try:
            self.conn.execute("PRAGMA search_path='main';")
            self.conn.execute("DETACH baseline;")
        except Exception:
            pass

    def touch(self) -> None:
        self.last_accessed = time.time()

    def close(self) -> None:
        try:
            self.detach_baseline()
            self.conn.close()
        except Exception:
            pass


class SessionManager:
    """Thread-safe registry managing isolated in-memory visitor analytical sessions."""

    _sessions: Dict[str, SessionState] = {}
    _lock = threading.Lock()

    @classmethod
    def get(cls, session_id: Optional[str]) -> Optional[SessionState]:
        if not session_id:
            return None
        with cls._lock:
            cls._cleanup_expired()
            session = cls._sessions.get(session_id)
            if session:
                session.touch()
                return session
            return None

    @classmethod
    def create_or_get(cls, session_id: Optional[str], baseline_db_path: Path) -> SessionState:
        with cls._lock:
            cls._cleanup_expired()
            if session_id and session_id in cls._sessions:
                session = cls._sessions[session_id]
                session.touch()
                return session

            # Evict oldest LRU session if capacity limit reached
            if len(cls._sessions) >= MAX_SESSIONS:
                oldest_id = min(cls._sessions.keys(), key=lambda k: cls._sessions[k].last_accessed)
                cls._sessions[oldest_id].close()
                del cls._sessions[oldest_id]

            new_id = str(uuid.uuid4())
            new_session = SessionState(new_id, baseline_db_path)
            cls._sessions[new_id] = new_session
            return new_session

    @classmethod
    def delete(cls, session_id: Optional[str]) -> None:
        if not session_id:
            return
        with cls._lock:
            if session_id in cls._sessions:
                cls._sessions[session_id].close()
                del cls._sessions[session_id]

    @classmethod
    def count(cls) -> int:
        with cls._lock:
            return len(cls._sessions)

    @classmethod
    def _cleanup_expired(cls) -> None:
        now = time.time()
        expired = [
            sid for sid, sess in cls._sessions.items()
            if (now - sess.last_accessed) > SESSION_TTL_SECONDS
        ]
        for sid in expired:
            try:
                cls._sessions[sid].close()
            except Exception:
                pass
            del cls._sessions[sid]


class AnalyzerRequestHandler(http.server.SimpleHTTPRequestHandler):
    """Custom HTTP request handler for the interactive dashboard with multi-visitor isolation."""

    def get_session_id(self) -> Optional[str]:
        """Extract and validate UUID session_id from Cookie header."""
        cookie_header = self.headers.get("Cookie")
        if not cookie_header:
            return None
        cookie = SimpleCookie()
        try:
            cookie.load(cookie_header)
            if "session_id" in cookie:
                sid = cookie["session_id"].value.strip()
                if sid and re.match(r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$", sid, re.I):
                    return sid
        except Exception:
            return None
        return None

    def get_session(self) -> Optional[SessionState]:
        """Return the active SessionState for the current visitor, if one exists."""
        sid = self.get_session_id()
        return SessionManager.get(sid)

    def do_GET(self):
        parsed = urllib.parse.urlparse(self.path)
        path = parsed.path

        if path == "/health" or path == "/api/health":
            self.send_json({
                "status": "healthy",
                "service": "research-task-ai-analyzer",
                "active_sessions": SessionManager.count()
            })
            return

        elif path == "/" or path == "/index.html":
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.end_headers()
            self.wfile.write(HTML_TEMPLATE.encode("utf-8"))
            return

        elif path == "/api/reset":
            sid = self.get_session_id()
            if sid:
                SessionManager.delete(sid)
            self.send_response(303)
            self.send_header("Location", "/?status=reset")
            self.send_header(
                "Set-Cookie",
                "session_id=; Path=/; Expires=Thu, 01 Jan 1970 00:00:00 GMT; Max-Age=0; HttpOnly; SameSite=Lax"
            )
            self.end_headers()
            return

        elif path == "/api/kpis":
            session = self.get_session()
            conn = get_connection(read_only=True)
            try:
                total_tasks = conn.execute("SELECT COUNT(*) FROM analytical_scoring_results;").fetchone()[0]
                high_fit = conn.execute("SELECT COUNT(*) FROM analytical_scoring_results WHERE feasibility_score >= 60.0;").fetchone()[0]
                constrained = conn.execute("SELECT COUNT(*) FROM analytical_scoring_results WHERE ai_fit_category = 'Constrained';").fetchone()[0]
            finally:
                conn.close()

            if session:
                with session.lock:
                    mod_row = session.conn.execute("""
                        SELECT
                            ROUND(SUM(potential_hours_released), 1) AS hrs,
                            ROUND(SUM(fte_capacity_equivalent), 2) AS fte
                        FROM scenario_results
                        WHERE scenario_id = 'SCEN_MODERATE';
                    """).fetchone()
            else:
                conn = get_connection(read_only=True)
                try:
                    mod_row = conn.execute("""
                        SELECT
                            ROUND(SUM(potential_hours_released), 1) AS hrs,
                            ROUND(SUM(fte_capacity_equivalent), 2) AS fte
                        FROM scenario_results
                        WHERE scenario_id = 'SCEN_MODERATE';
                    """).fetchone()
                finally:
                    conn.close()

            mod_hrs = mod_row[0] if mod_row and mod_row[0] is not None else 0.0
            mod_fte = mod_row[1] if mod_row and mod_row[1] is not None else 0.0
            self.send_json({
                "total_tasks": total_tasks,
                "high_fit_tasks": high_fit,
                "constrained_tasks": constrained,
                "moderate_hours_released": mod_hrs,
                "moderate_fte": mod_fte,
            })
            return

        elif path == "/api/domains":
            conn = get_connection(read_only=True)
            try:
                df = query_df("SELECT * FROM vw_domain_opportunity_summary;", conn=conn)
            finally:
                conn.close()
            self.send_json(df.to_dict("records"))
            return

        elif path == "/api/scenarios":
            from simulation.scenario_engine import DEFAULT_SCENARIOS
            session = self.get_session()
            if session:
                with session.lock:
                    scen_df = query_df("""
                        SELECT
                            scenario_id,
                            scenario_name,
                            ROUND(SUM(baseline_annual_hours), 1) AS total_baseline_hours,
                            ROUND(SUM(potential_hours_released), 1) AS total_hours_released,
                            ROUND(SUM(fte_capacity_equivalent), 2) AS total_fte_equivalent,
                            ROUND((SUM(potential_hours_released) / SUM(baseline_annual_hours)) * 100.0, 2) AS overall_hours_released_pct
                        FROM scenario_results
                        GROUP BY scenario_id, scenario_name
                        ORDER BY total_hours_released ASC;
                    """, conn=session.conn)
                    dept_df = query_df("""
                        SELECT
                            department,
                            ROUND(SUM(baseline_annual_hours), 1) AS baseline_hours,
                            ROUND(SUM(potential_hours_released), 1) AS hours_released,
                            ROUND(SUM(fte_capacity_equivalent), 2) AS fte_equivalent
                        FROM scenario_results
                        WHERE scenario_id = 'SCEN_MODERATE'
                        GROUP BY department
                        ORDER BY hours_released DESC;
                    """, conn=session.conn)
            else:
                conn = get_connection(read_only=True)
                try:
                    scen_df = query_df("""
                        SELECT
                            scenario_id,
                            scenario_name,
                            ROUND(SUM(baseline_annual_hours), 1) AS total_baseline_hours,
                            ROUND(SUM(potential_hours_released), 1) AS total_hours_released,
                            ROUND(SUM(fte_capacity_equivalent), 2) AS total_fte_equivalent,
                            ROUND((SUM(potential_hours_released) / SUM(baseline_annual_hours)) * 100.0, 2) AS overall_hours_released_pct
                        FROM scenario_results
                        GROUP BY scenario_id, scenario_name
                        ORDER BY total_hours_released ASC;
                    """, conn=conn)
                    dept_df = query_df("""
                        SELECT
                            department,
                            ROUND(SUM(baseline_annual_hours), 1) AS baseline_hours,
                            ROUND(SUM(potential_hours_released), 1) AS hours_released,
                            ROUND(SUM(fte_capacity_equivalent), 2) AS fte_equivalent
                        FROM scenario_results
                        WHERE scenario_id = 'SCEN_MODERATE'
                        GROUP BY department
                        ORDER BY hours_released DESC;
                    """, conn=conn)
                finally:
                    conn.close()

            param_map = {p.scenario_id: p for p in DEFAULT_SCENARIOS.values()}
            records = scen_df.to_dict("records")
            for rec in records:
                sid = rec.get("scenario_id", "")
                if sid in param_map:
                    p = param_map[sid]
                    rec["adoption_rate_pct"] = round(p.adoption_rate * 100)
                    rec["gross_efficiency_pct"] = round(p.gross_efficiency_gain * 100)
                    rec["verification_overhead_pct"] = round(p.verification_overhead * 100)
                else:
                    rec["adoption_rate_pct"] = "-"
                    rec["gross_efficiency_pct"] = "-"
                    rec["verification_overhead_pct"] = "-"

            self.send_json({
                "scenarios": records,
                "departments": dept_df.to_dict("records")
            })
            return

        elif path == "/api/tasks":
            conn = get_connection(read_only=True)
            try:
                df = query_df("""
                    SELECT
                        task_id, task, domain, level, classification, hours_per_year,
                        time_exposure_score, ai_suitability_score, physical_intensity_score,
                        regulatory_penalty_score, feasibility_score,
                        capacity_opportunity_score, ai_fit_category, priority_tier, explanation
                    FROM analytical_scoring_results
                    ORDER BY capacity_opportunity_score DESC
                    LIMIT 200;
                """, conn=conn)
            finally:
                conn.close()
            self.send_json(df.to_dict("records"))
            return

        elif path == "/api/org_summary":
            session = self.get_session()
            if session:
                with session.lock:
                    row = session.conn.execute("""
                        SELECT
                            COALESCE(MAX(organization_name), 'Uploaded Organization') AS organization_name,
                            COUNT(*) AS task_count,
                            COUNT(CASE WHEN matched_task_id IS NOT NULL THEN 1 END) AS matched_count,
                            ROUND(SUM(annual_task_hours), 1) AS total_annual_hours
                        FROM organization_task_usage;
                    """).fetchone()
                is_custom = True
            else:
                conn = get_connection(read_only=True)
                try:
                    row = conn.execute("""
                        SELECT
                            COALESCE(MAX(organization_name), 'Unknown Organization') AS organization_name,
                            COUNT(*) AS task_count,
                            COUNT(CASE WHEN matched_task_id IS NOT NULL THEN 1 END) AS matched_count,
                            ROUND(SUM(annual_task_hours), 1) AS total_annual_hours
                        FROM organization_task_usage;
                    """).fetchone()
                finally:
                    conn.close()
                is_custom = False

            total = row[1] if row else 0
            matched = row[2] if row else 0
            match_pct = round((matched / total * 100), 1) if total > 0 else 0.0
            self.send_json({
                "organization_name": row[0] if row else "Unknown",
                "task_count": total,
                "matched_count": matched,
                "match_rate_pct": match_pct,
                "total_annual_hours": row[3] if row and row[3] is not None else 0.0,
                "is_custom_upload": is_custom,
            })
            return

        elif path.startswith("/reports/"):
            file_name = path[len("/reports/"):]
            if not file_name or ".." in file_name or "/" in file_name or "\\" in file_name:
                self.send_error(400, "Invalid report file name")
                return
            if file_name not in ALLOWED_REPORT_FILES:
                self.send_error(404, "Report file not found")
                return

            session = self.get_session()
            if session:
                with session.lock:
                    session.attach_baseline()
                    try:
                        if file_name == "executive_decision_brief.md":
                            from reporting.report_generator import generate_executive_decision_brief
                            brief_content = generate_executive_decision_brief(
                                conn=session.conn,
                                organization_name=session.organization_name
                            )
                            data_bytes = brief_content.encode("utf-8")
                            content_type = "text/markdown; charset=utf-8"
                        elif file_name == "task_opportunity_scoring.csv":
                            df = query_df("SELECT * FROM analytical_scoring_results ORDER BY capacity_opportunity_score DESC;", conn=session.conn)
                            data_bytes = df.to_csv(index=False).encode("utf-8")
                            content_type = "text/csv; charset=utf-8"
                        elif file_name == "scenario_simulation_matrix.csv":
                            df = query_df("SELECT * FROM scenario_results ORDER BY scenario_id, potential_hours_released DESC;", conn=session.conn)
                            data_bytes = df.to_csv(index=False).encode("utf-8")
                            content_type = "text/csv; charset=utf-8"
                        elif file_name == "domain_opportunity_summary.csv":
                            df = query_df("SELECT * FROM vw_domain_opportunity_summary;", conn=session.conn)
                            data_bytes = df.to_csv(index=False).encode("utf-8")
                            content_type = "text/csv; charset=utf-8"
                        else:
                            self.send_error(404, "Report not found")
                            return
                    finally:
                        session.detach_baseline()

                self.send_response(200)
                self.send_header("Content-Type", content_type)
                self.send_header("Content-Disposition", f'attachment; filename="{file_name}"')
                self.send_header("Content-Length", str(len(data_bytes)))
                self.end_headers()
                self.wfile.write(data_bytes)
                return
            else:
                target_file = REPORTS_DIR / file_name
                if target_file.exists() and target_file.is_file():
                    self.send_response(200)
                    if file_name.endswith(".csv"):
                        self.send_header("Content-Type", "text/csv; charset=utf-8")
                    else:
                        self.send_header("Content-Type", "text/markdown; charset=utf-8")
                    self.send_header("Content-Disposition", f'attachment; filename="{file_name}"')
                    self.send_header("Content-Length", str(target_file.stat().st_size))
                    self.end_headers()
                    self.wfile.write(target_file.read_bytes())
                    return
                else:
                    self.send_error(404, "Report file not found")
                    return

        self.send_error(404, "Endpoint not found")
        return

    def do_POST(self):
        if self.path == "/api/upload":
            content_type = self.headers.get("Content-Type", "")
            if not content_type.startswith("multipart/form-data"):
                self.send_error(400, "Content-Type must be multipart/form-data")
                return

            try:
                content_length = int(self.headers.get("Content-Length", 0))
            except (ValueError, TypeError):
                content_length = 0

            if content_length <= 0:
                self.send_error(400, "Missing or empty request body")
                return

            if content_length > MAX_UPLOAD_BYTES:
                self.send_error(413, f"Uploaded file exceeds limit of {MAX_UPLOAD_BYTES // (1024 * 1024)} MB")
                return

            body_bytes = self.rfile.read(content_length)
            fields = parse_multipart_payload(content_type, body_bytes)

            file_info = fields.get("csv_file")
            if not file_info or not file_info.get("payload"):
                self.send_error(400, "No CSV file provided in upload")
                return

            csv_bytes = file_info["payload"]

            # Reject empty files
            if not csv_bytes or len(csv_bytes.strip()) == 0:
                self.send_error(400, "Uploaded CSV file is empty")
                return

            # Pre-validate required columns BEFORE initializing session database
            try:
                import io
                import pandas as pd
                preview_df = pd.read_csv(io.BytesIO(csv_bytes), nrows=0)
                preview_df.columns = [c.strip().lower() for c in preview_df.columns]
                required_cols = {"department", "role", "task"}
                missing_cols = required_cols - set(preview_df.columns)
                if missing_cols:
                    raise ValueError(
                        f"Missing required columns: {sorted(missing_cols)}. "
                        f"Found: {list(preview_df.columns)}"
                    )
            except ValueError as ve:
                self._redirect_with_error(sanitize_error_message(str(ve)))
                return
            except Exception as pe:
                self._redirect_with_error(f"Could not parse CSV: {sanitize_error_message(str(pe))}")
                return

            # Create or reuse isolated in-memory visitor session
            session_id = self.get_session_id()
            session = SessionManager.create_or_get(session_id, BASELINE_DB_PATH)

            with session.lock:
                session.attach_baseline()
                try:
                    load_organization_usage_data(session.conn, usage_csv_path=io.BytesIO(csv_bytes))
                    org_df = query_df("""
                        SELECT
                            u.*,
                            COALESCE(s.feasibility_score, 50.0) AS feasibility_score,
                            COALESCE(s.capacity_opportunity_score, 40.0) AS capacity_opportunity_score,
                            s.ai_fit_category,
                            s.priority_tier
                        FROM organization_task_usage u
                        LEFT JOIN analytical_scoring_results s ON u.matched_task_id = s.task_id;
                    """, conn=session.conn)
                    sim_results = run_scenario_simulation(org_df)
                    save_scenario_results_to_duckdb(sim_results, conn=session.conn)

                    # Extract organization name for report personalization
                    org_name_row = session.conn.execute(
                        "SELECT COALESCE(MAX(organization_name), 'Uploaded Organization') FROM organization_task_usage;"
                    ).fetchone()
                    if org_name_row and org_name_row[0]:
                        session.organization_name = org_name_row[0]

                except Exception as e:
                    self._redirect_with_error(sanitize_error_message(str(e)))
                    return
                finally:
                    session.detach_baseline()

            self.send_response(303)
            self.send_header("Location", "/?status=uploaded")
            self.send_header(
                "Set-Cookie",
                f"session_id={session.session_id}; Path=/; Max-Age={SESSION_TTL_SECONDS}; HttpOnly; SameSite=Lax"
            )
            self.end_headers()
            return

        self.send_error(404, "Endpoint not supported")

    def _redirect_with_error(self, message: str) -> None:
        """Redirect back to dashboard with error message in query string."""
        encoded_msg = urllib.parse.quote(str(message)[:200])
        self.send_response(303)
        self.send_header("Location", f"/?status=error&msg={encoded_msg}")
        self.end_headers()

    def send_json(self, data: Any) -> None:
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.end_headers()
        self.wfile.write(json.dumps(data, default=str).encode("utf-8"))

    def log_message(self, format, *args):
        # Suppress verbose per-request log lines; server startup prints port
        pass


class ThreadedHTTPServer(socketserver.ThreadingMixIn, http.server.HTTPServer):
    """Multi-threaded HTTP server enabling concurrent request handling."""
    daemon_threads = True
    allow_reuse_address = True


def run_server(port: Optional[int] = None) -> None:
    """Run interactive web server indefinitely."""
    # Always serve relative to project root so reports/ and data/ paths resolve
    os.chdir(str(PROJECT_ROOT))

    if port is None:
        port = int(os.environ.get("PORT", 8501))

    handler = AnalyzerRequestHandler
    with ThreadedHTTPServer(("", port), handler) as httpd:
        print(f"\n=======================================================")
        print(f"  Research Task AI Fit Analyzer Dashboard is live!")
        print(f"  URL: http://localhost:{port}")
        print(f"  Mode: Multi-threaded HTTP Server")
        print(f"=======================================================\n")
        try:
            httpd.serve_forever()
        except KeyboardInterrupt:
            print("\nShutting down web dashboard.")
            httpd.shutdown()


if __name__ == "__main__":
    import argparse
    default_port = int(os.environ.get("PORT", 8501))
    parser = argparse.ArgumentParser(
        description="Research Task AI Fit & Capacity Opportunity Analyzer - Web Dashboard"
    )
    parser.add_argument(
        "--port", type=int, default=default_port,
        help=f"Port to serve the dashboard on (default: {default_port})"
    )
    args = parser.parse_args()
    run_server(port=args.port)
