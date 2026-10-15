"""Phase-2 UAT page tests (live read-only DB required).

AppTest page runs + independent live-SQL reconciliation for pages 6-10:
Data Quality, Coverage & Eligibility, Customer Segmentation, Offer
Recommendations and What-If Simulation. Skips cleanly without FWA_DB_* env.
"""

from __future__ import annotations

import os
from pathlib import Path

import pytest
from streamlit.testing.v1 import AppTest

from app.services import database

ROOT = Path(__file__).resolve().parents[2]
DB_READY = any(
    os.environ.get(key) for key in ("FWA_DB_HOST", "FWA_DB_USER", "FWA_DB_PASSWORD")
)

pytestmark = pytest.mark.skipif(not DB_READY, reason="No FWA_DB_* environment variables")

SECRETS = {
    "database": {
        "host": os.environ.get("FWA_DB_HOST", "localhost"),
        "port": int(os.environ.get("FWA_DB_PORT", "5432")),
        "name": os.environ.get("FWA_DB_NAME", "postgres"),
        "user": os.environ.get("FWA_DB_USER", "postgres"),
        "password": os.environ.get("FWA_DB_PASSWORD", ""),
        "schema": os.environ.get("FWA_DB_SCHEMA", "cleaned_data"),
    }
}

PAGE = {
    "p6": ROOT / "app" / "pages" / "6_Data_Quality.py",
    "p7": ROOT / "app" / "pages" / "7_Coverage_and_Eligibility.py",
    "p8": ROOT / "app" / "pages" / "8_Customer_Segmentation.py",
    "p9": ROOT / "app" / "pages" / "9_Offer_Recommendations.py",
    "p10": ROOT / "app" / "pages" / "10_What_If_Simulation.py",
}

ELIGIBLE_FILTERS = {
    "population": "Eligible subscribers",
    "clusters": [], "churn_bands": [], "coverage_classes": [],
    "capacity_statuses": [], "offers": [], "campaign_actions": [],
}


def run_page(name: str, **state):
    at = AppTest.from_file(str(PAGE[name]), default_timeout=120)
    at.secrets["database"] = SECRETS["database"]
    for key, value in state.items():
        at.session_state[key] = value
    at.run()
    return at


def by_label(elements, label):
    return next(e for e in elements if e.label == label)


def sql_scalar(statement: str, params=None) -> float:
    return float(database.run_query(statement, params=params).iloc[0, 0])


def sql_row(statement: str, params=None):
    return database.run_query(statement, params=params).iloc[0]


def metric_map(at) -> dict:
    return {m.label: m.value for m in at.metric}


def clean_num(value: str) -> int:
    return int(str(value).replace(",", "").replace("%", ""))


def frame(at, index: int = 0):
    value = at.dataframe[index].value
    return value.to_pandas() if hasattr(value, "to_pandas") else value


# ---------------------------------------------------------------------------
# 6. Data Quality
# ---------------------------------------------------------------------------


def test_dataquality_overall_pass_plus_checks():
    at = run_page("p6")
    assert not at.exception, [str(e.value) for e in at.exception]
    assert not at.error
    values = metric_map(at)
    assert values["Overall"] == "PASS"
    assert clean_num(values["Checks run"]) >= 80
    assert clean_num(values["PASS"]) == clean_num(values["Checks run"]) - 1
    assert clean_num(values["Warnings"]) == 1
    infos = " ".join(str(i.value) for i in at.info)
    assert "Historical data-quality trends are unavailable" in infos


def test_data6_table_has_statuses_and_sections():
    at = run_page("p6")
    df = frame(at)
    assert {"check", "result", "expected", "status", "source"}.issubset(df.columns)
    assert df["status"].isin(["PASS", "WARN", "FAIL"]).all()
    assert "FAIL" not in set(df["status"])


# ---------------------------------------------------------------------------
# 7. Coverage & eligibility
# ---------------------------------------------------------------------------


def test_data7_kpis_reconciled_live():
    eligible = sql_scalar(
        "SELECT COUNT(*) FROM cleaned_data.step15_final_campaign_list "
        "WHERE fwa_suitability_score > 0"
    )
    excluded = 12412 - eligible
    at = run_page("p7")
    assert not at.exception and not at.error
    values = metric_map(at)
    assert values["Subscribers"] == "12,412"
    assert clean_num(values["Eligible (score > 0)"]) == int(eligible)
    assert clean_num(values["Excluded"]) == int(excluded)
    assert len(at.get("plotly_chart")) >= 4


def test_data7_coverage_focus_updates_counts():
    at = run_page("p7")
    by_label(at.selectbox, "Coverage class focus").set_value("5G_Feasible").run()
    assert not at.exception and not at.error
    expected = sql_scalar(
        "SELECT COUNT(*) FROM cleaned_data.step15_final_campaign_list s "
        "JOIN cleaned_data.abt_subscriber_month a "
        "ON a.subscriber_id = s.subscriber_id AND a.snapshot_month = s.snapshot_month "
        "WHERE a.radio_feasibility_class = '5G_Feasible'"
    )
    assert clean_num(metric_map(at)["Subscribers"]) == int(expected)


def test_data7_map_verified_gate():
    at = run_page("p7")
    assert not at.exception and not at.error
    warnings = " ".join(str(w.value) for w in at.warning)
    assert "Coverage map unavailable" not in warnings  # join is verified
    grid = {m.label: clean_num(m.value) for m in at.metric
            if m.label in ("Address points", "Serving cells", "Governorates")}
    assert grid["Address points"] == 12412
    assert grid["Serving cells"] == 731


# ---------------------------------------------------------------------------
# 8. Customer segmentation
# ---------------------------------------------------------------------------


def test_data8_segment_summary_reconciled():
    n_cluster = sql_scalar(
        "SELECT COUNT(*) FROM cleaned_data.abt_subscriber_month_clustered"
    )
    persona_bands = sql_scalar(
        "SELECT COUNT(DISTINCT cluster_id) "
        "FROM cleaned_data.abt_subscriber_month_clustered"
    )
    at = run_page("p8")
    assert not at.exception and not at.error
    values = metric_map(at)
    assert clean_num(values["Segmented subscribers"]) == int(n_cluster)
    assert clean_num(values["Personas"]) == int(persona_bands)
    assert len(at.dataframe) >= 2


def test_data8_cross_tab_dimension_switches():
    at = run_page("p8")
    assert not at.exception
    ids = by_label(at.selectbox, "Dimension")
    ids.set_value("contract_type").run()
    assert not at.exception and not at.error
    main = frame(at, 1)
    assert main.index.name == "contract_type"


# ---------------------------------------------------------------------------
# 9. Offer recommendations
# ---------------------------------------------------------------------------


def test_data9_overview_reconciled():
    with_offer = sql_scalar(
        "SELECT COUNT(*) FROM cleaned_data.step13_recommendations "
        "WHERE offer_category != 'N/A'"
    )
    with_reason = sql_scalar(
        "SELECT COUNT(*) FROM cleaned_data.step13_recommendations "
        "WHERE reason_codes IS NOT NULL AND reason_codes != ''"
    )
    at = run_page("p9")
    assert not at.exception and not at.error
    values = metric_map(at)
    assert clean_num(values["With offer"]) == int(with_offer)
    assert clean_num(values["With reason codes"]) == int(with_reason)


def test_data9_table_masked_and_paginated():
    at = run_page("p9")
    assert not at.exception and not at.error
    df = frame(at)
    assert len(df) == 50
    for sid in df["subscriber_id"].tolist():
        assert str(sid).endswith("..."), f"unmasked recommendation id: {sid}"
    assert "reason_codes" in df.columns
    assert (df["offer_category"] == "No Offer").sum() == 0


def test_data9_drilldown_selection():
    at = run_page("p9")
    chosen = by_label(at.selectbox, "Choose a subscriber (masked ID)").value
    assert str(chosen).endswith("...")
    by_label(at.button, "Open subscriber profile").click().run()
    selection = at.session_state["fwa.selection"]
    assert selection["subscriber_id"] is not None
    assert str(selection["subscriber_id"]).startswith("SUB_")


# ---------------------------------------------------------------------------
# 10. What-if simulation
# ---------------------------------------------------------------------------


def test_data10_run_identity_and_reset():
    at = run_page("p10")
    assert not at.exception and not at.error
    by_label(at.button, "Run simulation").click().run()
    assert not at.exception and not at.error
    values = metric_map(at)
    assert values["Changed actions"] == "0"
    assert values["Contact Now (scenario)"] == "731"
    why = at.session_state["fwa.whatif"]
    assert why["status"] == "ok" and why["stale"] is False

    by_label(at.number_input, "Take-up rate (%)").set_value(60.0).run()
    assert at.session_state["fwa.whatif"]["stale"] is True
    by_label(at.button, "Run simulation").click().run()
    what2 = at.session_state["fwa.whatif"]
    assert what2["status"] == "ok" and what2["stale"] is False
    assert {"Contact Now (scenario)", "Changed actions"} <= set(metric_map(at))

    by_label(at.button, "Reset").click().run()
    assert at.session_state["fwa.whatif"]["result"] is None
    assert at.session_state["fwa.whatif"]["status"] == "idle"


def test_data10_exploratory_warning_shown():
    at = run_page("p10")
    assert not at.exception
    warnings = " ".join(str(w.value) for w in at.warning)
    captions = " ".join(str(c.value) for c in at.caption)
    combined = warnings + " " + captions
    assert "not persisted" in combined and "exploratory" in combined
