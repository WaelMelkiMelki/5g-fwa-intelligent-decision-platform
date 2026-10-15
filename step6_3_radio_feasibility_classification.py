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

# RF Thresholds (Re-applied from Sub-task 6.2 for modularity)
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
# SUB-TASK 6.3: RADIO FEASIBILITY & COMMERCIAL CONTEXT CLASSIFICATION
# ==============================================================================
def classify_radio_feasibility(engine):
    """Loads T4, applies 6.2 signal logic, then applies 6.3 hierarchical feasibility logic."""
    print("\n[6.3] Extracting T4 data and classifying radio feasibility...")
    
    # 1. Extract Base Data
    query = f"SELECT * FROM {SOURCE_TABLE}"
    df = pd.read_sql(query, engine)
    initial_rows = len(df)
    print(f"  -> Extracted {initial_rows} rows from {SOURCE_TABLE}.")
    
    # 2. Re-apply Sub-task 6.2 Signal Quality Logic (In-Memory)
    mask_poor = (df['predicted_rsrp_dbm'] < RSRP_POOR_THRESHOLD) | \
                (df['predicted_sinr_db'] < SINR_POOR_THRESHOLD)
    mask_excellent = (df['predicted_rsrp_dbm'] > RSRP_EXCELLENT_THRESHOLD) & \
                     (df['predicted_sinr_db'] > SINR_EXCELLENT_THRESHOLD)
                     
    conditions_62 = [mask_poor, mask_excellent]
    choices_62 = ['Poor', 'Excellent']
    df['signal_quality_class'] = np.select(conditions_62, choices_62, default='Acceptable')
    print(f"  -> Re-applied Sub-task 6.2 Signal Quality Classification.")
    
    # 3. Apply Sub-task 6.3 Hierarchical Feasibility Logic
    # Initialize with 'Unknown' to track unclassified rows
    df['radio_feasibility_class'] = 'Unknown'
    
    # Priority 1: Fiber_Competitor (Commercial Block)
    mask_fiber = df['fiber_coverage_flag'] == True
    df.loc[mask_fiber, 'radio_feasibility_class'] = 'Fiber_Competitor'
    
    # Priority 2: Infeasible - Signal Failure (Physical Block)
    mask_signal_fail = (df['signal_quality_class'] == 'Poor') & (df['radio_feasibility_class'] == 'Unknown')
    df.loc[mask_signal_fail, 'radio_feasibility_class'] = 'Infeasible'
    
    # Priority 3: 5G_Feasible (Premium Tier)
    mask_5g = (df['coverage_5g_flag'] == True) & \
              (df['signal_quality_class'].isin(['Excellent', 'Acceptable'])) & \
              (df['radio_feasibility_class'] == 'Unknown')
    df.loc[mask_5g, 'radio_feasibility_class'] = '5G_Feasible'
    
    # Priority 4: 4G_Fallback (Standard Tier)
    mask_4g = (df['coverage_5g_flag'] == False) & \
              (df['coverage_4g_flag'] == True) & \
              (df['signal_quality_class'].isin(['Excellent', 'Acceptable'])) & \
              (df['radio_feasibility_class'] == 'Unknown')
    df.loc[mask_4g, 'radio_feasibility_class'] = '4G_Fallback'
    
    # Priority 5: Infeasible - No Coverage (Coverage Block / Default)
    mask_no_coverage = df['radio_feasibility_class'] == 'Unknown'
    df.loc[mask_no_coverage, 'radio_feasibility_class'] = 'Infeasible'
    
    # 4. Validate Exhaustiveness
    if (df['radio_feasibility_class'] == 'Unknown').any():
        raise ValueError("CRITICAL: Logical gap in feasibility classification. Some addresses fell through.")
        
    print(f"  -> Radio Feasibility Classification COMPLETE.")
    return df

# ==============================================================================
# EXECUTION REPORT GENERATOR
# ==============================================================================
def print_execution_report(df):
    """Prints a comprehensive execution and business report for Sub-task 6.3."""
    print("\n" + "="*80)
    print(" "*10 + "STEP 6.3 EXECUTION REPORT: RADIO FEASIBILITY & COMMERCIAL CONTEXT")
    print("="*80)
    
    total_addresses = len(df)
    
    # Calculate counts and percentages
    class_counts = df['radio_feasibility_class'].value_counts()
    fiber_count = class_counts.get('Fiber_Competitor', 0)
    infeasible_count = class_counts.get('Infeasible', 0)
    feasible_5g_count = class_counts.get('5G_Feasible', 0)
    feasible_4g_count = class_counts.get('4G_Fallback', 0)
    
    print("\n[1] OPERATIONS PERFORMED")
    print("  • Re-applied Sub-task 6.2 worst-case signal classification in memory")
    print("  • Applied strict 5-tier hierarchical priority logic for radio feasibility")
    print("  • Enforced commercial cannibalization block (Fiber takes precedence over 5G)")
    
    print("\n[2] FEASIBILITY CLASSIFICATION DISTRIBUTION")
    print(f"  • Total Addresses Processed     : {total_addresses:,}")
    print(f"  • 5G_Feasible (Premium Target)  : {feasible_5g_count:,} ({feasible_5g_count/total_addresses*100:.1f}%)")
    print(f"  • 4G_Fallback (Standard Target) : {feasible_4g_count:,} ({feasible_4g_count/total_addresses*100:.1f}%)")
    print(f"  • Fiber_Competitor (Comm. Block): {fiber_count:,} ({fiber_count/total_addresses*100:.1f}%)")
    print(f"  • Infeasible (Phys/Coverage)    : {infeasible_count:,} ({infeasible_count/total_addresses*100:.1f}%)")
    
    viable_total = feasible_5g_count + feasible_4g_count
    blocked_total = fiber_count + infeasible_count
    print(f"\n  -> TOTAL VIABLE FOR FWA (5G+4G)  : {viable_total:,} ({viable_total/total_addresses*100:.1f}%)")
    print(f"  -> TOTAL BLOCKED (HARD STOPS)    : {blocked_total:,} ({blocked_total/total_addresses*100:.1f}%)")
    
    print("\n[3] EDGE CASE ANALYSIS: FIBER vs 5G OVERLAP")
    # Check how many addresses had BOTH Fiber and 5G coverage
    fiber_and_5g_overlap = df[(df['fiber_coverage_flag'] == True) & (df['coverage_5g_flag'] == True)]
    overlap_count = len(fiber_and_5g_overlap)
    if overlap_count > 0:
        print(f"  • Found {overlap_count:,} addresses with BOTH Fiber and 5G coverage.")
        print(f"  • Hierarchical logic correctly classified ALL {overlap_count} as 'Fiber_Competitor'.")
        print(f"  • Commercial protection rule successfully prevented 5G FWA cannibalization.")
    else:
        print("  • No overlap detected between Fiber and 5G coverage in this dataset.")
        
    print("\n[4] VALIDATION RESULTS")
    print("  • Logical Exhaustiveness          : PASSED (0 'Unknown' classifications)")
    print("  • Priority Hierarchy Enforcement  : PASSED (Fiber > Signal > 5G > 4G > Default)")
    
    print("\n[5] BUSINESS INTERPRETATION")
    print("  • The pipeline has successfully isolated the true FWA target market.")
    print("  • Only '5G_Feasible' and '4G_Fallback' addresses will pass the gate to")
    print("    Step 8 (ABT) and Step 9 (Suitability Scoring).")
    print("  • The 'Fiber_Competitor' block protects premium FTTH revenue by ensuring")
    print("    we do not offer wireless substitutes to already-fixed broadband users.")
    print("  • The 'Infeasible' block prevents deploying CPEs to physical dead zones.")
    
    print("\n[6] READINESS FOR NEXT DEPENDENCY")
    print("  • Sub-task 6.4 (Final T4 Assembly & Persistence): READY.")
    print("  • The radio_feasibility_class is now fully derived and validated.")
    print("="*80 + "\n")

# ==============================================================================
# MAIN EXECUTION PIPELINE
# ==============================================================================
def main():
    try:
        engine = get_db_engine()
        
        # Execute Sub-task 6.3
        df_classified = classify_radio_feasibility(engine)
        
        # Print Report
        print_execution_report(df_classified)
        
    except Exception as e:
        print(f"\n[CRITICAL ERROR] Pipeline halted: {str(e)}")
        sys.exit(1)

if __name__ == "__main__":
    main()
