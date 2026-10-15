"""Runtime schema-integrity guards (DECISION 5 of the dashboard programme).

Before any subscriber_id-only join to the eligible-level sources
(step13_recommendations, step14_capacity_simulation,
abt_subscriber_month_clustered) the application MUST verify:

1. exactly one snapshot month exists in snapshot-carrying tables;
2. subscriber_id is unique in each joined eligible-level source.

If either check fails, a :class:`SchemaCompatibilityError` is raised with a
clear human-readable message and the ambiguous join is never performed.
Messages never contain subscriber identifiers (DECISION 10).

These guards are application-level replacements for the missing database
constraints (SCHEMA_MAPPING.md §7.6, DECISION 9). All queries are SELECT-only
and count-only (no raw identifiers are selected).
"""

from __future__ import annotations

from collections.abc import Callable, Sequence
from typing import Any

# Snapshot-carrying tables that must hold exactly one snapshot month.
SNAPSHOT_TABLES: Sequence[str] = (
    "step15_final_campaign_list",
    "abt_subscriber_month",
    "step12_churn_predictions",
    "t3_cell_monthly_kpi",
)

# Eligible-level sources joined on subscriber_id only (no snapshot_month).
# (table_name, key_column)
ELIGIBLE_JOIN_SOURCES: Sequence[tuple[str, str]] = (
    ("step13_recommendations", "subscriber_id"),
    ("step14_capacity_simulation", "subscriber_id"),
    ("abt_subscriber_month_clustered", "subscriber_id"),
)


class SchemaCompatibilityError(RuntimeError):
    """Raised when DB state violates the Phase 1 schema contract.

    Message contains NO subscription identifiers, only table names and counts.
    """


def ensure_single_snapshot(
    run_query: Callable[..., Any], tables: Sequence[str] = SNAPSHOT_TABLES
) -> int:
    """Verify every snapshot-carrying table holds exactly one snapshot month.

    ``run_query`` must accept (statement, params) with first positional
    statement argument and return a DataFrame (services.database.run_query).

    Returns the single snapshot month as a string when valid, otherwise raises
    :class:`SchemaCompatibilityError`.
    """
    import pandas as pd  # noqa: PLC0415

    snapshot: Any = None
    for table in tables:
        statement = (
            "SELECT DISTINCT snapshot_month "
            f"FROM {table} ORDER BY snapshot_month"
        )
        df: pd.DataFrame = run_query(statement)
        months = df["snapshot_month"].tolist()
        if len(months) != 1:
            raise SchemaCompatibilityError(
                f"Schema compatibility check failed: table "
                f"{table} contains {len(months)} distinct snapshot_month "
                f"value(s); exactly 1 is required for the Phase 1 join "
                f"contract (SCHEMA_MAPPING.md §3.1). "
                f"Avoid ambiguous joins and validate the dataset before "
                f"running the dashboard."
            )
        if snapshot is None:
            snapshot = months[0]
        elif months[0] != snapshot:
            raise SchemaCompatibilityError(
                f"Snapshot mismatch: {table} holds {months[0]} while other "
                f"tables hold {snapshot}. Exactly one global snapshot is "
                f"required (SCHEMA_MAPPING.md §3.1)."
            )
    return snapshot


def ensure_join_keys_unique(
    run_query: Callable[..., Any],
    *,
    sources: Sequence[tuple[str, str]] = ELIGIBLE_JOIN_SOURCES,
) -> None:
    """Verify each eligible-level source has a unique key column.

    Raises :class:`SchemaCompatibilityError` when any duplicate key value is
    found (count(*) != count(distinct key)). The message reports the table and
    the duplicate count, never the identifiers themselves.
    """
    import pandas as pd  # noqa: F0415

    for table, column in sources:
        statement = (
            "SELECT COUNT(*) AS total, COUNT(DISTINCT {col}) AS distinct_keys "
            f"FROM {table}"
        ).format(col=column)
        df: pd.DataFrame = run_query(statement)
        total = int(df.iloc[0]["total"])
        distinct = int(df.iloc[0]["distinct_keys"])
        if total != distinct:
            raise SchemaCompatibilityError(
                f"Schema compatibility check failed: {table} contains "
                f"{total} rows but only {distinct} distinct {column} "
                f"value(s) — {total - distinct} duplicate(s). The "
                f"subscriber_id-only join contract requires 1:1 matches "
                f"(SCHEMA_MAPPING.md §3.1). Ambiguous joins are not "
                f"performed."
            )


def ensure_join_integrity(
    run_query: Callable[..., Any],
    *,
    check_snapshot: bool = True,
    check_unique_keys: bool = True,
) -> None:
    """Run both guards; raise on the first failing condition."""
    if check_snapshot:
        ensure_single_snapshot(run_query)
    if check_unique_keys:
        ensure_join_keys_unique(run_query)
