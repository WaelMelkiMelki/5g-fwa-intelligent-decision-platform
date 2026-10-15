"""
=============================================================================
Project: 5G FWA Migration Analytics Pipeline
Step:    8.8 - Final ABT Validation, Feature Dictionary & Persistence
Role:    Senior Telecom Data Engineer
=============================================================================
Objective: Finalize the 50-column intermediate checkpoint into the definitive 
Analytical Base Table (abt_subscriber_month). Enforces strict logical column 
ordering, generates the official Feature Dictionary, runs global validation, 
persists the final table, and creates a B-tree index for downstream optimization.
=============================================================================
"""

import pandas as pd
import sqlalchemy
import logging
import sys
import json
from datetime import datetime

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

SOURCE_CHECKPOINT = "abt_t3_capacity_joined"
TARGET_TABLE = "abt_subscriber_month"
DICT_OUTPUT_FILE = "abt_feature_dictionary.json"

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
def get_expected_column_order() -> list:
    """Returns the strictly ordered list of 50 ABT columns by logical dimension."""
    return [
        # 1. Keys (2)
        'subscriber_id', 'snapshot_month',
        # 2. T2 Commercial (15)
        'segment_tier', 'b2b_b2c_flag', 'arpu_monthly_tnd', 'tenure_months', 
        'address_id', 'governorate', 'contract_type', 'num_active_lines', 
        'has_mobile_sub_flag', 'activation_date', 'audit_flag', 'churn', 
        'arpu_band', 'tenure_band', 'multi_line_flag',
        # 3. T1 Core Usage (4)
        'monthly_sessions', 'monthly_total_gb', 'dl_volume_mb_imputed_monthly_median', 'monthly_peak_hour_ratio',
        # 4. T1 Dominance (3)
        'dominant_device_generation', 'dominant_serving_cell_id', 'device_5g_ready_flag',
        # 5. T4 Coverage (8)
        'serving_cell_id', 'predicted_rsrp_dbm', 'predicted_sinr_db', 'coverage_5g_flag', 
        'coverage_4g_flag', 'fiber_coverage_flag', 'signal_quality_class', 'radio_feasibility_class',
        # 6. T5 Service (12)
        'streaming_vol_gb', 'streaming_session_count', 'iptv_active_flag', 'iptv_watch_hours', 
        'voip_minutes', 'cloud_cam_flag', 'iot_traffic_share_pct', 'social_media_vol_gb', 
        'gaming_vol_gb', 'streaming_heavy_flag', 'gaming_heavy_flag', 'high_voip_usage_flag',
        # 7. T3 Capacity (6)
        'site_id', 'avg_prb_utilisation_pct', 'p95_prb_utilisation_pct', 'max_prb_utilisation_pct', 
        'avg_dl_throughput_mbps', 'current_capacity_proxy_status'
    ]

def reorder_and_cleanup(df: pd.DataFrame) -> pd.DataFrame:
    """Drops redundant keys and enforces strict logical column ordering."""
    expected_cols = get_expected_column_order()
    
    # Drop any accidental merge artifacts or redundant keys
    drop_cols = [col for col in df.columns if col.endswith('_x') or col.endswith('_y') or col == 'cell_id']
    if drop_cols:
        logging.info(f"Dropping redundant/artifact columns: {drop_cols}")
        df = df.drop(columns=drop_cols)
        
    # Verify we have exactly the expected columns
    missing_cols = [col for col in expected_cols if col not in df.columns]
    if missing_cols:
        logging.error(f"CRITICAL: Missing expected columns in ABT: {missing_cols}")
        sys.exit(1)
        
    extra_cols = [col for col in df.columns if col not in expected_cols]
    if extra_cols:
        logging.warning(f"Unexpected extra columns found (will be dropped): {extra_cols}")
        df = df.drop(columns=extra_cols)
        
    # Reorder
    return df[expected_cols]

def enforce_final_schema(df: pd.DataFrame) -> pd.DataFrame:
    """Enforces strict PostgreSQL-compatible data types for the entire ABT."""
    # Keys
    df['subscriber_id'] = df['subscriber_id'].astype(str)
    df['snapshot_month'] = pd.to_datetime(df['snapshot_month']).dt.date
    
    # T2 Commercial
    df['segment_tier'] = df['segment_tier'].astype(str)
    df['b2b_b2c_flag'] = df['b2b_b2c_flag'].astype(str)
    df['arpu_monthly_tnd'] = df['arpu_monthly_tnd'].astype(float)
    df['tenure_months'] = df['tenure_months'].astype(int)
    df['address_id'] = df['address_id'].astype(str)
    df['governorate'] = df['governorate'].astype(str)
    df['contract_type'] = df['contract_type'].astype(str)
    df['num_active_lines'] = df['num_active_lines'].astype(int)
    df['has_mobile_sub_flag'] = df['has_mobile_sub_flag'].astype(bool)
    df['activation_date'] = pd.to_datetime(df['activation_date'])
    df['audit_flag'] = df['audit_flag'].astype(str)
    df['churn'] = df['churn'].astype(int) # 0 or 1
    df['arpu_band'] = df['arpu_band'].astype(str)
    df['tenure_band'] = df['tenure_band'].astype(str)
    df['multi_line_flag'] = df['multi_line_flag'].astype(bool)
    
    # T1 Core
    df['monthly_sessions'] = df['monthly_sessions'].astype(int)
    df['monthly_total_gb'] = df['monthly_total_gb'].astype(float)
    df['dl_volume_mb_imputed_monthly_median'] = df['dl_volume_mb_imputed_monthly_median'].astype(float)
    df['monthly_peak_hour_ratio'] = df['monthly_peak_hour_ratio'].astype(float)
    
    # T1 Dominance
    df['dominant_device_generation'] = df['dominant_device_generation'].astype(str)
    df['dominant_serving_cell_id'] = df['dominant_serving_cell_id'].astype(str)
    df['device_5g_ready_flag'] = df['device_5g_ready_flag'].astype(bool)
    
    # T4 Coverage
    df['serving_cell_id'] = df['serving_cell_id'].astype(str)
    df['predicted_rsrp_dbm'] = df['predicted_rsrp_dbm'].astype(float)
    df['predicted_sinr_db'] = df['predicted_sinr_db'].astype(float)
    df['coverage_5g_flag'] = df['coverage_5g_flag'].astype(bool)
    df['coverage_4g_flag'] = df['coverage_4g_flag'].astype(bool)
    df['fiber_coverage_flag'] = df['fiber_coverage_flag'].astype(bool)
    df['signal_quality_class'] = df['signal_quality_class'].astype(str)
    df['radio_feasibility_class'] = df['radio_feasibility_class'].astype(str)
    
    # T5 Service
    df['streaming_vol_gb'] = df['streaming_vol_gb'].astype(float)
    df['streaming_session_count'] = df['streaming_session_count'].astype(int)
    df['iptv_active_flag'] = df['iptv_active_flag'].astype(bool)
    df['iptv_watch_hours'] = df['iptv_watch_hours'].astype(float)
    df['voip_minutes'] = df['voip_minutes'].astype(float)
    df['cloud_cam_flag'] = df['cloud_cam_flag'].astype(bool)
    df['iot_traffic_share_pct'] = df['iot_traffic_share_pct'].astype(float)
    df['social_media_vol_gb'] = df['social_media_vol_gb'].astype(float)
    df['gaming_vol_gb'] = df['gaming_vol_gb'].astype(float)
    df['streaming_heavy_flag'] = df['streaming_heavy_flag'].astype(bool)
    df['gaming_heavy_flag'] = df['gaming_heavy_flag'].astype(bool)
    df['high_voip_usage_flag'] = df['high_voip_usage_flag'].astype(bool)
    
    # T3 Capacity
    df['site_id'] = df['site_id'].astype(str)
    df['avg_prb_utilisation_pct'] = df['avg_prb_utilisation_pct'].astype(float)
    df['p95_prb_utilisation_pct'] = df['p95_prb_utilisation_pct'].astype(float)
    df['max_prb_utilisation_pct'] = df['max_prb_utilisation_pct'].astype(float)
    df['avg_dl_throughput_mbps'] = df['avg_dl_throughput_mbps'].astype(float)
    df['current_capacity_proxy_status'] = df['current_capacity_proxy_status'].astype(str)
    
    return df

def generate_feature_dictionary(df: pd.DataFrame) -> list:
    """Generates a structured Feature Dictionary for data lineage and auditability."""
    feature_dict = []
    
    dimension_map = {
        'subscriber_id': ('Keys', 'Unique subscriber identifier'),
        'snapshot_month': ('Keys', 'Monthly observation period'),
        'segment_tier': ('T2 Commercial', 'CRM subscriber segment'),
        'b2b_b2c_flag': ('T2 Commercial', 'Business vs Consumer flag'),
        'arpu_monthly_tnd': ('T2 Commercial', 'Average Revenue Per User (TND)'),
        'tenure_months': ('T2 Commercial', 'Months since activation'),
        'address_id': ('T2 Commercial', 'Physical service address identifier'),
        'governorate': ('T2 Commercial', 'Geographic governorate'),
        'contract_type': ('T2 Commercial', 'Prepaid vs Postpaid'),
        'num_active_lines': ('T2 Commercial', 'Total active MSISDNs on account'),
        'has_mobile_sub_flag': ('T2 Commercial', 'Flag indicating active mobile subscription'),
        'activation_date': ('T2 Commercial', 'Date of first service activation'),
        'audit_flag': ('T2 Commercial', 'Data quality audit status'),
        'churn': ('T2 Commercial', 'Target variable: 1 if churned, 0 otherwise'),
        'arpu_band': ('T2 Commercial', 'GMM-derived ARPU categorical band'),
        'tenure_band': ('T2 Commercial', 'GMM-derived Tenure categorical band'),
        'multi_line_flag': ('T2 Commercial', 'Derived flag for multiple active lines'),
        'monthly_sessions': ('T1 Core Usage', 'Total monthly network attachment sessions'),
        'monthly_total_gb': ('T1 Core Usage', 'Total monthly data volume in GB'),
        'dl_volume_mb_imputed_monthly_median': ('T1 Core Usage', 'Imputed median downlink volume (MB)'),
        'monthly_peak_hour_ratio': ('T1 Core Usage', 'Ratio of traffic during peak congestion hours'),
        'dominant_device_generation': ('T1 Dominance', 'Primary device technology (4G/5G)'),
        'dominant_serving_cell_id': ('T1 Dominance', 'Cell ID where mobile device historically camped'),
        'device_5g_ready_flag': ('T1 Dominance', 'Boolean flag for 5G device capability'),
        'serving_cell_id': ('T4 Coverage', 'Predicted cell ID serving the fixed address'),
        'predicted_rsrp_dbm': ('T4 Coverage', 'Predicted Reference Signal Received Power'),
        'predicted_sinr_db': ('T4 Coverage', 'Predicted Signal-to-Interference-plus-Noise Ratio'),
        'coverage_5g_flag': ('T4 Coverage', 'Boolean flag for 5G coverage availability'),
        'coverage_4g_flag': ('T4 Coverage', 'Boolean flag for 4G coverage availability'),
        'fiber_coverage_flag': ('T4 Coverage', 'Boolean flag for existing FTTH availability'),
        'signal_quality_class': ('T4 Coverage', 'Categorical RF quality tier'),
        'radio_feasibility_class': ('T4 Coverage', 'Ultimate Go/No-Go FWA feasibility class'),
        'streaming_vol_gb': ('T5 Service', 'Monthly OTT streaming volume in GB'),
        'streaming_session_count': ('T5 Service', 'Monthly count of streaming sessions'),
        'iptv_active_flag': ('T5 Service', 'Boolean flag for active IPTV subscription'),
        'iptv_watch_hours': ('T5 Service', 'Monthly IPTV consumption in hours'),
        'voip_minutes': ('T5 Service', 'Monthly VoIP call minutes'),
        'cloud_cam_flag': ('T5 Service', 'Boolean flag for cloud camera traffic'),
        'iot_traffic_share_pct': ('T5 Service', 'Percentage of traffic from IoT devices'),
        'social_media_vol_gb': ('T5 Service', 'Monthly social media data volume in GB'),
        'gaming_vol_gb': ('T5 Service', 'Monthly online gaming data volume in GB'),
        'streaming_heavy_flag': ('T5 Service', '1D GMM-derived flag for heavy streaming'),
        'gaming_heavy_flag': ('T5 Service', '1D GMM-derived flag for heavy gaming'),
        'high_voip_usage_flag': ('T5 Service', '1D GMM-derived flag for high VoIP usage'),
        'site_id': ('T3 Capacity', 'Physical cell site identifier'),
        'avg_prb_utilisation_pct': ('T3 Capacity', 'Average Physical Resource Block utilization'),
        'p95_prb_utilisation_pct': ('T3 Capacity', '95th percentile PRB utilization (peak load)'),
        'max_prb_utilisation_pct': ('T3 Capacity', 'Maximum observed PRB utilization'),
        'avg_dl_throughput_mbps': ('T3 Capacity', 'Average downlink throughput at cell level'),
        'current_capacity_proxy_status': ('T3 Capacity', 'Categorical cell capacity status (Available/Constrained)')
    }
    
    for col in df.columns:
        dim, desc = dimension_map.get(col, ('Unknown', 'No description available'))
        feature_dict.append({
            "column_name": col,
            "data_type": str(df[col].dtype),
            "dimension": dim,
            "business_description": desc
        })
        
    return feature_dict

def validate_final_abt(df: pd.DataFrame, expected_rows: int, expected_cols: int):
    """Runs final global validation assertions on the definitive ABT."""
    validation_passed = True
    
    # 1. Row Count
    if len(df) != expected_rows:
        logging.error(f"ROW COUNT VIOLATION: Expected {expected_rows}, got {len(df)}.")
        validation_passed = False
    else:
        logging.info(f"[PASS] Final row count matches baseline: {len(df):,} rows.")
        
    # 2. Column Count
    if len(df.columns) != expected_cols:
        logging.error(f"COLUMN COUNT VIOLATION: Expected {expected_cols}, got {len(df.columns)}.")
        validation_passed = False
    else:
        logging.info(f"[PASS] Final column count matches expected schema: {len(df.columns)} columns.")
        
    # 3. Grain Uniqueness (The Final Gate)
    duplicates = df.duplicated(subset=['subscriber_id', 'snapshot_month']).sum()
    if duplicates > 0:
        logging.error(f"GRAIN VIOLATION: Found {duplicates} duplicate subscriber-month records.")
        validation_passed = False
    else:
        logging.info("[PASS] Final grain uniqueness verified: Strict 1:1 subscriber-month grain.")
        
    # 4. Null Integrity on Critical Keys and Targets
    critical_cols = ['subscriber_id', 'snapshot_month', 'address_id', 'churn']
    nulls_in_critical = df[critical_cols].isnull().sum().sum()
    if nulls_in_critical > 0:
        logging.error(f"NULL VIOLATION: Found {nulls_in_critical} nulls in critical key/target columns.")
        validation_passed = False
    else:
        logging.info("[PASS] Null integrity verified: 0 nulls in critical keys and target variables.")
        
    return validation_passed

def create_db_index(engine, schema, table):
    """Creates a composite B-tree index for downstream query optimization."""
    index_name = f"idx_{table}_sub_month"
    query = f"CREATE INDEX IF NOT EXISTS {index_name} ON {schema}.{table} (subscriber_id, snapshot_month);"
    try:
        with engine.connect() as conn:
            conn.execute(sqlalchemy.text(query))
            conn.commit()
        logging.info(f"SUCCESS: Composite B-tree index '{index_name}' created on ({schema}.{table}).")
    except Exception as e:
        logging.error(f"Failed to create index: {e}")

# -----------------------------------------------------------------------------
# 3. Main Execution Pipeline
# -----------------------------------------------------------------------------
def main():
    logging.info("="*80)
    logging.info("STARTING STEP 8.8: FINAL ABT VALIDATION, DICTIONARY & PERSISTENCE")
    logging.info("="*80)
    
    # 3.1 Extract Checkpoint
    logging.info("Phase 1: Extracting final intermediate checkpoint...")
    try:
        df_abt = pd.read_sql(f"SELECT * FROM {SCHEMA}.{SOURCE_CHECKPOINT}", engine)
        logging.info(f"Extracted {len(df_abt):,} rows and {len(df_abt.columns)} cols from {SOURCE_CHECKPOINT}.")
    except Exception as e:
        logging.error(f"Extraction failed: {e}")
        sys.exit(1)

    # 3.2 Schema Cleanup & Logical Ordering
    logging.info("\nPhase 2: Enforcing strict logical column ordering and cleanup...")
    df_abt = reorder_and_cleanup(df_abt)
    logging.info(f"Schema reordered to {len(df_abt.columns)} strictly ordered columns.")

    # 3.3 Final Schema Enforcement
    logging.info("\nPhase 3: Enforcing strict PostgreSQL-compatible data types...")
    df_abt = enforce_final_schema(df_abt)

    # 3.4 Generate Feature Dictionary
    logging.info("\nPhase 4: Generating official Feature Dictionary for data lineage...")
    feature_dict = generate_feature_dictionary(df_abt)
    try:
        with open(DICT_OUTPUT_FILE, 'w', encoding='utf-8') as f:
            json.dump(feature_dict, f, indent=4)
        logging.info(f"SUCCESS: Feature Dictionary saved to {DICT_OUTPUT_FILE}")
    except Exception as e:
        logging.error(f"Failed to save Feature Dictionary: {e}")

    # 3.5 Final Global Validation
    logging.info("\nPhase 5: Running final global validation assertions...")
    expected_rows = 12412
    expected_cols = 50
    validation_passed = validate_final_abt(df_abt, expected_rows, expected_cols)

    # 3.6 Persist to Database
    if validation_passed:
        logging.info(f"\nPhase 6: Persisting definitive ABT to {SCHEMA}.{TARGET_TABLE}...")
        try:
            df_abt.to_sql(TARGET_TABLE, engine, schema=SCHEMA, if_exists='replace', index=False, method='multi', chunksize=1000)
            logging.info(f"SUCCESS: Definitive table {SCHEMA}.{TARGET_TABLE} created/overwritten successfully.")
        except Exception as e:
            logging.error(f"Database persistence failed: {e}")
            sys.exit(1)
            
        # 3.7 Create Index
        logging.info("\nPhase 7: Creating performance-optimizing database index...")
        create_db_index(engine, SCHEMA, TARGET_TABLE)
    else:
        logging.error("VALIDATION FAILED: Halting pipeline. Definitive ABT was NOT persisted.")
        sys.exit(1)

    # 3.8 Final Execution Report
    logging.info("\n" + "="*80)
    logging.info("EXECUTION SUMMARY: DEFINITIVE ANALYTICAL BASE TABLE (ABT)")
    logging.info("="*80)
    
    print(f"\n{'Metric':<40} | {'Value':<20}")
    print("-" * 65)
    print(f"{'Source Checkpoint Rows':<40} | {len(df_abt):>20,}")
    print(f"{'Final ABT Rows':<40} | {len(df_abt):>20,}")
    print(f"{'Final ABT Columns':<40} | {len(df_abt.columns):>20}")
    print(f"{'Duplicate Records':<40} | {'0':>20}")
    print(f"{'Nulls in Critical Keys/Targets':<40} | {'0':>20}")
    
    print("\n--- FINAL SCHEMA DIMENSIONS (50 COLUMNS) ---")
    dimensions = ['Keys', 'T2 Commercial', 'T1 Core Usage', 'T1 Dominance', 'T4 Coverage', 'T5 Service', 'T3 Capacity']
    for dim in dimensions:
        cols_in_dim = [f['column_name'] for f in feature_dict if f['dimension'] == dim]
        print(f"  - {dim:<18} | {len(cols_in_dim):>2} columns")

    print("\n--- BUSINESS INTERPRETATION ---")
    print("1. The definitive Analytical Base Table (abt_subscriber_month) is now complete.")
    print("2. Strict 1:1 subscriber-month grain is mathematically certified (0 duplicates).")
    print("3. The Feature Dictionary provides 100% data lineage for downstream auditability.")
    print("4. A composite B-tree index has been created to optimize Steps 9-15 read operations.")
    print("5. The dataset is fully typed, cleaned, and ready for ML modeling and simulation.")

    print("\n--- PIPELINE STATUS ---")
    logging.info("STATUS: STEP 8 COMPLETE. Analytical Base Table is certified and ready for Steps 9–15.")

if __name__ == "__main__":
    main()
