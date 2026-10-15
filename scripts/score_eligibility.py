"""Score reconstructed ABT rows for explainable FWA eligibility."""

from __future__ import annotations

import argparse
from pathlib import Path
import sys

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

import pandas as pd

from data_pipeline.eligibility import save_eligibility, score_eligibility


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--abt-path", type=Path, default=Path("data/processed/abt_subscriber_month.parquet"))
    parser.add_argument("--output-dir", type=Path, default=Path("data/processed"))
    args = parser.parse_args()

    abt = pd.read_parquet(args.abt_path)
    scores = score_eligibility(abt)
    manifest = save_eligibility(scores, args.output_dir)
    print(f"Scored {manifest['rows']:,} subscribers")
    print(scores["fwa_suitability_band"].value_counts().sort_index().to_string())


if __name__ == "__main__":
    main()
