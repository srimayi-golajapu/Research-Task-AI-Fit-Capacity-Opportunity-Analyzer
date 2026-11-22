"""
Analytical Scoring Engine Module
================================
Implements transparent multi-factor analytical scoring for research tasks:
1. Task time exposure
2. Relative AI capability and suitability
3. Current AI adoption estimation
4. Physical-work intensity gating
5. Regulatory and operational restrictions
6. Composite capacity-release opportunity scoring
7. Categorization and natural-language explanations

All scoring logic is fully transparent, configurable, and backed by verifiable metrics.
"""

from dataclasses import dataclass
import math
from typing import Any, Dict, List, Optional
import numpy as np
import pandas as pd


@dataclass
class ScoringWeights:
    """Configurable weights and thresholds for analytical scoring."""
    # AI Suitability weights
    weight_information_medium: float = 0.40
    weight_cognitive_complexity: float = 0.30
    weight_mode_alignment: float = 0.20
    weight_verification_density: float = 0.10

    # Physical intensity gate scale
    max_physical_deployment: float = 5.0

    # Regulatory penalty scale
    max_regulatory_restriction: float = 5.0
    core_classification_penalty: float = 0.15

    # Opportunity composite weights
    weight_time_exposure: float = 0.50
    weight_feasibility: float = 0.50

    # Thresholds
    tier_1_threshold: float = 65.0
    tier_2_threshold: float = 45.0
    tier_3_threshold: float = 25.0


def compute_time_exposure_score(hours_per_year: float, benchmark_max_hours: float = 500.0) -> float:
    """
    Compute normalized time exposure score (0 to 100) using log scaling.
    Tasks requiring >= 500 hours/year achieve score 100.
    """
    if pd.isna(hours_per_year) or hours_per_year <= 0:
        return 0.0
    val = max(1.0, float(hours_per_year))
    score = (math.log10(val) / math.log10(benchmark_max_hours)) * 100.0
    return float(np.clip(score, 0.0, 100.0))


def compute_ai_suitability_score(row: pd.Series, weights: ScoringWeights) -> float:
    """
    Compute technical AI suitability score (0 to 100) based on cognitive complexity,
    information media, and cognitive modes.
    """
    # 1. Medium Information (0 to 100)
    med_info = float(row.get("medium_information", 50.0))
    if pd.isna(med_info):
        med_info = 50.0

    # 2. Cognitive Complexity fit (SciNet scale ~ 1.0 to 4.5)
    # LLMs excel at cognitive complexity between 2.0 and 4.0; sweet spot ~ 2.8
    cog = float(row.get("cognitive_complexity", 2.5))
    if pd.isna(cog):
        cog = 2.5
    # Normalized 1 to 4 -> score 0 to 100
    cog_fit = min(100.0, max(0.0, ((cog - 1.0) / 3.0) * 100.0))

    # 3. Mode alignment (qualitative, quantitative, theoretical vs none)
    q_quant = float(row.get("mode_quantitative", 0.0)) if not pd.isna(row.get("mode_quantitative")) else 0.0
    q_qual = float(row.get("mode_qualitative", 0.0)) if not pd.isna(row.get("mode_qualitative")) else 0.0
    q_theo = float(row.get("mode_theoretical", 0.0)) if not pd.isna(row.get("mode_theoretical")) else 0.0
    mode_score = min(100.0, q_quant + q_qual + q_theo)
    if mode_score == 0:
        mode_score = 50.0

    # 4. Verification feasibility (rl_verification 0 to 10)
    rl_verif = float(row.get("rl_verification", 5.0)) if not pd.isna(row.get("rl_verification")) else 5.0
    verif_score = min(100.0, (rl_verif / 10.0) * 100.0)

    score = (
        weights.weight_information_medium * med_info +
        weights.weight_cognitive_complexity * cog_fit +
        weights.weight_mode_alignment * mode_score +
        weights.weight_verification_density * verif_score
    )
    return float(np.clip(score, 0.0, 100.0))


def compute_physical_intensity_score(row: pd.Series, weights: ScoringWeights) -> float:
    """
    Compute physical-work intensity score (0 to 100).
    Higher score indicates higher physical gating preventing digital AI execution.
    """
    med_mat = float(row.get("medium_materials", 0.0)) if not pd.isna(row.get("medium_materials")) else 0.0
    phys_deploy = float(row.get("physical_deployment", 0.0)) if not pd.isna(row.get("physical_deployment")) else 0.0

    deploy_pct = min(100.0, (phys_deploy / weights.max_physical_deployment) * 100.0)

    score = 0.70 * med_mat + 0.30 * deploy_pct
    return float(np.clip(score, 0.0, 100.0))


def compute_regulatory_penalty_score(row: pd.Series, weights: ScoringWeights) -> float:
    """
    Compute regulatory and operational restriction penalty (0 to 100).
    Higher score indicates stricter governance, IRB compliance, or legal friction.
    """
    reg = float(row.get("regulatory_restriction", 0.0)) if not pd.isna(row.get("regulatory_restriction")) else 0.0
    reg_score = min(100.0, (reg / weights.max_regulatory_restriction) * 100.0)

    is_core = 1.0 if str(row.get("classification", "")).strip().lower() == "core" else 0.0
    core_penalty = is_core * (weights.core_classification_penalty * 100.0)

    total_penalty = 0.80 * reg_score + core_penalty
    return float(np.clip(total_penalty, 0.0, 100.0))


def compute_ai_adoption_score(row: pd.Series) -> float:
    """
    Compute estimated current AI adoption baseline (0 to 100).
    Higher score means AI is already extensively used (less untapped opportunity).
    """
    curr_usage = str(row.get("current_ai_usage", "")).lower()
    if "regular" in curr_usage or ">30" in curr_usage:
        return 75.0
    elif "occasional" in curr_usage or "10-30" in curr_usage:
        return 45.0
    elif "minimal" in curr_usage or "<10" in curr_usage:
        return 15.0
    elif "none" in curr_usage:
        return 0.0

    # Default estimation from SciNet pct_researchers and classification
    pct_res = float(row.get("pct_researchers", 50.0)) if not pd.isna(row.get("pct_researchers")) else 50.0
    return float(np.clip(pct_res * 0.35, 5.0, 60.0))


def generate_task_explanation(
    task: str,
    ai_suitability: float,
    physical_intensity: float,
    regulatory_penalty: float,
    feasibility: float,
    opportunity: float,
    hours_per_year: float
) -> str:
    """Generate transparent, natural-language scoring explanation."""
    reasons = []

    if ai_suitability >= 70:
        reasons.append("High cognitive-information alignment makes this task well-suited for frontier AI")
    elif ai_suitability >= 45:
        reasons.append("Moderate technical suitability for AI augmentation")
    else:
        reasons.append("Low digital/information alignment limits AI suitability")

    if physical_intensity >= 40:
        reasons.append(f"Substantial physical materials constraint ({physical_intensity:.0f}% intensity) limits direct automation")

    if regulatory_penalty >= 40:
        reasons.append(f"Regulatory/governance restrictions ({regulatory_penalty:.0f}% penalty) mandate continuous human oversight")

    if hours_per_year >= 100:
        reasons.append(f"High annual workload exposure ({hours_per_year:.0f} hrs/yr) amplifies capacity release value")
    elif hours_per_year < 20:
        reasons.append(f"Low annual workload exposure ({hours_per_year:.1f} hrs/yr) yields modest gross capacity gain")

    return "; ".join(reasons) + "."


def score_tasks(
    df: pd.DataFrame,
    weights: Optional[ScoringWeights] = None
) -> pd.DataFrame:
    """
    Execute end-to-end analytical scoring on a tasks DataFrame.

    Parameters
    ----------
    df : pd.DataFrame
        DataFrame containing tasks, dimensions, hours, and ratings.
    weights : ScoringWeights, optional
        Configurable weights and thresholds.

    Returns
    -------
    pd.DataFrame
        Enriched DataFrame containing all 6 analytical dimension scores,
        composite opportunity score, categorization, priority tier, and explanations.
    """
    w = weights if weights is not None else ScoringWeights()
    df_out = df.copy()

    # Determine hours column
    hours_col = "annual_task_hours" if "annual_task_hours" in df_out.columns else "hours_per_year"
    if hours_col not in df_out.columns:
        hours_col = "hours_per_year"
        df_out[hours_col] = 50.0

    records = df_out.to_dict("records")
    scored_records: List[Dict[str, Any]] = []

    for row in records:
        h = float(row.get(hours_col, 0.0)) if not pd.isna(row.get(hours_col)) else 0.0

        s_time = compute_time_exposure_score(h)
        s_ai = compute_ai_suitability_score(pd.Series(row), w)
        s_phys = compute_physical_intensity_score(pd.Series(row), w)
        s_reg = compute_regulatory_penalty_score(pd.Series(row), w)
        s_adopt = compute_ai_adoption_score(pd.Series(row))

        # Feasibility combines AI suitability discounted by physical and regulatory gates
        phys_discount = 1.0 - (s_phys / 100.0)
        reg_discount = 1.0 - (s_reg / 100.0) * 0.70
        s_feas = s_ai * phys_discount * reg_discount

        # Opportunity combines time exposure and feasibility, discounted by existing adoption
        untapped_factor = 1.0 - 0.40 * (s_adopt / 100.0)
        s_opp = (w.weight_time_exposure * s_time + w.weight_feasibility * s_feas) * untapped_factor
        s_opp = float(np.clip(s_opp, 0.0, 100.0))

        # AI Fit Category
        if s_phys >= 50.0 or s_reg >= 60.0:
            category = "Constrained"
        elif s_feas >= 60.0:
            category = "High Potential"
        elif s_feas >= 35.0:
            category = "Moderate Potential"
        else:
            category = "Low Potential"

        # Priority Tier
        if s_opp >= w.tier_1_threshold:
            tier = "Tier 1: Immediate Opportunity"
        elif s_opp >= w.tier_2_threshold:
            tier = "Tier 2: Targeted Augmentation"
        elif s_opp >= w.tier_3_threshold:
            tier = "Tier 3: Exploratory / Minor"
        else:
            tier = "Tier 4: Deprioritized / Blocked"

        task_title = str(row.get("task", "Unknown Task"))
        explanation = generate_task_explanation(
            task=task_title,
            ai_suitability=s_ai,
            physical_intensity=s_phys,
            regulatory_penalty=s_reg,
            feasibility=s_feas,
            opportunity=s_opp,
            hours_per_year=h
        )

        res = dict(row)
        res["time_exposure_score"] = round(s_time, 2)
        res["ai_suitability_score"] = round(s_ai, 2)
        res["ai_adoption_score"] = round(s_adopt, 2)
        res["physical_intensity_score"] = round(s_phys, 2)
        res["regulatory_penalty_score"] = round(s_reg, 2)
        res["feasibility_score"] = round(s_feas, 2)
        res["capacity_opportunity_score"] = round(s_opp, 2)
        res["ai_fit_category"] = category
        res["priority_tier"] = tier
        res["explanation"] = explanation

        scored_records.append(res)

    return pd.DataFrame(scored_records)


def save_scoring_results_to_duckdb(
    scored_df: pd.DataFrame,
    conn: Optional[Any] = None
) -> int:
    """Save scoring results into the analytical_scoring_results DuckDB table."""
    from database.db_manager import get_connection

    should_close = False
    if conn is None:
        conn = get_connection()
        should_close = True

    try:
        conn.execute("DELETE FROM analytical_scoring_results;")
        conn.register("df_temp_scoring", scored_df)
        conn.execute("""
            INSERT INTO analytical_scoring_results
            SELECT
                task_id,
                task,
                level,
                domain,
                field,
                subfield,
                category,
                classification,
                hours_per_year,
                time_exposure_score,
                ai_suitability_score,
                ai_adoption_score,
                physical_intensity_score,
                regulatory_penalty_score,
                feasibility_score,
                capacity_opportunity_score,
                ai_fit_category,
                priority_tier,
                explanation
            FROM df_temp_scoring;
        """)
        conn.unregister("df_temp_scoring")
        count = conn.execute("SELECT COUNT(*) FROM analytical_scoring_results;").fetchone()[0]
        return count
    finally:
        if should_close:
            conn.close()


if __name__ == "__main__":
    from database.db_manager import get_connection, query_df
    print("Testing scoring engine against DuckDB scinet_tasks_master...")
    conn = get_connection()
    tasks_df = query_df("SELECT * FROM scinet_tasks_master;", conn=conn)
    scored = score_tasks(tasks_df)
    saved_count = save_scoring_results_to_duckdb(scored, conn=conn)
    print(f"Scored and stored {saved_count} tasks.")

    print("\nPriority Tier Distribution:")
    print(scored["priority_tier"].value_counts())

    print("\nAI Fit Category Distribution:")
    print(scored["ai_fit_category"].value_counts())
    conn.close()
