"""
=============================================================================
Script Name : step_2_3_4_t1_zero_imputation_peak_ratio.py
Project     : FWA Telecom Data Pipeline
Step        : 2 & 3 -> Sub-task 4: T1 Zero-Imputation & Peak Hour Ratio
Description : Safely calculates the monthly peak_hour_ratio by imputing daily 
              zero-volume records with the subscriber's monthly median, 
              preventing division-by-zero errors. Updates t1_monthly_core.
=============================================================================
"""

import pandas as pd
import numpy as np
import sqlalchemy
from sqlalchemy.types import Float, Integer, Date, String, Boolean
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

def calculate_imputation_and_ratio(df_t1):
    """
    Applies non-destructive filtering, calculates monthly medians, imputes daily zeros,
    and safely aggregates the peak hour ratio.
    """
    # 1. NON-DESTRUCTIVE CONDITIONAL FILTERING
    df_home = df_t1[df_t1['roaming_flag'] == False].copy()
    logging.info(f"Filtered to {len(df_home)} home-network rows for imputation logic.")
    
    # 2. MONTHLY MEDIAN CALCULATION
    # Calculate the median dl_volume_mb per subscriber for the month
    monthly_medians = df_home.groupby(['subscriber_id', 'snapshot_month'])['dl_volume_mb'].median().reset_index()
    monthly_medians.rename(columns={'dl_volume_mb': 'dl_volume_mb_imputed_monthly_median'}, inplace=True)
    
    # 3. DAILY IMPUTATION
    # Merge medians back to the daily home-network dataframe
    df_home = df_home.merge(monthly_medians, on=['subscriber_id', 'snapshot_month'], how='left')
    
    # Fill NaN medians (for subs with 0 usage all month) with 0.0 to prevent errors
    df_home['dl_volume_mb_imputed_monthly_median'] = df_home['dl_volume_mb_imputed_monthly_median'].fillna(0.0)
    
    # Apply np.where to impute daily zeros
    df_home['dl_volume_mb_imputed'] = np.where(
        df_home['dl_volume_mb'] == 0, 
        df_home['dl_volume_mb_imputed_monthly_median'], 
        df_home['dl_volume_mb']
    )
    
    # 4. SAFE MONTHLY AGGREGATION
    # Aggregate numerator and denominator to the monthly level FIRST
    agg_dict = {
        'peak_hour_dl_mb': 'sum',
        'dl_volume_mb_imputed': 'sum',
        'dl_volume_mb_imputed_monthly_median': 'first' # Keep the median for the final table
    }
    
    df_monthly_features = df_home.groupby(['subscriber_id', 'snapshot_month']).agg(agg_dict).reset_index()
    
    # 5. SAFE RATIO CALCULATION
    # Calculate ratio, handling division by zero safely
    df_monthly_features['monthly_peak_hour_ratio'] = np.where(
        df_monthly_features['dl_volume_mb_imputed'] == 0,
        0.0,
        df_monthly_features['peak_hour_dl_mb'] / df_monthly_features['dl_volume_mb_imputed']
    )
    
    # Clean up intermediate daily column before returning
    df_monthly_features.drop(columns=['peak_hour_dl_mb', 'dl_volume_mb_imputed'], inplace=True)
    
    # Ensure strict float types
    df_monthly_features['monthly_peak_hour_ratio'] = df_monthly_features['monthly_peak_hour_ratio'].astype(float)
    df_monthly_features['dl_volume_mb_imputed_monthly_median'] = df_monthly_features['dl_volume_mb_imputed_monthly_median'].astype(float)
    
    return df_monthly_features

def merge_and_save(engine, df_core, df_new_features):
    """
    Merges the new features into the existing t1_monthly_core table and saves to PostgreSQL.
    """
    # 1. LEFT JOIN to preserve all subscribers from the core table
    df_updated_core = df_core.merge(
        df_new_features, 
        on=['subscriber_id', 'snapshot_month'], 
        how='left'
    )
    
    # 2. HANDLE EDGE CASES (Subscribers with no home-network days at all)
    # Fill NaNs with 0.0 to prevent ABT join failures downstream
    df_updated_core['dl_volume_mb_imputed_monthly_median'] = df_updated_core['dl_volume_mb_imputed_monthly_median'].fillna(0.0)
    df_updated_core['monthly_peak_hour_ratio'] = df_updated_core['monthly_peak_hour_ratio'].fillna(0.0)
    
    # 3. VALIDATION
    if len(df_updated_core) != len(df_core):
        raise ValueError(f"Validation Failed: Row count changed from {len(df_core)} to {len(df_updated_core)} during merge.")
    
    if df_updated_core[['dl_volume_mb_imputed_monthly_median', 'monthly_peak_hour_ratio']].isna().any().any():
        raise ValueError("Validation Failed: Null values found in new imputed/ratio columns after merge.")
        
    if np.isinf(df_updated_core['monthly_peak_hour_ratio']).any():
        raise ValueError("Validation Failed: Infinite values found in monthly_peak_hour_ratio.")
        
    logging.info("✅ All merge and ratio validations passed.")
    
    # 4. SAVE TO POSTGRES
    dtype_mapping = {
        'snapshot_month': Date(),
        'subscriber_id': String(),
        'monthly_total_gb': Float(),
        'monthly_sessions': Integer(),
        'dl_volume_mb_imputed_monthly_median': Float(),
        'monthly_peak_hour_ratio': Float()
    }
    
    df_updated_core.to_sql(
        name='t1_monthly_core',
        con=engine,
        schema=SCHEMA_NAME,
        if_exists='replace',
        index=False,
        dtype=dtype_mapping,
        method='multi'
    )
    logging.info(f"Successfully updated 't1_monthly_core' in {SCHEMA_NAME} schema.")
    
    return df_updated_core

def main():
    engine = get_engine()
    
    logging.info("Starting Sub-task 4: T1 Zero-Imputation & Peak Hour Ratio...")
    
    try:
        # 1. Load Data
        logging.info("Loading daily T1 and existing monthly core tables...")
        df_t1 = pd.read_sql(f"SELECT * FROM {SCHEMA_NAME}.t1_subscriber_daily_profile", engine)
        df_core = pd.read_sql(f"SELECT * FROM {SCHEMA_NAME}.t1_monthly_core", engine)
        
        # 2. Calculate Imputation and Ratio
        df_new_features = calculate_imputation_and_ratio(df_t1)
        
        # 3. Merge and Save
        df_final_core = merge_and_save(engine, df_core, df_new_features)
        
        # --- Calculate Summary Statistics ---
        total_subs = len(df_final_core)
        high_peak_ratio_subs = (df_final_core['monthly_peak_hour_ratio'] > 0.30).sum() # >30% concentration
        avg_median_imputed = df_final_core['dl_volume_mb_imputed_monthly_median'].mean()
        avg_peak_ratio = df_final_core['monthly_peak_hour_ratio'].mean()
        
        # --- Print Final Execution Summary ---
        print("\n" + "="*80)
        print("EXECUTION SUMMARY: Sub-task 4 (T1 Zero-Imputation & Peak Hour Ratio)")
        print("="*80)
        print(f"📊 Original Daily T1 Rows:       {len(df_t1):,}")
        print(f"👥 Subscribers in Monthly Core:   {total_subs:,}")
        print("-" * 80)
        print("📈 Imputation & Ratio Statistics:")
        print(f"   - Avg Monthly Median (MB):     {avg_median_imputed:,.2f} MB")
        print(f"   - Avg Peak Hour Ratio:         {avg_peak_ratio:.2%}")
        print(f"   - High Peak Ratio Users (>30%):{high_peak_ratio_subs:,} ({(high_peak_ratio_subs/total_subs)*100:.1f}%)")
        print("-" * 80)
        print("✅ SUCCESS: 't1_monthly_core' updated with zero-division-proof metrics.")
        print("📌 NEXT DEPENDENCY: Step 4 (CRM and Commercial Feature Preparation from T2).")
        print("="*80 + "\n")

    except Exception as e:
        logging.error(f"Pipeline failed: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()
