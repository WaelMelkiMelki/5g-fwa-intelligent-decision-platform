"""Shared UI components — reusable Streamlit widgets.

Each module exposes small functions that render styled, accessible primitives.
They accept data (DataFrames/dicts) and never talk to the DB directly;
services remain the only DB boundary.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

COLOR_SEQUENCE = px.colors.qualitative.Safe


def kpi_row(
    kpis: List[Dict[str, Any]],
    columns: int = 4,
) -> None:
    """Render a responsive KPI strip. kpis: [{label,value,delta,help}]."""
    cols = st.columns(columns)
    for i, kpi in enumerate(kpis):
        with cols[i % columns]:
            st.metric(
                label=kpi["label"],
                value=kpi.get("value", "—"),
                delta=kpi.get("delta"),
                help=kpi.get("help"),
            )


def empty_state(message: str = "No data for this selection.") -> None:
    st.info(f"📭 {message}")


def error_state(message: str) -> None:
    st.error(message)


def warning_banner(message: str) -> None:
    st.warning(message)


def success_banner(message: str) -> None:
    st.success(message)


def donut_chart(labels, values, title=None, height=320):
    fig = go.Figure(
        data=[
            go.Pie(
                labels=labels,
                values=values,
                hole=0.45,
                textinfo="label+value",
                marker=dict(colors=COLOR_SEQUENCE[: len(labels)]),
            )
        ]
    )
    fig.update_layout(title=title, height=height, margin=dict(l=10, r=10, t=40, b=10))
    return fig


def bar_chart(df: Any, x, y, title=None, orient="v", color=None, height=320):
    """Generic bar chart (single series by default)."""
    if df is None or df.empty:
        return None
    fig = px.bar(df, x=x, y=y, orientation=orient, color=color, title=title, height=height)
    fig.update_layout(margin=dict(l=10, r=10, t=40, b=10))
    return fig


def histogram_chart(series, nbins=30, title=None, vlines: Optional[list] = None, height=320):
    """Histogram with optional vertical reference lines (e.g. 80% PRB)."""
    if series is None or series.empty:
        return None
    fig = px.histogram(series, nbins=nbins, title=title, height=height)
    if vlines:
        for v in vlines:
            fig.add_vline(x=v, line_dash="dash", line_color="red", annotation_text=str(v))
    fig.update_layout(margin=dict(l=10, r=10, t=40, b=10))
    return fig


def funnel_chart(stages: List[Dict[str, Any]], title=None, height=380):
    """Funnel using plotly go.Funnel (values per stage)."""
    labels = [s["label"] for s in stages]
    values = [s["value"] for s in stages]
    fig = go.Figure(go.Funnel(y=labels, x=values, textinfo="value+percent initial"))
    fig.update_layout(title=title, height=height, margin=dict(l=10, r=10, t=40, b=10))
    return fig


def heatmap_chart(df_pivot, title=None, height=380):
    """Numeric heatmap from a pivot DataFrame."""
    if df_pivot is None or df_pivot.empty:
        return None
    fig = go.Figure(
        data=go.Heatmap(
            z=df_pivot.values,
            x=[str(c) for c in df_pivot.columns],
            y=[str(i) for i in df_pivot.index],
            colorscale="YlGnBu",
            text=df_pivot.values,
            texttemplate="%{text}",
            colorbar=dict(title="count"),
        )
    )
    fig.update_layout(title="Cross-tab", height=height, margin=dict(l=10, r=10, t=40, b=10))
    return fig
