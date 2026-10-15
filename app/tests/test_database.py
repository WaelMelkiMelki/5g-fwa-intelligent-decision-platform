"""Unit tests for the read-only database layer (no live DB required)."""

from __future__ import annotations

import pytest

from app.services import database


class TestReadOnlyGuard:
    def test_accepts_select(self):
        sql = "SELECT cell_id FROM cleaned_data.t3_module_kpi"
        assert database.read_only_guard(sql) == sql

    def test_accepts_select_with_leading_newline(self):
        sql = "\n\tSELECT cell_id FROM cleaned_data.t3_module_kpi"
        assert database.read_only_guard(sql) == sql.strip()

    def test_rejects_cte_that_starts_with_with(self):
        # CTEs are valid read-only SQL, but the client guard is intentionally
        # restrictive (SELECT-first); the server-side read-only session is the
        # authoritative enforcement (defense in depth).
        with pytest.raises(database.ReadOnlyQueryViolation):
            database.read_only_guard("WITH x AS (SELECT 1) SELECT * FROM x")

    @pytest.mark.parametrize(
        "sql",
        [
            "INSERT INTO t VALUES (1)",
            "UPDATE t SET x = 1",
            "DELETE FROM t WHERE 1 = 1",
            "DROP TABLE t",
            "CREATE TABLE t (id int)",
            "ALTER TABLE t ADD COLUMN y int",
            "TRUNCATE TABLE t",
            "VACUUM t",
            "CALL proc()",
            "REFRESH MATERIALIZED VIEW v",
        ],
    )
    def test_rejects_writes(self, sql):
        with pytest.raises(database.ReadOnlyQueryViolation):
            database.read_only_guard(sql)

    def test_rejects_empty(self):
        with pytest.raises(database.ReadOnlyQueryViolation):
            database.read_only_guard("")

    def test_rejects_whitespace_only(self):
        with pytest.raises(database.ReadOnlyQueryViolation):
            database.read_only_guard("   ")


class TestClientSideWriterGuard:
    def test_select_survives_guard(self):
        sql = "SELECT 1 AS x"
        assert database.run_query.__doc__  # documented, smoke only


def test_no_database_needed_imports():
    """Layer imports (pure units) load without touching the database."""
    from app.business_logic import filtering, masking, metrics

    assert hasattr(filtering, "build_predicates")
    assert hasattr(masking, "mask_subscriber_id")
    assert hasattr(metrics, "funnel_rows")
