"""Database access layer — pooled SQLAlchemy engine, read-only by design.

Security posture:
- Credentials come ONLY from environment variables (FWA_DB_*) or Streamlit
  secrets ([database] section). Never hard-coded.
- Connection is forced into a read-only session
  (``default_transaction_read_only=on``) so INSERT/UPDATE/DELETE/DDL fail at
  the server level even if a bug introduces them.
- Every query must pass through :func:`run_query`, which additionally rejects
  any statement whose first keyword is not ``SELECT`` (defense in depth).
- All queries are parameterized (SQLAlchemy ``text()`` with bound params).
- No ``SELECT *`` — callers must pass explicit column lists.
- Errors are logged without parameters, values or personal data.
"""

from __future__ import annotations

import logging
import os
import time
from functools import lru_cache
from typing import Any, Mapping, Optional, Sequence

import pandas as pd
import sqlalchemy as sa
from sqlalchemy.engine import Connection, Engine

logger = logging.getLogger("fwa_dashboard.db")

DEFAULT_SCHEMA = "cleaned_data"
READ_ONLY_SESSION_OPTION = "-c default_transaction_read_only=on"


class DatabaseConfigError(RuntimeError):
    """Raised when database configuration is missing or invalid."""


class ReadOnlyQueryViolation(ValueError):
    """Raised when a non-SELECT statement is rejected by the guard."""


def _secrets_value(key: str) -> Optional[str]:
    """Best-effort read of a Streamlit secret (outside a running app returns None)."""
    try:
        import streamlit as st  # type: ignore

        section = st.secrets.get("database", {}) if hasattr(st, "secrets") else {}
        return section.get(key)  # type: ignore[no-any-return]
    except Exception:  # noqa: BLE001 - secrets not available outside runtime
        return None


def database_config() -> dict:
    """Resolve DB config. Precedence: env vars, then Streamlit secrets, then defaults."""
    cfg = {
        "host": os.environ.get("FWA_DB_HOST") or _secrets_value("host"),
        "port": os.environ.get("FWA_DB_PORT") or _secrets_value("port") or "5432",
        "dbname": os.environ.get("FWA_DB_NAME") or _secrets_value("name") or "postgres",
        "user": os.environ.get("FWA_DB_USER") or _secrets_value("user"),
        "password": os.environ.get("FWA_DB_PASSWORD") or _secrets_value("password"),
        "schema": (
            os.environ.get("FWA_DB_SCHEMA")
            or _secrets_value("schema")
            or DEFAULT_SCHEMA
        ),
    }
    missing = [k for k in ("host", "user", "password") if not cfg[k]]
    if missing:
        raise DatabaseConfigError(
            "Missing database configuration for: "
            + ", ".join(missing)
            + ". Set FWA_DB_* environment variables or the [database] section in "
            "app/.streamlit/secrets.toml."
        )
    try:
        port = int(str(cfg["port"]))
        if not 1 <= port <= 65535:
            raise ValueError(port)
    except (TypeError, ValueError) as exc:
        raise DatabaseConfigError(f"Invalid port value: {cfg['port']!r}") from exc
    return cfg


@lru_cache(maxsize=1)
def engine() -> Engine:
    """Create (and cache) the pooled read-only engine."""
    cfg = database_config()
    url = sa.engine.URL.create(
        drivername="postgresql+psycopg2",
        username=cfg["user"],
        password=cfg["password"],
        host=cfg["host"],
        port=cfg["port"],
        database=cfg["dbname"],
    )
    connect_args: dict[str, Any] = {
        "options": READ_ONLY_SESSION_OPTION,
        "connect_timeout": 10,
    }
    return sa.create_engine(
        url,
        pool_size=5,
        max_overflow=5,
        pool_pre_ping=True,
        pool_recycle=1800,
        connect_args=connect_args,
        future=True,
    )


def read_only_guard(statement: str) -> str:
    """Reject any statement whose first keyword is not SELECT."""
    stripped = (statement or "").strip()
    if not stripped:
        raise ReadOnlyQueryViolation("Empty SQL statement")
    first_word = stripped.split(None, 1)[0].lower().rstrip(";")
    if first_word != "select":
        raise ReadOnlyQueryViolation(
            f"Read-only guard: statement must start with SELECT, got {first_word!r}"
        )
    return stripped


def _set_search_path(connection: Connection, schema: Optional[str]) -> None:
    """Scope the connection search_path to the allowed schema."""
    target = schema or DEFAULT_SCHEMA
    connection.execute(sa.text(f"SET search_path TO {target}"))


def run_query(
    statement: str,
    params: Optional[Sequence[Any] | Mapping[str, Any]] = None,
    *,
    schema: Optional[str] = None,
    max_rows: int = 200_000,
) -> pd.DataFrame:
    """Execute a parameterized read-only SELECT and return a DataFrame.

    Raises:
        DatabaseConfigError: bad/missing configuration.
        ReadOnlyQueryViolation: non-SELECT statement rejected.
        RuntimeError: row-count safety cap exceeded.
    """
    statement = read_only_guard(statement)
    try:
        started = time.monotonic()
        with engine().connect() as conn:
            _set_search_path(conn, schema)
            df = pd.read_sql_query(
                sa.text(statement),
                conn,
                params=params if params is not None else {},
            )
        elapsed_ms = int((time.monotonic() - started) * 1000)
        logger.info("query_ok rows=%d elapsed_ms=%d", len(df), elapsed_ms)
        if len(df) > max_rows:
            raise RuntimeError(
                f"Query returned {len(df)} rows exceeding cap {max_rows}"
            )
        return df
    except DatabaseConfigError:
        raise
    except ReadOnlyQueryViolation:
        raise
    except Exception:
        logger.exception("database_error (no sensitive data logged)")
        raise
