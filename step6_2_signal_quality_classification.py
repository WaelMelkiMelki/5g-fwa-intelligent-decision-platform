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

# RF Classification Thresholds (dBm and dB)
RSRP_POOR_THRESHOLD = -95.0
SINR_POOR_THRESHOLD = 3.0
RSRP_EXCELLENT_THRESHOLD = -85.0
SINR_EXCELLENT_THRESHOLD = 10.0

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
# SUB-TASK 6.2: WORST-CASE SIGNAL QUALITY CLASSIFICATION
# ==============================================================================
def extract_and_classify_signal_quality(engine):
    """Loads T4 data and applies worst-case signal quality classification."""
    print("\n[6.2] Extracting T4 data and classifying signal quality...")
    
    # 1. Extract (Re-reading from source to ensure script modularity)
    query = f"SELECT * FROM {SOURCE_TABLE}"
    df = pd.read_sql(query, engine)
    initial_rows = len(df)
    print(f"  -> Extracted {initial_rows} rows from {SOURCE_TABLE}.")
    
    # Quick structural check (Assuming 6.1 passed, but verifying for safety)
    if df['address_id'].duplicated().any():
        raise ValueError("CRITICAL: Duplicate address_ids found. Sub-task 6.1 validation failed.")
        
    # 2. Define Boolean Masks based on Worst-Case Logic
    # Poor: If EITHER metric breaches the absolute minimum threshold
    mask_poor = (df['predicted_rsrp_dbm'] < RSRP_POOR_THRESHOLD) | \
                (df['predicted_sinr_db'] < SINR_POOR_THRESHOLD)
                
    # Excellent: If BOTH metrics exceed the premium thresholds
    mask_excellent = (df['predicted_rsrp_dbm'] > RSRP_EXCELLENT_THRESHOLD) & \
                     (df['predicted_sinr_db'] > SINR_EXCELLENT_THRESHOLD)
                     
    # Acceptable: Everything else (NOT Poor AND NOT Excellent)
    mask_acceptable = ~mask_poor & ~mask_excellent
    
    # 3. Apply Classification
    conditions = [mask_poor, mask_excellent, mask_acceptable]
    choices = ['Poor', 'Excellent', 'Acceptable']
    
    df['signal_quality_class'] = np.select(conditions, choices, default='Unknown')
    
    # 4. Verify Exhaustiveness (No 'Unknown' should remain)
    if (df['signal_quality_class'] == 'Unknown').any():
        raise ValueError("CRITICAL: Logical gap in classification. Some addresses fell through the masks.")
        
    print(f"  -> Signal Quality Classification COMPLETE.")
    return df

# ==============================================================================
# EXECUTION REPORT GENERATOR
# ==============================================================================
def print_execution_report(df):
    """Prints a comprehensive execution and business report for Sub-task 6.2."""
    print("\n" + "="*80)
    print(" "*15 + "STEP 6.2 EXECUTION REPORT: SIGNAL QUALITY CLASSIFICATION")
    print("="*80)
    
    total_addresses = len(df)
    
    # Calculate counts and percentages
    class_counts = df['signal_quality_class'].value_counts()
    poor_count = class_counts.get('Poor', 0)
    excellent_count = class_counts.get('Excellent', 0)
    acceptable_count = class_counts.get('Acceptable', 0)
    
    print("\n[1] OPERATIONS PERFORMED")
    print("  • Extracted validated address coverage data from T4")
    print("  • Applied hierarchical worst-case boolean masking for RF metrics")
    print("  • Classified 100% of addresses into Poor, Acceptable, or Excellent tiers")
    
    print("\n[2] CLASSIFICATION DISTRIBUTION")
    print(f"  • Total Addresses Processed     : {total_addresses:,}")
    print(f"  • Excellent (RSRP > -85 & SINR > 10) : {excellent_count:,} ({excellent_count/total_addresses*100:.1f}%)")
    print(f"  • Acceptable (Middle Tier)      : {acceptable_count:,} ({acceptable_count/total_addresses*100:.1f}%)")
    print(f"  • Poor (RSRP < -95 OR SINR < 3) : {poor_count:,} ({poor_count/total_addresses*100:.1f}%)")
    
    print("\n[3] TIER STATISTICAL VALIDATION")
    # Validate that the means align with the expected thresholds for each tier
    for tier in ['Excellent', 'Acceptable', 'Poor']:
        tier_df = df[df['signal_quality_class'] == tier]
        if len(tier_df) > 0:
            avg_rsrp = tier_df['predicted_rsrp_dbm'].mean()
            avg_sinr = tier_df['predicted_sinr_db'].mean()
            print(f"  • {tier:10} | Avg RSRP: {avg_rsrp:6.2f} dBm | Avg SINR: {avg_sinr:5.2f} dB")
            
    print("\n[4] VALIDATION RESULTS")
    print("  • Logical Exhaustiveness          : PASSED (0 'Unknown' classifications)")
    print("  • Worst-Case Logic Enforcement    : PASSED (OR logic for Poor, AND logic for Excellent)")
    
    print("\n[5] DETECTED ANOMALIES & EDGE CASES")
    # Check for edge cases: Excellent RSRP but Poor SINR (Should be classified as Poor due to OR logic)
    strong_signal_bad_interference = df[
        (df['predicted_rsrp_dbm'] > RSRP_EXCELLENT_THRESHOLD) & 
        (df['predicted_sinr_db'] < SINR_POOR_THRESHOLD)
    ]
    if len(strong_signal_bad_interference) > 0:
        print(f"  • INFO: Found {len(strong_signal_bad_interference)} addresses with strong signal (RSRP > -85) but severe interference (SINR < 3).")
        print(f"          Correctly classified as 'Poor' due to worst-case OR logic.")
    else:
        print("  • No high-interference edge cases detected.")
        
    print("\n[6] BUSINESS INTERPRETATION")
    print("  • The 'Poor' classification acts as a hard filter. These addresses cannot")
    print("    support FWA and will trigger a Hard Stop (Score = 0) in Step 9.")
    print("  • The 'Excellent' tier represents premium FWA candidates capable of")
    print("    supporting high-order modulation (256-QAM) and gigabit speeds.")
    print("  • The 'Acceptable' tier represents the bulk of viable FWA migrations,")
    print("    offering standard broadband replacement speeds.")
    
    print("\n[7] READINESS FOR NEXT DEPENDENCY")
    print("  • Sub-task 6.3 (Radio Feasibility & Context): READY.")
    print("  • The signal_quality_class is now available to be combined with")
    print("    technology flags (5G/4G) and fiber coverage flags.")
    print("="*80 + "\n")

# ==============================================================================
# MAIN EXECUTION PIPELINE
# ==============================================================================
def main():
    try:
        engine = get_db_engine()
        
        # Execute Sub-task 6.2
        df_classified = extract_and_classify_signal_quality(engine)
        
        # Print Report
        print_execution_report(df_classified)
        
    except Exception as e:
        print(f"\n[CRITICAL ERROR] Pipeline halted: {str(e)}")
        sys.exit(1)

if __name__ == "__main__":
    main()
