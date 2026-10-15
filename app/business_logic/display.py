"""Display aliases for stored sentinel values (DECISION 2).

Sentinel values are preserved in the data pipeline and in SQL predicates;
this module maps them to customer-facing labels ONLY at the display layer
(after SQL retrieval). SQL never receives these aliases.

Verified sentinel mapping (SCHEMA_MAPPING.md §4.6):

    cluster_id == -1                       -> "Not Segmented"
    offer_category == 'N/A'               -> "No Offer"
    rollout_status IS NULL                -> "Not Applicable"
    post_migration_capacity_risk IS NULL  -> "Not Applicable"
"""

from __future__ import annotations

from typing import Any, Dict, Optional

import pandas as pd

SENTINEL_LABELS: Dict[str, Dict[Any, str]] = {
    "cluster_id": {-1: "Not Segmented"},
    "offer_category": {"N/A": "No Offer"},
    "rollout_status": {None: "Not Applicable"},
    "post_migration_capacity_risk": {None: "Not Applicable"},
}

# Columns eligible for sentinel label substitution at display time.
SENTINEL_COLUMNS = tuple(SENTINEL_LABELS)


def apply_sentinel_labels(df: pd.DataFrame) -> pd.DataFrame:
    """Return a copy with sentinel values replaced by UI labels (display only)."""
    out = df.copy()
    for column, mapping in SENTINEL_LABELS.items():
        if column not in out.columns:
            continue
        out[column] = out[column].map(
            lambda v: mapping.get(v, mapping.get(None, v) if pd.isna(v) else v)
        )
    return out


def display_value(column: str, value: Any) -> Any:
    """Map a single stored value to its display label (None-safe)."""
    mapping = SENTINEL_LABELS.get(column, {})
    if value is None:
        return mapping.get(None, None)
    return mapping.get(value, value)
