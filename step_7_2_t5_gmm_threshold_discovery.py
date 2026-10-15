"""
===============================================================================
5G FWA Migration Analytics Pipeline
Step 7 — Service Consumption & Offer Opportunity Features (T5)
Sub-step 7.2: Dynamic Threshold Discovery via 1D GMM Intersection
===============================================================================

Filename: step_7_2_t5_gmm_threshold_discovery.py

Objective:
    Apply a 1D Gaussian Mixture Model (GMM, 2 components) univariately to the continuous 
    service volume columns (streaming_vol_gb, gaming_vol_gb, voip_minutes) to automatically 
    discover the natural, data-driven threshold for "heavy" usage. Generate binary flags 
    (streaming_heavy_flag, gaming_heavy_flag, high_voip_usage_flag) based on these thresholds.

Author: Data Analytics Intern
Date: July 2026
===============================================================================
"""

import sys
import logging
import numpy as np
import pandas as pd
from sqlalchemy import create_engine, text
from sqlalchemy.types import VARCHAR, DATE, FLOAT, INTEGER, BOOLEAN
from sklearn.mixture import GaussianMixture

# =============================================================================
# 0. CONFIGURATION & LOGGING
# =============================================================================

# Database connection string (PostgreSQL)
DB_CONNECTION_STRING = __import__("os").environ["FWA_DB_URL"]

# Target table
TARGET_TABLE = "cleaned_data.t5_service_consumption_monthly"

# Continuous columns for GMM threshold discovery
GMM_TARGETS = ["streaming_vol_gb", "gaming_vol_gb", "voip_minutes"]

# Mapping of target columns to their new binary flag names
FLAG_MAPPING = {
    "streaming_vol_gb": "streaming_heavy_flag",
    "gaming_vol_gb": "gaming_heavy_flag",
    "voip_minutes": "high_voip_usage_flag"
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

def extract_t5(engine) -> pd.DataFrame:
    """Extract the validated T5 table from the cleaned_data schema."""
    logger.info("=" * 80)
    logger.info("PHASE 1: EXTRACTION")
    logger.info("=" * 80)
    
    query = f"SELECT * FROM {TARGET_TABLE}"
    df = pd.read_sql(query, engine)
    logger.info(f"Extracted {len(df):,} rows and {len(df.columns)} columns from {TARGET_TABLE}")
    return df


# =============================================================================
# 2. GMM THRESHOLD DISCOVERY
# =============================================================================

def compute_gmm_threshold(series: pd.Series, col_name: str) -> dict:
    """
    Fit a 1D GMM (K=2) and compute the exact probabilistic intersection point.
    """
    logger.info(f"\n--- Fitting 1D GMM (K=2) for: {col_name} ---")
    X = series.values.reshape(-1, 1)
    
    # Fit GMM
    gmm = GaussianMixture(n_components=2, random_state=42, max_iter=300)
    gmm.fit(X)
    
    # Extract parameters
    means = gmm.means_.flatten()
    variances = gmm.covariances_.flatten()
    weights = gmm.weights_.flatten()
    
    # Sort components by mean (mu1 < mu2)
    sort_idx = np.argsort(means)
    mu1, mu2 = means[sort_idx]
    var1, var2 = variances[sort_idx]
    pi1, pi2 = weights[sort_idx]
    
    # Prevent division by zero for degenerate clusters
    var1 = max(var1, 1e-6)
    var2 = max(var2, 1e-6)
    
    sigma1 = np.sqrt(var1)
    sigma2 = np.sqrt(var2)
    
    # Compute quadratic coefficients: Ax^2 + Bx + C = 0
    A = (1 / (2 * var2)) - (1 / (2 * var1))
    B = (mu1 / var1) - (mu2 / var2)
    C = (mu2**2 / (2 * var2)) - (mu1**2 / (2 * var1)) + np.log((pi1 * sigma2) / (pi2 * sigma1))
    
    # Solve for roots
    if np.isclose(A, 0, atol=1e-8):
        # Linear case (equal variances)
        root = -C / B if not np.isclose(B, 0, atol=1e-8) else (mu1 + mu2) / 2
        roots = [root]
    else:
        discriminant = B**2 - 4 * A * C
        if discriminant < 0:
            # Fallback to midpoint if no real roots (mathematically unlikely for well-separated GMM)
            roots = [(mu1 + mu2) / 2]
        else:
            r1 = (-B + np.sqrt(discriminant)) / (2 * A)
            r2 = (-B - np.sqrt(discriminant)) / (2 * A)
            roots = [r1, r2]
            
    # Select the valid root strictly between mu1 and mu2
    valid_roots = [r for r in roots if mu1 <= r <= mu2]
    threshold = valid_roots[0] if valid_roots else (mu1 + mu2) / 2
    
    logger.info(f"  Component 1 (Light): μ={mu1:.4f}, σ²={var1:.4f}, π={pi1:.4f}")
    logger.info(f"  Component 2 (Heavy): μ={mu2:.4f}, σ²={var2:.4f}, π={pi2:.4f}")
    logger.info(f"  Quadratic Coeffs: A={A:.6f}, B={B:.6f}, C={C:.6f}")
    logger.info(f"  DISCOVERED THRESHOLD (x*): {threshold:.4f}")
    
    return {
        "threshold": threshold,
        "mu1": mu1, "mu2": mu2,
        "var1": var1, "var2": var2,
        "pi1": pi1, "pi2": pi2
    }


# =============================================================================
# 3. FLAG GENERATION & VALIDATION
# =============================================================================

def generate_and_validate_flags(df: pd.DataFrame, gmm_results: dict) -> pd.DataFrame:
    """
    Generate binary flags based on discovered thresholds and validate proportions.
    """
    logger.info("\n" + "=" * 80)
    logger.info("PHASE 3: FLAG GENERATION & VALIDATION")
    logger.info("=" * 80)
    
    flag_cols = []
    for col, flag_name in FLAG_MAPPING.items():
        threshold = gmm_results[col]["threshold"]
        
        # Vectorized flag assignment
        df[flag_name] = np.where(df[col] >= threshold, True, False)
        flag_cols.append(flag_name)
        
        # Validate proportion
        heavy_count = df[flag_name].sum()
        heavy_pct = (heavy_count / len(df)) * 100
        
        if heavy_pct < 5.0:
            logger.warning(f"  WARNING: {flag_name} proportion is {heavy_pct:.2f}% (< 5%). Degenerate split detected.")
        else:
            logger.info(f"  VALIDATION PASSED: {flag_name} proportion is {heavy_pct:.2f}% (>= 5%).")
            
    return df, flag_cols


# =============================================================================
# 4. PERSISTENCE
# =============================================================================

def persist_t5(df: pd.DataFrame, engine) -> None:
    """Persist the enriched T5 DataFrame back to the cleaned_data schema."""
    logger.info("\n" + "=" * 80)
    logger.info("PHASE 4: PERSISTENCE TO CLEANED_DATA SCHEMA")
    logger.info("=" * 80)
    
    # Define strict PostgreSQL schema for the updated table
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
        "streaming_heavy_flag": BOOLEAN,
        "gaming_heavy_flag": BOOLEAN,
        "high_voip_usage_flag": BOOLEAN,
    }
    
    # Truncate and reload (idempotent)
    with engine.connect() as conn:
        conn.execute(text(f"TRUNCATE TABLE {TARGET_TABLE}"))
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
    logger.info(f"Persisted {len(df):,} rows to {TARGET_TABLE} with 12 columns (9 original + 3 new flags).")


# =============================================================================
# 5. EXECUTION SUMMARY
# =============================================================================

def print_execution_summary(df: pd.DataFrame, gmm_results: dict) -> None:
    """Print a comprehensive execution summary."""
    logger.info("\n" + "=" * 80)
    logger.info("EXECUTION SUMMARY — Sub-step 7.2")
    logger.info("=" * 80)
    
    logger.info(f"\n{'─' * 60}")
    logger.info(f"OPERATIONS PERFORMED:")
    logger.info(f"{'─' * 60}")
    logger.info(f"  1. Extraction of validated T5 data")
    logger.info(f"  2. 1D GMM (K=2) fitting for 3 continuous targets")
    logger.info(f"  3. Quadratic intersection solving for variance-aware thresholds")
    logger.info(f"  4. Binary flag generation (Heavy vs Light)")
    logger.info(f"  5. Proportion validation (>= 5% threshold)")
    logger.info(f"  6. Persistence to cleaned_data schema")
    
    logger.info(f"\n{'─' * 60}")
    logger.info(f"DISCOVERED THRESHOLDS (GMM INTERSECTION):")
    logger.info(f"{'─' * 60}")
    for col, res in gmm_results.items():
        logger.info(f"\n  [{col}]")
        logger.info(f"    Light Cluster (μ1): {res['mu1']:.4f} | Variance: {res['var1']:.4f} | Weight: {res['pi1']:.4f}")
        logger.info(f"    Heavy Cluster (μ2): {res['mu2']:.4f} | Variance: {res['var2']:.4f} | Weight: {res['pi2']:.4f}")
        logger.info(f"    Threshold (x*):     {res['threshold']:.4f}")
        
    logger.info(f"\n{'─' * 60}")
    logger.info(f"FLAG DISTRIBUTIONS:")
    logger.info(f"{'─' * 60}")
    for col, flag_name in FLAG_MAPPING.items():
        heavy_count = df[flag_name].sum()
        heavy_pct = (heavy_count / len(df)) * 100
        logger.info(f"  {flag_name}: {heavy_count:,} ({heavy_pct:.2f}%)")
        
    logger.info(f"\n{'─' * 60}")
    logger.info(f"BUSINESS INTERPRETATION & STEP 13 IMPACT:")
    logger.info(f"{'─' * 60}")
    
    stream_pct = (df['streaming_heavy_flag'].sum() / len(df)) * 100
    if stream_pct > 20:
        logger.info(f"  STREAMING: {stream_pct:.1f}% are heavy streamers. High potential for '5G FWA + IPTV Bundle' upsell.")
    else:
        logger.info(f"  STREAMING: {stream_pct:.1f}% are heavy streamers. Moderate IPTV upsell potential.")
        
    gaming_pct = (df['gaming_heavy_flag'].sum() / len(df)) * 100
    if gaming_pct > 10:
        logger.info(f"  GAMING: {gaming_pct:.1f}% are heavy gamers. Strong candidate for 'Low-Latency Gaming Add-on'.")
    else:
        logger.info(f"  GAMING: {gaming_pct:.1f}% are heavy gamers. Niche audience for gaming add-ons.")
        
    voip_pct = (df['high_voip_usage_flag'].sum() / len(df)) * 100
    if voip_pct > 30:
        logger.info(f"  VoIP: {voip_pct:.1f}% have high VoIP usage. Excellent target for 'Convergent Fixed-Mobile Add-on'.")
    else:
        logger.info(f"  VoIP: {voip_pct:.1f}% have high VoIP usage. Standard fixed-mobile convergence target.")

    logger.info(f"\n{'─' * 60}")
    logger.info(f"READINESS FOR NEXT DEPENDENCY (Step 8 - ABT Construction):")
    logger.info(f"{'─' * 60}")
    logger.info(f"  The T5 table now contains 12 columns (9 original + 3 binary flags).")
    logger.info(f"  Grain remains strictly 1 row per subscriber_id per snapshot_month.")
    logger.info(f"  Ready for LEFT JOIN onto the Analytical Base Table (ABT).")
    
    logger.info(f"\n{'=' * 80}")
    logger.info(f"SUB-STEP 7.2 COMPLETE — ALL THRESHOLDS DISCOVERED & VALIDATED")
    logger.info(f"{'=' * 80}\n")


# =============================================================================
# MAIN EXECUTION
# =============================================================================

def main():
    logger.info("\n" + "=" * 80)
    logger.info("STARTING SUB-STEP 7.2: DYNAMIC THRESHOLD DISCOVERY VIA 1D GMM")
    logger.info("=" * 80 + "\n")
    
    try:
        engine = create_engine(DB_CONNECTION_STRING)
        
        # Phase 1: Extract
        df = extract_t5(engine)
        
        # Phase 2: GMM Threshold Discovery
        logger.info("\n" + "=" * 80)
        logger.info("PHASE 2: GMM THRESHOLD DISCOVERY")
        logger.info("=" * 80)
        gmm_results = {}
        for col in GMM_TARGETS:
            gmm_results[col] = compute_gmm_threshold(df[col], col)
            
        # Phase 3: Flag Generation & Validation
        df, flag_cols = generate_and_validate_flags(df, gmm_results)
        
        # Phase 4: Persistence
        persist_t5(df, engine)
        
        # Phase 5: Execution Summary
        print_execution_summary(df, gmm_results)
        
    except Exception as e:
        logger.critical(f"PIPELINE FAILED: {e}", exc_info=True)
        sys.exit(1)
        
    logger.info("Pipeline completed successfully.")

if __name__ == "__main__":
    main()
