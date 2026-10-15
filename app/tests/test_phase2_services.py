"""Phase-2 service & engine unit tests (no live DB required).

Covers the simulation engine (determinism, identity, clamping,
multiplier governance), the data-quality service (PASS/FAIL status
semantics, allowlist), recommendation overview semantics and segmentation
validation — all with a mocked ``database.run_query``.
"""

from __future__ import annotations

from typing import Dict

import numpy as np
import pandas as pd
import pytest

from app.business_logic import simulation
from app.services import data_quality_service as dq
from app.services import recommendation_service as reco
from app.services import segmentation_service as seg
from app.services import database

# ---------------------------------------------------------------------------
# fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def fake_db(monkeypatch):
    """Replace run_query with a capture-and-return; expose last SQL call."""

    class FakeDB:
        def __init__(self):
            self.calls: list[tuple[str, Dict]] = []
            self.queue: list[pd.DataFrame] = []

        def __call__(self, statement, params=None, **kw):
            self.calls.append((statement, params or {}))
            if self.queue:
                return self.queue.pop(0)
            return pd.DataFrame()

    fake = FakeDB()
    monkeypatch.setattr(database, "run_query", fake)
    return fake


def _eligible(n: int = 100) -> pd.DataFrame:
    rng = np.random.RandomState(42)
    categories = list(simulation.VERIFIED_OFFER_MULTIPLIERS)
    return pd.DataFrame(
        {
            "subscriber_id": [f"SUB_{i:08d}" for i in range(n)],
            "dominant_serving_cell_id": [f"CELL_{i % 8}" for i in range(n)],
            "offer_category": [categories[i % len(categories)] for i in range(n)],
            "monthly_total_gb": rng.uniform(4, 200, n),
            "avg_dl_throughput_mbps": np.where(rng.random(n) < 0.1, 0.0,
                                               rng.uniform(40, 300, n)),
            "p95_prb_utilisation_pct": rng.uniform(20, 95, n),
            "fwa_suitability_score": np.where(np.arange(n) % 5 == 0, 40, 60),
            "fwa_suitability_band": "Marginal",
            "churn_risk_band": np.where(np.arange(n) % 10 == 0, "High Risk", "Low Risk"),
            "final_priority_score": rng.uniform(0, 900, n),
        }
    )


# ---------------------------------------------------------------------------
# simulation engine
# ---------------------------------------------------------------------------


def test_simulation_default_params_identity():
    """Default parameters must reproduce the stored baseline (identity)."""
    df = _eligible(200)
    result = simulation.run_simulation(df)
    assert result["params"]["take_rate_pct"] == 100.0
    assert result["changed_actions"] == 0
    assert result["contact_now_scenario"] == result["contact_now_baseline"]
    assert result["cells_at_risk_scenario"] == result["cells_at_risk_baseline"]


def test_simulation_take_rate_scales_demand():
    df = _eligible(400)
    low = simulation.run_simulation(df, take_rate_pct=10.0)
    full = simulation.run_simulation(df, take_rate_pct=100.0)
    assert low["contact_now_scenario"] <= full["contact_now_scenario"]
    assert low["mean_post_scenario"] <= full["mean_post_scenario"]
    # 100% take rate = full verified uplift -> baseline (no action changes)
    assert full["changed_actions"] == 0


def test_simulation_missing_columns_raise():
    with pytest.raises(ValueError, match="monthly_total_gb"):
        simulation.run_simulation(_eligible(10).drop(columns=["monthly_total_gb"]))


def test_simulation_empty_input_returns_stable_result():
    result = simulation.run_simulation(pd.DataFrame(columns=simulation.REQUIRED_COLUMNS))
    assert result["contact_now_scenario"] == 0 and result["cells_total"] == 0
    assert result["params"]["take_rate_pct"] == 100.0


def test_simulation_params_clamped_to_documented_bounds():
    params = simulation.validate_params(
        take_rate_pct=250, uplift_cap_pct=99, safe_threshold=10, waitlist_threshold=200
    )
    assert params["take_rate_pct"] == 100.0
    assert params["uplift_cap_pct"] == 30.0
    assert params["safe_threshold"] == 40.0
    assert params["waitlist_threshold"] == 100.0


def test_simulation_deterministic_pure():
    df = _eligible(300)
    a = simulation.run_simulation(df, take_rate_pct=50.0)
    b = simulation.run_simulation(df, take_rate_pct=50.0)
    assert a["contact_now_scenario"] == b["contact_now_scenario"]
    assert (a["subscriber_rows"]["post_prb_scenario"].reset_index(drop=True)
            == b["subscriber_rows"]["post_prb_scenario"].reset_index(drop=True)).all()


def test_simulation_multipliers_only_override_verified_keys():
    multipliers = simulation.effective_multipliers({"Base Only": 2.0, "Bogus": 9.9})
    assert multipliers["Base Only"] == 2.0
    assert "Bogus" not in multipliers
    assert multipliers["Multi-Addon Bundle"] == 1.5


# ---------------------------------------------------------------------------
# data-quality service (mocked DB)
# ---------------------------------------------------------------------------


def _count_df(n: int) -> pd.DataFrame:
    return pd.DataFrame({"n": [n]})


def test_dq_row_counts_pass_when_matching(monkeypatch):
    def fake(_statement, params=None, **kw):
        table = _statement.split("FROM ")[-1].split(" ")[0].split(".", 1)[-1]
        return _count_df(dq.STAGE_ROW_BASELINES[table])

    monkeypatch.setattr(database, "run_query", fake)
    result = dq.row_count_checks()
    assert all(r["status"] == "PASS" for r in result["rows"])
    assert len(result["rows"]) == len(dq.STAGE_ROW_BASELINES)


def test_dq_row_count_mismatch_is_fail(monkeypatch):
    def fake(_statement, params=None, **kw):
        if "step13_recommendations" in _statement:
            return _count_df(100)
        return _count_df(12412)

    monkeypatch.setattr(database, "run_query", fake)
    row = next(r for r in dq.row_count_checks()["rows"] if "step13" in r["check"])
    assert row["status"] == "FAIL" and row["result"] == "100"


def test_dq_historical_checks_warn_without_invented_numbers():
    rows = dq.historical_checks()["rows"]
    assert len(rows) == 1 and rows[0]["status"] == "WARN"
    assert "unavailable" in rows[0]["result"].lower()


def test_dq_allowlist_rejects_unknown_tables(monkeypatch):
    monkeypatch.setattr(database, "run_query", lambda *a, **k: pd.DataFrame())
    with pytest.raises(ValueError, match="allowlisted"):
        dq._count("nonexistent_table")


# ---------------------------------------------------------------------------
# recommendation service
# ---------------------------------------------------------------------------


def test_reco_overview_counts_reason_presence(fake_db):
    rows = pd.DataFrame(
        {
            "subscriber_id": ["SUB_A", "SUB_B", "SUB_C", "SUB_D"],
            "offer_category": ["Base Only", "N/A", "Base + IPTV", "Base Only"],
            "recommended_offer": ["X", None, "Y", "Z"],
            "reason_codes": ["STR_HEAVY", "", "GAM_HEAVY;5G_COV", ""],
        }
    )
    fake_db.queue = [
        pd.DataFrame({"snapshot_month": [pd.Timestamp("2026-01-01")]}) for _ in range(4)
    ] + [
        pd.DataFrame({"n": [4]}),            # rows count
        rows,                                # rows
    ]
    overview = reco.get_recommendation_overview({"population": "All subscribers"})
    assert overview["total"] == 4
    assert overview["no_offer"] == 1 and overview["with_offer"] == 3
    assert overview["with_reason"] == 2 and overview["without_reason"] == 2


def test_reco_columns_explicit_no_star():
    assert "*" not in " ".join(reco.RECOMMENDATION_COLUMNS)


# ---------------------------------------------------------------------------
# segmentation service
# ---------------------------------------------------------------------------


def test_segmentation_unknown_dimension_raises():
    with pytest.raises(ValueError, match="dimension"):
        seg.get_segment_cross_tab({}, "bogus")


def test_segmentation_cluster_summary_aggregates(fake_db):
    fake_db.queue = [
        pd.DataFrame({"snapshot_month": [pd.Timestamp("2026-01-01")]}) for _ in range(4)
] + [
        pd.DataFrame({
            "subscriber_id": ["SUB_1", "SUB_2", "SUB_3"],
            "cluster_id": [0, 0, 2],
            "business_label": ["Persona A", "Persona A", "Persona B"],
            "arpu_monthly_tnd": [30.0, 40.0, 25.0],
            "monthly_total_gb": [10.0, 20.0, 30.0],
            "streaming_vol_gb": [1.0, 2.0, 3.0],
            "gaming_vol_gb": [0.0, 0.0, 0.0],
            "voip_minutes": [60.0, 70.0, 80.0],
            "tenure_months": [12.0, 24.0, 36.0],
            "contract_type": ["Prepaid", "Postpaid", "Prepaid"],
            "arpu_band": ["High", "High", "Mid"],
            "tenure_band": ["1Y", "2Y", "3Y"],
            "segment_tier": ["T1", "T1", "T2"],
            "handset_5g_ready_flag": [1, 1, 0],
            "multi_line_flag": [0, 1, 0],
        })
    ]
    summary = seg.get_cluster_summary({"population": "Eligible subscribers"})
    assert list(summary["subscribers"]) == [2, 1]
    assert summary["mean_arpu"].iloc[0] == pytest.approx(35.0)
    assert summary["mean_gb"].iloc[1] == pytest.approx(30.0)
