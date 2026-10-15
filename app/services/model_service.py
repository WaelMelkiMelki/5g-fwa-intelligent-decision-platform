"""Model Performance service — verified precomputed metrics only.

Displays ONLY metrics found in verified files (audit report, report_v4 LaTeX
chapters) and database objects. Conflicting values are surfaced together with
"metric validation required" instead of picking one as authoritative
(interaction spec §7, R10). NO live inference, NO retraining, NO artifacts.
"""

from __future__ import annotations

from typing import Any, Dict, List

# ---------------------------------------------------------------------------
# Verified values — sources cited inline (report_v4 chapters / step scripts).
# The pipeline-script documented configuration (step12 script) and the report
# tables are shown side by side where they differ; nothing is silently picked.
# ---------------------------------------------------------------------------

CHURN_METRICS: List[Dict[str, Any]] = [
    {
        "metric": "ROC-AUC (held-out test set, 585 rows)",
        "values": [
            {"value": 0.7094, "label": "Report ch.12 key-results table", "source": "report_v4/chapters/step12_churn_model.tex"},
            {"value": 0.8956, "label": "Appendix model comparison", "source": "report_v4/chapters/appendix/appendix.tex"},
        ],
        "conflict": True,
    },
    {
        "metric": "PR-AUC",
        "values": [{"value": 0.1854, "label": "Both sources agree", "source": "report_v4 (ch12 + appendix)"}],
        "conflict": False,
    },
    {
        "metric": "Random baseline PR-AUC",
        "values": [{"value": 0.102, "label": "Report ch12", "source": "report_v4/chapters/step12_churn_model.tex"}],
        "conflict": False,
    },
    {
        "metric": "Recall (threshold τ=0.15)",
        "values": [{"value": 0.3990, "label": "Report ch12", "source": "report_v4/chapters/step12_churn_model.tex"}],
        "conflict": False,
    },
    {
        "metric": "Precision (threshold τ=0.15)",
        "values": [{"value": 0.2351, "label": "Report ch12", "source": "report_v4/chapters/step12_churn_model.tex"}],
        "conflict": False,
    },
    {
        "metric": "F1 (threshold τ=0.15)",
        "values": [{"value": 0.2959, "label": "Report ch12", "source": "report_v4/chapters/step12_churn_model.tex"}],
        "conflict": False,
    },
    {
        "metric": "CV F1 (5-fold, chosen config)",
        "values": [{"value": "0.291 ± 0.041", "label": "Report ch12", "source": "report_v4/chapters/step12_churn_model.tex"}],
        "conflict": False,
    },
    {
        "metric": "Churn base rate",
        "values": [
            {"value": "10.2% (298 / 2,923)", "label": "Report ch12", "source": "report_v4/chapters/step12_churn_model.tex"},
            {"value": "6.7% (appendix, scale_pos_weight ≈ 13.93)", "label": "Appendix D", "source": "report_v4/chapters/appendix/appendix.tex"},
        ],
        "conflict": True,
    },
]

CONFUSION_MATRIX = {
    "label": "Churn confusion matrix (τ=0.15, held-out test set 585 rows) — Report ch12",
    "source": "report_v4/chapters/step12_churn_model.tex",
    "matrix": {
        "actual_churn_pred_churn": 24,
        "actual_churn_pred_active": 36,
        "actual_active_pred_churn": 78,
        "actual_active_pred_active": 447,
    },
}

TRAINING_METADATA: Dict[str, Any] = {
    "model": "XGBoost (binary:logistic) — classifier",
    "script": "step12_supervised_churn_model.py",
    "config_script": "n_estimators=300, max_depth=6, lr=0.05, random_state=42, scale_pos_weight≈8.81",
    "validation": "80/20 stratified split + 5-fold stratified CV; Platt (sigmoid) calibration",
    "band_bins": "[0.0, 0.15, 0.35, 0.60, 1.0] → Low / Medium / High / Critical Risk",
    "snapshot": "2026-01-01 (12,412 scored rows in step12_churn_predictions)",
    "note": "live inference not supported in Phase 1 — dashboard reads precomputed churn_probability.",
}

FEATURE_IMPORTANCE_DB_SOURCE = "report_v4/chapters/step12_churn_model.tex (Gain, XGBoost scikit-api)"
FEATURE_IMPORTANCE = [
    ("serving_cell_id_CELL_TN_0585", 0.0812),
    ("contract_type_Postpaid", 0.0678),
    ("segment_tier_Premium", 0.0583),
    ("site_id_SITE_TN_103", 0.0541),
    ("tenure_band_Short Tenure", 0.0497),
    ("arpu_monthly_tnd", 0.0432),
    ("contract_type_Prepaid", 0.0389),
    ("monthly_total_gb", 0.0355),
    ("serving_cell_id_CELL_TN_1207", 0.0324),
    ("handset_5g_ready_flag_True", 0.0301),
]

STEP15_SURROGATE = {
    "model": "XGBRegressor (200 trees, depth 5, seed 42) — priority-score surrogate",
    "test_r2": 0.9994,
    "source": "report_v4/chapters/step15_final_prioritisation.tex",
}

SNAPSHOT_STATS_SQL = """
SELECT COUNT(*)                                          AS n_subscribers,
       COUNT(*) FILTER (WHERE churn_risk_band = 'High Risk')    AS n_high_risk,
       COUNT(*) FILTER (WHERE churn_risk_band = 'Medium Risk') AS n_medium_risk,
       COUNT(*) FILTER (WHERE churn_risk_band = 'Low Risk')    AS n_low_risk,
       ROUND(AVG(churn_probability)::numeric, 4)         AS avg_churn_prob,
       MAX(churn_probability)                             AS max_churn_prob
FROM cleaned_data.step12_churn_predictions
"""


def get_model_performance_metadata() -> Dict[str, Any]:
    """Bundle of verified model-performance metadata (read-only, no inference)."""
    return {
        "churn_metrics": CHURN_METRICS,
        "confusion_matrix": CONFUSION_MATRIX,
        "training_metadata": TRAINING_METADATA,
        "feature_importance": FEATURE_IMPORTANCE,
        "feature_importance_source": FEATURE_IMPORTANCE_DB_SOURCE,
        "step15_surrogate": STEP15_SURROGATE,
        "has_conflicts": any(m["conflict"] for m in CHURN_METRICS),
        "conflicts": [m["metric"] for m in CHURN_METRICS if m["conflict"]],
    }


def get_snapshot_churn_stats() -> dict:
    """Live precomputed churn stats from step12_churn_predictions (read-only)."""
    from app.services import database

    return database.run_query(SNAPSHOT_STATS_SQL).iloc[0].to_dict()
