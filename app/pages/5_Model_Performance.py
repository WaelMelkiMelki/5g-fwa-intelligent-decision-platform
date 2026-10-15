"""Page 5 — Model Performance.

Displays ONLY verified precomputed model metrics (report_v4 chapters + live
precomputed churn columns). Conflicting values are shown with sources and a
"metric validation required" warning — never a single authoritative pick.
No live inference, no retraining, no artifacts (audit R2), no prediction.
"""

from __future__ import annotations

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from app.components import charts as C
from app.components import filters as F
from app.components import messages as M
from app.services import model_service

st.set_page_config(page_title="Model Performance", page_icon="5️⃣", layout="wide")


def main() -> None:
    F.render_global_filters()
    st.title("5 · Model Performance (verified precomputed metrics)")
    st.caption(
        "Displayed metrics are sourced from the verified pipeline report "
        "(`report_v4`) and the live precomputed `step12_churn_predictions` table. "
        "No live inference, no retraining, no serialized artifacts."
    )

    try:
        meta = model_service.get_model_performance_metadata()
        stats = model_service.get_snapshot_churn_stats()
    except Exception as exc:  # noqa: BLE001
        M.render_error_state(f"Could not load model metadata: {exc}")
        return

    # --- conflict warning (DECISION 3) ---
    if meta["has_conflicts"]:
        M.render_warning(
            "Metric validation required: project sources contain conflicting "
            "churn thresholds, base rates and AUC values. Conflicting metrics "
            "are displayed below with their source names; no supposedly "
            "correct value is selected or calculated."
        )

    # --- live precomputed stats (read-only DB) ---
    st.subheader("Precomputed scores in the database")
    col1, col2, col3, col4, col5 = st.columns(5)
    col1.metric("Scored subscribers", f"{int(stats['n_subscribers']):,}")
    col2.metric("High Risk", int(stats["n_high_risk"] or 0))
    col3.metric("Medium Risk", int(stats["n_medium_risk"] or 0))
    col4.metric("Mean churn probability", f"{stats['avg_churn_prob']:.3f}"
                if stats["avg_churn_prob"] is not None else "—")
    col5.metric("Max churn probability", f"{stats['max_churn_prob']:.3f}"
                if stats["max_churn_prob"] is not None else "—")
    st.caption("Source: `cleaned_data.step12_churn_predictions` (live count, read-only).")

    # --- churn metric rows with sources ---
    st.subheader("Churn model evaluation (verified sources)")
    rows = []
    for m in meta["churn_metrics"]:
        for variant in m["values"]:
            rows.append(
                {
                    "Metric": m["metric"],
                    "Value": str(variant["value"]),
                    "Source label": variant["label"],
                    "Source file": variant["source"],
                    "Conflict": "⚠️ conflicting" if m["conflict"] else "agreed",
                }
            )
    st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True, height=260)

    # --- confusion matrix ---
    st.subheader("Confusion matrix (τ = 0.15, held-out test set, 585 rows)")
    st.caption(meta["confusion_matrix"]["label"] + " — " + meta["confusion_matrix"]["source"])
    cm = meta["confusion_matrix"]["matrix"]
    z = [
        [cm["actual_churn_pred_churn"], cm["actual_churn_pred_active"]],
        [cm["actual_active_pred_churn"], cm["actual_active_pred_active"]],
    ]
    fig = go.Figure(
        data=go.Heatmap(
            z=z,
            x=["Predicted Churn", "Predicted Active"],
            y=["Actual Churn", "Actual Active"],
            colorscale="Blues",
            text=z,
            texttemplate="%{text} (TP/FP/FN/TN)",
            zmin=0,
            zmax=520,
        )
    )
    fig.update_layout(height=360, margin=dict(l=10, r=10, t=30, b=10))
    st.plotly_chart(fig, use_container_width=True)

    # --- training metadata (pipeline config) ---
    st.subheader("Training metadata (pipeline script config)")
    tm = meta["training_metadata"]
    st.dataframe(
        pd.DataFrame(
            [
                {"Attribute": "Model", "Value": tm["model"]},
                {"Attribute": "Script", "Value": tm["script"]},
                {"Attribute": "Configuration (script)", "Value": tm["config_script"]},
                {"Attribute": "Validation", "Value": tm["validation"]},
                {"Attribute": "Risk-band bins", "Value": tm["band_bins"]},
                {"Attribute": "Snapshot scored", "Value": tm["snapshot"]},
                {"Attribute": "Phase-1 inference", "Value": tm["note"]},
            ]
        ),
        use_container_width=True,
        hide_index=True,
    )

    # --- feature importance ---
    st.subheader("Feature importance (Gain, XGBoost churn classifier)")
    st.caption("Source: " + meta["feature_importance_source"])
    fi = pd.DataFrame(meta["feature_importance"], columns=["feature", "gain"])
    fig = C.bar_chart(
        fi.sort_values("gain"),
        x="gain", y="feature", orient="h",
        title="Top-10 features by Gain",
    )
    st.plotly_chart(fig, use_container_width=True)

    # --- step15 surrogate ---
    st.subheader("Priority-scoring surrogate (step15)")
    st.dataframe(
        pd.DataFrame(
            [
                {"Attribute": "Model", "Value": meta["step15_surrogate"]["model"]},
                {"Attribute": "Test R²", "Value": str(meta["step15_surrogate"]["test_r2"])},
                {"Attribute": "Source", "Value": meta["step15_surrogate"]["source"]},
            ]
        ),
        use_container_width=True,
        hide_index=True,
    )

    st.divider()
    st.caption(
        "Phase-1 scope: dashboard reads precomputed columns only. Live churn "
        "re-inference requires serialized artifacts (audit R2) — out of scope."
    )


if __name__ == "__main__":
    main()
