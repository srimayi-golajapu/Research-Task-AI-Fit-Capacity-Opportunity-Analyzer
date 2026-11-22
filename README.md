# Research Task AI Fit & Capacity Opportunity Analyzer

[![Python 3.13](https://img.shields.io/badge/python-3.13-blue.svg)](https://www.python.org/downloads/)
[![DuckDB](https://img.shields.io/badge/duckdb-2.0.1-yellow.svg)](https://duckdb.org/)
[![uv](https://img.shields.io/badge/package%20manager-uv-purple.svg)](https://github.com/astral-sh/uv)
[![Tests](https://img.shields.io/badge/tests-44%20passed-brightgreen.svg)]()
[![License: MIT](https://img.shields.io/badge/License-MIT-green.svg)](LICENSE)
[![Data License: CC BY 4.0](https://img.shields.io/badge/Data%20License-CC%20BY%204.0-lightgrey.svg)](LICENSES.md)

An end-to-end analytical decision-support application and portfolio project that evaluates organizational research tasks for generative AI assistance, enforces physical-work and regulatory constraint gates, models capacity-release opportunities across policy scenarios, and generates executive decision briefs.

---

> **Portfolio Project Disclosure:**<br>
> This repository is a demonstrable personal portfolio project showcasing end-to-end data engineering, analytical modeling, in-process OLAP data storage (DuckDB), scenario simulation, and a local-first interactive dashboard with zero heavy external web framework dependencies.<br>
> The organizational data for the **Nexus Institute for Advanced Research** is intentional, synthetic demonstration data. Users may upload custom organization CSV files to re-evaluate capacity release dynamically.

---

## 📖 Table of Contents
1. [Project Purpose & Problem Statement](#1-project-purpose--problem-statement)
2. [Architecture Overview](#2-architecture-overview)
3. [Technology Stack](#3-technology-stack)
4. [Dataset Foundations & Lineage](#4-dataset-foundations--lineage)
5. [Installation & Setup](#5-installation--setup)
6. [How to Run the Application](#6-how-to-run-the-application)
   - [Interactive Local Web Dashboard](#a-interactive-local-web-dashboard)
   - [Command-Line Interface (CLI)](#b-command-line-interface-cli)
7. [Screenshots](#7-screenshots)
8. [How to Provide Custom Organization Data](#8-how-to-provide-custom-organization-data)
9. [Analytical Methodology & Scoring Engine](#9-analytical-methodology--scoring-engine)
10. [Scenario Modelling & Capacity Release Simulation](#10-scenario-modelling--capacity-release-simulation)
11. [Reporting & Decision Brief Exports](#11-reporting--decision-brief-exports)
12. [Testing & Quality Verification](#12-testing--quality-verification)
13. [Deployment Guide](#13-deployment-guide)
14. [Known Limitations & Governance Caveats](#14-known-limitations--governance-caveats)
15. [License & Third-Party Attribution](#15-license--third-party-attribution)

---

## 1. Project Purpose & Problem Statement

Higher education, corporate R&D divisions, and public research institutes face a dual challenge: rising administrative and analytical workloads paired with the rapid emergence of generative AI tools. Organizations often oscillate between uncritical blanket adoption and rigid rejection.

This application provides an **evidence-based decision-support framework** that:
- Deconstructs research workflows into **27,823 granular, observable tasks** grounded in the peer-reviewed SciNet taxonomy.
- Evaluates **technical AI suitability** across cognitive complexity, information media, and working modes.
- Applies strict **physical-work intensity gates** (preventing digital AI deployment on wet-bench synthesis) and **regulatory/IRB penalties**.
- Models **capacity-release opportunities** across Conservative, Moderate, and Optimistic adoption curves.
- Translates released hours into **Full-Time Equivalent (FTE) capacity equivalents** for institutional workforce planning.

> **Crucial Distinction:** Estimated capacity release represents *repurposed capacity* for core research ideation, discovery, and funding acquisition, **not** guaranteed productivity gains or workforce reduction.

---

## 2. Architecture Overview

```text
┌────────────────────────────────────────────────────────────────────────┐
│                        DATA INGESTION PIPELINE                         │
│  data/raw/scinet/ (6 CSVs)  +  data/synthetic/ (Org task allocations)  │
└───────────────────────────────────┬────────────────────────────────────┘
                                    ▼
┌────────────────────────────────────────────────────────────────────────┐
│               VALIDATION & NORMALIZATION (src/ingestion/)              │
│   • Schema & type enforcement    • Deterministic SHA-256 Task IDs      │
│   • 1,020 universal tasks saved  • Zero silent record loss             │
└───────────────────────────────────┬────────────────────────────────────┘
                                    ▼
┌────────────────────────────────────────────────────────────────────────┐
│                    EMBEDDED ANALYTICAL STORAGE (DuckDB)                │
│  database/research_task_analyzer.duckdb (27,823 tasks, org usage, views│
└───────────────────────────────────┬────────────────────────────────────┘
                                    ▼
┌────────────────────────────────────────────────────────────────────────┐
│                    ANALYTICAL & SCENARIO ENGINES                       │
│   • src/analytics/scoring_engine.py  (6-dimension multi-factor score)   │
│   • src/simulation/scenario_engine.py (Conservative/Moderate/Optimistic)│
└───────────────────────────────────┬────────────────────────────────────┘
                                    ▼
┌────────────────────────────────────────────────────────────────────────┐
│                        PRESENTATION & EXPORT TIER                      │
│   • app/web_app.py (Multi-threaded HTTP Server with /health check)     │
│   • app/cli.py (Command-line pipeline runner & summary inspection)     │
│   • reports/ (Executive Decision Briefs & CSV Exports)                 │
└────────────────────────────────────────────────────────────────────────┘
```

---

## 3. Technology Stack

- **Language:** Python 3.13.3
- **Package Management:** `uv`
- **Database:** DuckDB 2.0.1 (embedded in-process analytical SQL OLAP engine)
- **Data Engineering:** Pandas 3.1.1, NumPy 2.5.4
- **Testing:** pytest 9.2.0
- **Web Application:** Python standard library `http.server` & `socketserver.ThreadingMixIn` (Zero external heavy web framework dependencies)
- **UI Styling:** Native CSS3 responsive grid layout, accessible color palette

---

## 4. Dataset Foundations & Lineage

The application integrates three distinct data tiers:

| Tier | Data Source | Records | Role in the System |
|---|---|---:|---|
| **Primary Taxonomy** | **SciNet — The Anatomy of Science** (`data/raw/scinet/`) | 27,823 master rows | Peer-reviewed academic task taxonomy spanning 6 scientific domains, with dimensional scores for cognitive complexity, physical deployment, and regulatory constraints. |
| **Contextual Evidence** | **Anthropic Economic Research Findings** | Calibration parameters | Aggregate macroeconomic findings on LLM task exposure, citation velocity, and verification overhead used as contextual calibration anchors. |
| **Organizational Input** | **Nexus Institute for Advanced Research** (`data/synthetic/`) | 150 allocations (151,275.8 hrs) | Intentional demonstration dataset representing faculty, postdoc, and researcher task hours across 5 departments. Replaceable via custom CSV upload. |

### Handling the 1,020 Universal Tasks
In `task_time.csv`, exactly 1,020 rows represent universal research activities that lack domain/subfield specialization. The pipeline **preserves 100% of these records** (`is_universal_unmatched = True`) and merges them into `scinet_tasks_master`, ensuring no silent data loss.

---

## 5. Installation & Setup

### Prerequisites
- Windows, macOS, or Linux
- Python 3.12 or 3.13
- `uv` package manager (`curl -LsSf https://astral.sh/uv/install.sh | sh` or `winget install astral-sh.uv`)

### Setup Instructions
1. **Clone the repository:**
   ```bash
   git clone https://github.com/srimayi-golajapu/Research-Task-AI-Fit-Capacity-Opportunity-Analyzer.git
   cd Research-Task-AI-Fit-Capacity-Opportunity-Analyzer
   ```

2. **Initialize the virtual environment with `uv`:**
   ```bash
   uv sync --system-certs
   ```

3. **Verify installed packages:**
   ```bash
   uv pip list
   ```

---

## 6. How to Run the Application

### A. Interactive Local Web Dashboard

Launch the zero-dependency, local-first interactive dashboard:

```bash
uv run python app/web_app.py --port 8501
```

Open your browser to:
👉 **`http://localhost:8501`**

#### Dashboard Features:
- **Executive Overview:** Live KPI cards for total evaluated tasks, high-fit opportunities, released hours, and FTE equivalents.
- **Scenario Simulation Matrix:** Side-by-side comparison of Conservative, Moderate, and Optimistic outcomes across all departments.
- **Task Opportunity Explorer:** Real-time search, domain filtering, and priority tier categorization for all 27,823 tasks. Click **"Explain"** on any row to open the complete multi-factor justification modal.
- **Organization CSV Uploader:** Upload your own department usage CSV and re-run scenarios instantly.
- **Reports & Downloads:** One-click downloads for Markdown decision briefs and analytical CSVs.

---

### B. Command-Line Interface (CLI)

The CLI provides full programmatic control for automation and batch execution:

```bash
# 1. Run full end-to-end pipeline (Ingestion -> Normalization -> DuckDB -> Scoring -> Simulation -> Reports)
uv run python app/cli.py run-pipeline

# 2. View executive analytical summary and scenario comparison directly in the terminal
uv run python app/cli.py summary

# 3. Ingest custom organization task usage CSV and re-run simulations
uv run python app/cli.py load-org path/to/my_organization_tasks.csv

# 4. Regenerate all Markdown decision briefs and CSV exports
uv run python app/cli.py export

# 5. Start the web dashboard via CLI
uv run python app/cli.py serve --port 8501
```

---

## 7. Screenshots

<!-- Screenshots will be added post-deployment. Placeholders below illustrate dashboard structure. -->

| Section | Preview |
|---|---|
| **Executive Overview & KPI Cards** | *[ Screenshot Placeholder: Executive KPI cards, macro domain landscape, and navigation tabs ]* |
| **Capacity Release Scenario Matrix** | *[ Screenshot Placeholder: Side-by-side Conservative, Moderate, and Optimistic policy simulation tables ]* |
| **Task Opportunity Explorer & Modal** | *[ Screenshot Placeholder: Searchable task catalog with priority badges and Explain modal ]* |
| **Organization CSV Data & Upload** | *[ Screenshot Placeholder: Demonstration staffing overview and CSV file upload interface ]* |

---

## 8. How to Provide Custom Organization Data

You can evaluate custom departmental task usage instead of the default demonstration dataset.

### Expected CSV Schema
Prepare a CSV file with the following column headers:

```csv
department,role,task,fte_count,weekly_hours_per_fte,weeks_per_year,current_ai_usage
Department of Biosciences,Senior Researcher,Extract and sequence microbial DNA from soil samples,4,6.5,48,Minimal (<10%)
Institute for Social Sciences,Data Analyst,Fit Bayesian hierarchical model to survey data,3,8.0,46,Occasional (10-30%)
```

### Loading your Data:
1. **Via the Web Dashboard:** Navigate to the **"Organization Data"** tab, select your file, and click **"Upload & Run Analysis"**.
2. **Via the CLI:**
   ```bash
   uv run python app/cli.py load-org my_org_data.csv
   ```
The pipeline matches tasks against `scinet_tasks_master` using composite hierarchy keys and falls back gracefully when subfields are omitted. Failed uploads automatically roll back without corrupting database state.

---

## 9. Analytical Methodology & Scoring Engine

Every task is evaluated across six transparent analytical dimensions (0–100 scale):

1. **Time Exposure Score ($S_{\text{time}}$):**
   $$S_{\text{time}} = \min\left(100, \frac{\log_{10}(\max(1, \text{hours}))}{\log_{10}(500)} \times 100\right)$$
   Reflects the annual workload footprint. Tasks taking $\ge 500$ hours/year score 100.

2. **AI Suitability Score ($S_{\text{ai}}$):**
   $$S_{\text{ai}} = 0.40 \cdot \text{Info\_Medium} + 0.30 \cdot \text{Cognitive\_Fit} + 0.20 \cdot \text{Mode\_Alignment} + 0.10 \cdot \text{Verification\_Density}$$
   Synthesizes digital information density, cognitive complexity alignment, and qualitative/quantitative modes.

3. **Physical-Work Intensity Gate ($P_{\text{phys}}$):**
   $$P_{\text{phys}} = 0.70 \cdot \text{Materials\_Medium} + 0.30 \cdot \left(\frac{\text{Physical\_Deployment}}{5.0} \times 100\right)$$
   Tasks requiring physical laboratory materials or in-situ deployment are strictly gated.

4. **Regulatory & Operational Penalty ($R_{\text{reg}}$):**
   $$R_{\text{reg}} = 0.80 \cdot \left(\frac{\text{Regulatory\_Restriction}}{5.0} \times 100\right) + (\text{Is\_Core} \times 15.0)$$
   Penalizes tasks bound by ethics protocols, human subject oversight, or legal sign-offs.

5. **Feasibility Score ($S_{\text{feas}}$):**
   $$S_{\text{feas}} = S_{\text{ai}} \times \left(1 - \frac{P_{\text{phys}}}{100}\right) \times \left(1 - 0.70 \cdot \frac{R_{\text{reg}}}{100}\right)$$

6. **Composite Capacity Opportunity Score ($S_{\text{opp}}$):**
   $$S_{\text{opp}} = \left(0.50 \cdot S_{\text{time}} + 0.50 \cdot S_{\text{feas}}\right) \times \left(1 - 0.40 \cdot \frac{S_{\text{adopt}}}{100}\right)$$

### Priority Tiers:
- **Tier 1: Immediate Opportunity ($S_{\text{opp}} \ge 65$):** High workload + high feasibility + minimal physical gating.
- **Tier 2: Targeted Augmentation ($45 \le S_{\text{opp}} < 65$):** Meaningful time release with moderate human-in-the-loop review.
- **Tier 3: Exploratory / Minor ($25 \le S_{\text{opp}} < 45$).**
- **Tier 4: Deprioritized / Blocked ($S_{\text{opp}} < 25$).**

---

## 10. Scenario Modelling & Capacity Release Simulation

Capacity release is simulated across three governance stances:

$$\Delta H_i = H_i \times \text{Adoption\_Rate} \times \left[\text{Gross\_Efficiency} \times (1 - \text{Verification\_Friction})\right] \times \frac{S_{\text{feas}, i}}{100}$$
$$\text{FTE Equivalent} = \frac{\Delta H_i}{1800 \text{ hrs/year}}$$

| Scenario | Adoption Rate | Gross Speedup | Verification Friction | Net Efficiency Factor |
|---|---:|---:|---:|---:|
| **Conservative** | 35% | 20% | 30% | 14.0% |
| **Moderate** | 60% | 35% | 20% | 28.0% |
| **Optimistic** | 85% | 50% | 10% | 45.0% |

### Baseline Results on Nexus Institute Demonstration Data (151,275.8 Baseline Hours):
- **Conservative:** 3,313.4 hours released (1.84 FTE equivalent, 2.19% net capacity gain).
- **Moderate:** 11,360.7 hours released (6.31 FTE equivalent, 7.51% net capacity gain).
- **Optimistic:** 25,868.0 hours released (14.37 FTE equivalent, 17.10% net capacity gain).

---

## 11. Reporting & Decision Brief Exports

Running `app/cli.py export` or `export_all_reports()` automatically generates four deliverables in [`reports/`](reports/):

1. **`reports/executive_decision_brief.md`**: Executive C-level decision brief summarizing strategic findings, departmental breakdowns, sensitivity comparisons, and governance recommendations.
2. **`reports/task_opportunity_scoring.csv`**: Task-level scores across all 27,823 tasks with dimensional metrics and explanations.
3. **`reports/scenario_simulation_matrix.csv`**: Granular simulation outputs across Conservative, Moderate, and Optimistic scenarios.
4. **`reports/domain_opportunity_summary.csv`**: Aggregated macro metrics by scientific domain.

---

## 12. Testing & Quality Verification

The test suite covers unit tests, schema validation, normalization preservation, database integrity, scoring logic, scenario calculations, HTTP routes, multipart CSV uploads, and CLI commands.

Execute tests using pytest:

```bash
uv run pytest -v tests
```

Execute the comprehensive 10-suite end-to-end functional QA runner:

```bash
uv run python tests/functional_qa_runner.py
```

### Test Suite Summary:
```text
tests/test_analytics.py                     3 passed
tests/test_app_cli.py                       2 passed
tests/test_database.py                      3 passed
tests/test_ingestion.py                     4 passed
tests/test_normalization.py                 2 passed
tests/test_reporting.py                     2 passed
tests/test_scenarios.py                     2 passed
tests/test_validation.py                    3 passed
tests/test_web_app.py                      23 passed
============================= 44 passed in 10.09s =============================
```

---

## 13. Deployment Guide

The application is cloud-ready and can be deployed to free hosting platforms such as **Render** or **Hugging Face Spaces**.

### Deploying on Render (Free Web Service)
1. Fork or push this repository to your GitHub account.
2. Sign in to [Render](https://render.com) and click **New > Web Service**.
3. Select your repository.
4. Configure the service:
   - **Runtime:** `Python 3`
   - **Build Command:** `pip install uv && uv sync --system-certs` (or `pip install duckdb pandas pytest`)
   - **Start Command:** `python app/web_app.py --port $PORT`
5. The application will bind to the dynamically assigned `$PORT` environment variable and expose the `/health` endpoint for uptime monitoring.

---

## 14. Known Limitations & Governance Caveats

1. **No Autonomous Laboratory Execution:** Generative AI models operate exclusively in digital and informational domains. Tasks requiring wet-lab chemical synthesis, surgical trials, or physical specimen collection cannot be executed by digital models alone.
2. **Mandatory Human Accountability:** Scientific peer review and regulatory bodies require authoritative human accountability. AI augmentation cannot replace the principal investigator's liability.
3. **Verification Friction Reality:** Time savings from AI draft generation are partially offset by the necessary cognitive labor of prompt refinement, factual verification, and hallucination auditing.
4. **Dynamic Model Capabilities:** Frontier model benchmarks evolve continuously. The scoring parameters reflect current frontier LLM capabilities and can be updated in `src/analytics/scoring_engine.py`.

---

## 15. License & Third-Party Attribution

- **Application Code:** MIT License (see [LICENSE](LICENSE)).
- **SciNet Datasets:** Creative Commons Attribution 4.0 International (CC BY 4.0) by Lukas Althoff et al. (see [LICENSES.md](LICENSES.md)).
