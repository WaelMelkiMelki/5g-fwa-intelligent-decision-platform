"""Generate the local synthetic FWA source dataset."""

from __future__ import annotations

import argparse
from pathlib import Path
import sys

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from data_generation.synthetic_fwa import SyntheticFwaConfig, generate_dataset, save_dataset


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-dir", type=Path, default=Path("data/processed"))
    parser.add_argument("--subscribers", type=int, default=1000)
    parser.add_argument("--cells", type=int, default=40)
    parser.add_argument("--snapshot-month", default="2026-01-01")
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--inject-anomalies", action="store_true")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    config = SyntheticFwaConfig(
        subscribers=args.subscribers,
        cells=args.cells,
        snapshot_month=args.snapshot_month,
        seed=args.seed,
        inject_anomalies=args.inject_anomalies,
    )
    dataset = generate_dataset(config)
    manifest = save_dataset(dataset, args.output_dir, config)
    print(f"Generated {len(manifest['tables'])} tables in {args.output_dir}")
    for table_name, metadata in manifest["tables"].items():
        print(f"  {table_name}: {metadata['rows']:,} rows")


if __name__ == "__main__":
    main()
