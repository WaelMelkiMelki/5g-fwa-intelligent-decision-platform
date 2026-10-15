"""
=============================================================================
Script Name : step_2_3_3_t1_device_cell_dominance.py
Project     : FWA Telecom Data Pipeline
Step        : 2 & 3 -> Sub-task 3: T1 Device & Serving Cell Dominance
Description : Calculates the monthly dominant device generation, 5G readiness 
              flag, and dominant serving cell per subscriber using statistical 
              mode on home-network daily records. Outputs to a modular table.
=============================================================================
"""

import pandas as pd
import sqlalchemy
from sqlalchemy.types import String, Boolean, Date
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

def calculate_dominance_features(df):
    """
    Applies non-destructive conditional filtering and calculates statistical 
    mode for device and cell dominance.
    """
    original_row_count = len(df)
    
    # 1. NON-DESTRUCTIVE CONDITIONAL FILTERING
    # Isolate home-network records without dropping rows from the original dataframe
    df_home = df[df['roaming_flag'] == False].copy()
    filtered_row_count = len(df_home)
    
    logging.info(f"Filtered to {filtered_row_count} home-network rows (Excluded {original_row_count - filtered_row_count} roaming rows).")
    
    # 2. STATISTICAL MODE CALCULATION (DOMINANCE)
    # We group by subscriber and month. 
    # Using value_counts().index[0] is a highly robust and fast way to get the mode 
    # (most frequent value). It deterministically handles ties.
    agg_funcs = {
        'device_generation': lambda x: x.value_counts().index[0],
        'serving_cell_id': lambda x: x.value_counts().index[0]
    }
    
    df_dominance = df_home.groupby(['subscriber_id', 'snapshot_month']).agg(agg_funcs).reset_index()
    
    # Rename columns to reflect they are monthly dominant features
    df_dominance.rename(columns={
        'device_generation': 'dominant_device_generation',
        'serving_cell_id': 'dominant_serving_cell_id'
    }, inplace=True)
    
    # 3. DERIVE 5G READY FLAG
    df_dominance['device_5g_ready_flag'] = (df_dominance['dominant_device_generation'] == '5G')
    
    # Ensure strict boolean type
    df_dominance['device_5g_ready_flag'] = df_dominance['device_5g_ready_flag'].astype(bool)
    
    return df_dominance, original_row_count, filtered_row_count

def validate_dominance_table(df):
    """
    Validates the newly created monthly dominance table.
    """
    # Check 1: No nulls in critical columns
    null_check = df[['subscriber_id', 'snapshot_month', 'dominant_device_generation', 'dominant_serving_cell_id']].isna().any().any()
    if null_check:
        raise ValueError("Validation Failed: Null values found in dominant device or cell columns.")
    
    # Check 2: Strict monthly grain (1 row per subscriber per month)
    grain_check = df.groupby(['subscriber_id', 'snapshot_month']).size()
    if (grain_check > 1).any():
        raise ValueError("Validation Failed: Duplicate subscriber/month combinations found. Grain is not unique.")
        
    # Check 3: Device generation must be valid categories
    valid_devices = {'2G', '3G', '4G', '5G'}
    actual_devices = set(df['dominant_device_generation'].unique())
    if not actual_devices.issubset(valid_devices):
        invalid = actual_devices - valid_devices
        raise ValueError(f"Validation Failed: Invalid device generations found: {invalid}")
        
    logging.info("✅ All monthly dominance validations passed.")

def save_to_postgres(engine, df, table_name):
    """
    Writes the DataFrame to PostgreSQL with strict type enforcement.
    """
    dtype_mapping = {
        'snapshot_month': Date(),
        'subscriber_id': String(),
        'dominant_device_generation': String(),
        'dominant_serving_cell_id': String(),
        'device_5g_ready_flag': Boolean()
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
    
    logging.info("Starting Sub-task 3: T1 Device & Serving Cell Dominance...")
    
    try:
        # 1. Load Data
        query = f"SELECT * FROM {SCHEMA_NAME}.t1_subscriber_daily_profile"
        df_t1 = pd.read_sql(query, engine)
        
        # 2. Calculate Dominance
        df_dominance, orig_rows, filtered_rows = calculate_dominance_features(df_t1)
        
        # 3. Validate
        validate_dominance_table(df_dominance)
        
        # 4. Save
        save_to_postgres(engine, df_dominance, 't1_monthly_dominance')
        
        # --- Calculate Summary Statistics ---
        total_subs = len(df_dominance)
        subs_5g_ready = df_dominance['device_5g_ready_flag'].sum()
        subs_4g_dominant = (df_dominance['dominant_device_generation'] == '4G').sum()
        unique_cells = df_dominance['dominant_serving_cell_id'].nunique()
        
        # --- Print Final Execution Summary ---
        print("\n" + "="*80)
        print("EXECUTION SUMMARY: Sub-task 3 (T1 Device & Serving Cell Dominance)")
        print("="*80)
        print(f"📊 Original Daily T1 Rows:       {orig_rows:,}")
        print(f"✅ Home-Network Rows Processed:   {filtered_rows:,}")
        print(f"👥 Final Unique Subscribers:      {total_subs:,}")
        print("-" * 80)
        print("📱 Device Dominance Statistics:")
        print(f"   - 5G Ready Subscribers:        {subs_5g_ready:,} ({(subs_5g_ready/total_subs)*100:.1f}%)")
        print(f"   - 4G Dominant Subscribers:     {subs_4g_dominant:,} ({(subs_4g_dominant/total_subs)*100:.1f}%)")
        print("-" * 80)
        print("📡 Cell Dominance Statistics:")
        print(f"   - Unique Dominant Cells:       {unique_cells}")
        print("-" * 80)
        print("✅ SUCCESS: 't1_monthly_dominance' created in 'cleaned_data' schema.")
        print("📌 NEXT DEPENDENCY: Sub-task 4 (T1 Zero-Imputation & Peak Hour Ratio).")
        print("="*80 + "\n")

    except Exception as e:
        logging.error(f"Pipeline failed: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()
