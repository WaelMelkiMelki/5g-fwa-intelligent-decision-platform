"""Run source-table and ABT data-quality checks."""

from __future__ import annotations

import argparse
from pathlib import Path
import sys

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from data_pipeline.abt import build_abt, load_source_dataset
from data_pipeline.quality import run_quality_checks, save_quality_report


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source-dir", type=Path, default=Path("data/processed"))
    parser.add_argument("--abt-path", type=Path, default=None)
    parser.add_argument("--output", type=Path, default=Path("data/processed/quality_report.json"))
    args = parser.parse_args()

    dataset = load_source_dataset(args.source_dir)
    abt = (
        __import__("pandas").read_parquet(args.abt_path)
        if args.abt_path
        else build_abt(dataset)
    )
    report = run_quality_checks(dataset, abt)
    save_quality_report(report, args.output)
    summary = report["summary"]
    print(f"Quality status: {summary['status']}")
    print(f"Checks: {summary['passed']} passed, {summary['failed']} failed")
    if summary["failed"]:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
