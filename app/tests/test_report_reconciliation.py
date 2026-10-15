"""Report <-> database reconciliation tests (SELECT-only).

Each test recomputes a KPI published in the project report (report_v4 LaTeX
chapters / compiled main.pdf) directly from the live ``cleaned_data`` tables
and compares it with the value the dashboard displays (the dashboard renders
the same tables via ``app.services``). Tests skip cleanly when no
``FWA_DB_*`` environment variables are present.

Two classes of tests:

* ``test_*_report_*``  â€” metrics where report, DB and dashboard agree (PASS
  rows in REPORT_DASHBOARD_RECONCILIATION.md).
* ``test_*_current_*`` â€” metrics of pipeline layers that were regenerated
  after the report was written (DATA REFRESH rows in the reconciliation
  document). The test pins the CURRENT database value so a future pipeline
  re-run cannot silently change the dashboard.

Run:
    FWA_DB_HOST=... FWA_DB_PORT=... FWA_DB_NAME=... FWA_DB_USER=... \\
    FWA_DB_PASSWORD=... python -m pytest app/tests/test_report_reconciliation.py -q
"""

from __future__ import annotations

import os

import pytest

from app.services import database

DB_READY = all(
    os.environ.get(k) for k in ("FWA_DB_HOST", "FWA_DB_USER", "FWA_DB_PASSWORD")
)

pytestmark = pytest.mark.skipif(
    not DB_READY, reason="No FWA_DB_* environment variables"
)

SCHEMA = os.environ.get("FWA_DB_SCHEMA", "cleaned_data")


def _count(sql: str) -> int:
    return int(database.run_query(sql).iloc[0]["n"])


def _scalar(sql: str) -> float:
    return float(database.run_query(sql).iloc[0].iloc[0])


def _eq(value: float, expected: float, tol: float = 0.01) -> bool:
    return abs(value - expected) <= max(abs(expected) * tol, tol)


# ---------------------------------------------------------------------------
# Population & grain (report ch1 p7, ch2 validation, ch4.1 key results)
# ---------------------------------------------------------------------------

def test_report_total_base_12412():
    assert _count(f"SELECT COUNT(*) AS n FROM {SCHEMA}.step15_final_campaign_list") == 12412


def test_report_eligible_2923():
    assert (
        _count(
            f"SELECT COUNT(*) AS n FROM {SCHEMA}.step15_final_campaign_list "
            f"WHERE fwa_suitability_score > 0"
        )
        == 2923
    )


def test_report_excluded_9489():
    assert (
        _count(
            f"SELECT COUNT(*) AS n FROM {SCHEMA}.step15_final_campaign_list "
            f"WHERE fwa_suitability_score = 0"
        )
        == 9489
    )


def test_report_eligible_share_23_5():
    v = _scalar(
        f"SELECT 100.0 * COUNT(*) FILTER (WHERE fwa_suitability_score > 0) / COUNT(*) "
        f"FROM {SCHEMA}.step15_final_campaign_list"
    )
    assert _eq(v, 23.5)


def test_report_grain_row_counts():
    checks = {
        "t1_monthly_core": 12412,
        "t2_crm_subscriber_master": 12412,
        "t3_cell_monthly_kpi": 731,
        "t4_coverage_address_grid": 12412,
        "t5_service_consumption_monthly": 12412,
        "abt_subscriber_month": 12412,
        "abt_subscriber_month_clustered": 2923,
        "step11_prioritization": 2923,
        "step13_recommendations": 2923,
        "step14_capacity_simulation": 2923,
    }
    for table, expected in checks.items():
        assert _count(f"SELECT COUNT(*) AS n FROM {SCHEMA}.{table}") == expected, table


def test_report_t1_daily_381836():
    assert _count(f"SELECT COUNT(*) AS n FROM {SCHEMA}.t1_subscriber_daily_profile") == 381836


def test_report_t3_daily_21965():
    assert _count(f"SELECT COUNT(*) AS n FROM {SCHEMA}.t3_ran_kpi_cell_daily") == 21965


def test_single_snapshot_month():
    n = _scalar(f"SELECT COUNT(DISTINCT snapshot_month) FROM {SCHEMA}.t2_crm_subscriber_master")
    assert n == 1.0


# ---------------------------------------------------------------------------
# Network layer (report ch2.5 p22-23) â€” dashboard page 4
# ---------------------------------------------------------------------------

def test_report_cells_731_network():
    assert _count(f"SELECT COUNT(*) AS n FROM {SCHEMA}.t3_cell_monthly_kpi") == 731


def test_report_network_kpis():
    assert _eq(
        _scalar(f"SELECT AVG(avg_prb_utilisation_pct) FROM {SCHEMA}.t3_cell_monthly_kpi"), 20.29, 0.011
    )
    assert _eq(
        _scalar(
            f"SELECT percentile_cont(0.5) WITHIN GROUP (ORDER BY p95_prb_utilisation_pct) "
            f"FROM {SCHEMA}.t3_cell_monthly_kpi"
        ),
        33.97,
        0.011,
    )
    assert _eq(
        _scalar(f"SELECT MAX(max_prb_utilisation_pct) FROM {SCHEMA}.t3_cell_monthly_kpi"), 74.68, 0.011
    )
    assert _eq(
        _scalar(f"SELECT AVG(avg_dl_throughput_mbps) FROM {SCHEMA}.t3_cell_monthly_kpi"), 99.97, 0.011
    )


def test_report_zero_constrained_cells():
    assert (
        _count(
            f"SELECT COUNT(*) AS n FROM {SCHEMA}.t3_cell_monthly_kpi "
            f"WHERE p95_prb_utilisation_pct >= 80 OR max_prb_utilisation_pct >= 80"
        )
        == 0
    )


# ---------------------------------------------------------------------------
# Coverage & eligibility (report ch2.6 p24-25, ch4.1 p37-38) â€” page 7
# ---------------------------------------------------------------------------

def test_report_signal_quality_classes():
    classes = {
        "Excellent": 782,
        "Acceptable": 2181,
        "Poor": 9449,
    }
    for cls, expected in classes.items():
        assert (
            _count(
                f"SELECT COUNT(*) AS n FROM {SCHEMA}.abt_subscriber_month "
                f"WHERE signal_quality_class = '{cls}'"
            )
            == expected
        ), cls


def test_report_exclusion_reasons():
    assert (
        _count(
            f"SELECT COUNT(*) AS n FROM {SCHEMA}.abt_subscriber_month "
            f"WHERE fwa_exclusion_reason = 'RF_Failure'"
        )
        == 9449
    )
    assert (
        _count(
            f"SELECT COUNT(*) AS n FROM {SCHEMA}.abt_subscriber_month "
            f"WHERE fwa_exclusion_reason = 'Fiber_Cannibalization'"
        )
        == 40
    )
    assert (
        _count(
            f"SELECT COUNT(*) AS n FROM {SCHEMA}.abt_subscriber_month "
            f"WHERE fwa_exclusion_reason = 'Capacity Constrained'"
        )
        == 0
    )


def test_report_eligible_score_stats():
    sql = (
        f"SELECT MIN(fwa_suitability_score), MAX(fwa_suitability_score), "
        f"AVG(fwa_suitability_score), STDDEV(fwa_suitability_score) "
        f"FROM {SCHEMA}.step15_final_campaign_list WHERE fwa_suitability_score > 0"
    )
    row = database.run_query(sql).iloc[0]
    assert int(row.iloc[0]) == 55
    assert int(row.iloc[1]) == 100
    assert _eq(float(row.iloc[2]), 64.0, 0.02)
    assert _eq(float(row.iloc[3]), 11.0, 0.02)


def test_report_eligible_with_5g_coverage_291():
    assert (
        _count(
            f"SELECT COUNT(*) AS n FROM {SCHEMA}.abt_subscriber_month a "
            f"JOIN {SCHEMA}.step15_final_campaign_list s ON s.subscriber_id = a.subscriber_id "
            f"WHERE s.fwa_suitability_score > 0 AND a.coverage_5g_flag"
        )
        == 291
    )


def test_current_radio_feasibility_classes():
    """Layer regenerated after report (report: 430/2228/305/9449)."""
    classes = {
        "5G_Feasible": 291,
        "4G_Fallback": 2338,
        "Fiber_Competitor": 109,
        "Infeasible": 9674,
    }
    for cls, expected in classes.items():
        assert (
            _count(
                f"SELECT COUNT(*) AS n FROM {SCHEMA}.abt_subscriber_month "
                f"WHERE radio_feasibility_class = '{cls}'"
            )
            == expected
        ), cls


def test_current_suitability_bands():
    """Score layer regenerated after report (report: 276/1030/1323)."""
    bands = {"Premium": 308, "Standard": 1036, "Marginal": 1579}
    for band, expected in bands.items():
        assert (
            _count(
                f"SELECT COUNT(*) AS n FROM {SCHEMA}.step15_final_campaign_list "
                f"WHERE fwa_suitability_band = '{band}'"
            )
            == expected
        ), band


# ---------------------------------------------------------------------------
# Commercial binning & household (report ch2.4 p19-20) â€” page 8 cross-tabs
# ---------------------------------------------------------------------------

def test_report_stored_arpu_bands():
    assert (
        _count(f"SELECT COUNT(*) AS n FROM {SCHEMA}.abt_subscriber_month WHERE arpu_band = 'Low ARPU'")
        == 8381
    )
    assert (
        _count(f"SELECT COUNT(*) AS n FROM {SCHEMA}.abt_subscriber_month WHERE arpu_band = 'High ARPU'")
        == 4031
    )


def test_report_stored_tenure_bands():
    assert (
        _count(
            f"SELECT COUNT(*) AS n FROM {SCHEMA}.abt_subscriber_month WHERE tenure_band = 'Short Tenure'"
        )
        == 6372
    )
    assert (
        _count(
            f"SELECT COUNT(*) AS n FROM {SCHEMA}.abt_subscriber_month WHERE tenure_band = 'Long Tenure'"
        )
        == 6040
    )


def test_report_household_flags():
    assert _count(f"SELECT COUNT(*) AS n FROM {SCHEMA}.abt_subscriber_month WHERE multi_line_flag") == 4104
    assert _count(f"SELECT COUNT(*) AS n FROM {SCHEMA}.abt_subscriber_month WHERE NOT multi_line_flag") == 8308
    assert _eq(_scalar(f"SELECT AVG(num_active_lines) FROM {SCHEMA}.abt_subscriber_month"), 1.81, 0.01)


# ---------------------------------------------------------------------------
# Prioritisation (report ch4.3 p48) â€” step11 statistics are exact
# ---------------------------------------------------------------------------

def test_report_priority_score_distribution():
    sql = (
        f"SELECT MIN(candidate_prioritization_score), "
        f"percentile_cont(0.25) WITHIN GROUP (ORDER BY candidate_prioritization_score), "
        f"percentile_cont(0.5) WITHIN GROUP (ORDER BY candidate_prioritization_score), "
        f"AVG(candidate_prioritization_score), "
        f"percentile_cont(0.75) WITHIN GROUP (ORDER BY candidate_prioritization_score), "
        f"MAX(candidate_prioritization_score), "
        f"STDDEV(candidate_prioritization_score) "
        f"FROM {SCHEMA}.step11_prioritization"
    )
    row = database.run_query(sql).iloc[0]
    expected = [8.04, 19.26, 28.41, 35.98, 51.79, 90.56, 19.12]
    for got, want in zip([float(v) for v in row.iloc], expected):
        assert _eq(got, want, 0.005)


def test_report_top_decile_cluster_mix():
    assert (
        _count(
            f"SELECT COUNT(*) AS n FROM (SELECT cluster_id FROM {SCHEMA}.step11_prioritization "
            f"ORDER BY candidate_prioritization_score DESC LIMIT 292) t WHERE cluster_id = 0"
        )
        == 232
    )
    assert (
        _count(
            f"SELECT COUNT(*) AS n FROM (SELECT cluster_id FROM {SCHEMA}.step11_prioritization "
            f"ORDER BY candidate_prioritization_score DESC LIMIT 292) t WHERE cluster_id = 2"
        )
        == 58
    )
    assert (
        _count(
            f"SELECT COUNT(*) AS n FROM (SELECT cluster_id FROM {SCHEMA}.step11_prioritization "
            f"ORDER BY candidate_prioritization_score DESC LIMIT 292) t WHERE cluster_id = 3"
        )
        == 2
    )


def test_report_priority_extremes():
    assert (
        _count(
            f"SELECT COUNT(*) AS n FROM {SCHEMA}.step11_prioritization "
            f"WHERE subscriber_id = 'SUB_B00385A9' AND ROUND(candidate_prioritization_score::numeric, 2) = 90.56"
        )
        == 1
    )
    assert (
        _count(
            f"SELECT COUNT(*) AS n FROM {SCHEMA}.step11_prioritization "
            f"WHERE subscriber_id = 'SUB_BF5FFDF1' AND ROUND(candidate_prioritization_score::numeric, 2) = 8.04"
        )
        == 1
    )


# ---------------------------------------------------------------------------
# Churn (report ch4.4 p50-51, Table 4.7 risk bands) â€” page 5
# ---------------------------------------------------------------------------

def test_report_churn_risk_bands_eligible():
    """Report Table 4.7 counts reproduce exactly over the eligible subset."""
    assert (
        _count(
            f"SELECT COUNT(*) AS n FROM {SCHEMA}.step12_churn_predictions b "
            f"JOIN {SCHEMA}.step15_final_campaign_list s ON s.subscriber_id = b.subscriber_id "
            f"WHERE s.fwa_suitability_score > 0 AND b.churn_risk_band = 'Low Risk'"
        )
        == 2795
    )
    assert (
        _count(
            f"SELECT COUNT(*) AS n FROM {SCHEMA}.step12_churn_predictions b "
            f"JOIN {SCHEMA}.step15_final_campaign_list s ON s.subscriber_id = b.subscriber_id "
            f"WHERE s.fwa_suitability_score > 0 AND b.churn_risk_band = 'Medium Risk'"
        )
        == 114
    )
    assert (
        _count(
            f"SELECT COUNT(*) AS n FROM {SCHEMA}.step12_churn_predictions b "
            f"JOIN {SCHEMA}.step15_final_campaign_list s ON s.subscriber_id = b.subscriber_id "
            f"WHERE s.fwa_suitability_score > 0 AND b.churn_risk_band = 'High Risk'"
        )
        == 14
    )


def test_no_critical_risk_rows():
    assert (
        _count(
            f"SELECT COUNT(*) AS n FROM {SCHEMA}.step12_churn_predictions "
            f"WHERE churn_risk_band = 'Critical Risk'"
        )
        == 0
    )


def test_current_churn_label_rate():
    """Churn ground-truth labels were regenerated after the report was written.

    Report ch4.4 Table 4.2: 298 churners (10.2%) among eligible. Current DB:
    142 (4.9%). Pinned here so a future re-run cannot drift silently.
    """
    assert (
        _count(
            f"SELECT COUNT(*) AS n FROM {SCHEMA}.abt_subscriber_month a "
            f"JOIN {SCHEMA}.step15_final_campaign_list s ON s.subscriber_id = a.subscriber_id "
            f"WHERE s.fwa_suitability_score > 0 AND a.churn = 1"
        )
        == 142
    )


# ---------------------------------------------------------------------------
# Recommendations (report ch5.1 p54-56) â€” page 9
# ---------------------------------------------------------------------------

def test_report_tier1_base_plans():
    assert (
        _count(f"SELECT COUNT(*) AS n FROM {SCHEMA}.step13_recommendations WHERE tier1_base_plan LIKE '%Prepaid'")
        == 1932
    )
    assert (
        _count(f"SELECT COUNT(*) AS n FROM {SCHEMA}.step13_recommendations WHERE tier1_base_plan LIKE '%Postpaid'")
        == 991
    )


def test_report_addon_hits():
    assert _count(f"SELECT COUNT(*) AS n FROM {SCHEMA}.step13_recommendations WHERE tier2_addons ILIKE '%IPTV%'") == 604
    assert _count(f"SELECT COUNT(*) AS n FROM {SCHEMA}.step13_recommendations WHERE tier2_addons ILIKE '%Gaming%'") == 89
    assert _count(f"SELECT COUNT(*) AS n FROM {SCHEMA}.step13_recommendations WHERE tier2_addons ILIKE '%Convergent%'") == 440
    assert _count(f"SELECT COUNT(*) AS n FROM {SCHEMA}.step13_recommendations WHERE tier2_addons <> ''") == 1011


def test_report_offer_categories():
    offers = {
        "Base Only": 1912,
        "Base + IPTV": 498,
        "Base + Convergent Fixed-Mobile Add-on": 343,
        "Multi-Addon Bundle": 118,
        "Base + Gaming Add-on": 52,
    }
    for offer, expected in offers.items():
        assert (
            _count(
                f"SELECT COUNT(*) AS n FROM {SCHEMA}.step13_recommendations "
                f"WHERE offer_category = '{offer}'"
            )
            == expected
        ), offer


# ---------------------------------------------------------------------------
# Capacity simulation (report ch5.2 p59-60) â€” page 10
# ---------------------------------------------------------------------------

def test_report_capacity_400_cells():
    assert (
        _count(
            f"SELECT COUNT(DISTINCT dominant_serving_cell_id) AS n FROM {SCHEMA}.step14_capacity_simulation"
        )
        == 400
    )


def test_report_capacity_metrics():
    assert _eq(
        _scalar(
            f"SELECT AVG(expected_additional_prb_proxy) FROM {SCHEMA}.step14_capacity_simulation"
        ),
        0.50,
        0.011,
    )
    assert _eq(
        _scalar(
            f"SELECT AVG(post_migration_prb_utilisation_proxy) FROM {SCHEMA}.step14_capacity_simulation"
        ),
        40.49,
        0.011,
    )
    assert _eq(
        _scalar(
            f"SELECT MAX(post_migration_prb_utilisation_proxy) FROM {SCHEMA}.step14_capacity_simulation"
        ),
        67.13,
        0.011,
    )
    assert (
        _count(
            f"SELECT COUNT(*) AS n FROM {SCHEMA}.step14_capacity_simulation WHERE rollout_status = 'Approved'"
        )
        == 2923
    )
    assert (
        _count(
            f"SELECT COUNT(*) AS n FROM {SCHEMA}.step14_capacity_simulation "
            f"WHERE expected_additional_prb_proxy >= 15.0"
        )
        == 65
    )


# ---------------------------------------------------------------------------
# Final campaign actions (report ch5.3 p64) â€” pages 1/2
# ---------------------------------------------------------------------------

def test_report_campaign_actions():
    actions = {"Exclude": 9489, "Contact Later": 2180, "Contact Now": 731, "Manual Review": 12}
    for action, expected in actions.items():
        assert (
            _count(
                f"SELECT COUNT(*) AS n FROM {SCHEMA}.step15_final_campaign_list "
                f"WHERE campaign_action = '{action}'"
            )
            == expected
        ), action


def test_report_exclusion_reason_step15():
    assert (
        _count(
            f"SELECT COUNT(*) AS n FROM {SCHEMA}.step15_final_campaign_list "
            f"WHERE exclusion_reason = 'RF_Failure'"
        )
        == 9449
    )
    assert (
        _count(
            f"SELECT COUNT(*) AS n FROM {SCHEMA}.step15_final_campaign_list "
            f"WHERE exclusion_reason = 'Fiber_Cannibalization'"
        )
        == 40
    )


def test_q3_contact_now_rule():
    assert (
        _count(
            f"SELECT COUNT(*) AS n FROM {SCHEMA}.step15_final_campaign_list "
            f"WHERE fwa_suitability_score > 0 AND final_priority_score >= ("
            f"SELECT percentile_cont(0.75) WITHIN GROUP (ORDER BY final_priority_score) "
            f"FROM {SCHEMA}.step15_final_campaign_list WHERE fwa_suitability_score > 0)"
        )
        == 731
    )


def test_report_top_final_score_value():
    assert _eq(
        _scalar(f"SELECT MAX(final_priority_score) FROM {SCHEMA}.step15_final_campaign_list"),
        1184.75,
        0.01,
    )


# ---------------------------------------------------------------------------
# Join integrity (dashboard relies on these joins)
# ---------------------------------------------------------------------------

def test_dashboard_join_integrity():
    assert (
        _count(
            f"SELECT COUNT(*) AS n FROM {SCHEMA}.step15_final_campaign_list s "
            f"JOIN {SCHEMA}.abt_subscriber_month a ON a.subscriber_id = s.subscriber_id "
            f"AND a.snapshot_month = s.snapshot_month"
        )
        == 12412
    )
    assert (
        _count(
            f"SELECT COUNT(*) AS n FROM {SCHEMA}.abt_subscriber_month a "
            f"JOIN {SCHEMA}.t4_coverage_address_grid g ON g.address_id = a.address_id"
        )
        == 12412
    )
    assert (
        _count(
            f"SELECT COUNT(*) AS n FROM {SCHEMA}.step12_churn_predictions b "
            f"LEFT JOIN {SCHEMA}.step15_final_campaign_list s ON s.subscriber_id = b.subscriber_id "
            f"WHERE s.subscriber_id IS NULL"
        )
        == 0
    )
