"""Tables component — paginated DataFrames with selection, export button."""

from __future__ import annotations

from typing import Any, Dict, List, Optional

import pandas as pd
import streamlit as st

from app.business_logic import masking


def render_paginated_table(
    df: pd.DataFrame,
    key_prefix: str,
    page: int,
    page_size: int,
    total: int,
    on_page_change,
    on_rows_per_page=None,
    sort_options: Optional[List[str]] = None,
    on_sort_change=None,
) -> None:
    """Render a paginated table with prev/next + optional sort controls.

    Caller owns the pager state (page, page_size) and supplies callbacks
    (typically ``st.session_state`` keys + rerun).
    """
    if df.empty:
        st.info("No rows match the current filters.")
        return

    st.dataframe(
        df,
        use_container_width=True,
        hide_index=True,
        height=440,
    )

    n_pages = max(1, -(-total // max(1, page_size)))
    c1, c2, c3 = st.columns([1, 3, 1])
    with c1:
        if st.button("◀ Prev", key=f"prev_{page_prefix(page)}", disabled=page <= 1, on_click=on_page_change(page - 1)):
            pass
    with c2:
        st.write(f"Page **{page}** of **{n_pages}** — {total:,} rows")
    with c3:
        if st.button("Next ▶", key=f"next_{page}", disabled=page >= n_pages, on_click=on_page_change(page + 1)):
            pass


def page_prefix(page: int) -> str:
    return f"p{page}"


def render_table_with_export(
    df: pd.DataFrame,
    export_label: str = "Export CSV",
    filename: Optional[str] = None,
    extra_help_text: Optional[str] = None,
) -> None:
    """Render a (masked) dataframe with a CSV export button (I6)."""
    col1, col2 = st.columns([6, 1])
    with col2:
        if df.empty:
            st.button(export_label, disabled=True, help="No rows to export.")
        else:
            content = df.to_csv(index=False).encode("utf-8-sig")
            st.download_button(
                label=export_label,
                data=content,
                file_name=filename or "fwa_export.csv",
                mime="text/csv",
                help=extra_help(extra_help_text),
            )
    with col1:
        st.dataframe(
            df,
            use_container_width=True,
            hide_index=True,
            height=min(560, 40 * len(df) + 40),
        )


def extra_help(h: Optional[str]) -> Optional[str]:
    return h or "Exported data is masked (no PII)."
