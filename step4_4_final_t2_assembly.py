#!/usr/bin/env python3
"""
=============================================================================
FWA Migration Analytics Pipeline
Step 4 — CRM & Commercial Feature Preparation (T2)
Sub-task 4.4: Final T2 Commercial Table Assembly & Persistence
=============================================================================

Objective:
    Merge the modular intermediate tables (t2_commercial_features_binned and 
    t2_commercial_features_household) into a single, cohesive, and definitive 
    t2_commercial_features table. Enforce strict 1-row-per-subscriber grain, 
    validate referential integrity, and persist the final schema to PostgreSQL.

Source:      cleaned_data.t2_commercial_features_binned
             cleaned_data.t2_commercial_features_household
Output:      cleaned_data.t2_commercial_features
Grain:       1 row per subscriber_id per snapshot_month
Dependencies: Sub-tasks 4.1, 4.2, 4.3 — COMPLETED

Author:  FWA Analytics Pipeline
Date:    2026-07-18
=============================================================================
"""

import sys
import pandas as pd
from sqlalchemy import create_engine, text, types as sa_types

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
INPUT_BINNED_TABLE = f"{SCHEMA}.t2_commercial_features_binned"
INPUT_HOUSEHOLD_TABLE = f"{SCHEMA}.t2_commercial_features_household"
OUTPUT_TABLE = f"{SCHEMA}.t2_commercial_features"

# Expected final row count based on Step 1/2 baseline
EXPECTED_ROW_COUNT = 12412

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
# 3. EXTRACTION & MERGE (ETVL PATTERN)
# ─────────────────────────────────────────────────────────────────────────────

def extract_and_merge(engine: "sqlalchemy.engine.Engine") -> pd.DataFrame:
    """
    Extracts the binned features and the household flag, then performs a 
    strict 1:1 inner merge on the composite grain key.
    """
    print("=" * 72)
    print("EXTRACTION & MERGE")
    print("=" * 72)
    
    # 1. Extract Binned Features (Base T2 table)
    df_binned = pd.read_sql(f"SELECT * FROM {INPUT_BINNED_TABLE};", engine)
    print(f"✓ Extracted {len(df_binned):,} rows from {INPUT_BINNED_TABLE}.")
    
    # 2. Extract Household Features (Only need the new flag and grain keys)
    # We explicitly select only the flag to avoid duplicating 'num_active_lines'
    cols_household = "subscriber_id, snapshot_month, multi_line_flag"
    df_household = pd.read_sql(f"SELECT {cols_household} FROM {INPUT_HOUSEHOLD_TABLE};", engine)
    print(f"✓ Extracted {len(df_household):,} rows from {INPUT_HOUSEHOLD_TABLE}.")
    
    # 3. Perform 1:1 Inner Merge
    grain_keys = ["subscriber_id", "snapshot_month"]
    df_final = pd.merge(
        df_binned, 
        df_household, 
        on=grain_keys, 
        how="inner", 
        validate="1:1"  # Pandas built-in 1:1 merge validation
    )
    
    print(f"✓ Completed 1:1 Inner Merge on {grain_keys}.")
    print(f"  ↳ Final merged row count: {len(df_final):,}")
    print()
    
    return df_final

# ─────────────────────────────────────────────────────────────────────────────
# 4. PROGRAMMATIC VALIDATION
# ─────────────────────────────────────────────────────────────────────────────

def validate_assembly(df: pd.DataFrame) -> bool:
    """
    Runs strict referential integrity and schema assertions on the merged table.
    """
    print("=" * 72)
    print("REFERENTIAL INTEGRITY & SCHEMA VALIDATION")
    print("=" * 72)
    
    all_passed = True
    checks = []
    
    # Check 1: Exact Row Count (No fan-out, no data loss)
    passed = len(df) == EXPECTED_ROW_COUNT
    checks.append((f"Row count exactly matches baseline ({EXPECTED_ROW_COUNT:,})", 
                   passed, f"Actual: {len(df):,}"))
    
    # Check 2: Grain Uniqueness
    n_dupes = df.duplicated(subset=["subscriber_id", "snapshot_month"], keep=False).sum()
    passed = n_dupes == 0
    checks.append(("Grain uniqueness (subscriber_id, snapshot_month)", 
                   passed, f"Duplicate rows: {n_dupes}"))
    
    # Check 3: Zero Nulls in Critical Merged Columns
    critical_cols = ["multi_line_flag", "arpu_band", "tenure_band", "arpu_monthly_tnd"]
    nulls_in_critical = df[critical_cols].isnull().sum().sum()
    passed = nulls_in_critical == 0
    checks.append(("Zero nulls in critical commercial columns", 
                   passed, f"Total nulls in {critical_cols}: {nulls_in_critical}"))
    
    # Check 4: Verify all expected columns are present
    expected_cols = {
        "subscriber_id", "snapshot_month", "segment_tier", "arpu_monthly_tnd", 
        "tenure_months", "contract_type", "num_active_lines", "has_mobile_sub_flag", 
        "arpu_band", "tenure_band", "multi_line_flag"
    }
    missing_cols = expected_cols - set(df.columns)
    passed = len(missing_cols) == 0
    checks.append(("All expected T2 commercial columns present", 
                   passed, f"Missing: {missing_cols if missing_cols else 'None'}"))

    # Print Results
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
# 5. PERSISTENCE
# ─────────────────────────────────────────────────────────────────────────────

def persist_to_db(df: pd.DataFrame, engine: "sqlalchemy.engine.Engine") -> None:
    """Writes the final unified T2 table to the cleaned_data schema."""
    
    # Explicit SQLAlchemy type mapping for PostgreSQL
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
        "multi_line_flag": sa_types.Boolean(),
    }
    
    # Convert Pandas categories to strings for PostgreSQL compatibility
    df_out = df.copy()
    for col in ["segment_tier", "contract_type", "arpu_band", "tenure_band"]:
        if df_out[col].dtype.name == 'category':
            df_out[col] = df_out[col].astype(str)
            
    df_out.to_sql(
        name="t2_commercial_features",
        con=engine,
        schema=SCHEMA,
        if_exists="replace",
        index=False,
        dtype=dtype_map,
    )
    print(f"✓ Persisted {len(df_out):,} rows to {OUTPUT_TABLE}.\n")

# ─────────────────────────────────────────────────────────────────────────────
# 6. EXECUTION SUMMARY
# ─────────────────────────────────────────────────────────────────────────────

def print_execution_summary(df: pd.DataFrame) -> None:
    """Prints the final execution report for Step 4."""
    print("=" * 72)
    print("SUB-TASK 4.4 — EXECUTION SUMMARY")
    print("=" * 72)
    
    print(f"""
  WORK COMPLETED
  ──────────────
  • Extracted modular intermediate tables (binned + household)
  • Performed strict 1:1 Inner Merge on (subscriber_id, snapshot_month)
  • Ran 4 programmatic referential integrity and schema validations
  • Enforced explicit PostgreSQL data types (VARCHAR, DATE, FLOAT, INT, BOOLEAN)
  • Persisted final unified schema to {OUTPUT_TABLE}

  FINAL SCHEMA (cleaned_data.t2_commercial_features)
  ──────────────────────────────────────────────────
  • subscriber_id        (VARCHAR)   : Unique subscriber identifier
  • snapshot_month       (DATE)      : Cross-sectional snapshot date
  • segment_tier         (VARCHAR)   : Commercial segment (Premium/High/Mid/LV)
  • arpu_monthly_tnd     (FLOAT)     : Continuous monthly ARPU
  • arpu_band            (VARCHAR)   : GMM-derived ARPU tier (Low/High)
  • tenure_months        (INT)       : Continuous tenure in months
  • tenure_band          (VARCHAR)   : GMM-derived tenure tier (Short/Long)
  • contract_type        (VARCHAR)   : Prepaid / Postpaid / Hybrid
  • num_active_lines     (INT)       : Raw household/B2B line count
  • multi_line_flag      (BOOLEAN)   : Derived household indicator (>1 line)
  • has_mobile_sub_flag  (BOOLEAN)   : Active mobile subscription indicator

  VALIDATION RESULTS
  ──────────────────
  • Row Count           : {len(df):,} (Matches baseline exactly)
  • Grain Duplicates    : 0
  • Critical Nulls      : 0
  • Missing Columns     : 0
  • Status              : 100% REFERENTIALLY SOUND

  BUSINESS INTERPRETATION
  ───────────────────────
  • Step 4 is now COMPLETE. We have successfully transformed raw CRM data 
    into a mathematically rigorous, commercially enriched feature set.
  • The dynamic GMM binning ensures ARPU and Tenure thresholds are driven 
    by actual data density, not arbitrary business rules.
  • The long-tail analysis of 'num_active_lines' validates the uncapped 
    household multiplier strategy for Step 15.
  • This unified table is now the definitive "Anchor" for the Analytical 
    Base Table (ABT) construction in Step 8.

  NEXT DEPENDENCY
  ───────────────
  → STEP 8: Analytical Base Table (ABT) Construction
    Action    : LEFT JOIN T1 (Network) and T5 (Device) onto this final 
                T2 Commercial table to create the unified modeling dataset.
""")

# ─────────────────────────────────────────────────────────────────────────────
# 7. MAIN ORCHESTRATOR
# ─────────────────────────────────────────────────────────────────────────────

def main():
    print("=" * 72)
    print("FWA MIGRATION PIPELINE — STEP 4, SUB-TASK 4.4")
    print("Final T2 Commercial Table Assembly & Persistence")
    print("=" * 72 + "\n")
    
    engine = get_engine()
    
    # Extract and Merge
    df_final = extract_and_merge(engine)
    
    # Validate
    all_valid = validate_assembly(df_final)
    if not all_valid:
        print("✗ VALIDATION FAILED — Aborting persistence.")
        print("  The merge resulted in data loss, fan-out, or nulls.")
        sys.exit(1)
        
    # Persist
    persist_to_db(df_final, engine)
    
    # Summary
    print_execution_summary(df_final)
    
    print("=" * 72)
    print("SUB-TASK 4.4 COMPLETE ✓")
    print("STEP 4 (CRM & COMMERCIAL FEATURE PREPARATION) IS FULLY COMPLETE ✓")
    print("=" * 72)

if __name__ == "__main__":
    main()
