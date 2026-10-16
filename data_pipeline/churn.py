"""Leakage-controlled churn modelling for the reconstructed ABT."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import datetime, timezone
import json
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
from sklearn.compose import ColumnTransformer
from sklearn.ensemble import HistGradientBoostingClassifier
from sklearn.metrics import average_precision_score, roc_auc_score
from sklearn.model_selection import train_test_split
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import OneHotEncoder


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
class ChurnConfig:
    """Controls the reproducible single-snapshot churn baseline."""

    test_size: float = 0.2
    seed: int = 42
    max_iter: int = 200
    learning_rate: float = 0.08
    max_leaf_nodes: int = 31


class ChurnModelError(ValueError):
    """Raised when the churn training contract cannot be satisfied."""


def _prepare(abt: pd.DataFrame) -> tuple[pd.DataFrame, pd.Series]:
    required = set(NUMERIC_FEATURES) | set(CATEGORICAL_FEATURES) | {
        "subscriber_id",
        "snapshot_month",
        "churn",
    }
    missing = required.difference(abt.columns)
    if missing:
        raise ChurnModelError(f"ABT is missing churn columns: {sorted(missing)}")
    if abt[list(NUMERIC_FEATURES) + list(CATEGORICAL_FEATURES)].isna().any().any():
        raise ChurnModelError("Churn features cannot contain null values")
    target = pd.to_numeric(abt["churn"], errors="coerce")
    if target.isna().any() or not target.isin([0, 1]).all():
        raise ChurnModelError("Churn target must contain only 0 and 1")
    features = abt[list(NUMERIC_FEATURES) + list(CATEGORICAL_FEATURES)].copy()
    features[list(CATEGORICAL_FEATURES)] = features[list(CATEGORICAL_FEATURES)].astype(str)
    return features, target.astype(int)


def _risk_band(probabilities: np.ndarray) -> pd.Categorical:
    percentile = pd.Series(probabilities).rank(method="average", pct=True).to_numpy()
    return pd.cut(
        percentile,
        bins=[-np.inf, 0.75, 0.90, 0.95, np.inf],
        labels=["Low Risk", "Medium Risk", "High Risk", "Critical Risk"],
        include_lowest=True,
    )


def train_churn_model(
    abt: pd.DataFrame,
    config: ChurnConfig | None = None,
) -> tuple[Pipeline, pd.DataFrame, dict[str, Any]]:
    """Train the CPU-native baseline and return model, predictions, and metrics."""
    config = config or ChurnConfig()
    features, target = _prepare(abt)
    if target.nunique() < 2:
        raise ChurnModelError("Churn target must contain both classes")
    if not 0 < config.test_size < 1:
        raise ChurnModelError("test_size must be between 0 and 1")

    train_x, test_x, train_y, test_y = train_test_split(
        features,
        target,
        test_size=config.test_size,
        random_state=config.seed,
        stratify=target,
    )
    preprocessor = ColumnTransformer(
        [
            ("numeric", "passthrough", list(NUMERIC_FEATURES)),
            ("categorical", OneHotEncoder(handle_unknown="ignore", sparse_output=False), list(CATEGORICAL_FEATURES)),
        ],
        verbose_feature_names_out=False,
    )
    estimator = HistGradientBoostingClassifier(
        max_iter=config.max_iter,
        learning_rate=config.learning_rate,
        max_leaf_nodes=config.max_leaf_nodes,
        random_state=config.seed,
    )
    model = Pipeline([("preprocess", preprocessor), ("classifier", estimator)])
    model.fit(train_x, train_y)
    test_probabilities = model.predict_proba(test_x)[:, 1]
    metrics = {
        "algorithm": "HistGradientBoostingClassifier",
        "evaluation": "stratified single-snapshot holdout",
        "seed": config.seed,
        "train_rows": len(train_x),
        "test_rows": len(test_x),
        "positive_rate": float(target.mean()),
        "roc_auc": float(roc_auc_score(test_y, test_probabilities)),
        "average_precision": float(average_precision_score(test_y, test_probabilities)),
        "average_precision_baseline": float(test_y.mean()),
        "config": asdict(config),
    }

    probabilities = model.predict_proba(features)[:, 1]
    predictions = abt[["subscriber_id", "snapshot_month"]].copy()
    predictions["churn_probability"] = probabilities
    predictions["churn_risk_band"] = _risk_band(probabilities)
    return model, predictions, metrics


def validate_churn_predictions(predictions: pd.DataFrame) -> None:
    required = {"subscriber_id", "snapshot_month", "churn_probability", "churn_risk_band"}
    missing = required.difference(predictions.columns)
    if missing:
        raise ChurnModelError(f"Predictions are missing columns: {sorted(missing)}")
    if predictions[["subscriber_id", "snapshot_month"]].duplicated().any():
        raise ChurnModelError("Predictions must be unique by subscriber and snapshot")
    if not predictions["churn_probability"].between(0, 1).all():
        raise ChurnModelError("Churn probabilities must be between 0 and 1")


def save_churn_outputs(
    predictions: pd.DataFrame,
    metrics: dict[str, Any],
    output_dir: str | Path,
) -> None:
    """Persist predictions and evaluation metadata."""
    validate_churn_predictions(predictions)
    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)
    predictions.to_parquet(output_path / "churn_predictions.parquet", index=False)
    report = {
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "metrics": metrics,
        "prediction_rows": len(predictions),
        "features": {
            "numeric": list(NUMERIC_FEATURES),
            "categorical": list(CATEGORICAL_FEATURES),
        },
        "leakage_exclusions": [
            "subscriber_id",
            "snapshot_month",
            "fwa_suitability_score",
            "fwa_suitability_band",
            "fwa_exclusion_reason",
            "cluster_id",
            "campaign_action",
        ],
    }
    (output_path / "churn_metrics.json").write_text(
        json.dumps(report, indent=2) + "\n", encoding="utf-8"
    )
