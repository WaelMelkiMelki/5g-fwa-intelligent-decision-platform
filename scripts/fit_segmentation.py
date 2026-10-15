"""Fit K-Prototypes customer segments on eligible reconstructed subscribers."""

from __future__ import annotations

import argparse
from pathlib import Path
import sys

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

import pandas as pd

from data_pipeline.segmentation import SegmentationConfig, fit_segmentation, save_segmentation


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--abt-path", type=Path, default=Path("data/processed/abt_subscriber_month.parquet"))
    parser.add_argument("--eligibility-path", type=Path, default=Path("data/processed/fwa_eligibility.parquet"))
    parser.add_argument("--output-dir", type=Path, default=Path("data/processed"))
    parser.add_argument("--clusters", type=int, default=4)
    parser.add_argument("--seed", type=int, default=42)
    args = parser.parse_args()

    abt = pd.read_parquet(args.abt_path)
    eligibility = pd.read_parquet(args.eligibility_path)
    config = SegmentationConfig(n_clusters=args.clusters, seed=args.seed)
    assignments, profiles, cost = fit_segmentation(abt, eligibility, config)
    manifest = save_segmentation(assignments, profiles, cost, args.output_dir, config)
    print(f"Fitted {manifest['cluster_count']} K-Prototypes clusters")
    print(f"Eligible rows: {manifest['eligible_rows']:,}; cost: {manifest['model_cost']:.2f}")
    print(profiles[["cluster_id", "subscriber_count", "business_label"]].to_string(index=False))


if __name__ == "__main__":
    main()
