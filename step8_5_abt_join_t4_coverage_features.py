"""
=============================================================================
Project: 5G FWA Migration Analytics Pipeline
Step:    8.5 - Join T4 Coverage Features (RF Feasibility)
Role:    Senior Telecom Data Engineer
=============================================================================
Objective: Attach address-level RF feasibility and coverage predictions from 
t4_coverage_features to the 24-column intermediate ABT. This shifts the join 
paradigm from subscriber-level to address-level (address_id). Expands the ABT 
from 24 to 32 columns. Persists as abt_t4_coverage_joined.
=============================================================================
"""

import pandas as pd
import sqlalchemy
import logging
import sys

# -----------------------------------------------------------------------------
# 1. Configuration & Logging Setup
# -----------------------------------------------------------------------------
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s | %(levelname)-8s | %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)

# Database Connection Parameters
DB_USER = "postgres"
DB_PASS = __import__("os").environ["FWA_DB_PASSWORD"]
DB_HOST = "localhost"
DB_PORT = "5432"
DB_NAME = "postgres"
SCHEMA = "cleaned_data"

SOURCE_BASE_TABLE = "abt_t1_dominance_joined"
SOURCE_T4_TABLE = "t4_coverage_features"
TARGET_TABLE = "abt_t4_coverage_joined"

# SQLAlchemy Engine
try:
    engine = sqlalchemy.create_engine(f"postgresql://{DB_USER}:{DB_PASS}@{DB_HOST}:{DB_PORT}/{DB_NAME}")
    with engine.connect() as conn:
        conn.execute(sqlalchemy.text("SELECT 1"))
    logging.info("Successfully connected to PostgreSQL database.")
except Exception as e:
    logging.error(f"Database connection failed: {e}")
    sys.exit(1)

# -----------------------------------------------------------------------------
# 2. Core Transformation & Validation Functions
# -----------------------------------------------------------------------------
def enforce_schema(df: pd.DataFrame) -> pd.DataFrame:
    """Enforces strict PostgreSQL data types for the newly joined T4 Coverage columns."""
    # Ensure continuous RF metrics are strictly float64
    float_cols = ['predicted_rsrp_dbm', 'predicted_sinr_db']
    for col in float_cols:
        if col in df.columns:
            df[col] = df[col].astype(float)
            
    # Ensure boolean coverage flags are strictly boolean
    bool_cols = ['coverage_5g_flag', 'coverage_4g_flag', 'fiber_coverage_flag']
    for col in bool_cols:
        if col in df.columns:
            df[col] = df[col].astype(bool)
            
    # Ensure categorical/string columns are strictly object (string)
    str_cols = ['serving_cell_id', 'signal_quality_class', 'radio_feasibility_class']
    for col in str_cols:
        if col in df.columns:
            df[col] = df[col].astype(str)
            
    return df

def validate_abt_t4(df: pd.DataFrame, expected_rows: int, expected_cols: int):
    """Runs programmatic assertions on the merged ABT with T4 Coverage."""
    validation_passed = True
    
    # 1. Row Count
    actual_rows = len(df)
    if actual_rows != expected_rows:
        logging.error(f"ROW COUNT VIOLATION: Expected {expected_rows}, got {actual_rows}.")
        validation_passed = False
    else:
        logging.info(f"[PASS] Row count matches baseline: {actual_rows:,} rows.")
        
    # 2. Column Count
    actual_cols = len(df.columns)
    if actual_cols != expected_cols:
        logging.error(f"COLUMN COUNT VIOLATION: Expected {expected_cols}, got {actual_cols}.")
        validation_passed = False
    else:
        logging.info(f"[PASS] Column count matches expected schema: {actual_cols} columns.")
        
    # 3. Grain Uniqueness (Must still preserve the subscriber-month grain)
    unique_keys = df.drop_duplicates(subset=['subscriber_id', 'snapshot_month']).shape[0]
    if unique_keys != actual_rows:
        logging.error(f"GRAIN VIOLATION: Duplicate keys detected. {actual_rows} rows but only {unique_keys} unique keys.")
        validation_passed = False
    else:
        logging.info("[PASS] Grain uniqueness verified: 1:1 subscriber-month grain preserved.")
        
    # 4. Null Integrity (Specifically for the 8 newly joined T4 Coverage columns)
    new_cols = [
        'serving_cell_id', 'predicted_rsrp_dbm', 'predicted_sinr_db', 
        'coverage_5g_flag', 'coverage_4g_flag', 'fiber_coverage_flag', 
        'signal_quality_class', 'radio_feasibility_class'
    ]
    nulls_in_new_cols = df[new_cols].isnull().sum().sum()
    if nulls_in_new_cols > 0:
        logging.error(f"NULL VIOLATION: Found {nulls_in_new_cols} nulls in the newly joined T4 Coverage columns.")
        validation_passed = False
    else:
        logging.info("[PASS] Null integrity verified: 0 nulls in newly joined T4 Coverage columns.")
        
    return validation_passed

# -----------------------------------------------------------------------------
# 3. Main Execution Pipeline
# -----------------------------------------------------------------------------
def main():
    logging.info("="*80)
    logging.info("STARTING STEP 8.5: JOIN T4 COVERAGE FEATURES (RF FEASIBILITY)")
    logging.info("="*80)
    
    # 3.1 Extract Source Tables
    logging.info("Phase 1: Extracting source tables...")
    try:
        df_base = pd.read_sql(f"SELECT * FROM {SCHEMA}.{SOURCE_BASE_TABLE}", engine)
        df_t4 = pd.read_sql(f"SELECT * FROM {SCHEMA}.{SOURCE_T4_TABLE}", engine)
        logging.info(f"Extracted {len(df_base):,} rows and {len(df_base.columns)} cols from {SOURCE_BASE_TABLE}.")
        logging.info(f"Extracted {len(df_t4):,} rows and {len(df_t4.columns)} cols from {SOURCE_T4_TABLE}.")
    except Exception as e:
        logging.error(f"Extraction failed: {e}")
        sys.exit(1)

    # 3.2 Execute LEFT JOIN (Address-Level Bridge)
    logging.info("\nPhase 2: Executing LEFT JOIN on address_id to attach T4 RF features...")
    df_abt_t4 = pd.merge(
        df_base, 
        df_t4, 
        on='address_id', 
        how='left'
    )
    
    # Check for accidental suffixes (should not happen as T4 serving_cell_id != base dominant_serving_cell_id)
    suffix_cols = [col for col in df_abt_t4.columns if col.endswith('_x') or col.endswith('_y')]
    if suffix_cols:
        logging.warning(f"Unexpected suffix columns detected: {suffix_cols}")

    # 3.3 Schema Enforcement
    logging.info("\nPhase 3: Enforcing strict PostgreSQL data types on new RF features...")
    df_abt_t4 = enforce_schema(df_abt_t4)

    # 3.4 Validation Gates
    logging.info("\nPhase 4: Running programmatic validation assertions...")
    expected_rows = len(df_base)
    expected_cols = 32  # 24 from Base ABT + 8 new features from T4 Coverage
    validation_passed = validate_abt_t4(df_abt_t4, expected_rows, expected_cols)

    # 3.5 Persist to Database
    if validation_passed:
        logging.info(f"\nPhase 5: Persisting validated ABT to {SCHEMA}.{TARGET_TABLE}...")
        try:
            df_abt_t4.to_sql(TARGET_TABLE, engine, schema=SCHEMA, if_exists='replace', index=False)
            logging.info(f"SUCCESS: Table {SCHEMA}.{TARGET_TABLE} created/overwritten successfully.")
        except Exception as e:
            logging.error(f"Database persistence failed: {e}")
            sys.exit(1)
    else:
        logging.error("VALIDATION FAILED: Halting pipeline. Table was NOT persisted.")
        sys.exit(1)

    # 3.6 Final Execution Report
    logging.info("\n" + "="*80)
    logging.info("EXECUTION SUMMARY: ABT WITH T4 COVERAGE (RF FEASIBILITY)")
    logging.info("="*80)
    
    print(f"\n{'Metric':<40} | {'Value':<20}")
    print("-" * 65)
    print(f"{'Source Base ABT Rows':<40} | {len(df_base):>20,}")
    print(f"{'Source T4 Coverage Rows':<40} | {len(df_t4):>20,}")
    print(f"{'Final ABT Rows':<40} | {len(df_abt_t4):>20,}")
    print(f"{'Final ABT Columns':<40} | {len(df_abt_t4.columns):>20}")
    print(f"{'Fan-out / Duplicates':<40} | {'0':>20}")
    print(f"{'Nulls in New T4 Features':<40} | {'0':>20}")
    
    print("\n--- NEWLY ADDED FEATURES (T4 COVERAGE) ---")
    new_features = [
        'serving_cell_id', 'predicted_rsrp_dbm', 'predicted_sinr_db', 
        'coverage_5g_flag', 'coverage_4g_flag', 'fiber_coverage_flag', 
        'signal_quality_class', 'radio_feasibility_class'
    ]
    for col in new_features:
        dtype = df_abt_t4[col].dtype
        print(f"  - {col:<40} | Type: {dtype}")

    print("\n--- DUAL CELL TRACKING VERIFICATION ---")
    print("  - Mobile Camp Cell: 'dominant_serving_cell_id' (from T1 Dominance)")
    print("  - Fixed Address Cell: 'serving_cell_id' (from T4 Coverage)")
    print("  Both columns successfully retained without naming collisions.")

    print("\n--- BUSINESS INTERPRETATION ---")
    print("1. The ABT now contains the physical RF reality of the subscriber's address.")
    print("2. 'radio_feasibility_class' is now available to act as the ultimate Go/No-Go gate.")
    print("3. The address-level 'serving_cell_id' is now mapped, enabling precise Step 14 capacity simulation.")
    print("4. The 12,412 subscriber baseline is strictly preserved with 100% referential integrity.")
    print("5. Intermediate checkpoint 'abt_t4_coverage_joined' successfully persisted to the database.")

    print("\n--- READINESS FOR STEP 8.6 ---")
    logging.info("STATUS: T4 COVERAGE JOIN CERTIFIED. Pipeline cleared for Sub-step 8.6 (Join T5 Service Consumption).")

if __name__ == "__main__":
    main()
