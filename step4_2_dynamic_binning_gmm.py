#!/usr/bin/env python3
"""
=============================================================================
FWA Migration Analytics Pipeline
Step 4 — CRM & Commercial Feature Preparation (T2)
Sub-task 4.2: Dynamic Binning via 1D Gaussian Mixture Model (GMM) Intersection
=============================================================================

Objective:
    Create 'arpu_band' and 'tenure_band' by applying a 1D Gaussian Mixture 
    Model (K=2) to the continuous ARPU and Tenure distributions. Instead of 
    using a simple midpoint, we calculate the exact probabilistic intersection 
    of the two PDFs to find a variance-aware, skewness-robust threshold.

Source:      cleaned_data.t2_commercial_features_raw
Output:      cleaned_data.t2_commercial_features_binned
Grain:       1 row per subscriber_id per snapshot_month
Dependencies: Sub-task 4.1 (Raw Extraction) — COMPLETED

Author:  FWA Analytics Pipeline
Date:    2026-07-18
=============================================================================
"""

import sys
import numpy as np
import pandas as pd
from sqlalchemy import create_engine, text, types as sa_types
from sklearn.mixture import GaussianMixture

# ─────────────────────────────────────────────────────────────────────────────
# 1. CONFIGURATION
# ─────────────────────────────────────────────────────────────────────────────

DB_CONFIG = {
    "host": "localhost",
    "port": 5432,
    "database": "postgres",
    "user": "postgres",
    "password": __import__("os").environ["FWA_DB_PASSWORD"],
}

SCHEMA = "cleaned_data"
INPUT_TABLE = f"{SCHEMA}.t2_commercial_features_raw"
OUTPUT_TABLE = f"{SCHEMA}.t2_commercial_features_binned"

# Columns to carry over from the raw table
CARRY_OVER_COLS = [
    "subscriber_id", "snapshot_month", "segment_tier", "contract_type", 
    "num_active_lines", "has_mobile_sub_flag"
]

# Columns to bin
BINNING_TARGETS = {
    "arpu_monthly_tnd": {
        "new_col": "arpu_band",
        "labels": ("Low ARPU", "High ARPU")
    },
    "tenure_months": {
        "new_col": "tenure_band",
        "labels": ("Short Tenure", "Long Tenure")
    }
}

# ─────────────────────────────────────────────────────────────────────────────
# 2. DATABASE CONNECTION
# ─────────────────────────────────────────────────────────────────────────────

def get_engine() -> "sqlalchemy.engine.Engine":
    """Create and return a SQLAlchemy engine."""
    url = (
        f"postgresql://{DB_CONFIG['user']}:{DB_CONFIG['password']}"
        f"@{DB_CONFIG['host']}:{DB_CONFIG['port']}/{DB_CONFIG['database']}"
    )
    engine = create_engine(url, echo=False)
    with engine.connect() as conn:
        conn.execute(text("SELECT 1"))
    print("✓ Database connection established successfully.\n")
    return engine

# ─────────────────────────────────────────────────────────────────────────────
# 3. MATHEMATICAL ENGINE: 1D GMM INTERSECTION
# ─────────────────────────────────────────────────────────────────────────────

def calculate_gmm_threshold(data: np.ndarray) -> tuple[float, dict]:
    """
    Fits a 1D Gaussian Mixture Model (K=2) and calculates the exact 
    probabilistic intersection point of the two PDFs.
    
    Math:
    Equates the two Gaussian PDFs and solves the resulting quadratic equation:
    A*x^2 + B*x + C = 0
    
    Returns:
        threshold (float): The optimal split point.
        params (dict): The extracted GMM parameters for logging.
    """
    X = data.reshape(-1, 1)
    
    # Fit GMM with 2 components
    gmm = GaussianMixture(n_components=2, random_state=42, max_iter=200)
    gmm.fit(X)
    
    # Extract parameters
    means = gmm.means_.flatten()
    variances = gmm.covariances_.flatten()
    weights = gmm.weights_.flatten()
    
    # Sort components by mean so mu1 < mu2
    sort_idx = np.argsort(means)
    mu1, mu2 = means[sort_idx]
    var1, var2 = variances[sort_idx]
    pi1, pi2 = weights[sort_idx]
    
    # Calculate quadratic coefficients A, B, C
    A = 0.5 * (1/var2 - 1/var1)
    B = (mu1/var1) - (mu2/var2)
    # Note: sigma = sqrt(variance)
    C = 0.5 * ((mu2**2)/var2 - (mu1**2)/var1) + np.log((pi1 * np.sqrt(var2)) / (pi2 * np.sqrt(var1)))
    
    # Solve for the intersection threshold
    if np.isclose(A, 0, atol=1e-8):
        # Variances are practically equal; reduces to a linear equation (midpoint)
        threshold = -C / B if not np.isclose(B, 0) else (mu1 + mu2) / 2
    else:
        discriminant = B**2 - 4*A*C
        if discriminant < 0:
            # Fallback if no real roots (mathematically unlikely for valid GMMs)
            threshold = (mu1 + mu2) / 2
        else:
            root1 = (-B + np.sqrt(discriminant)) / (2*A)
            root2 = (-B - np.sqrt(discriminant)) / (2*A)
            
            # The valid threshold must lie strictly between the two means
            if mu1 <= root1 <= mu2:
                threshold = root1
            elif mu1 <= root2 <= mu2:
                threshold = root2
            else:
                threshold = (mu1 + mu2) / 2

    params = {
        'mu1': mu1, 'mu2': mu2,
        'var1': var1, 'var2': var2,
        'pi1': pi1, 'pi2': pi2,
        'A': A, 'B': B, 'C': C
    }
    
    return float(threshold), params

# ─────────────────────────────────────────────────────────────────────────────
# 4. EXTRACTION & BINNING APPLICATION
# ─────────────────────────────────────────────────────────────────────────────

def extract_and_bin(engine: "sqlalchemy.engine.Engine") -> tuple[pd.DataFrame, dict]:
    """
    Extracts data from the raw table and applies the GMM binning logic.
    """
    cols_sql = ", ".join(CARRY_OVER_COLS + list(BINNING_TARGETS.keys()))
    query = f"SELECT {cols_sql} FROM {INPUT_TABLE};"
    df = pd.read_sql(query, engine)
    print(f"✓ Extracted {len(df):,} rows from {INPUT_TABLE}.")
    
    thresholds = {}
    
    for col, config in BINNING_TARGETS.items():
        print(f"\n  ▸ Processing {col}...")
        data = df[col].dropna().values
        
        # Calculate threshold
        threshold, params = calculate_gmm_threshold(data)
        thresholds[col] = {'threshold': threshold, 'params': params}
        
        # Apply vectorized binning
        new_col = config['new_col']
        label_low, label_high = config['labels']
        
        df[new_col] = np.where(df[col] < threshold, label_low, label_high)
        df[new_col] = df[new_col].astype('category')
        
        print(f"    ↳ GMM Threshold: {threshold:.2f}")
        print(f"    ↳ Centroids (μ1, μ2): {params['mu1']:.2f}, {params['mu2']:.2f}")
        print(f"    ↳ Variances (σ1², σ2²): {params['var1']:.2f}, {params['var2']:.2f}")
        print(f"    ↳ Band Distribution: {df[new_col].value_counts().to_dict()}")
        
    return df, thresholds

# ─────────────────────────────────────────────────────────────────────────────
# 5. VALIDATION
# ─────────────────────────────────────────────────────────────────────────────

def validate(df: pd.DataFrame, thresholds: dict) -> bool:
    """Validates the newly created binned columns."""
    print("\n" + "=" * 72)
    print("VALIDATION ASSERTIONS")
    print("=" * 72)
    
    all_passed = True
    checks = []
    
    # Check 1: No nulls in new columns
    for col in ["arpu_band", "tenure_band"]:
        nulls = df[col].isnull().sum()
        passed = nulls == 0
        checks.append((f"No nulls in {col}", passed, f"Nulls: {nulls}"))
        
    # Check 2: Distribution balance (no band < 5% of total)
    for col in ["arpu_band", "tenure_band"]:
        min_pct = df[col].value_counts(normalize=True).min() * 100
        passed = min_pct >= 5.0
        checks.append((f"{col} minimum band proportion ≥ 5%", passed, 
                       f"Min proportion: {min_pct:.1f}%"))
        
    # Check 3: Threshold is within physical data bounds
    for col, data in thresholds.items():
        thresh = data['threshold']
        min_val = df[col].min()
        max_val = df[col].max()
        passed = min_val <= thresh <= max_val
        checks.append((f"{col} threshold within data bounds [{min_val}, {max_val}]", 
                       passed, f"Threshold: {thresh:.2f}"))

    for desc, passed, detail in checks:
        icon = "✓" if passed else "✗"
        status = "PASS" if passed else "FAIL"
        print(f"  {icon} [{status}] {desc}")
        print(f"           {detail}")
        if not passed:
            all_passed = False
            
    print()
    return all_passed

# ─────────────────────────────────────────────────────────────────────────────
# 6. PERSISTENCE
# ─────────────────────────────────────────────────────────────────────────────

def persist_to_db(df: pd.DataFrame, engine: "sqlalchemy.engine.Engine") -> None:
    """Writes the binned dataframe to the cleaned_data schema."""
    dtype_map = {
        "subscriber_id": sa_types.VARCHAR(50),
        "snapshot_month": sa_types.Date(),
        "segment_tier": sa_types.VARCHAR(30),
        "arpu_monthly_tnd": sa_types.Float(),
        "tenure_months": sa_types.Integer(),
        "contract_type": sa_types.VARCHAR(20),
        "num_active_lines": sa_types.Integer(),
        "has_mobile_sub_flag": sa_types.Boolean(),
        "arpu_band": sa_types.VARCHAR(20),
        "tenure_band": sa_types.VARCHAR(20),
    }
    
    df_out = df.copy()
    # Convert categories to string for PostgreSQL
    for col in ["segment_tier", "contract_type", "arpu_band", "tenure_band"]:
        df_out[col] = df_out[col].astype(str)
        
    df_out.to_sql(
        name="t2_commercial_features_binned",
        con=engine,
        schema=SCHEMA,
        if_exists="replace",
        index=False,
        dtype=dtype_map,
    )
    print(f"✓ Persisted {len(df_out):,} rows to {OUTPUT_TABLE}.\n")

# ─────────────────────────────────────────────────────────────────────────────
# 7. EXECUTION SUMMARY
# ─────────────────────────────────────────────────────────────────────────────

def print_execution_summary(df: pd.DataFrame, thresholds: dict) -> None:
    """Prints the final execution report."""
    print("=" * 72)
    print("SUB-TASK 4.2 — EXECUTION SUMMARY")
    print("=" * 72)
    
    arpu_thresh = thresholds['arpu_monthly_tnd']['threshold']
    tenure_thresh = thresholds['tenure_months']['threshold']
    
    print(f"""
  WORK COMPLETED
  ──────────────
  • Extracted raw continuous features from {INPUT_TABLE}
  • Fitted 1D Gaussian Mixture Models (K=2) for ARPU and Tenure
  • Calculated probabilistic intersection thresholds (variance-aware)
  • Applied vectorized binning to create categorical bands
  • Validated distribution balance and threshold boundaries
  • Persisted output to {OUTPUT_TABLE}

  DISCOVERED THRESHOLDS (Data-Driven)
  ───────────────────────────────────
  • ARPU Threshold   : {arpu_thresh:.2f} TND
    ↳ Low ARPU (< {arpu_thresh:.2f})   : {len(df[df['arpu_band'] == 'Low ARPU']):,} subs
    ↳ High ARPU (≥ {arpu_thresh:.2f})  : {len(df[df['arpu_band'] == 'High ARPU']):,} subs
    
  • Tenure Threshold : {tenure_thresh:.0f} months
    ↳ Short Tenure (< {tenure_thresh:.0f}) : {len(df[df['tenure_band'] == 'Short Tenure']):,} subs
    ↳ Long Tenure (≥ {tenure_thresh:.0f})  : {len(df[df['tenure_band'] == 'Long Tenure']):,} subs

  BUSINESS INTERPRETATION
  ───────────────────────
  • The ARPU threshold of {arpu_thresh:.2f} TND dynamically separates the mass 
    market from the high-value segment based on actual revenue density, 
    not arbitrary rules. This ensures fair penalty application in Step 9.
  • The Tenure threshold of {tenure_thresh:.0f} months identifies the natural 
    breakpoint between transient and loyal subscribers, providing a strong 
    non-linear signal for the churn model (Step 12).
  • Because we used the GMM intersection, the thresholds automatically 
    adjusted for the right-skewed variance inherent in telecom data.

  NEXT DEPENDENCY
  ───────────────
  → Sub-task 4.3: Household & Lineage Feature Engineering (multi_line_flag)
    Reads from: {OUTPUT_TABLE}
""")

# ─────────────────────────────────────────────────────────────────────────────
# 8. MAIN ORCHESTRATOR
# ─────────────────────────────────────────────────────────────────────────────

def main():
    print("=" * 72)
    print("FWA MIGRATION PIPELINE — STEP 4, SUB-TASK 4.2")
    print("Dynamic Binning via 1D GMM Intersection")
    print("=" * 72 + "\n")
    
    engine = get_engine()
    
    # Extract and Bin
    df, thresholds = extract_and_bin(engine)
    
    # Validate
    all_valid = validate(df, thresholds)
    if not all_valid:
        print("✗ VALIDATION FAILED — Aborting persistence.")
        sys.exit(1)
        
    # Persist
    persist_to_db(df, engine)
    
    # Summary
    print_execution_summary(df, thresholds)
    
    print("=" * 72)
    print("SUB-TASK 4.2 COMPLETE ✓")
    print("=" * 72)

if __name__ == "__main__":
    main()
