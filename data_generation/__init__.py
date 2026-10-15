"""Reproducible synthetic data for the public FWA platform."""

from .synthetic_fwa import SyntheticFwaConfig, generate_dataset, validate_dataset

__all__ = ["SyntheticFwaConfig", "generate_dataset", "validate_dataset"]
