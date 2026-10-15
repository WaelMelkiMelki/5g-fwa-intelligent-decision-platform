"""Filter construction — pure functions that turn the session filter dict into
parameterized SQL predicates (SQL-side pushdown per interaction spec §7 I1).

No dynamic string interpolation of user values into SQL: every value is bound
via SQLAlchemy named parameters. Column identities come from a hard-coded
allowlist (no unvalidated column names ever reach the SQL).

The base subscriber query pattern:

    SELECT <explicit cols>
    FROM cleaned_data.step15_final_campaign_list s
    JOIN cleaned_data.abt_subscriber_month a
      ON s.subscriber_id = a.subscriber_id AND s.snapshot_month = a.snapshot_month
    WHERE s.snapshot_month = :snapshot_month
      AND <extra predicates>            -- built by build_predicates()

All filter values are validated against verified distinct values (SCHEMA_MAPPING.md §4).
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional, Tuple

# Allowlist: filter key -> (table_alias, column)
FILTER_COLUMNS: Dict[str, Tuple[str, str]] = {
    "clusters": ("s", "cluster_id"),
    "churn_bands": ("s", "churn_risk_band"),
    "coverage_classes": ("a", "radio_feasibility_class"),
    "capacity_statuses": ("a", "current_capacity_proxy_status"),
    "offers": ("s", "offer_category"),
    "campaign_actions": ("s", "campaign_action"),
}

# Population scope is a single-value select (not a multi-value column filter);
# it expands to a verified rank predicate on step15.fwa_suitability_score.
POPULATION_KEY = "population"
POPULATION_ALL = "All subscribers"
POPULATION_ELIGIBLE = "Eligible subscribers"
POPULATION_EXCLUDED = "Excluded subscribers"
POPULATION_VALUES: List[str] = [
    POPULATION_ALL,
    POPULATION_ELIGIBLE,
    POPULATION_EXCLUDED,
]

SNAPSHOT_COLUMN = ("s", "snapshot_month")

# Verified value vocabularies (SCHEMA_MAPPING.md §4) used for input validation.
ALLOWED_VALUES: Dict[str, List[Any]] = {
    "churn_bands": ["Low Risk", "Medium Risk", "High Risk"],
    "coverage_classes": ["5G_Feasible", "4G_Fallback", "Infeasible", "Fiber_Competitor"],
    "capacity_statuses": ["Available", "Constrained"],
    "offers": [
        "Base Only",
        "Base + IPTV",
        "Base + Convergent Fixed-Mobile Add-on",
        "Multi-Addon Bundle",
        "Base + Gaming Add-on",
        "N/A",
    ],
    "campaign_actions": ["Contact Now", "Contact Later", "Manual Review", "Exclude"],
}

# cluster_id is numeric; range validated separately (-1..3 in current snapshot).
ALLOWED_CLUSTERS = [-1, 0, 1, 2, 3]


def validate_filter_value(key: str, value: Any) -> None:
    """Raise ValueError on an out-of-domain filter value (defensive validation)."""
    if key not in FILTER_COLUMNS:
        raise ValueError(f"Unsupported filter key: {key}")
    if key == "clusters":
        if not isinstance(value, (int, float)) or int(value) not in ALLOWED_CLUSTERS:
            raise ValueError(f"Invalid cluster_id: {value!r}")
        return
    allowed = ALLOWED_VALUES.get(key)
    if allowed is None:
        return
    if value not in allowed:
        raise ValueError(f"Invalid value {value!r} for filter '{key}'")


def validate_filters(filters: Dict[str, Any]) -> None:
    """Validate a whole filter dict (keys and each selected value)."""
    unknown = set(filters) - (set(FILTER_COLUMNS) | {POPULATION_KEY})
    if unknown:
        raise ValueError(f"Unknown filter keys: {sorted(unknown)}")
    population = filters.get(POPULATION_KEY, POPULATION_ALL)
    if population not in POPULATION_VALUES:
        raise ValueError(f"Invalid population scope: {population!r}")
    for key, values in filters.items():
        if key == POPULATION_KEY:
            continue
        for value in values or []:
            validate_filter_value(key, value)


def build_predicates(
    filters: Dict[str, Any],
    snapshot_month: Optional[str] = None,
) -> Tuple[List[str], Dict[str, Any]]:
    """Build (predicate_sql, params) for the subscriber base query.

    Returns a list of SQL predicate fragments using named params like
    ``:f_churn_bands_0`` and the matching parameter mapping. Caller joins with
    `` AND `` and passes params to :func:`services.database.run_query`.
    """
    validate_filters(filters)
    predicates: List[str] = []
    params: Dict[str, Any] = {}

    if snapshot_month is not None:
        predicates.append(f"{SNAPSHOT_COLUMN[0]}.{SNAPSHOT_COLUMN[1]} = :snapshot_month")
        params["snapshot_month"] = snapshot_month

    population = filters.get(POPULATION_KEY, POPULATION_ALL)
    if population == POPULATION_ELIGIBLE:
        predicates.append("s.fwa_suitability_score > 0")
    elif population == POPULATION_EXCLUDED:
        predicates.append("s.fwa_suitability_score <= 0")

    for key, values in filters.items():
        if key == POPULATION_KEY:
            continue
        alias, column = FILTER_COLUMNS[key]
        selected = [v for v in (values or []) if v is not None]
        if not selected:
            continue
        placeholders = []
        for i, val in enumerate(selected):
            param_name = f"filters_{key}_{i}"
            placeholders.append(f":{param_name}")
            params[param_name] = val
        predicates.append(f"{alias}.{column} IN ({', '.join(placeholders)})")
    return predicates, params


def build_where_clause(predicates: List[str]) -> str:
    """Join predicate list into a WHERE clause fragment."""
    if not predicates:
        return ""
    return " WHERE " + " AND ".join(predicates)
