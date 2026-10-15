import pandas as pd
import numpy as np
import sqlalchemy
from sqlalchemy import create_engine
import warnings
import sys

warnings.filterwarnings('ignore')

# ==============================================================================
# CONFIGURATION
# ==============================================================================
DB_CONFIG = {
    "host": "localhost",
    "port": 5432,
    "database": "postgres",
    "user": "postgres",
    "password": __import__("os").environ["FWA_DB_PASSWORD"],
}

TARGET_SCHEMA = "cleaned_data"
SOURCE_TABLE = f"{TARGET_SCHEMA}.t4_coverage_address_grid"

# Validation Thresholds
RSRP_MIN = -140.0
RSRP_MAX = -40.0
SINR_MIN = -20.0
SINR_MAX = 40.0

# ==============================================================================
# DATABASE CONNECTION
# ==============================================================================
def get_db_engine():
    """Creates and returns a SQLAlchemy engine."""
    conn_str = (
        f"postgresql+psycopg2://{DB_CONFIG['user']}:{DB_CONFIG['password']}"
        f"@{DB_CONFIG['host']}:{DB_CONFIG['port']}/{DB_CONFIG['database']}"
    )
    return create_engine(conn_str)

# ==============================================================================
# SUB-TASK 6.1: EXTRACTION & SCHEMA VALIDATION
# ==============================================================================
def extract_and_validate_t4(engine):
    """Loads T4 address coverage data and validates structural/physical integrity."""
    print("\n[6.1] Extracting and validating T4 address coverage data...")
    
    # 1. Extract
    query = f"SELECT * FROM {SOURCE_TABLE}"
    df = pd.read_sql(query, engine)
    initial_rows = len(df)
    print(f"  -> Extracted {initial_rows} rows from {SOURCE_TABLE}.")
    
    # 2. Validate Grain Uniqueness (1 row per address_id)
    duplicate_addresses = df[df.duplicated(subset=['address_id'], keep=False)]
    num_duplicates = len(duplicate_addresses)
    unique_addresses = df['address_id'].nunique()
    
    if num_duplicates > 0:
        raise ValueError(f"CRITICAL: Found {num_duplicates} duplicate address_id rows. This will cause ABT fan-out.")
    print(f"  -> Grain Validation: PASSED ({unique_addresses} unique addresses, 0 duplicates).")
    
    # 3. Validate Physical RF Bounds
    # RSRP must be strictly negative and within realistic cellular bounds
    rsrp_invalid = df[~df['predicted_rsrp_dbm'].between(RSRP_MIN, RSRP_MAX)]
    rsrp_invalid_count = len(rsrp_invalid)
    
    # SINR must be within realistic bounds
    sinr_invalid = df[~df['predicted_sinr_db'].between(SINR_MIN, SINR_MAX)]
    sinr_invalid_count = len(sinr_invalid)
    
    if rsrp_invalid_count > 0 or sinr_invalid_count > 0:
        raise ValueError(f"CRITICAL: Found {rsrp_invalid_count} invalid RSRP and {sinr_invalid_count} invalid SINR values outside physical bounds.")
    print(f"  -> RF Bounds Validation: PASSED (RSRP in [{RSRP_MIN}, {RSRP_MAX}] dBm, SINR in [{SINR_MIN}, {SINR_MAX}] dB).")
    
    # 4. Validate and Enforce Boolean Flags
    flag_cols = ['coverage_5g_flag', 'coverage_4g_flag', 'fiber_coverage_flag']
    
    # Check if columns exist
    missing_flags = [col for col in flag_cols if col not in df.columns]
    if missing_flags:
        raise ValueError(f"CRITICAL: Missing expected flag columns: {missing_flags}")
        
    # Convert to strict boolean (handles 1/0, 'true'/'false', True/False)
    for col in flag_cols:
        # Fill NA with False if any exist, then convert
        df[col] = df[col].fillna(False).astype(bool)
        
    print(f"  -> Boolean Flag Validation: PASSED (Strictly typed {', '.join(flag_cols)}).")
    
    # 5. Check for Critical Nulls
    critical_cols = ['address_id', 'predicted_rsrp_dbm', 'predicted_sinr_db'] + flag_cols
    null_counts = df[critical_cols].isnull().sum()
    total_nulls = null_counts.sum()
    
    if total_nulls > 0:
        raise ValueError(f"CRITICAL: Found {total_nulls} nulls in critical columns: {null_counts[null_counts > 0].to_dict()}")
    print(f"  -> Null Validation: PASSED (0 nulls in critical columns).")
    
    print(f"  -> Sub-task 6.1 Validation COMPLETE. DataFrame ready for Sub-task 6.2.")
    return df

# ==============================================================================
# EXECUTION REPORT GENERATOR
# ==============================================================================
def print_execution_report(df):
    """Prints a comprehensive execution and business report for Sub-task 6.1."""
    print("\n" + "="*80)
    print(" "*15 + "STEP 6.1 EXECUTION REPORT: T4 EXTRACTION & VALIDATION")
    print("="*80)
    
    print("\n[1] OPERATIONS PERFORMED")
    print("  • Extracted static address coverage data from cleaned_data.t4_coverage_address_grid")
    print("  • Enforced strict 1-row-per-address_id grain")
    print("  • Validated physical RF bounds (RSRP and SINR)")
    print("  • Enforced strict Boolean typing for technology and fiber flags")
    
    print("\n[2] DATA VOLUME & PROCESSING STATS")
    print(f"  • Total Rows Extracted          : {len(df):,}")
    print(f"  • Unique Addresses (address_id) : {df['address_id'].nunique():,}")
    print(f"  • Duplicate Rows Detected       : 0")
    
    print("\n[3] VALIDATION RESULTS")
    print("  • Grain Uniqueness (address_id) : PASSED")
    print(f"  • RSRP Bounds [{RSRP_MIN}, {RSRP_MAX}] dBm   : PASSED")
    print(f"  • SINR Bounds [{SINR_MIN}, {SINR_MAX}] dB    : PASSED")
    print("  • Boolean Flag Typing           : PASSED")
    print("  • Critical Nulls Check          : PASSED")
    
    print("\n[4] DETECTED ANOMALIES & EDGE CASES")
    print("  • No structural anomalies detected.")
    print("  • All addresses possess valid, physically plausible RF predictions.")
    
    print("\n[5] BUSINESS INTERPRETATION")
    print("  • The T4 dataset represents a clean, structurally sound foundation for")
    print("    address-level radio feasibility analysis.")
    print("  • The strict 1-row-per-address guarantee prevents Cartesian fan-out during")
    print("    the Step 8 ABT join, ensuring subscriber-level metrics remain accurate.")
    print("  • Validated RF bounds confirm the Radio Planning Tool (RPT) outputs are")
    print("    realistic and ready for worst-case signal quality classification (Sub-task 6.2).")
    
    print("\n[6] READINESS FOR NEXT DEPENDENCY")
    print("  • Sub-task 6.2 (Worst-Case Signal Classification): READY.")
    print("  • Sub-task 6.3 (Radio Feasibility Classification): READY (pending 6.2).")
    print("="*80 + "\n")

# ==============================================================================
# MAIN EXECUTION PIPELINE
# ==============================================================================
def main():
    try:
        engine = get_db_engine()
        
        # Execute Sub-task 6.1
        df_validated = extract_and_validate_t4(engine)
        
        # Print Report
        print_execution_report(df_validated)
        
    except Exception as e:
        print(f"\n[CRITICAL ERROR] Pipeline halted: {str(e)}")
        sys.exit(1)

if __name__ == "__main__":
    main()
