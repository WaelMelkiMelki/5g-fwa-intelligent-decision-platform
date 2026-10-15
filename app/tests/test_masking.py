"""Tests for subscriber/export masking and identifier contracts."""

from __future__ import annotations

import pandas as pd
import pytest

from app.business_logic import masking


@pytest.mark.parametrize(
    "raw,expected",
    [
        ("SUB_7EDE1041", "SUB_7EDE..."),
        ("ADD_3EA1B2C9", "ADD_3EA1..."),
        ("CELL_TN_0001", "CELL_TN_0..."),
        ("SITE_TN_103", "SITE_TN_1..."),
    ],
)
def test_mask_identifier_prefix(raw, expected):
    """Masked id: prefix + first 4 body chars + ellipsis."""
    assert masking.mask_subscriber_id(raw) == expected


def test_mask_when_none_and_empty():
    assert masking.mask_subscriber_id(None) is None
    assert masking.mask_subscriber_id("") == ""


def test_mask_non_identifier_passthrough():
    assert masking.mask_subscriber_id("Tunis") == "Tunis"


def test_forbidden_columns_always_removed():
    df = pd.DataFrame(
        {
            "msisdn": ["+21611111111"],
            "address_street": ["1 Rue X"],
            "subscriber_id": ["SUB_7EDE1041"],
        }
    )
    removed = masking.drop_forbidden_columns(df)
    assert set(removed) == {"msisdn", "address_street"}
    assert "msisdn" not in df.columns
    assert "address_street" not in df.columns


def test_whitelist_keeps_known_export_columns():
    cols = ["subscriber_id", "campaign_action", "msisdn", "latitude"]
    kept = masking.whitelist_columns(cols)
    assert "msisdn" not in kept
    assert "latitude" not in kept
    assert kept == ["subscriber_id", "campaign_action"]


def test_export_prep_masks_and_whitelists():
    df = pd.DataFrame(
        {
            "subscriber_id": ["SUB_7EDE1041"],
            "campaign_action": ["Contact Now"],
            "msisdn": ["+216..."],
            "latitude": [36.8],
        }
    )
    out, removed = masking.strip_and_mask_for_export(df)
    assert "msisdn" not in out.columns
    assert "latitude" not in out.columns
    assert out.iloc[0]["subscriber_id"] == "SUB_7EDE..."
    # no PII pattern in exported CSV
    csv = out.to_csv()
    assert "msisdn" not in csv
    assert "+216" not in csv


def test_export_never_contains_forbidden_patterns():
    """Spec I6: exported CSV must not contain msisdn-like rows (regression)."""
    import re

    df = pd.DataFrame({"subscriber_id": ["SUB_00000001"], "campaign_action": ["X"]})
    out, _ = masking.strip_and_mask_for_export(df)
    csv = out.to_csv(index=False)
    assert not re.search(r"(?:\+?216)?\d{8,15}", csv)


def test_identifiers_never_full_in_visible_frame():
    df = pd.DataFrame({"subscriber_id": ["SUB_A1B2C3D4"], "governorate": ["Tunis"]})
    masking.mask_dataframe_identifiers(df)
    assert "SUB_A1B2..." == df.iloc[0]["subscriber_id"]
