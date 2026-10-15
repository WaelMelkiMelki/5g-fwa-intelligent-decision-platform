"""Data Quality service — aggregate quality checks against approved objects.

Source of truth: ``cleaned_data`` (ten approved objects, SCHEMA_MAPPING.md §1)
and the verified baselines documented in SCHEMA_MAPPING.md (§1, §4, §5) and
``app/sql/verify_schema_mapping.sql`` (sections 1-7). Every check is an
aggregate SELECT (COUNT / COUNT DISTINCT); NO subscriber identifiers are ever
selected, and NO statement can write (the read-only guard enforces it).

Status semantics (data-quality page):
  PASS  — live aggregate equals the documented expected value
  FAIL  — live aggregate differs from the documented expected value
  WARN  — indicator cannot be verified from the approved objects (e.g.
          historical pipeline-cleaning statistics require the polluted_data
          layer, which is outside the approved ten) or is informational

Historical note: no time series exists — pipeline tables are single-snapshot
(2026-01-01) by design; the page prints:
  "Historical data-quality trends are unavailable for the current snapshot."
"""

from __future__ import annotations

from typing import Any, Dict, List, Sequence

import pandas as pd

from app.services import database

# ---------------------------------------------------------------------------
# Documented baselines (SCHEMA_MAPPING.md §1 tables, §5 baselines). Expected
# values per object; live counts are computed, never hard-coded.
# ---------------------------------------------------------------------------
STAGE_ROW_BASELINES: Dict[str, int] = {
    "step15_final_campaign_list": 12412,
    "abt_subscriber_month": 12412,
    "step12_churn_predictions": 12412,
    "step13_recommendations": 2923,
    "step14_capacity_simulation": 2923,
    "t3_cell_monthly_kpi": 731,
    "t4_coverage_features": 12412,
    "t4_coverage_address_grid": 12412,
    "abt_subscriber_month_clustered": 2923,
    "step11_prioritization": 2923,
}

ALLOWED_TABLES: frozenset = frozenset(STAGE_ROW_BASELINES)

# Important dashboard fields that must carry NO NULLs (expected 0).
ZERO_NULL_FIELDS: Dict[str, Sequence[str]] = {
    "step15_final_campaign_list": [
        "fwa_suitability_band",
        "churn_probability",
        "churn_risk_band",
        "offer_category",
        "campaign_action",
        "final_priority_score",
        "Base_Score",
        "business_label",
    ],
    "abt_subscriber_month": [
        "governorate",
        "signal_quality_class",
        "radio_feasibility_class",
        "dominant_serving_cell_id",
        "p95_prb_utilisation_pct",
        "predicted_rsrp_dbm",
        "predicted_sinr_db",
        "monthly_total_gb",
    ],
    "step12_churn_predictions": ["churn_probability"],
    "step13_recommendations": [
        "tier1_base_plan", "tier2_addons", "recommended_offer", "offer_category",
    ],
    "step14_capacity_simulation": [
        "expected_additional_prb_proxy",
        "post_migration_prb_utilisation_proxy",
    ],
    "t3_cell_monthly_kpi": ["p95_prb_utilisation_pct"],
    "t4_coverage_address_grid": ["latitude", "longitude"],
}

# By-design NULLs (sentinel / eligibility design, NOT defects).
BY_DESIGN_NULLS: Dict[str, Dict[str, int]] = {
    "step15_final_campaign_list": {
        "rollout_status": 9489,
        "post_migration_capacity_risk": 9489,
    },
    "abt_subscriber_month": {"fwa_exclusion_reason": 2923},
}

NO_CRITICAL_CHURN_NOTE = (
    "Vocabulary allows 'Critical Risk' (bins [0,.15,.35,.60,1]); the snapshot "
    "contains no Critical row (verified)."
)


def _row(section: str, name: str, live: Any, expected: Any, status: str,
         source: str, detail: str = "") -> Dict[str, Any]:
    return {
        "section": section,
        "check": name,
        "result": str(live),
        "expected": str(expected),
        "status": status,
        "source": source,
        "detail": detail,
    }


def _qq(identifier: str) -> str:
    """Quote an identifier for case-safe SQL (mixed-case columns exist)."""
    return f'"{identifier}"'


def _count(table: str, where: str = "") -> int:
    """COUNT(*) on an allowlisted table with an optional WHERE fragment."""
    if table not in ALLOWED_TABLES:
        raise ValueError(f"Table not allowlisted: {table!r}")
    sql = f"SELECT COUNT(*) AS n FROM cleaned_data.{table} {where}"
    return int(database.run_query(sql).iloc[0]["n"])


def _count_distinct(table: str, column: str) -> int:
    if table not in ALLOWED_TABLES:
        raise ValueError(f"Table not allowlisted: {table!r}")
    sql = (f"SELECT COUNT(DISTINCT {_qq(column)}) AS n "
           f"FROM cleaned_data.{table}")
    return int(database.run_query(sql).iloc[0]["n"])


def _count_pair_distinct(table: str, columns: Sequence[str]) -> int:
    if table not in ALLOWED_TABLES:
        raise ValueError(f"Table not allowlisted: {table!r}")
    cols = ", ".join(_qq(c) for c in columns)
    sql = f"SELECT COUNT(DISTINCT ({cols})) AS n FROM cleaned_data.{table}"
    return int(database.run_query(sql).iloc[0]["n"])


def _eq(live: Any, expected: Any) -> str:
    return "PASS" if live == expected else "FAIL"


# ---------------------------------------------------------------------------
# Check bands
# ---------------------------------------------------------------------------


def row_count_checks() -> Dict[str, Any]:
    """Operational — row counts by analytical stage."""
    out = []
    for table, expected in STAGE_ROW_BASELINES.items():
        live = _count(table)
        out.append(_row("Stage row counts", f"{table}",
                        f"{live:,}", f"{expected:,}", _eq(live, expected),
                        "SCHEMA_MAPPING §1/§5"))
    return {"section": "Stage row counts", "rows": out}


def uniqueness_checks() -> Dict[str, Any]:
    """Operational — subscriber uniqueness per stage."""
    out = []
    for table, key in [
        ("step15_final_campaign_list", "subscriber_id"),
        ("abt_subscriber_month", "subscriber_id"),
        ("step12_churn_predictions", "subscriber_id"),
        ("step13_recommendations", "subscriber_id"),
        ("step14_capacity_simulation", "subscriber_id"),
        ("abt_subscriber_month_clustered", "subscriber_id"),
        ("step11_prioritization", "subscriber_id"),
        ("t4_coverage_address_grid", "address_id"),
        ("t3_cell_monthly_kpi", "cell_id"),
    ]:
        total = _count(table)
        distinct = _count_distinct(table, key)
        dup = total - distinct
        out.append(_row(
            "Subscriber uniqueness", f"{table}: {key}",
            f"{distinct:,} distinct", "== row count (no duplicates)",
            "PASS" if dup == 0 else "FAIL",
            "verify_schema_mapping.sql §3", f"duplicates={dup:,}"))
    return {"rows": out}


def snapshot_checks() -> Dict[str, Any]:
    """Operational — exactly one snapshot month (DECISION 5 / I8)."""
    out = []
    for table in ("step15_final_campaign_list", "abt_subscriber_month",
                  "step12_churn_predictions", "t3_cell_monthly_kpi"):
        df = database.run_query(
            f"SELECT DISTINCT snapshot_month FROM cleaned_data.{table} "
            "ORDER BY snapshot_month"
        )
        months = [str(m) for m in df["snapshot_month"].tolist()]
        live = "; ".join(months) if months else "(none)"
        ok = len(months) == 1 and months[0] == "2026-01-01"
        out.append(_row("Snapshot count", f"{table} snapshot_month",
                        live, "1 value: 2026-01-01",
                        "PASS" if ok else "FAIL",
                        "SCHEMA_MAPPING §5",
                        f"distinct={len(months)}"))
    return {"rows": out}


def duplicate_key_checks() -> Dict[str, Any]:
    """Operational — duplicate-key detection on (subscriber_id, snapshot)."""
    out = []
    for table, columns in [
        ("step15_final_campaign_list", ("subscriber_id", "snapshot_month")),
        ("abt_subscriber_month", ("subscriber_id", "snapshot_month")),
        ("step12_churn_predictions", ("subscriber_id", "snapshot_month")),
    ]:
        total = _count(table)
        distinct = _count_pair_distinct(table, columns)
        out.append(_row("Duplicate keys",
                        f"{table} ({', '.join(columns)})",
                        f"{total:,} rows",
                        "rows == distinct pairs",
                        "PASS" if total == distinct else "FAIL",
                        "verify_schema_mapping.sql §3",
                        f"duplicates={total - distinct:,}"))
    return {"rows": out}


def missing_value_checks() -> Dict[str, Any]:
    """Operational — NULL counts in important dashboard fields."""
    out = []
    for table, columns in ZERO_NULL_FIELDS.items():
        for column in columns:
            live = _count(table, f"WHERE {_qq(column)} IS NULL")
            out.append(_row("Missing values", f"{table}.{column}",
                            f"{live:,}", "0", _eq(live, 0),
                            "verify_schema_mapping.sql §4"))
    for table, mapping in BY_DESIGN_NULLS.items():
        for column, expected in mapping.items():
            live = _count(table, f"WHERE {_qq(column)} IS NULL")
            out.append(_row("Missing values (by design)", f"{table}.{column}",
                            f"{live:,}", f"{expected:,} NULL",
                            _eq(live, expected),
                            "SCHEMA_MAPPING §4.6"))
    return {"rows": out}


def sentinel_checks() -> Dict[str, Any]:
    """Operational — sentinel display conventions (DECISION 2), DB values."""
    out = []
    for predicate, expected in [
        ("cluster_id = -1", 9489),
        ("offer_category = 'N/A'", 9489),
    ]:
        live = _count("step15_final_campaign_list", f"WHERE {predicate}")
        out.append(_row("Sentinel values", f"step15 {predicate}",
                        f"{live:,}", f"{expected:,}",
                        _eq(live, expected), "SCHEMA_MAPPING §4.6"))
    return {"rows": out}


def join_coverage_checks() -> Dict[str, Any]:
    """Operational — join coverage between analytical stages."""
    out = []
    checks = [
        ("step15 ⋈ abt", 12412,
         "SELECT COUNT(*) FROM cleaned_data.step15_final_campaign_list s "
         "JOIN cleaned_data.abt_subscriber_month a "
         "ON a.subscriber_id = s.subscriber_id AND a.snapshot_month = s.snapshot_month"),
        ("step15 ⋈ step12", 12412,
         "SELECT COUNT(*) FROM cleaned_data.step15_final_campaign_list s "
         "JOIN cleaned_data.step12_churn_predictions c ON c.subscriber_id = s.subscriber_id"),
        ("step15 ⋈ step13", 2923,
         "SELECT COUNT(*) FROM cleaned_data.step15_final_campaign_list s "
         "JOIN cleaned_data.step13_recommendations r ON r.subscriber_id = s.subscriber_id"),
        ("step15 ⋈ step14", 2923,
         "SELECT COUNT(*) FROM cleaned_data.step15_final_campaign_list s "
         "JOIN cleaned_data.step14_capacity_simulation d ON d.subscriber_id = s.subscriber_id"),
        ("step15 ⋈ clustered", 2923,
         "SELECT COUNT(*) FROM cleaned_data.step15_final_campaign_list s "
         "JOIN cleaned_data.abt_subscriber_month_clustered k "
         "ON k.subscriber_id = s.subscriber_id"),
        ("abt ⋈ t4 grid", 12412,
         "SELECT COUNT(*) FROM cleaned_data.abt_subscriber_month a "
         "JOIN cleaned_data.t4_coverage_address_grid g ON g.address_id = a.address_id"),
        ("t4 grid cells matched to t3", 731,
         "SELECT COUNT(DISTINCT g.serving_cell_id) "
         "FROM cleaned_data.t4_coverage_address_grid g "
         "JOIN cleaned_data.t3_cell_monthly_kpi c ON c.cell_id = g.serving_cell_id"),
    ]
    for name, expected, sql in checks:
        live = int(database.run_query(sql).iloc[0, 0])
        out.append(_row("Join coverage", name, f"{live:,}", f"{expected:,}",
                        _eq(live, expected), "verify_schema_mapping.sql §6"))
    return {"rows": out}


def eligibility_checks() -> Dict[str, Any]:
    """Operational — eligibility and exclusion completeness."""
    out = []
    eligible = _count("step15_final_campaign_list", "WHERE fwa_suitability_score > 0")
    excluded = _count("step15_final_campaign_list", "WHERE fwa_suitability_score <= 0")
    base = _count("step15_final_campaign_list")
    out.append(_row("Eligibility complete", "eligible (score > 0)",
                    f"{eligible:,}", "2,923", _eq(eligible, 2923),
                    "SCHEMA_MAPPING §5"))
    out.append(_row("Eligibility complete", "excluded (score <= 0)",
                    f"{excluded:,}", "9,489", _eq(excluded, 9489),
                    "SCHEMA_MAPPING §5"))
    out.append(_row("Eligibility complete", "eligible + excluded == total",
                    f"{eligible + excluded:,}", f"{base:,}",
                    _eq(eligible + excluded, base),
                    "arithmetic identity on step15"))
    for reason, expected in [("RF_Failure", 9449), ("Fiber_Cannibalization", 40)]:
        live = _count("abt_subscriber_month",
                      f"WHERE fwa_exclusion_reason = '{reason}'")
        out.append(_row("Eligibility complete", f"exclusion reason {reason}",
                        f"{live:,}", f"{expected:,}", _eq(live, expected),
                        "SCHEMA_MAPPING §4.2"))
    null_eligible = _count("abt_subscriber_month", "WHERE fwa_exclusion_reason IS NULL")
    out.append(_row("Eligibility complete", "exclusion reason NULL (eligible)",
                    f"{null_eligible:,}", "2,923", _eq(null_eligible, 2923),
                    "SCHEMA_MAPPING §4.2"))
    for band, expected in [("Excluded", 9489), ("Marginal", 1579),
                           ("Standard", 1036), ("Premium", 308)]:
        live = _count("step15_final_campaign_list",
                      f"WHERE fwa_suitability_band = '{band}'")
        out.append(_row("Eligibility complete", f"suitability band {band}",
                        f"{live:,}", f"{expected:,}", _eq(live, expected),
                        "SCHEMA_MAPPING §4.1"))
    return {"rows": out}


def recommendation_checks() -> Dict[str, Any]:
    """Operational — recommendation completeness (step13 vs eligible)."""
    out = []
    step13 = _count("step13_recommendations")
    out.append(_row("Recommendations complete", "step13 rows == eligible",
                    f"{step13:,}", "2,923", _eq(step13, 2923),
                    "SCHEMA_MAPPING §1"))
    null_offer = _count("step13_recommendations", "WHERE recommended_offer IS NULL")
    out.append(_row("Recommendations complete", "recommended_offer NULL",
                    f"{null_offer:,}", "0", _eq(null_offer, 0),
                    "SCHEMA_MAPPING §2.4"))
    null_tier1 = _count("step13_recommendations", "WHERE tier1_base_plan IS NULL")
    out.append(_row("Recommendations complete", "tier1_base_plan NULL",
                    f"{null_tier1:,}", "0", _eq(null_tier1, 0),
                    "SCHEMA_MAPPING §2.4"))
    missing = _count_eligible_without_recommendation()
    out.append(_row("Recommendations complete", "eligible without recommendation",
                    f"{missing:,}", "0", _eq(missing, 0),
                    "SCHEMA_MAPPING §3"))
    return {"rows": out}


def _count_eligible_without_recommendation() -> int:
    sql = (
        "SELECT COUNT(*) FROM cleaned_data.step15_final_campaign_list s "
        "LEFT JOIN cleaned_data.step13_recommendations r "
        "ON r.subscriber_id = s.subscriber_id "
        "WHERE s.fwa_suitability_score > 0 AND r.subscriber_id IS NULL"
    )
    return int(database.run_query(sql).iloc[0, 0])


def capacity_result_checks() -> Dict[str, Any]:
    """Operational — capacity-result completeness (step14)."""
    out = []
    step14 = _count("step14_capacity_simulation")
    out.append(_row("Capacity results complete", "step14 rows",
                    f"{step14:,}", "2,923", _eq(step14, 2923),
                    "SCHEMA_MAPPING §1"))
    for column in ["post_migration_capacity_risk", "rollout_status",
                   "post_migration_prb_utilisation_proxy",
                   "expected_additional_prb_proxy"]:
        nulls = _count("step14_capacity_simulation", f"WHERE {column} IS NULL")
        out.append(_row("Capacity results complete", f"{column} NULL",
                        f"{nulls:,}", "0", _eq(nulls, 0),
                        "SCHEMA_MAPPING §2.5"))
    safe = _count("step14_capacity_simulation",
                  "WHERE post_migration_capacity_risk = 'Safe'")
    out.append(_row("Capacity results complete", "all Safe in snapshot",
                    f"{safe:,}", "2,923", _eq(safe, 2923),
                    "SCHEMA_MAPPING §4.4"))
    return {"rows": out}


def churn_result_checks() -> Dict[str, Any]:
    """Operational — churn-result completeness (step12)."""
    out = []
    step12 = _count("step12_churn_predictions")
    out.append(_row("Churn results complete", "step12 rows",
                    f"{step12:,}", "12,412", _eq(step12, 12412),
                    "SCHEMA_MAPPING §1"))
    nulls = _count("step12_churn_predictions", "WHERE churn_probability IS NULL")
    out.append(_row("Churn results complete", "churn_probability NULL",
                    f"{nulls:,}", "0", _eq(nulls, 0),
                    "SCHEMA_MAPPING §2.3"))
    for band, expected in [("Low Risk", 10465), ("Medium Risk", 1771),
                           ("High Risk", 176)]:
        live = _count("step12_churn_predictions",
                      f"WHERE churn_risk_band = '{band}'")
        out.append(_row("Churn results complete", f"band {band}",
                        f"{live:,}", f"{expected:,}", _eq(live, expected),
                        "SCHEMA_MAPPING §4.1"))
    crit = _count("step12_churn_predictions",
                  "WHERE churn_risk_band = 'Critical Risk'")
    out.append(_row("Churn results complete", "Critical Risk present",
                    f"{crit:,}", "0 in snapshot", _eq(crit, 0),
                    NO_CRITICAL_CHURN_NOTE))
    return {"rows": out}


def historical_checks() -> Dict[str, Any]:
    """Historical pipeline-cleaning statistics. NOT verifiable from the
    approved objects (they live in polluted_data / the P1-P7 probe JSON,
    outside the allowed ten). Reported as WARN with an explicit no-claim
    explanation instead of an invented figure."""
    return {
        "rows": [
            _row(
                "Historical cleaning trends",
                "P1-P7 pollution repair counts",
                "unavailable",
                "n/a",
                "WARN",
                "polluted_data layer (outside approved objects — SCHEMA_MAPPING §1)",
                ("Historical pollution statistics are not reported because their "
                 "source layer is outside the approved objects cap. No repair "
                 "claim is made. Historical data-quality trends are unavailable "
                 "for the current snapshot."),
            )
        ]
    }


ALL_BANDS = (
    ("Stage row counts", row_count_checks),
    ("Subscriber uniqueness", uniqueness_checks),
    ("Snapshot count", snapshot_checks),
    ("Duplicate keys", duplicate_key_checks),
    ("Missing values", missing_value_checks),
    ("Sentinel values", sentinel_checks),
    ("Join coverage", join_coverage_checks),
    ("Eligibility complete", eligibility_checks),
    ("Recommendations complete", recommendation_checks),
    ("Capacity results complete", capacity_result_checks),
    ("Churn results complete", churn_result_checks),
    ("Historical cleaning trends", historical_checks),
)


def run_all_checks() -> Dict[str, Any]:
    """Run every check band; returns (checks table, summary)."""
    checks: list[Dict[str, Any]] = []
    for _section, band in ALL_BANDS:
        checks.extend(band()["rows"])

    df = pd.DataFrame(checks)
    fails = int((df["status"] == "FAIL").sum())
    warns = int((df["status"] == "WARN").sum())
    passed = int((df["status"] == "PASS").sum())
    overall = "FAIL" if fails else ("PASS" if passed else "WARN")
    return {
        "checks": df,
        "summary": {
            "total": int(len(df)),
            "passed": passed,
            "warnings": warns,
            "fails": fails,
            "overall": overall,
            "snapshot": "2026-01-01",
        },
    }
