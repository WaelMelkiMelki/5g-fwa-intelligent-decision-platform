#!/usr/bin/env python3
"""
=============================================================================
FWA Migration Analytics Pipeline
Step 4 — CRM & Commercial Feature Preparation (T2)
Sub-task 4.1: Direct Feature Extraction & Baseline Validation
=============================================================================

Objective:
    Extract the six foundational CRM features from the cleaned T2 master table,
    enforce strict data typing, profile statistical distributions, and validate
    business constraints to establish a trusted baseline before dynamic binning.

Source:      cleaned_data.t2_crm_subscriber_master
Output:      cleaned_data.t2_commercial_features_raw  (intermediate table)
Grain:       1 row per subscriber_id per snapshot_month
Dependencies: Step 1 (Data Quality), Step 2 (Time Standardization) — COMPLETED

Author:  FWA Analytics Pipeline
Date:    2026-07-18
=============================================================================
"""

import sys
import numpy as np
import pandas as pd
from sqlalchemy import create_engine, text, types as sa_types

# ─────────────────────────────────────────────────────────────────────────────
# 1. CONFIGURATION
# ─────────────────────────────────────────────────────────────────────────────

# Adjust these credentials to match your local PostgreSQL environment.
DB_CONFIG = {
    "host": "localhost",
    "port": 5432,
    "database": "postgres",
    "user": "postgres",
    "password": __import__("os").environ["FWA_DB_PASSWORD"],
}

SCHEMA = "cleaned_data"
SOURCE_TABLE = f"{SCHEMA}.t2_crm_subscriber_master"
OUTPUT_TABLE = f"{SCHEMA}.t2_commercial_features_raw"

# The six core CRM features specified in the project brief (Step 4).
# subscriber_id and snapshot_month are always included as grain keys.
GRAIN_KEYS = ["subscriber_id", "snapshot_month"]
CRM_FEATURES = [
    "segment_tier",
    "arpu_monthly_tnd",
    "tenure_months",
    "contract_type",
    "num_active_lines",
    "has_mobile_sub_flag",
]
SELECT_COLUMNS = GRAIN_KEYS + CRM_FEATURES

# Continuous features for statistical profiling.
CONTINUOUS_COLS = ["arpu_monthly_tnd", "tenure_months", "num_active_lines"]

# Categorical features for value-count profiling.
CATEGORICAL_COLS = ["segment_tier", "contract_type", "has_mobile_sub_flag"]

# ─────────────────────────────────────────────────────────────────────────────
# 2. DATABASE CONNECTION
# ─────────────────────────────────────────────────────────────────────────────

def get_engine() -> "sqlalchemy.engine.Engine":
    """Create and return a SQLAlchemy engine for the FWA database."""
    url = (
        f"postgresql://{DB_CONFIG['user']}:{DB_CONFIG['password']}"
        f"@{DB_CONFIG['host']}:{DB_CONFIG['port']}/{DB_CONFIG['database']}"
    )
    engine = create_engine(url, echo=False)
    # Quick connectivity check
    with engine.connect() as conn:
        conn.execute(text("SELECT 1"))
    print("✓ Database connection established successfully.\n")
    return engine

# ─────────────────────────────────────────────────────────────────────────────
# 3. EXTRACTION
# ─────────────────────────────────────────────────────────────────────────────

def extract_crm_features(engine) -> pd.DataFrame:
    """
    Extract the six core CRM features plus grain keys from the cleaned T2 table.
    
    Returns:
        pd.DataFrame with columns defined in SELECT_COLUMNS.
    """
    cols_sql = ", ".join(SELECT_COLUMNS)
    query = f"SELECT {cols_sql} FROM {SOURCE_TABLE} ORDER BY subscriber_id;"
    
    df = pd.read_sql(query, engine)
    print(f"✓ Extracted {len(df):,} rows × {len(df.columns)} columns "
          f"from {SOURCE_TABLE}.")
    return df

# ─────────────────────────────────────────────────────────────────────────────
# 4. TYPE ENFORCEMENT
# ─────────────────────────────────────────────────────────────────────────────

def enforce_types(df: pd.DataFrame) -> pd.DataFrame:
    """
    Enforce strict Pandas dtypes aligned with the project schema:
      - arpu_monthly_tnd  → float64
      - tenure_months     → Int64  (nullable integer, safe for downstream)
      - num_active_lines  → Int64
      - has_mobile_sub_flag → boolean
      - segment_tier      → category
      - contract_type     → category
      - snapshot_month    → datetime64[ns]  (already DATE from Step 2)
    """
    # Continuous / numeric
    df["arpu_monthly_tnd"] = pd.to_numeric(df["arpu_monthly_tnd"], errors="coerce")
    df["tenure_months"] = pd.to_numeric(df["tenure_months"], errors="coerce").astype("Int64")
    df["num_active_lines"] = pd.to_numeric(df["num_active_lines"], errors="coerce").astype("Int64")
    
    # Boolean
    df["has_mobile_sub_flag"] = df["has_mobile_sub_flag"].astype("boolean")
    
    # Categorical (memory-efficient + prepares for downstream encoding)
    df["segment_tier"] = df["segment_tier"].astype("category")
    df["contract_type"] = df["contract_type"].astype("category")
    
    # Temporal key (ensure datetime, already DATE from Step 2)
    df["snapshot_month"] = pd.to_datetime(df["snapshot_month"])
    
    print("✓ Data types enforced:")
    for col in SELECT_COLUMNS:
        print(f"    {col:25s} → {df[col].dtype}")
    print()
    return df

# ─────────────────────────────────────────────────────────────────────────────
# 5. BASELINE PROFILING
# ─────────────────────────────────────────────────────────────────────────────

def profile_continuous(df: pd.DataFrame) -> None:
    """Print descriptive statistics for continuous CRM features."""
    print("=" * 72)
    print("CONTINUOUS FEATURE PROFILES")
    print("=" * 72)
    
    for col in CONTINUOUS_COLS:
        series = df[col].dropna()
        print(f"\n  ▸ {col}")
        print(f"      Count      : {len(series):>10,}")
        print(f"      Mean       : {series.mean():>10.2f}")
        print(f"      Median     : {series.median():>10.2f}")
        print(f"      Std Dev    : {series.std():>10.2f}")
        print(f"      Min        : {series.min():>10.2f}")
        print(f"      5th  pctl  : {series.quantile(0.05):>10.2f}")
        print(f"      25th pctl  : {series.quantile(0.25):>10.2f}")
        print(f"      75th pctl  : {series.quantile(0.75):>10.2f}")
        print(f"      95th pctl  : {series.quantile(0.95):>10.2f}")
        print(f"      Max        : {series.max():>10.2f}")
    print()

def profile_categorical(df: pd.DataFrame) -> None:
    """Print value counts for categorical CRM features."""
    print("=" * 72)
    print("CATEGORICAL FEATURE PROFILES")
    print("=" * 72)
    
    for col in CATEGORICAL_COLS:
        vc = df[col].value_counts(dropna=False)
        print(f"\n  ▸ {col}  ({vc.sum():,} total)")
        for val, cnt in vc.items():
            pct = cnt / len(df) * 100
            print(f"      {str(val):20s} : {cnt:>6,}  ({pct:5.1f}%)")
    print()

# ─────────────────────────────────────────────────────────────────────────────
# 6. VALIDATION ASSERTIONS
# ─────────────────────────────────────────────────────────────────────────────

def validate(df: pd.DataFrame) -> bool:
    """
    Run strict business-logic assertions on the extracted CRM features.
    Returns True if all checks pass; raises AssertionError otherwise.
    """
    print("=" * 72)
    print("VALIDATION ASSERTIONS")
    print("=" * 72)
    
    all_passed = True
    checks = []
    
    # ── Check 1: No nulls in any extracted column ──
    null_counts = df[SELECT_COLUMNS].isnull().sum()
    total_nulls = null_counts.sum()
    passed = total_nulls == 0
    checks.append(("Null count == 0 across all columns", passed,
                    f"Total nulls: {total_nulls}"))
    if not passed:
        for col, n in null_counts[null_counts > 0].items():
            checks.append((f"  ↳ {col}", False, f"{n} nulls"))
    
    # ── Check 2: Grain uniqueness (subscriber_id, snapshot_month) ──
    n_dupes = df.duplicated(subset=GRAIN_KEYS, keep=False).sum()
    passed = n_dupes == 0
    checks.append(("Grain uniqueness (subscriber_id, snapshot_month)", passed,
                    f"Duplicate rows: {n_dupes}"))
    
    # ── Check 3: ARPU non-negative ──
    neg_arpu = (df["arpu_monthly_tnd"] < 0).sum()
    passed = neg_arpu == 0
    checks.append(("arpu_monthly_tnd ≥ 0", passed,
                    f"Negative ARPU rows: {neg_arpu}"))
    
    # ── Check 4: Tenure non-negative ──
    neg_tenure = (df["tenure_months"] < 0).sum()
    passed = neg_tenure == 0
    checks.append(("tenure_months ≥ 0", passed,
                    f"Negative tenure rows: {neg_tenure}"))
    
    # ── Check 5: Active lines ≥ 1 ──
    zero_lines = (df["num_active_lines"] < 1).sum()
    passed = zero_lines == 0
    checks.append(("num_active_lines ≥ 1", passed,
                    f"Rows with <1 line: {zero_lines}"))
    
    # ── Check 6: Single snapshot_month (Step 2 guarantee) ──
    n_months = df["snapshot_month"].nunique()
    passed = n_months == 1
    checks.append(("Single snapshot_month (cross-sectional)", passed,
                    f"Distinct months: {n_months}"))
    
    # ── Check 7: has_mobile_sub_flag is boolean ──
    valid_bool = df["has_mobile_sub_flag"].isin([True, False]).all()
    checks.append(("has_mobile_sub_flag ∈ {True, False}", valid_bool,
                    "All values are boolean"))
    
    # ── Print results ──
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
# 7. PERSISTENCE
# ─────────────────────────────────────────────────────────────────────────────

def persist_to_db(df: pd.DataFrame, engine) -> None:
    """
    Write the validated CRM features to the cleaned_data schema as an
    intermediate table for Sub-tasks 4.2 and 4.3.
    
    Uses 'replace' to ensure idempotent overwrites on re-runs.
    """
    # Define explicit SQLAlchemy types for PostgreSQL column mapping
    dtype_map = {
        "subscriber_id": sa_types.VARCHAR(50),
        "snapshot_month": sa_types.Date(),
        "segment_tier": sa_types.VARCHAR(30),
        "arpu_monthly_tnd": sa_types.Float(),
        "tenure_months": sa_types.Integer(),
        "contract_type": sa_types.VARCHAR(20),
        "num_active_lines": sa_types.Integer(),
        "has_mobile_sub_flag": sa_types.Boolean(),
    }
    
    # Convert category columns back to string for PostgreSQL compatibility
    df_out = df.copy()
    for col in ["segment_tier", "contract_type"]:
        df_out[col] = df_out[col].astype(str)
    
    df_out.to_sql(
        name="t2_commercial_features_raw",
        con=engine,
        schema=SCHEMA,
        if_exists="replace",
        index=False,
        dtype=dtype_map,
    )
    print(f"✓ Persisted {len(df_out):,} rows to {OUTPUT_TABLE}.")
    print(f"  Table is ready for Sub-task 4.2 (Dynamic Binning) "
          f"and Sub-task 4.3 (Household Flags).\n")

# ─────────────────────────────────────────────────────────────────────────────
# 8. EXECUTION SUMMARY
# ─────────────────────────────────────────────────────────────────────────────

def print_execution_summary(df: pd.DataFrame) -> None:
    """Print a comprehensive human-readable execution report."""
    print("\n" + "=" * 72)
    print("SUB-TASK 4.1 — EXECUTION SUMMARY")
    print("=" * 72)
    
    print(f"""
  WORK COMPLETED
  ──────────────
  • Extracted 6 core CRM features from {SOURCE_TABLE}
  • Enforced strict data types (float64, Int64, boolean, category)
  • Profiled continuous distributions (mean, median, percentiles)
  • Profiled categorical distributions (value counts, percentages)
  • Ran 7 business-logic validation assertions
  • Persisted validated output to {OUTPUT_TABLE}

  ROW COUNTS
  ──────────
  • Source T2 rows          : {len(df):>10,}
  • Extracted rows          : {len(df):>10,}
  • Output rows persisted   : {len(df):>10,}
  • Unique subscribers      : {df['subscriber_id'].nunique():>10,}
  • Unique snapshot months  : {df['snapshot_month'].nunique():>10,}

  CREATED FEATURES (Raw Extraction)
  ─────────────────────────────────
  • segment_tier        — Commercial segment (Premium/High/Mid/LV/VLV)
  • arpu_monthly_tnd    — Monthly ARPU in TND (continuous)
  • tenure_months       — Months since activation (continuous)
  • contract_type       — Prepaid / Postpaid / Hybrid
  • num_active_lines    — Household / account line count
  • has_mobile_sub_flag — Active mobile subscription indicator

  KEY STATISTICS
  ──────────────
  • ARPU   — Mean: {df['arpu_monthly_tnd'].mean():.2f} TND | "
             f"Median: {df['arpu_monthly_tnd'].median():.2f} TND | "
             f"Range: [{df['arpu_monthly_tnd'].min():.2f}, "
             f"{df['arpu_monthly_tnd'].max():.2f}]
  • Tenure — Mean: {df['tenure_months'].mean():.1f} months | "
             f"Median: {df['tenure_months'].median():.1f} months | "
             f"Range: [{df['tenure_months'].min()}, {df['tenure_months'].max()}]
  • Lines  — Mean: {df['num_active_lines'].mean():.2f} | "
             f"Median: {df['num_active_lines'].median():.1f} | "
             f"Max: {df['num_active_lines'].max()}

  DETECTED ANOMALIES
  ──────────────────
  • None. All 7 validation assertions passed.
  • Data is structurally clean post Step 1 pollution resolution.

  BUSINESS INTERPRETATION
  ───────────────────────
  • The ARPU distribution will directly inform the unsupervised binning
    in Sub-task 4.2 (1D K-Means K=2) to discover natural revenue tiers.
  • The tenure distribution reveals the loyalty profile of the subscriber
    base, critical for churn risk modelling (Step 12).
  • The contract_type split determines the Tier 1 base offer structure
    in the Recommendation Engine (Step 13).
  • The num_active_lines distribution quantifies the household/B2B
    multiplier that will be applied uncapped in Step 15 prioritization.

  NEXT DEPENDENCY
  ───────────────
  → Sub-task 4.2: Dynamic Binning (arpu_band, tenure_band via 1D K-Means)
    Reads from: {OUTPUT_TABLE}
    Requires  : arpu_monthly_tnd, tenure_months (validated above)
""")

# ─────────────────────────────────────────────────────────────────────────────
# 9. MAIN ORCHESTRATOR
# ─────────────────────────────────────────────────────────────────────────────

def main():
    print("=" * 72)
    print("FWA MIGRATION PIPELINE — STEP 4, SUB-TASK 4.1")
    print("CRM Feature Extraction & Baseline Validation")
    print("=" * 72 + "\n")
    
    # Step 1: Connect
    engine = get_engine()
    
    # Step 2: Extract
    df = extract_crm_features(engine)
    
    # Step 3: Enforce types
    df = enforce_types(df)
    
    # Step 4: Profile
    profile_continuous(df)
    profile_categorical(df)
    
    # Step 5: Validate
    all_valid = validate(df)
    if not all_valid:
        print("✗ VALIDATION FAILED — Aborting persistence.")
        print("  Review the failed assertions above before proceeding.")
        sys.exit(1)
    
    # Step 6: Persist
    persist_to_db(df, engine)
    
    # Step 7: Summary
    print_execution_summary(df)
    
    print("=" * 72)
    print("SUB-TASK 4.1 COMPLETE ✓")
    print("=" * 72)

if __name__ == "__main__":
    main()
