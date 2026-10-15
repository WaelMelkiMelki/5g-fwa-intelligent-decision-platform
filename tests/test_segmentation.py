"""Tests for mixed-type K-Prototypes segmentation."""

from __future__ import annotations

import pandas as pd
import pytest

from data_generation.synthetic_fwa import SyntheticFwaConfig, generate_dataset
from data_pipeline.abt import build_abt
from data_pipeline.eligibility import score_eligibility
from data_pipeline.segmentation import (
    SegmentationConfig,
    fit_segmentation,
    save_segmentation,
    validate_segmentation,
)


def _inputs(seed: int = 41):
    dataset = generate_dataset(SyntheticFwaConfig(subscribers=80, cells=6, seed=seed))
    abt = build_abt(dataset)
    eligibility = score_eligibility(abt)
    return abt, eligibility


def test_segmentation_uses_eligible_rows_and_declared_clusters():
    abt, eligibility = _inputs()
    config = SegmentationConfig(n_clusters=3, seed=7, n_init=2)
    assignments, profiles, cost = fit_segmentation(abt, eligibility, config)
    validate_segmentation(assignments, config.n_clusters)
    assert len(assignments) == int((eligibility["fwa_suitability_score"] > 0).sum())
    assert assignments["cluster_id"].nunique() == 3
    assert len(profiles) == 3
    assert cost > 0


def test_segmentation_is_reproducible():
    abt, eligibility = _inputs(42)
    config = SegmentationConfig(n_clusters=3, seed=9, n_init=2)
    first = fit_segmentation(abt, eligibility, config)[0].sort_values("subscriber_id").reset_index(drop=True)
    second = fit_segmentation(abt, eligibility, config)[0].sort_values("subscriber_id").reset_index(drop=True)
    pd.testing.assert_frame_equal(first, second)


def test_segmentation_persistence(tmp_path):
    abt, eligibility = _inputs(43)
    config = SegmentationConfig(n_clusters=3, seed=4, n_init=2)
    assignments, profiles, cost = fit_segmentation(abt, eligibility, config)
    manifest = save_segmentation(assignments, profiles, cost, tmp_path, config)
    assert manifest["method"] == "K-Prototypes"
    assert (tmp_path / "subscriber_segments.parquet").exists()
    assert (tmp_path / "segment_profiles.parquet").exists()
    assert (tmp_path / "segmentation_manifest.json").exists()


def test_segmentation_rejects_too_few_clusters():
    abt, eligibility = _inputs(44)
    with pytest.raises(ValueError, match="at least 2"):
        fit_segmentation(abt, eligibility, SegmentationConfig(n_clusters=1))
