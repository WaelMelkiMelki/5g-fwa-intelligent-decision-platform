"""
=============================================================================
Script Name : step_2_3_1_time_frame_standardization.py
Project     : FWA Telecom Data Pipeline
Step        : 2 & 3 -> Sub-task 1: Time Frame Standardization
Description : Standardizes temporal dimensions across T1, T2, T3, and T5 
              into a unified 'snapshot_month' column (1st day of the month).
              Enforces strict PostgreSQL DATE types and validates the 
              single-month cross-sectional snapshot assumption.
=============================================================================
"""

import pandas as pd
import sqlalchemy
from sqlalchemy.types import Date
import logging
import sys

# Configure logging for clean execution output
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

# --- Configuration ---
# Update these credentials to match your local PostgreSQL environment
DB_USER = 'postgres'
DB_PASS = __import__("os").environ["FWA_DB_PASSWORD"]
DB_HOST = 'localhost'
DB_PORT = '5432'
DB_NAME = 'postgres'
SCHEMA_NAME = 'cleaned_data'

# Connection string
DATABASE_URI = f"postgresql+psycopg2://{DB_USER}:{DB_PASS}@{DB_HOST}:{DB_PORT}/{DB_NAME}"

# Define table mappings: (table_name, original_date_column_name)
TABLE_DATE_MAPPINGS = {
    't1_subscriber_daily_profile': 'snapshot_date',
    't3_ran_kpi_cell_daily': 'kpi_date',
    't2_crm_subscriber_master': 'snapshot_month',
    't5_service_consumption_monthly': 'month'
}

def get_engine():
    """Initializes and returns the SQLAlchemy engine."""
    try:
        engine = sqlalchemy.create_engine(DATABASE_URI)
        # Test connection
        with engine.connect() as conn:
            logging.info("Successfully connected to the PostgreSQL database.")
        return engine
    except Exception as e:
        logging.error(f"Database connection failed: {e}")
        sys.exit(1)

def standardize_temporal_dimension(df, original_date_col, table_name):
    """
    Converts the original date column to a standardized 'snapshot_month' column.
    """
    df = df.copy()
    
    # 1. Handle T5 specific rename (if the column is named 'month')
    if original_date_col == 'month':
        df.rename(columns={'month': 'snapshot_month'}, inplace=True)
        original_date_col = 'snapshot_month'
    
    # 2. Convert to datetime and normalize to the 1st day of the month
    # Using .dt.to_period('M').dt.to_timestamp() is the safest way to strip days/hours
    df['snapshot_month'] = pd.to_datetime(df[original_date_col], errors='coerce') \
                             .dt.to_period('M') \
                             .dt.to_timestamp()
    
    # 3. Drop the original daily column if it's not the target column itself (to avoid redundancy)
    # Actually, for T1 and T3, we KEEP the daily grain for Step 3 imputation. 
    # We only drop if it was exactly 'month' in T5 which we already renamed.
    
    return df

def validate_temporal_integrity(df, table_name):
    """
    Enforces strict data quality rules for the single-month snapshot assumption.
    """
    # Check 1: No nulls in the new column
    null_count = df['snapshot_month'].isna().sum()
    if null_count > 0:
        raise ValueError(f"Validation Failed: {null_count} null values found in snapshot_month for {table_name}.")
    
    # Check 2: All dates must be the 1st of the month
    invalid_days = df[df['snapshot_month'].dt.day != 1]
    if not invalid_days.empty:
        raise ValueError(f"Validation Failed: Found {len(invalid_days)} rows where day != 1 in {table_name}.")
    
    # Check 3: Strict single-month cross-sectional snapshot
    unique_months = df['snapshot_month'].nunique()
    if unique_months != 1:
        raise ValueError(f"Validation Failed: Expected 1 unique month, found {unique_months} in {table_name}.")
        
    return df['snapshot_month'].iloc[0]

def save_to_postgres(engine, df, table_name):
    """
    Writes the DataFrame back to PostgreSQL, strictly enforcing the DATE type.
    """
    # Explicitly map the pandas datetime64 to PostgreSQL DATE
    dtype_mapping = {'snapshot_month': Date()}
    
    # We use 'replace' to overwrite the table with the newly standardized schema
    df.to_sql(
        name=table_name,
        con=engine,
        schema=SCHEMA_NAME,
        if_exists='replace',
        index=False,
        dtype=dtype_mapping,
        method='multi' # Optimizes insert speed
    )

def main():
    engine = get_engine()
    execution_summary = []
    
    logging.info("Starting Sub-task 1: Time Frame Standardization...")
    
    for table_name, date_col in TABLE_DATE_MAPPINGS.items():
        logging.info(f"Processing table: {table_name} (Source column: {date_col})")
        
        try:
            # 1. Load Data
            query = f"SELECT * FROM {SCHEMA_NAME}.{table_name}"
            df = pd.read_sql(query, engine)
            original_row_count = len(df)
            
            # 2. Standardize
            df_std = standardize_temporal_dimension(df, date_col, table_name)
            
            # 3. Validate
            unique_month = validate_temporal_integrity(df_std, table_name)
            
            # 4. Save
            save_to_postgres(engine, df_std, table_name)
            
            # Record success
            execution_summary.append({
                'Table': table_name,
                'Rows_Processed': original_row_count,
                'Snapshot_Month': unique_month.strftime('%Y-%m-%d'),
                'Validation': 'PASSED',
                'Status': 'SUCCESS'
            })
            logging.info(f"Successfully processed and saved {table_name}.")
            
        except Exception as e:
            logging.error(f"Failed to process {table_name}: {e}")
            execution_summary.append({
                'Table': table_name,
                'Rows_Processed': len(df) if 'df' in locals() else 0,
                'Snapshot_Month': 'N/A',
                'Validation': 'FAILED',
                'Status': f'ERROR: {str(e)[:50]}'
            })
            # Halt pipeline on critical validation failure
            sys.exit(1)

    # --- Print Final Execution Summary ---
    print("\n" + "="*80)
    print("EXECUTION SUMMARY: Sub-task 1 (Time Frame Standardization)")
    print("="*80)
    summary_df = pd.DataFrame(execution_summary)
    print(summary_df.to_string(index=False))
    print("="*80)
    print("✅ ALL TABLES SUCCESSFULLY STANDARDIZED TO 'snapshot_month' (DATE TYPE).")
    print("📌 NEXT DEPENDENCY: Sub-task 2 (T1 Roaming Exclusion & Core Aggregation).")
    print("="*80 + "\n")

if __name__ == "__main__":
    main()
