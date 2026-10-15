"""Privacy masking — subscriber identifiers and export column governance.

Rules (design spec §12, audit §14):
- ``msisdn`` is PII present only in daily T1; it is NEVER selected by this app.
- ``subscriber_id`` is pseudonymous (``SUB_XXXXXXXX``); visible screens show a
  masked form ``SUB_XXXX***`` derived deterministically.
- Exports go through a column whitelist (per page); forbidden fields are never
  included at all (defense in depth), and a test scans exports for forbidden
  patterns.
"""

from __future__ import annotations

import re
from typing import Iterable, List

PSEUDO_ID_PATTERN = re.compile(r"^(SUB_|ADD_|CELL_|SITE_)([A-Z0-9_]+)$")

# Fields that must never appear in any export or display table.
FORBIDDEN_COLUMNS = {"msisdn", "msisdn_masked", "address_street", "address", "latitude", "longitude"}
ALLOWED_EXPORT_COLUMNS = frozenset(
    {
        "subscriber_id",  # displayed masked
        "snapshot_month",
        "cluster_id",
        "business_label",
        "governorate",
        "fwa_suitability_band",
        "fwa_exclusion_reason",
        "churn_risk_band",
        "churn_probability",
        "offer_category",
        "recommended_offer",
        "final_priority_score",
        "final_priority_band",
        "campaign_action",
        "rollout_status",
        "post_migration_capacity_risk",
        "arpu_monthly_tnd",
        "tenure_months",
        "num_active_lines",
        "contract_type",
        "segment_tier",
        "fwa_suitability_score",
        "candidate_prioritization_score",
        "suitability_based_ranking",
        "cell_id",
        "site_id",
        "p95_prb_utilisation_pct",
        "max_prb_utilisation_pct",
        "avg_prb_utilisation_pct",
        "current_capacity_proxy_status",
        "avg_dl_throughput_mbps",
        "signal_quality_class",
        "radio_feasibility_class",
        "address_id",  # pseudonymous ADD_*, exported as masked form (allowed)
    }
)


def mask_subscriber_id(value: Optional[str]) -> Optional[str]:
    """Mask a pseudonymous ID (SUB_/ADD_/CELL_/SITE_) to ``PREFIX_XXXX...``.

    Deterministic, not reversible within the app. Non-matching strings pass
    through unchanged (they are not identifiers).
    """
    if value is None or str(value) == "":
        return value
    text = str(value)
    match = PSEUDO_ID_PATTERN.match(text)
    if not match:
        return text
    prefix, body = match.group(1), match.group(2)
    return f"{prefix}{body[:4]}..."


def mask_dataframe_identifiers(df, columns: Optional[List[str]] = None) -> None:
    """In-place mask of identifier columns in a DataFrame (masked, no return)."""
    targets = columns or ["subscriber_id", "address_id"]
    for col in targets:
        if col in df.columns:
            df[col] = df[col].map(mask_subscriber_id)
    return df


def drop_forbidden_columns(df, extra_forbidden: Optional[List[str]] = None) -> List[str]:
    """Return names of forbidden columns found/present (columns removed in place).
    """
    forbidden = set(FORBIDDEN_COLUMNS) | set(extra_forbidden or [])
    present = [c for c in df.columns if c in forbidden]
    df.drop(columns=present, errors="ignore", inplace=True)
    return present


def whitelist_columns(columns: List[str], allowed: Optional[set] = None) -> List[str]:
    """Keep only export-allowlisted columns, in their given order."""
    allowed_set = allowed or ALLOWED_EXPORT_COLUMNS
    return [c for c in columns if c in allowed_set]


def strip_and_mask_for_export(df, *, extra_forbidden: Optional[List[str]] = None):
    """Return a copy with only allowlisted columns and masked identifiers."""
    allowed = whitelist_columns(list(df.columns))
    out = df[allowed].copy()
    present = drop_forbidden_columns(out)  # no-op: whitelist already excludes
    mask_dataframe_identifiers(out)
    return out, present
