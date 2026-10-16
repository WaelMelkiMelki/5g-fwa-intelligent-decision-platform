"""Train the reconstructed single-snapshot churn baseline."""

from __future__ import annotations

import argparse
from pathlib import Path
import sys

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

import pandas as pd

from data_pipeline.churn import ChurnConfig, save_churn_outputs, train_churn_model


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--abt-path", type=Path, default=Path("data/processed/abt_subscriber_month.parquet"))
    parser.add_argument("--output-dir", type=Path, default=Path("data/processed"))
    parser.add_argument("--seed", type=int, default=42)
    args = parser.parse_args()

    abt = pd.read_parquet(args.abt_path)
    _, predictions, metrics = train_churn_model(abt, ChurnConfig(seed=args.seed))
    save_churn_outputs(predictions, metrics, args.output_dir)
    print(f"Trained {metrics['algorithm']} on {metrics['train_rows']:,} rows")
    print(f"ROC-AUC: {metrics['roc_auc']:.4f}")
    print(f"Average precision: {metrics['average_precision']:.4f}")
    print(f"Predictions: {len(predictions):,}")


if __name__ == "__main__":
    main()
