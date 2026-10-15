"""Tests for business_logic.guards — schema-integrity guards (DECISION 5)."""

from __future__ import annotations

import pandas as pd
import pytest

from app.business_logic import guards


def _ok_query(statement, params=None, **kwargs):
    if "COUNT(DISTINCT snapshot_month)" in statement:
        return pd.DataFrame({"snapshot_month": ["2026-01-01"]})
    if statement.startswith("SELECT DISTINCT snapshot_month"):
        return pd.DataFrame({"snapshot_month": ["2026-01-01"]})
    if "COUNT(DISTINCT " in statement and "snapshot_month" not in statement:
        return pd.DataFrame({"total": [2923], "distinct_keys": [2923]})
    raise AssertionError(f"unexpected statement: {statement}")


def test_ensure_single_snapshot_passes_on_one_snapshot():
    snapshot = guards.ensure_single_snapshot(_ok_query)
    assert snapshot == "2026-01-01"


def test_ensure_single_snapshot_fails_on_multiple_snapshots():
    calls = {"n": 0}

    def query(statement, params=None, **kwargs):
        calls["n"] += 1
        if calls["n"] == 1:
            return pd.DataFrame({"snapshot_month": ["2026-01-01", "2026-02-01"]})
        return pd.DataFrame({"snapshot_month": ["2026-01-01"]})

    with pytest.raises(guards.SchemaCompatibilityError) as exc:
        guards.ensure_single_snapshot(query)
    assert "distinct snapshot_month" in str(exc.value)


def test_ensure_single_snapshot_fails_on_cross_table_mismatch():
    calls = {"n": 0}

    def query(statement, params=None, **kwargs):
        calls["n"] += 1
        if calls["n"] == 1:
            return pd.DataFrame({"snapshot_month": ["2026-01-01"]})
        return pd.DataFrame({"snapshot_month": ["2026-02-01"]})

    with pytest.raises(guards.SchemaCompatibilityError) as exc:
        guards.ensure_single_snapshot(query)
    assert "Snapshot mismatch" in str(exc.value)


def test_ensure_join_keys_unique_passes():
    guards.ensure_join_keys_unique(_ok_query)


def test_ensure_join_keys_unique_fails_on_duplicates():
    def query(statement, params=None, **kwargs):
        return pd.DataFrame({"total": [2923], "distinct_keys": [2922]})

    with pytest.raises(guards.SchemaCompatibilityError) as exc:
        guards.ensure_join_keys_unique(query)
    message = str(exc.value)
    assert "duplicate" in message
    assert "step13_recommendations" in message
    # guard messages must never contain subscriber identifiers
    assert "SUB_" not in message


def test_error_messages_do_not_contain_identifiers():
    def query(statement, params=None, **kwargs):
        return pd.DataFrame({"total": [5], "distinct_keys": [4]})

    with pytest.raises(guards.SchemaCompatibilityError) as exc:
        guards.ensure_join_keys_unique(query, sources=(("step14_capacity_simulation", "subscriber_id"),))
    assert "SUB_" not in str(exc.value)


def test_ensure_join_integrity_runs_both_guards():
    guards.ensure_join_integrity(_ok_query)
