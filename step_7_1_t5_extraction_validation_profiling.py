"""
===============================================================================
5G FWA Migration Analytics Pipeline
Step 7 — Service Consumption & Offer Opportunity Features (T5)
Sub-step 7.1: T5 Extraction, Schema Validation, and Baseline Profiling
===============================================================================

Filename: step_7_1_t5_extraction_validation_profiling.py

Objective:
    Extract the monthly service consumption data from cleaned_data.t5_service_consumption_monthly,
    enforce strict schema typing, validate the expected grain (one row per subscriber_id per
    snapshot_month), and perform baseline statistical profiling on continuous service volume
    columns (streaming_vol_gb, gaming_vol_gb, voip_minutes).

This establishes a clean, validated, and statistically understood foundation for the dynamic
threshold discovery in Sub-step 7.2 (1D GMM intersection).

Author: Data Analytics Intern
Date: July 2026
===============================================================================
"""

import sys
import logging
import numpy as np
import pandas as pd
from sqlalchemy import create_engine, text, inspect
from sqlalchemy.types import (
    VARCHAR, DATE, FLOAT, INTEGER, BOOLEAN
)

# =============================================================================
# 0. CONFIGURATION & LOGGING
# =============================================================================

# Database connection string (PostgreSQL)
DB_CONNECTION_STRING = __import__("os").environ["FWA_DB_URL"]

# Target table in cleaned_data schema
SOURCE_TABLE = "cleaned_data.t5_service_consumption_monthly"

# Expected grain keys
GRAIN_KEYS = ["subscriber_id", "snapshot_month"]

# Continuous columns to profile (the targets for 1D GMM threshold discovery in 7.2)
CONTINUOUS_TARGETS = ["streaming_vol_gb", "gaming_vol_gb", "voip_minutes"]

# All expected columns and their strict PostgreSQL types
EXPECTED_SCHEMA = {
    "subscriber_id": VARCHAR(50),
    "snapshot_month": DATE,
    "streaming_vol_gb": FLOAT,
    "streaming_session_count": INTEGER,
    "iptv_active_flag": BOOLEAN,
    "iptv_watch_hours": FLOAT,
    "voip_minutes": FLOAT,
    "social_media_vol_gb": FLOAT,
    "gaming_vol_gb": FLOAT,
}

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)-7s | %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger(__name__)


# =============================================================================
# 1. EXTRACTION
# =============================================================================

def extract_t5(engine: create_engine) -> pd.DataFrame:
    """
    Extract the full T5 service consumption table from the cleaned_data schema.
    """
    logger.info("=" * 80)
    logger.info("PHASE 1: EXTRACTION")
    logger.info("=" * 80)
    
    query = f"SELECT * FROM {SOURCE_TABLE}"
    logger.info(f"Executing query: {query}")
    
    df = pd.read_sql(query, engine)
    logger.info(f"Extracted {len(df):,} rows and {len(df.columns)} columns from {SOURCE_TABLE}")
    
    return df


# =============================================================================
# 2. GRAIN VALIDATION
# =============================================================================

def validate_grain(df: pd.DataFrame) -> None:
    """
    Assert that the composite key (subscriber_id, snapshot_month) is strictly unique.
    Raises an exception if duplicates are found, halting the pipeline.
    """
    logger.info("=" * 80)
    logger.info("PHASE 2: GRAIN VALIDATION")
    logger.info("=" * 80)
    
    duplicates = df[df.duplicated(subset=GRAIN_KEYS, keep=False)]
    n_duplicates = len(duplicates)
    
    if n_duplicates > 0:
        logger.error(f"GRAIN VIOLATION: Found {n_duplicates} duplicate rows on {GRAIN_KEYS}")
        logger.error(f"Sample duplicates:\n{duplicates.head(10)}")
        raise ValueError(f"Pipeline halted: {n_duplicates} duplicate rows found on grain keys {GRAIN_KEYS}")
    
    logger.info(f"GRAIN CHECK PASSED: {len(df):,} rows, 0 duplicates on {GRAIN_KEYS}")
    logger.info(f"Unique subscribers: {df['subscriber_id'].nunique():,}")
    logger.info(f"Unique snapshot months: {df['snapshot_month'].nunique()}")


# =============================================================================
# 3. SCHEMA & TYPE ENFORCEMENT
# =============================================================================

def enforce_schema(df: pd.DataFrame) -> pd.DataFrame:
    """
    Enforce strict column-level data types matching the expected PostgreSQL schema.
    """
    logger.info("=" * 80)
    logger.info("PHASE 3: SCHEMA & TYPE ENFORCEMENT")
    logger.info("=" * 80)
    
    # Check for missing columns
    missing_cols = set(EXPECTED_SCHEMA.keys()) - set(df.columns)
    if missing_cols:
        raise ValueError(f"Missing expected columns: {missing_cols}")
    
    # Check for unexpected columns
    extra_cols = set(df.columns) - set(EXPECTED_SCHEMA.keys())
    if extra_cols:
        logger.warning(f"Unexpected columns found (will be dropped): {extra_cols}")
        df = df.drop(columns=list(extra_cols))
    
    # Enforce types
    for col, pg_type in EXPECTED_SCHEMA.items():
        if pg_type == VARCHAR(50):
            df[col] = df[col].astype(str)
        elif pg_type == DATE:
            df[col] = pd.to_datetime(df[col])
        elif pg_type == FLOAT:
            df[col] = pd.to_numeric(df[col], errors="coerce")
        elif pg_type == INTEGER:
            df[col] = pd.to_numeric(df[col], errors="coerce").astype("Int64")
        elif pg_type == BOOLEAN:
            # Handle various boolean representations
            df[col] = df[col].map({True: True, False: False, 1: True, 0: False, 
                                    "TRUE": True, "FALSE": False, "true": True, "false": False})
    
    logger.info(f"Schema enforcement complete. Final columns: {list(df.columns)}")
    logger.info(f"Column dtypes:\n{df.dtypes}")
    
    return df


# =============================================================================
# 4. NULL INTEGRITY CHECK
# =============================================================================

def validate_nulls(df: pd.DataFrame) -> None:
    """
    Assert zero null values across all critical columns.
    """
    logger.info("=" * 80)
    logger.info("PHASE 4: NULL INTEGRITY CHECK")
    logger.info("=" * 80)
    
    null_counts = df.isnull().sum()
    total_nulls = null_counts.sum()
    
    if total_nulls > 0:
        logger.error(f"NULL VIOLATION: Found {total_nulls} total null values across columns:")
        for col, count in null_counts.items():
            if count > 0:
                logger.error(f"  {col}: {count} nulls ({count/len(df)*100:.2f}%)")
        raise ValueError(f"Pipeline halted: {total_nulls} null values found. T5 must be fully complete.")
    
    logger.info(f"NULL CHECK PASSED: 0 null values across all {len(df.columns)} columns")


# =============================================================================
# 5. PHYSICAL BOUNDS VALIDATION
# =============================================================================

def validate_physical_bounds(df: pd.DataFrame) -> None:
    """
    Assert that all volume and minute columns are non-negative.
    """
    logger.info("=" * 80)
    logger.info("PHASE 5: PHYSICAL BOUNDS VALIDATION")
    logger.info("=" * 80)
    
    volume_cols = ["streaming_vol_gb", "gaming_vol_gb", "social_media_vol_gb", 
                   "iptv_watch_hours", "voip_minutes"]
    
    violations = 0
    for col in volume_cols:
        negative_count = (df[col] < 0).sum()
        if negative_count > 0:
            logger.error(f"BOUND VIOLATION: {col} has {negative_count} negative values")
            violations += negative_count
    
    if violations > 0:
        raise ValueError(f"Pipeline halted: {violations} negative volume/minute values found.")
    
    logger.info(f"BOUNDS CHECK PASSED: All volume/minute columns are non-negative")
    
    # Session count validation
    negative_sessions = (df["streaming_session_count"] < 0).sum()
    if negative_sessions > 0:
        raise ValueError(f"Pipeline halted: {negative_sessions} negative session counts found.")
    logger.info(f"Session count check passed: all values >= 0")


# =============================================================================
# 6. BASELINE STATISTICAL PROFILING
# =============================================================================

def profile_continuous_features(df: pd.DataFrame) -> dict:
    """
    Compute descriptive statistics for the continuous service volume columns
    that will be thresholded via 1D GMM in Sub-step 7.2.
    """
    logger.info("=" * 80)
    logger.info("PHASE 6: BASELINE STATISTICAL PROFILING")
    logger.info("=" * 80)
    
    profiles = {}
    
    for col in CONTINUOUS_TARGETS:
        logger.info(f"\n--- Profiling: {col} ---")
        
        series = df[col]
        profile = {
            "count": int(series.count()),
            "mean": float(series.mean()),
            "median": float(series.median()),
            "std": float(series.std()),
            "min": float(series.min()),
            "max": float(series.max()),
            "q25": float(series.quantile(0.25)),
            "q50": float(series.quantile(0.50)),
            "q75": float(series.quantile(0.75)),
            "q90": float(series.quantile(0.90)),
            "q95": float(series.quantile(0.95)),
            "q99": float(series.quantile(0.99)),
            "zero_count": int((series == 0).sum()),
            "zero_pct": float((series == 0).sum() / len(series) * 100),
            "skewness": float(series.skew()),
            "kurtosis": float(series.kurtosis()),
        }
        
        profiles[col] = profile
        
        logger.info(f"  Count:    {profile['count']:,}")
        logger.info(f"  Mean:     {profile['mean']:.4f}")
        logger.info(f"  Median:   {profile['median']:.4f}")
        logger.info(f"  Std Dev:  {profile['std']:.4f}")
        logger.info(f"  Min:      {profile['min']:.4f}")
        logger.info(f"  Max:      {profile['max']:.4f}")
        logger.info(f"  Q25:      {profile['q25']:.4f}")
        logger.info(f"  Q75:      {profile['q75']:.4f}")
        logger.info(f"  Q95:      {profile['q95']:.4f}")
        logger.info(f"  Zeros:    {profile['zero_count']:,} ({profile['zero_pct']:.2f}%)")
        logger.info(f"  Skewness: {profile['skewness']:.4f}")
        logger.info(f"  Kurtosis: {profile['kurtosis']:.4f}")
    
    # Also profile secondary continuous columns for completeness
    secondary_cols = ["social_media_vol_gb", "iptv_watch_hours"]
    for col in secondary_cols:
        series = df[col]
        logger.info(f"\n--- Secondary Profile: {col} ---")
        logger.info(f"  Mean: {series.mean():.4f}, Median: {series.median():.4f}, "
                     f"Max: {series.max():.4f}, Zeros: {(series==0).sum():,} "
                     f"({(series==0).sum()/len(series)*100:.2f}%)")
    
    return profiles


# =============================================================================
# 7. BOOLEAN FLAG VALIDATION
# =============================================================================

def validate_boolean_flags(df: pd.DataFrame) -> None:
    """
    Assert that boolean flag columns contain only True/False values.
    """
    logger.info("=" * 80)
    logger.info("PHASE 7: BOOLEAN FLAG VALIDATION")
    logger.info("=" * 80)
    
    bool_cols = ["iptv_active_flag"]
    
    for col in bool_cols:
        unique_vals = df[col].dropna().unique()
        invalid = [v for v in unique_vals if not isinstance(v, (bool, np.bool_))]
        
        if invalid:
            raise ValueError(f"Boolean violation: {col} contains non-boolean values: {invalid}")
        
        true_count = df[col].sum()
        false_count = len(df) - true_count
        logger.info(f"  {col}: {true_count:,} TRUE ({true_count/len(df)*100:.2f}%), "
                     f"{false_count:,} FALSE ({false_count/len(df)*100:.2f}%)")
    
    logger.info(f"BOOLEAN CHECK PASSED: All flag columns are strictly boolean")


# =============================================================================
# 8. PERSISTENCE TO CLEANED_DATA SCHEMA
# =============================================================================

def persist_t5(df: pd.DataFrame, engine: create_engine) -> None:
    """
    Persist the validated T5 DataFrame to cleaned_data.t5_service_consumption_monthly
    with strict PostgreSQL type mapping.
    """
    logger.info("=" * 80)
    logger.info("PHASE 8: PERSISTENCE TO CLEANED_DATA SCHEMA")
    logger.info("=" * 80)
    
    target_table = "cleaned_data.t5_service_consumption_monthly"
    
    # Build SQLAlchemy dtype dictionary
    dtype_dict = {
        "subscriber_id": VARCHAR(50),
        "snapshot_month": DATE,
        "streaming_vol_gb": FLOAT,
        "streaming_session_count": INTEGER,
        "iptv_active_flag": BOOLEAN,
        "iptv_watch_hours": FLOAT,
        "voip_minutes": FLOAT,
        "social_media_vol_gb": FLOAT,
        "gaming_vol_gb": FLOAT,
    }
    
    # Truncate and reload (idempotent)
    with engine.connect() as conn:
        conn.execute(text(f"TRUNCATE TABLE {target_table}"))
        conn.commit()
    
    df.to_sql(
        name="t5_service_consumption_monthly",
        con=engine,
        schema="cleaned_data",
        if_exists="append",
        index=False,
        dtype=dtype_dict,
        method="multi",
    )
    
    logger.info(f"Persisted {len(df):,} rows to {target_table} with strict type enforcement")


# =============================================================================
# 9. EXECUTION SUMMARY
# =============================================================================

def print_execution_summary(df: pd.DataFrame, profiles: dict) -> None:
    """
    Print a comprehensive execution summary for audit and documentation.
    """
    logger.info("=" * 80)
    logger.info("EXECUTION SUMMARY — Sub-step 7.1")
    logger.info("=" * 80)
    
    logger.info(f"\n{'─' * 60}")
    logger.info(f"OPERATIONS PERFORMED:")
    logger.info(f"{'─' * 60}")
    logger.info(f"  1. Extraction from cleaned_data.t5_service_consumption_monthly")
    logger.info(f"  2. Grain validation on (subscriber_id, snapshot_month)")
    logger.info(f"  3. Schema & type enforcement (9 columns)")
    logger.info(f"  4. Null integrity check (0 nulls required)")
    logger.info(f"  5. Physical bounds validation (non-negative volumes)")
    logger.info(f"  6. Baseline statistical profiling (3 continuous targets)")
    logger.info(f"  7. Boolean flag validation")
    logger.info(f"  8. Persistence to cleaned_data schema")
    
    logger.info(f"\n{'─' * 60}")
    logger.info(f"DATASET STATISTICS:")
    logger.info(f"{'─' * 60}")
    logger.info(f"  Total rows processed:    {len(df):,}")
    logger.info(f"  Unique subscribers:      {df['subscriber_id'].nunique():,}")
    logger.info(f"  Unique snapshot months:  {df['snapshot_month'].nunique()}")
    logger.info(f"  Snapshot month value:    {df['snapshot_month'].iloc[0]}")
    logger.info(f"  Total columns:           {len(df.columns)}")
    
    logger.info(f"\n{'─' * 60}")
    logger.info(f"VALIDATION RESULTS:")
    logger.info(f"{'─' * 60}")
    logger.info(f"  Grain uniqueness:        PASSED (0 duplicates)")
    logger.info(f"  Null integrity:          PASSED (0 nulls)")
    logger.info(f"  Physical bounds:         PASSED (0 negative values)")
    logger.info(f"  Boolean flags:           PASSED (strict True/False)")
    
    logger.info(f"\n{'─' * 60}")
    logger.info(f"BASELINE PROFILING — CONTINUOUS TARGETS:")
    logger.info(f"{'─' * 60}")
    
    for col, p in profiles.items():
        logger.info(f"\n  [{col}]")
        logger.info(f"    Distribution: Mean={p['mean']:.2f}, Median={p['median']:.2f}, "
                     f"Std={p['std']:.2f}, Range=[{p['min']:.2f}, {p['max']:.2f}]")
        logger.info(f"    Skewness: {p['skewness']:.2f} | Kurtosis: {p['kurtosis']:.2f}")
        logger.info(f"    Zero-inflation: {p['zero_count']:,} zeros ({p['zero_pct']:.1f}%)")
        logger.info(f"    Percentiles: P25={p['q25']:.2f}, P50={p['q50']:.2f}, "
                     f"P75={p['q75']:.2f}, P95={p['q95']:.2f}")
    
    logger.info(f"\n{'─' * 60}")
    logger.info(f"IPTV ACTIVE FLAG DISTRIBUTION:")
    logger.info(f"{'─' * 60}")
    iptv_true = df["iptv_active_flag"].sum()
    iptv_false = len(df) - iptv_true
    logger.info(f"  IPTV Active:   {iptv_true:,} ({iptv_true/len(df)*100:.1f}%)")
    logger.info(f"  IPTV Inactive: {iptv_false:,} ({iptv_false/len(df)*100:.1f}%)")
    
    logger.info(f"\n{'─' * 60}")
    logger.info(f"BUSINESS INTERPRETATION:")
    logger.info(f"{'─' * 60}")
    
    # Streaming interpretation
    stream_p = profiles["streaming_vol_gb"]
    if stream_p["zero_pct"] > 50:
        logger.info(f"  STREAMING: Highly zero-inflated ({stream_p['zero_pct']:.1f}% zeros). "
                     f"Majority are light/non-streamers. Heavy streamers are a distinct minority.")
    else:
        logger.info(f"  STREAMING: Widespread adoption ({100-stream_p['zero_pct']:.1f}% have usage). "
                     f"Median={stream_p['median']:.1f} GB suggests moderate baseline consumption.")
    
    # Gaming interpretation
    gaming_p = profiles["gaming_vol_gb"]
    if gaming_p["zero_pct"] > 80:
        logger.info(f"  GAMING: Extremely niche ({gaming_p['zero_pct']:.1f}% zeros). "
                     f"Gaming add-on bundles will target a very small, high-value segment.")
    elif gaming_p["zero_pct"] > 50:
        logger.info(f"  GAMING: Moderate adoption ({100-gaming_p['zero_pct']:.1f}% have usage). "
                     f"Low-latency gaming bundles have a viable target audience.")
    else:
        logger.info(f"  GAMING: Broad adoption ({100-gaming_p['zero_pct']:.1f}% have usage). "
                     f"Gaming add-ons are a strong commercial lever.")
    
    # VoIP interpretation
    voip_p = profiles["voip_minutes"]
    if voip_p["zero_pct"] > 50:
        logger.info(f"  VoIP: High zero-inflation ({voip_p['zero_pct']:.1f}% zeros). "
                     f"Convergent fixed-mobile bundles will target the active VoIP minority.")
    else:
        logger.info(f"  VoIP: Widespread usage ({100-voip_p['zero_pct']:.1f}% have minutes). "
                     f"Fixed-mobile convergence is a strong value proposition.")
    
    logger.info(f"\n{'─' * 60}")
    logger.info(f"READINESS FOR NEXT DEPENDENCY (Sub-step 7.2):")
    logger.info(f"{'─' * 60}")
    logger.info(f"  The validated T5 DataFrame is ready for 1D GMM threshold discovery.")
    logger.info(f"  The baseline profiles inform the GMM fitting:")
    
    for col, p in profiles.items():
        if p["zero_pct"] > 50:
            logger.info(f"    {col}: High zero-inflation ({p['zero_pct']:.1f}%) — "
                         f"GMM may need to account for zero-inflated distribution.")
        else:
            logger.info(f"    {col}: Moderate zero-inflation ({p['zero_pct']:.1f}%) — "
                         f"Standard 2-component GMM should perform well.")
    
    logger.info(f"\n{'=' * 80}")
    logger.info(f"SUB-STEP 7.1 COMPLETE — ALL VALIDATIONS PASSED")
    logger.info(f"{'=' * 80}\n")


# =============================================================================
# MAIN EXECUTION
# =============================================================================

def main():
    """
    Main execution pipeline for Sub-step 7.1.
    """
    logger.info("\n" + "=" * 80)
    logger.info("STARTING SUB-STEP 7.1: T5 EXTRACTION, VALIDATION & PROFILING")
    logger.info("=" * 80 + "\n")
    
    try:
        # Initialize database engine
        engine = create_engine(DB_CONNECTION_STRING)
        
        # Phase 1: Extract
        df = extract_t5(engine)
        
        # Phase 2: Grain validation
        validate_grain(df)
        
        # Phase 3: Schema enforcement
        df = enforce_schema(df)
        
        # Phase 4: Null integrity
        validate_nulls(df)
        
        # Phase 5: Physical bounds
        validate_physical_bounds(df)
        
        # Phase 6: Baseline profiling
        profiles = profile_continuous_features(df)
        
        # Phase 7: Boolean flag validation
        validate_boolean_flags(df)
        
        # Phase 8: Persist
        persist_t5(df, engine)
        
        # Phase 9: Execution summary
        print_execution_summary(df, profiles)
        
    except Exception as e:
        logger.critical(f"PIPELINE FAILED: {e}", exc_info=True)
        sys.exit(1)
    
    logger.info("Pipeline completed successfully.")


if __name__ == "__main__":
    main()
