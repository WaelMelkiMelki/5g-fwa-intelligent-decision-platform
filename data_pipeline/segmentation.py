"""Mixed-type K-Prototypes segmentation for eligible FWA subscribers."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
import json
from pathlib import Path
from typing import Mapping

import numpy as np
import pandas as pd
from kmodes.kprototypes import KPrototypes
from sklearn.preprocessing import StandardScaler


NUMERIC_FEATURES = (
    "arpu_monthly_tnd",
    "tenure_months",
    "num_active_lines",
    "monthly_sessions",
    "monthly_total_gb",
    "monthly_peak_hour_ratio",
    "streaming_vol_gb",
    "gaming_vol_gb",
    "voip_minutes",
    "p95_prb_utilisation_pct",
)
CATEGORICAL_FEATURES = (
    "contract_type",
    "segment_tier",
    "dominant_device_generation",
    "radio_feasibility_class",
    "iptv_active_flag",
    "multi_line_flag",
)


@dataclass(frozen=True)
class SegmentationConfig:
    """Controls K-Prototypes training and feature preparation."""

    n_clusters: int = 4
    seed: int = 42
    n_init: int = 5
    init: str = "Cao"


def prepare_segmentation_frame(
    abt: pd.DataFrame,
    eligibility: pd.DataFrame,
) -> pd.DataFrame:
    """Return the eligible ABT rows with the declared clustering features."""
    required = set(NUMERIC_FEATURES) | set(CATEGORICAL_FEATURES) | {
        "subscriber_id",
        "snapshot_month",
    }
    missing = required.difference(abt.columns)
    if missing:
        raise ValueError(f"ABT is missing segmentation columns: {sorted(missing)}")
    if not {"subscriber_id", "snapshot_month", "fwa_suitability_score"}.issubset(eligibility.columns):
        raise ValueError("Eligibility output is missing segmentation keys or score")

    keys = ["subscriber_id", "snapshot_month"]
    eligible_keys = eligibility.loc[eligibility["fwa_suitability_score"] > 0, keys]
    frame = abt.merge(eligible_keys, on=keys, how="inner", validate="one_to_one")
    if frame.empty:
        raise ValueError("No eligible subscribers are available for segmentation")
    if frame[list(NUMERIC_FEATURES) + list(CATEGORICAL_FEATURES)].isna().any().any():
        raise ValueError("Segmentation features cannot contain null values")
    return frame


def fit_segmentation(
    abt: pd.DataFrame,
    eligibility: pd.DataFrame,
    config: SegmentationConfig | None = None,
) -> tuple[pd.DataFrame, pd.DataFrame, float]:
    """Fit K-Prototypes and return assignments, profiles, and model cost."""
    config = config or SegmentationConfig()
    if config.n_clusters < 2:
        raise ValueError("n_clusters must be at least 2")
    frame = prepare_segmentation_frame(abt, eligibility)
    numeric = StandardScaler().fit_transform(frame[list(NUMERIC_FEATURES)])
    categorical = frame[list(CATEGORICAL_FEATURES)].astype(str).to_numpy()
    matrix = np.column_stack([numeric, categorical]).astype(object)
    categorical_indices = list(range(len(NUMERIC_FEATURES), matrix.shape[1]))

    model = KPrototypes(
        n_clusters=config.n_clusters,
        init=config.init,
        n_init=config.n_init,
        random_state=config.seed,
        verbose=0,
    )
    labels = model.fit_predict(matrix, categorical=categorical_indices)
    assignments = frame[["subscriber_id", "snapshot_month"]].copy()
    assignments["cluster_id"] = labels.astype(int)
    assignments["business_label"] = assignments["cluster_id"].map(lambda value: f"Cluster {value}")

    profile_frame = frame.copy()
    profile_frame["cluster_id"] = labels.astype(int)
    numeric_profile = profile_frame.groupby("cluster_id", as_index=False)[list(NUMERIC_FEATURES)].mean()
    categorical_profile = profile_frame.groupby("cluster_id", as_index=False)[list(CATEGORICAL_FEATURES)].agg(
        lambda series: series.mode().iloc[0]
    )
    counts = profile_frame.groupby("cluster_id").size().rename("subscriber_count").reset_index()
    profiles = counts.merge(numeric_profile, on="cluster_id").merge(categorical_profile, on="cluster_id")
    profiles["business_label"] = profiles["cluster_id"].map(lambda value: f"Cluster {value}")
    return assignments, profiles, float(model.cost_)


def validate_segmentation(assignments: pd.DataFrame, expected_clusters: int) -> None:
    """Validate assignment grain and cluster-domain invariants."""
    required = {"subscriber_id", "snapshot_month", "cluster_id", "business_label"}
    missing = required.difference(assignments.columns)
    if missing:
        raise ValueError(f"Segmentation output is missing columns: {sorted(missing)}")
    if assignments[["subscriber_id", "snapshot_month"]].duplicated().any():
        raise ValueError("Segmentation output must be unique by subscriber and snapshot")
    if assignments.empty or assignments["cluster_id"].nunique() < min(expected_clusters, len(assignments)):
        raise ValueError("Segmentation did not produce the expected cluster coverage")
    if not assignments["cluster_id"].between(0, expected_clusters - 1).all():
        raise ValueError("Segmentation contains an invalid cluster id")


def save_segmentation(
    assignments: pd.DataFrame,
    profiles: pd.DataFrame,
    cost: float,
    output_dir: str | Path,
    config: SegmentationConfig,
) -> dict:
    """Validate and persist assignments, profiles, and experiment metadata."""
    validate_segmentation(assignments, config.n_clusters)
    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)
    assignments.to_parquet(output_path / "subscriber_segments.parquet", index=False)
    profiles.to_parquet(output_path / "segment_profiles.parquet", index=False)
    manifest = {
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "method": "K-Prototypes",
        "config": {
            "n_clusters": config.n_clusters,
            "seed": config.seed,
            "n_init": config.n_init,
            "init": config.init,
        },
        "eligible_rows": len(assignments),
        "cluster_count": int(assignments["cluster_id"].nunique()),
        "model_cost": cost,
    }
    (output_path / "segmentation_manifest.json").write_text(
        json.dumps(manifest, indent=2) + "\n", encoding="utf-8"
    )
    return manifest
