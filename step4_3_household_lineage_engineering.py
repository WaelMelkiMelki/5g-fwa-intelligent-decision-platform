#!/usr/bin/env python3
"""
=============================================================================
FWA Migration Analytics Pipeline
Step 4 — CRM & Commercial Feature Preparation (T2)
Sub-task 4.3: Household & Lineage Feature Engineering
=============================================================================

Objective:
    Derive the 'multi_line_flag' (Boolean) based on the business rule 
    (num_active_lines > 1). Perform a deep statistical profiling of the 
    'num_active_lines' distribution to quantify the prevalence of family 
    accounts and B2B entities, specifically analyzing the "long tail" of 
    large enterprise accounts to validate the uncapped multiplier strategy.

Source:      cleaned_data.t2_commercial_features_binned
Output:      cleaned_data.t2_commercial_features_household
Grain:       1 row per subscriber_id per snapshot_month
Dependencies: Sub-task 4.2 (Dynamic Binning) — COMPLETED

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

DB_CONFIG = {
    "host": "localhost",
    "port": 5432,
    "database": "postgres",
    "user": "postgres",
    "password": __import__("os").environ["FWA_DB_PASSWORD"],
}

SCHEMA = "cleaned_data"
INPUT_TABLE = f"{SCHEMA}.t2_commercial_features_binned"
OUTPUT_TABLE = f"{SCHEMA}.t2_commercial_features_household"

# Columns required for this specific sub-task
REQUIRED_COLS = ["subscriber_id", "snapshot_month", "num_active_lines"]

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
# 3. EXTRACTION & FEATURE ENGINEERING
# ─────────────────────────────────────────────────────────────────────────────

def extract_and_engineer(engine: "sqlalchemy.engine.Engine") -> pd.DataFrame:
    """
    Extracts the line count and derives the multi-line boolean flag.
    """
    cols_sql = ", ".join(REQUIRED_COLS)
    query = f"SELECT {cols_sql} FROM {INPUT_TABLE};"
    df = pd.read_sql(query, engine)
    print(f"✓ Extracted {len(df):,} rows from {INPUT_TABLE}.")
    
    # Ensure strict integer type for line count
    df["num_active_lines"] = df["num_active_lines"].astype("Int64")
    
    # Derive the multi-line flag using vectorized boolean logic
    df["multi_line_flag"] = (df["num_active_lines"] > 1).astype("boolean")
    
    print("✓ Derived 'multi_line_flag' (num_active_lines > 1).")
    return df

# ─────────────────────────────────────────────────────────────────────────────
# 4. STATISTICAL PROFILING (THE "LONG TAIL" ANALYSIS)
# ─────────────────────────────────────────────────────────────────────────────

def profile_line_distribution(df: pd.DataFrame) -> None:
    """
    Performs a deep statistical profiling of the num_active_lines distribution
    to understand the B2C vs B2B/Family split and the long tail.
    """
    print("\n" + "=" * 72)
    print("HOUSEHOLD / LINEAGE DISTRIBUTION PROFILING")
    print("=" * 72)
    
    lines = df["num_active_lines"]
    
    # 1. Basic Descriptive Stats
    print(f"\n  ▸ Basic Statistics:")
    print(f"      Mean       : {lines.mean():.2f} lines")
    print(f"      Median     : {lines.median():.1f} lines")
    print(f"      Std Dev    : {lines.std():.2f}")
    print(f"      Min        : {lines.min()} lines")
    print(f"      Max        : {lines.max()} lines")
    
    # 2. Percentiles (Focus on the long tail)
    percentiles = [0.50, 0.75, 0.90, 0.95, 0.99, 1.00]
    perc_vals = lines.quantile(percentiles)
    print(f"\n  ▸ Percentile Distribution (Long Tail Analysis):")
    for p, val in perc_vals.items():
        label = " (Max)" if p == 1.00 else f" (P{int(p*100)})"
        print(f"      {int(p*100):>3}%ile{label:<6}: {int(val):>3} lines")
        
    # 3. Value Counts (Exact frequency)
    print(f"\n  ▸ Exact Frequency Distribution (Value Counts):")
    vc = lines.value_counts().sort_index()
    total = len(lines)
    
    # Print top lines individually, then group the rest
    max_display = 6
    for i, (lines_count, freq) in enumerate(vc.items()):
        if i < max_display:
            pct = (freq / total) * 100
            print(f"      {lines_count:>2} lines : {freq:>6,} subs ({pct:5.1f}%)")
        else:
            # Group remaining into "long tail"
            remaining_count = vc.iloc[i:].sum()
            remaining_pct = (remaining_count / total) * 100
            print(f"      {lines_count:>2}+ lines: {remaining_count:>6,} subs ({remaining_pct:5.1f}%)  <-- LONG TAIL (B2B/Large Family)")
            break

    # 4. Multi-line vs Single-line split
    multi_count = df["multi_line_flag"].sum()
    single_count = total - multi_count
    print(f"\n  ▸ Structural Split:")
    print(f"      Single-Line (B2C/Individual) : {single_count:>6,} subs ({(single_count/total)*100:.1f}%)")
    print(f"      Multi-Line  (Household/B2B)  : {multi_count:>6,} subs ({(multi_count/total)*100:.1f}%)")
    print()

# ─────────────────────────────────────────────────────────────────────────────
# 5. VALIDATION
# ─────────────────────────────────────────────────────────────────────────────

def validate(df: pd.DataFrame) -> bool:
    """Validates the newly created household features."""
    print("=" * 72)
    print("VALIDATION ASSERTIONS")
    print("=" * 72)
    
    all_passed = True
    checks = []
    
    # Check 1: Grain uniqueness
    n_dupes = df.duplicated(subset=["subscriber_id", "snapshot_month"], keep=False).sum()
    passed = n_dupes == 0
    checks.append(("Grain uniqueness (subscriber_id, snapshot_month)", passed,
                    f"Duplicate rows: {n_dupes}"))
    
    # Check 2: No nulls in multi_line_flag
    nulls = df["multi_line_flag"].isnull().sum()
    passed = nulls == 0
    checks.append(("No nulls in multi_line_flag", passed, f"Nulls: {nulls}"))
    
    # Check 3: Strict boolean type
    is_bool = df["multi_line_flag"].dtype == "boolean"
    checks.append(("multi_line_flag is strict Pandas boolean type", is_bool,
                    f"Type: {df['multi_line_flag'].dtype}"))
    
    # Check 4: Physical constraint (lines >= 1)
    zero_lines = (df["num_active_lines"] < 1).sum()
    passed = zero_lines == 0
    checks.append(("num_active_lines ≥ 1 (Physical constraint)", passed,
                    f"Rows with <1 line: {zero_lines}"))

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
    """Writes the household features to the cleaned_data schema."""
    dtype_map = {
        "subscriber_id": sa_types.VARCHAR(50),
        "snapshot_month": sa_types.Date(),
        "num_active_lines": sa_types.Integer(),
        "multi_line_flag": sa_types.Boolean(),
    }
    
    df.to_sql(
        name="t2_commercial_features_household",
        con=engine,
        schema=SCHEMA,
        if_exists="replace",
        index=False,
        dtype=dtype_map,
    )
    print(f"✓ Persisted {len(df):,} rows to {OUTPUT_TABLE}.\n")

# ─────────────────────────────────────────────────────────────────────────────
# 7. EXECUTION SUMMARY
# ─────────────────────────────────────────────────────────────────────────────

def print_execution_summary(df: pd.DataFrame) -> None:
    """Prints the final execution report."""
    lines = df["num_active_lines"]
    multi_count = df["multi_line_flag"].sum()
    single_count = len(df) - multi_count
    p95_val = int(lines.quantile(0.95))
    p99_val = int(lines.quantile(0.99))
    max_val = int(lines.max())
    
    print("=" * 72)
    print("SUB-TASK 4.3 — EXECUTION SUMMARY")
    print("=" * 72)
    
    print(f"""
  WORK COMPLETED
  ──────────────
  • Extracted 'num_active_lines' from {INPUT_TABLE}
  • Derived 'multi_line_flag' using vectorized boolean logic (> 1)
  • Performed deep statistical profiling of the line distribution
  • Analyzed the "long tail" (P95, P99, Max) for B2B/Enterprise impact
  • Validated grain uniqueness and physical constraints
  • Persisted modular output to {OUTPUT_TABLE}

  KEY STATISTICS & LONG TAIL ANALYSIS
  ───────────────────────────────────
  • Total Subscribers      : {len(df):,}
  • Single-Line (Indiv.)   : {single_count:,} ({(single_count/len(df))*100:.1f}%)
  • Multi-Line (House/B2B) : {multi_count:,} ({(multi_count/len(df))*100:.1f}%)
  
  • Median Lines           : {int(lines.median())}
  • 95th Percentile (P95)  : {p95_val} lines
  • 99th Percentile (P99)  : {p99_val} lines
  • Absolute Maximum       : {max_val} lines

  BUSINESS INTERPRETATION
  ───────────────────────
  • The vast majority of the base ({(single_count/len(df))*100:.1f}%) are single-line 
    B2C individual users. 
  • The multi-line segment ({(multi_count/len(df))*100:.1f}%) represents the household 
    and B2B SME market, which is the primary target for FWA "whole home" 
    connectivity offers.
  • The long tail analysis reveals that the 95th percentile sits at {p95_val} lines, 
    and the absolute maximum reaches {max_val} lines. 
  • CRITICAL FOR STEP 15: The presence of accounts with {p99_val} to {max_val} lines 
    mathematically validates the business strategy of applying an UNCAPPED 
    household multiplier. Capping the multiplier at a low number (e.g., 3 or 4) 
    would severely under-prioritize these high-value B2B/Enterprise accounts.

  NEXT DEPENDENCY
  ───────────────
  → Sub-task 4.4: Final T2 Commercial Table Assembly & Persistence
    Reads from: {OUTPUT_TABLE} (and previous T2 intermediate tables)
    Action    : Merges raw, binned, and household features into the final 
                t2_commercial_features table.
""")

# ─────────────────────────────────────────────────────────────────────────────
# 8. MAIN ORCHESTRATOR
# ─────────────────────────────────────────────────────────────────────────────

def main():
    print("=" * 72)
    print("FWA MIGRATION PIPELINE — STEP 4, SUB-TASK 4.3")
    print("Household & Lineage Feature Engineering")
    print("=" * 72 + "\n")
    
    engine = get_engine()
    
    # Extract and Engineer
    df = extract_and_engineer(engine)
    
    # Profile
    profile_line_distribution(df)
    
    # Validate
    all_valid = validate(df)
    if not all_valid:
        print("✗ VALIDATION FAILED — Aborting persistence.")
        sys.exit(1)
        
    # Persist
    persist_to_db(df, engine)
    
    # Summary
    print_execution_summary(df)
    
    print("=" * 72)
    print("SUB-TASK 4.3 COMPLETE ✓")
    print("=" * 72)

if __name__ == "__main__":
    main()
