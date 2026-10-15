"""Build the local subscriber-month Analytical Base Table."""

from __future__ import annotations

import argparse
from pathlib import Path
import sys

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from data_pipeline.abt import build_abt, load_source_dataset, save_abt


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source-dir", type=Path, default=Path("data/processed"))
    parser.add_argument("--output-dir", type=Path, default=Path("data/processed"))
    args = parser.parse_args()

    dataset = load_source_dataset(args.source_dir)
    abt = build_abt(dataset)
    manifest = save_abt(abt, args.output_dir)
    print(f"Built {manifest['table']} with {manifest['rows']:,} rows")
    print(f"  grain: {', '.join(manifest['grain'])}")
    print(f"  columns: {len(manifest['columns'])}")


if __name__ == "__main__":
    main()
