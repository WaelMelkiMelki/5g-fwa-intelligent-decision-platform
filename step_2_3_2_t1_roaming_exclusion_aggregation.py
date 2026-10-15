"""
=============================================================================
Script Name : step_2_3_2_t1_roaming_exclusion_aggregation.py
Project     : FWA Telecom Data Pipeline
Step        : 2 & 3 -> Sub-task 2: T1 Roaming Exclusion & Core Aggregation
Description : Filters out roaming data using conditional boolean masking 
              (non-destructive) and aggregates daily T1 volumes/sessions 
              into monthly subscriber-level features.
=============================================================================
"""

import pandas as pd
import sqlalchemy
from sqlalchemy.types import Float, Integer, Date
import logging
import sys

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

# --- Configuration ---
DB_USER = 'postgres'
DB_PASS = __import__("os").environ["FWA_DB_PASSWORD"]
DB_HOST = 'localhost'
DB_PORT = '5432'
DB_NAME = 'postgres'
SCHEMA_NAME = 'cleaned_data'

DATABASE_URI = f"postgresql+psycopg2://{DB_USER}:{DB_PASS}@{DB_HOST}:{DB_PORT}/{DB_NAME}"

def get_engine():
    """Initializes and returns the SQLAlchemy engine."""
    try:
        engine = sqlalchemy.create_engine(DATABASE_URI)
        with engine.connect() as conn:
            logging.info("Successfully connected to the PostgreSQL database.")
        return engine
    except Exception as e:
        logging.error(f"Database connection failed: {e}")
        sys.exit(1)

def filter_and_aggregate_t1(df):
    """
    Applies non-destructive conditional filtering for roaming and aggregates to monthly grain.
    """
    original_row_count = len(df)
    
    # 1. NON-DESTRUCTIVE CONDITIONAL FILTERING
    # Instead of dropping rows (e.g., df.drop()), we use boolean masking to isolate 
    # home-network records. This preserves the original dataframe structure in memory.
    df_home = df[df['roaming_flag'] == False]
    filtered_row_count = len(df_home)
    roaming_excluded_count = original_row_count - filtered_row_count
    
    logging.info(f"Filtered out {roaming_excluded_count} roaming rows. Retained {filtered_row_count} home-network rows.")
    
    # 2. DAILY VOLUME CALCULATION (in MB)
    # Summing MBs first prevents daily floating-point rounding errors before GB conversion
    df_home = df_home.copy()
    df_home['total_daily_mb'] = df_home['dl_volume_mb'] + df_home['ul_volume_mb']
    
    # 3. MONTHLY AGGREGATION
    agg_dict = {
        'total_daily_mb': 'sum',
        'session_count': 'sum'
    }
    
    df_monthly = df_home.groupby(['subscriber_id', 'snapshot_month']).agg(agg_dict).reset_index()
    
    # 4. UNIT CONVERSION & RENAMING
    df_monthly['monthly_total_gb'] = df_monthly['total_daily_mb'] / 1024.0
    df_monthly.rename(columns={'session_count': 'monthly_sessions'}, inplace=True)
    
    # Drop intermediate calculation column
    df_monthly.drop(columns=['total_daily_mb'], inplace=True)
    
    # Ensure correct data types
    df_monthly['monthly_total_gb'] = df_monthly['monthly_total_gb'].astype(float)
    df_monthly['monthly_sessions'] = df_monthly['monthly_sessions'].astype(int)
    
    return df_monthly, original_row_count, filtered_row_count

def validate_monthly_t1(df):
    """
    Validates the aggregated monthly T1 table.
    """
    # Check 1: No nulls in key columns
    if df[['subscriber_id', 'snapshot_month', 'monthly_total_gb', 'monthly_sessions']].isna().any().any():
        raise ValueError("Validation Failed: Null values found in core monthly columns.")
    
    # Check 2: Strict monthly grain (1 row per subscriber per month)
    grain_check = df.groupby(['subscriber_id', 'snapshot_month']).size()
    if (grain_check > 1).any():
        raise ValueError("Validation Failed: Duplicate subscriber/month combinations found. Grain is not unique.")
        
    # Check 3: No negative volumes or sessions
    if (df['monthly_total_gb'] < 0).any() or (df['monthly_sessions'] < 0).any():
        raise ValueError("Validation Failed: Negative values found in volumes or sessions.")
        
    logging.info("✅ All monthly T1 validations passed.")

def save_to_postgres(engine, df, table_name):
    """
    Writes the DataFrame to PostgreSQL with strict type enforcement.
    """
    dtype_mapping = {
        'snapshot_month': Date(),
        'monthly_total_gb': Float(),
        'monthly_sessions': Integer()
    }
    
    df.to_sql(
        name=table_name,
        con=engine,
        schema=SCHEMA_NAME,
        if_exists='replace',
        index=False,
        dtype=dtype_mapping,
        method='multi'
    )
    logging.info(f"Successfully saved {table_name} to {SCHEMA_NAME} schema.")

def main():
    engine = get_engine()
    
    logging.info("Starting Sub-task 2: T1 Roaming Exclusion & Core Aggregation...")
    
    try:
        # 1. Load Data
        query = f"SELECT * FROM {SCHEMA_NAME}.t1_subscriber_daily_profile"
        df_t1 = pd.read_sql(query, engine)
        
        # 2. Filter and Aggregate
        df_monthly, orig_rows, filtered_rows = filter_and_aggregate_t1(df_t1)
        
        # 3. Validate
        validate_monthly_t1(df_monthly)
        
        # 4. Save
        save_to_postgres(engine, df_monthly, 't1_monthly_core')
        
        # --- Print Final Execution Summary ---
        print("\n" + "="*80)
        print("EXECUTION SUMMARY: Sub-task 2 (T1 Roaming Exclusion & Aggregation)")
        print("="*80)
        print(f"📊 Original Daily T1 Rows:       {orig_rows:,}")
        print(f"🚫 Roaming Rows Excluded:        {orig_rows - filtered_rows:,} (Filtered via conditional mask)")
        print(f"✅ Home-Network Rows Processed:   {filtered_rows:,}")
        print(f"📅 Final Monthly Aggregated Rows: {len(df_monthly):,}")
        print("-" * 80)
        print("📈 Key Statistics (Home-Network Only):")
        print(f"   - Total Monthly Volume (GB):   {df_monthly['monthly_total_gb'].sum():,.2f}")
        print(f"   - Total Monthly Sessions:      {df_monthly['monthly_sessions'].sum():,}")
        print(f"   - Avg Volume per Sub (GB):     {df_monthly['monthly_total_gb'].mean():,.2f}")
        print("-" * 80)
        print("✅ SUCCESS: 't1_monthly_core' created in 'cleaned_data' schema.")
        print("📌 NEXT DEPENDENCY: Sub-task 3 (T1 Device & Serving Cell Dominance).")
        print("="*80 + "\n")

    except Exception as e:
        logging.error(f"Pipeline failed: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()
