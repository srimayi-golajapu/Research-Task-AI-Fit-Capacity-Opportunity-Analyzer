-- =============================================================================
-- Research Task AI Fit & Capacity Opportunity Analyzer
-- DuckDB Database Schema DDL
-- =============================================================================

-- 1. Organization Task Usage (Synthetic or User-Provided)
CREATE TABLE IF NOT EXISTS organization_task_usage (
    usage_id VARCHAR PRIMARY KEY,
    org_id VARCHAR NOT NULL,
    organization_name VARCHAR,
    department VARCHAR NOT NULL,
    role VARCHAR NOT NULL,
    task VARCHAR NOT NULL,
    level VARCHAR,
    domain VARCHAR,
    field VARCHAR,
    subfield VARCHAR,
    fte_count DOUBLE NOT NULL,
    weekly_hours_per_fte DOUBLE NOT NULL,
    weeks_per_year DOUBLE NOT NULL,
    annual_task_hours DOUBLE NOT NULL,
    current_ai_usage VARCHAR,
    matched_task_id VARCHAR
);

-- 2. Analytical Scoring Results Table
CREATE TABLE IF NOT EXISTS analytical_scoring_results (
    task_id VARCHAR PRIMARY KEY,
    task VARCHAR NOT NULL,
    level VARCHAR,
    domain VARCHAR,
    field VARCHAR,
    subfield VARCHAR,
    category VARCHAR,
    classification VARCHAR,
    hours_per_year DOUBLE,
    -- Analytical Dimensions (0 to 100 Scale)
    time_exposure_score DOUBLE,
    ai_suitability_score DOUBLE,
    ai_adoption_score DOUBLE,
    physical_intensity_score DOUBLE,
    regulatory_penalty_score DOUBLE,
    feasibility_score DOUBLE,
    -- Synthesis & Categorization
    capacity_opportunity_score DOUBLE,
    ai_fit_category VARCHAR,
    priority_tier VARCHAR,
    explanation TEXT
);

-- 3. Scenario Simulation Outputs Table
CREATE TABLE IF NOT EXISTS scenario_results (
    scenario_id VARCHAR,
    scenario_name VARCHAR NOT NULL,
    task_id VARCHAR NOT NULL,
    department VARCHAR,
    role VARCHAR,
    baseline_annual_hours DOUBLE,
    potential_hours_released DOUBLE,
    effective_capacity_released_pct DOUBLE,
    net_hours_retained DOUBLE,
    fte_capacity_equivalent DOUBLE,
    PRIMARY KEY (scenario_id, task_id, department, role)
);

-- =============================================================================
-- Analytical Views (Created after analytical tables are populated)
-- =============================================================================

CREATE OR REPLACE VIEW vw_domain_opportunity_summary AS
SELECT
    domain,
    COUNT(*) AS total_tasks,
    ROUND(AVG(time_exposure_score), 2) AS avg_time_exposure,
    ROUND(AVG(ai_suitability_score), 2) AS avg_ai_suitability,
    ROUND(AVG(physical_intensity_score), 2) AS avg_physical_intensity,
    ROUND(AVG(regulatory_penalty_score), 2) AS avg_regulatory_penalty,
    ROUND(AVG(capacity_opportunity_score), 2) AS avg_opportunity_score,
    COUNT(CASE WHEN ai_fit_category = 'High Potential' THEN 1 END) AS high_fit_tasks,
    COUNT(CASE WHEN ai_fit_category = 'Moderate Potential' THEN 1 END) AS moderate_fit_tasks,
    COUNT(CASE WHEN ai_fit_category = 'Constrained' THEN 1 END) AS constrained_tasks
FROM analytical_scoring_results
GROUP BY domain
ORDER BY avg_opportunity_score DESC;

CREATE OR REPLACE VIEW vw_top_capacity_opportunities AS
SELECT
    task_id,
    task,
    domain,
    field,
    category,
    classification,
    ROUND(hours_per_year, 1) AS hours_per_year,
    ROUND(ai_suitability_score, 1) AS ai_suitability,
    ROUND(feasibility_score, 1) AS feasibility,
    ROUND(capacity_opportunity_score, 1) AS opportunity_score,
    ai_fit_category,
    priority_tier
FROM analytical_scoring_results
WHERE capacity_opportunity_score >= 50.0
ORDER BY capacity_opportunity_score DESC;
