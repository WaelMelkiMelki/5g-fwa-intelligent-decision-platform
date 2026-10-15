import pandas as pd
import numpy as np
import sqlalchemy
from sqlalchemy import create_engine
import warnings
import sys
from datetime import date

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
SOURCE_TABLE = f"{TARGET_SCHEMA}.t3_ran_kpi_cell_daily"
TARGET_TABLE = f"{TARGET_SCHEMA}.t3_cell_monthly_kpi"
EXPECTED_SNAPSHOT_MONTH = "2026-01-01"
PRB_THRESHOLD = 80.0
MIN_DAYS_PER_CELL = 25  # Statistical minimum for robust P95 calculation

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
# SUB-TASK 5.1: EXTRACTION & TEMPORAL VALIDATION
# ==============================================================================
def extract_and_validate_t3(engine):
    """Loads T3 daily data and validates temporal integrity."""
    print("\n[5.1] Extracting and validating T3 daily data...")
    
    # Extract
    query = f"SELECT * FROM {SOURCE_TABLE}"
    df = pd.read_sql(query, engine)
    initial_rows = len(df)
    
    # Validate 1: Snapshot Month Purity
    unique_months = df['snapshot_month'].unique()
    if len(unique_months) != 1 or str(unique_months[0])[:10] != EXPECTED_SNAPSHOT_MONTH:
        raise ValueError(f"Temporal purity failed. Expected {EXPECTED_SNAPSHOT_MONTH}, found {unique_months}")
    
    # Validate 2: Critical Metric Nulls
    critical_cols = ['prb_utilisation_pct', 'avg_dl_throughput_mbps']
    null_counts = df[critical_cols].isnull().sum()
    if null_counts.sum() > 0:
        raise ValueError(f"Critical nulls found in T3 metrics: {null_counts.to_dict()}")
        
    # Validate 3: Temporal Completeness (Days per cell)
    days_per_cell = df.groupby('cell_id')['kpi_date'].nunique()
    cells_with_insufficient_days = days_per_cell[days_per_cell < MIN_DAYS_PER_CELL]
    if len(cells_with_insufficient_days) > 0:
        print(f"  [WARNING] {len(cells_with_insufficient_days)} cells have < {MIN_DAYS_PER_CELL} days of data.")
        
    print(f"  -> Extracted {initial_rows} daily rows across {df['cell_id'].nunique()} unique cells.")
    return df

# ==============================================================================
# SUB-TASK 5.2: CELL-LEVEL MONTHLY AGGREGATION
# ==============================================================================
def aggregate_monthly_kpis(df):
    """Aggregates daily cell metrics to a monthly grain."""
    print("\n[5.2] Aggregating daily metrics to monthly cell-level...")
    
    df_agg = df.groupby('cell_id').agg(
        site_id=('site_id', 'first'),
        snapshot_month=('snapshot_month', 'first'),
        avg_prb_utilisation_pct=('prb_utilisation_pct', 'mean'),
        p95_prb_utilisation_pct=('prb_utilisation_pct', lambda x: x.quantile(0.95)),
        max_prb_utilisation_pct=('prb_utilisation_pct', 'max'),
        avg_dl_throughput_mbps=('avg_dl_throughput_mbps', 'mean')
    ).reset_index()
    
    # Round for reporting clarity
    for col in ['avg_prb_utilisation_pct', 'p95_prb_utilisation_pct', 'max_prb_utilisation_pct', 'avg_dl_throughput_mbps']:
        df_agg[col] = df_agg[col].round(2)
        
    print(f"  -> Aggregated to {len(df_agg)} monthly cell records.")
    return df_agg

# ==============================================================================
# SUB-TASK 5.3: CAPACITY PROXY CLASSIFICATION
# ==============================================================================
def classify_capacity_proxy(df_agg):
    """Applies the 80% PRB hard threshold business rule."""
    print("\n[5.3] Applying 80% PRB capacity proxy business rule...")
    
    # OR logic: Constrained if P95 >= 80 OR Max >= 80
    is_constrained = (df_agg['p95_prb_utilisation_pct'] >= PRB_THRESHOLD) | \
                     (df_agg['max_prb_utilisation_pct'] >= PRB_THRESHOLD)
                     
    df_agg['current_capacity_proxy_status'] = np.where(is_constrained, 'Constrained', 'Available')
    
    constrained_count = (df_agg['current_capacity_proxy_status'] == 'Constrained').sum()
    available_count = (df_agg['current_capacity_proxy_status'] == 'Available').sum()
    
    print(f"  -> Classified {constrained_count} cells as 'Constrained'.")
    print(f"  -> Classified {available_count} cells as 'Available'.")
    return df_agg

# ==============================================================================
# SUB-TASK 5.4: FINAL ASSEMBLY, VALIDATION & PERSISTENCE
# ==============================================================================
def validate_and_persist(df_agg, engine):
    """Enforces schema, runs assertions, and writes to PostgreSQL."""
    print("\n[5.4] Validating schema and persisting to database...")
    
    # 1. Enforce Types
    df_agg['cell_id'] = df_agg['cell_id'].astype(str)
    df_agg['site_id'] = df_agg['site_id'].astype(str)
    df_agg['snapshot_month'] = pd.to_datetime(df_agg['snapshot_month']).dt.date
    df_agg['avg_prb_utilisation_pct'] = df_agg['avg_prb_utilisation_pct'].astype(float)
    df_agg['p95_prb_utilisation_pct'] = df_agg['p95_prb_utilisation_pct'].astype(float)
    df_agg['max_prb_utilisation_pct'] = df_agg['max_prb_utilisation_pct'].astype(float)
    df_agg['avg_dl_throughput_mbps'] = df_agg['avg_dl_throughput_mbps'].astype(float)
    df_agg['current_capacity_proxy_status'] = df_agg['current_capacity_proxy_status'].astype(str)
    
    # 2. Programmatic Assertions
    assertions = {
        "No nulls in any column": df_agg.isnull().sum().sum() == 0,
        "Unique cell_id (1 row per cell)": df_agg['cell_id'].is_unique,
        "PRB metrics within [0, 100]": (
            (df_agg['avg_prb_utilisation_pct'].between(0, 100)) &
            (df_agg['p95_prb_utilisation_pct'].between(0, 100)) &
            (df_agg['max_prb_utilisation_pct'].between(0, 100))
        ).all(),
        "Throughput is non-negative": (df_agg['avg_dl_throughput_mbps'] >= 0).all(),
        "Status is strictly Constrained/Available": df_agg['current_capacity_proxy_status'].isin(['Constrained', 'Available']).all(),
        "Single snapshot month": df_agg['snapshot_month'].nunique() == 1
    }
    
    failed_assertions = [k for k, v in assertions.items() if not v]
    if failed_assertions:
        raise ValueError(f"Validation failed for: {failed_assertions}")
        
    # 3. Persist to DB
    df_agg.to_sql(
        name='t3_cell_monthly_kpi',
        con=engine,
        schema=TARGET_SCHEMA,
        if_exists='replace',
        index=False,
        dtype={
            'cell_id': sqlalchemy.types.VARCHAR(50),
            'site_id': sqlalchemy.types.VARCHAR(50),
            'snapshot_month': sqlalchemy.types.DATE,
            'avg_prb_utilisation_pct': sqlalchemy.types.FLOAT,
            'p95_prb_utilisation_pct': sqlalchemy.types.FLOAT,
            'max_prb_utilisation_pct': sqlalchemy.types.FLOAT,
            'avg_dl_throughput_mbps': sqlalchemy.types.FLOAT,
            'current_capacity_proxy_status': sqlalchemy.types.VARCHAR(20)
        }
    )
    print(f"  -> Successfully persisted {len(df_agg)} rows to {TARGET_TABLE}.")
    return df_agg

# ==============================================================================
# EXECUTION REPORT GENERATOR
# ==============================================================================
def print_execution_report(df_daily, df_final):
    """Prints a comprehensive execution and business report."""
    print("\n" + "="*80)
    print(" "*15 + "STEP 5 EXECUTION REPORT: NETWORK KPI AGGREGATION")
    print("="*80)
    
    print("\n[1] OPERATIONS PERFORMED")
    print("  • Extracted daily RAN KPIs from cleaned_data.t3_ran_kpi_cell_daily")
    print("  • Validated temporal purity (snapshot_month = 2026-01-01)")
    print("  • Aggregated daily PRB and Throughput to monthly cell-level grain")
    print("  • Applied 80% PRB Hard Threshold (P95 OR Max) for capacity proxy")
    print(f"  • Persisted final table to {TARGET_TABLE}")
    
    print("\n[2] DATA VOLUME & PROCESSING STATS")
    print(f"  • Source Daily Rows Processed : {len(df_daily):,}")
    print(f" • Unique Cells in Source      : {df_daily['cell_id'].nunique():,}")
    print(f"  • Final Monthly Rows Output   : {len(df_final):,}")
    print(f"  • Avg Days per Cell           : {df_daily.groupby('cell_id')['kpi_date'].nunique().mean():.1f}")
    
    print("\n[3] AGGREGATION STATISTICS (Monthly Cell-Level)")
    print(f"  • Avg PRB Utilisation         : {df_final['avg_prb_utilisation_pct'].mean():.2f}%")
    print(f"  • P95 PRB Utilisation         : {df_final['p95_prb_utilisation_pct'].median():.2f}% (Median of P95s)")
    print(f"  • Max PRB Utilisation         : {df_final['max_prb_utilisation_pct'].max():.2f}% (Absolute Peak)")
    print(f"  • Avg DL Throughput           : {df_final['avg_dl_throughput_mbps'].mean():.2f} Mbps")
    
    print("\n[4] VALIDATION RESULTS")
    print("  • Temporal Purity (Jan 2026)    : PASSED")
    print("  • Critical Metric Nulls         : PASSED (0 nulls)")
    print("  • PRB Bounds [0-100]            : PASSED")
    print("  • Throughput Non-Negative       : PASSED")
    print("  • Grain Uniqueness (cell_id)    : PASSED")
    
    print("\n[5] CAPACITY PROXY DISTRIBUTION")
    constrained = (df_final['current_capacity_proxy_status'] == 'Constrained').sum()
    available = (df_final['current_capacity_proxy_status'] == 'Available').sum()
    total = len(df_final)
    print(f"  • Constrained Cells (>=80% PRB) : {constrained:,} ({constrained/total*100:.1f}%)")
    print(f"  • Available Cells (<80% PRB)    : {available:,} ({available/total*100:.1f}%)")
    
    print("\n[6] DETECTED ANOMALIES & EDGE CASES")
    low_data_cells = df_daily.groupby('cell_id')['kpi_date'].nunique()
    low_data_cells = low_data_cells[low_data_cells < 25]
    if len(low_data_cells) > 0:
        print(f"  • WARNING: {len(low_data_cells)} cells have < 25 days of data (P95 may be less stable).")
    else:
        print("  • No temporal data gaps detected. All cells have >= 25 days of data.")
        
    print("\n[7] BUSINESS INTERPRETATION")
    print("  • The 80% PRB threshold successfully isolates cells experiencing severe")
    print("    MAC scheduler contention during peak hours.")
    print("  • The 'OR' logic (P95 >= 80 OR Max >= 80) ensures a conservative stance:")
    print("    cells that hit the physical ceiling even once, or regularly during peaks,")
    print("    are blocked from FWA migration to protect mobile user QoS.")
    print("  • These 'Constrained' cells will trigger a Hard Stop (Score=0) in Step 9.")
    
    print("\n[8] READINESS FOR NEXT DEPENDENCY")
    print("  • Step 8 (ABT Construction): READY. Table is joined via T1.serving_cell_id.")
    print("  • Step 9 (Suitability Scoring): READY. Capacity flag is available for Hard Stops.")
    print("  • Step 14 (Capacity Simulation): READY. Baseline P95 is established.")
    print("="*80 + "\n")

# ==============================================================================
# MAIN EXECUTION PIPELINE
# ==============================================================================
def main():
    try:
        engine = get_db_engine()
        
        # Execute Sub-tasks
        df_daily = extract_and_validate_t3(engine)
        df_monthly = aggregate_monthly_kpis(df_daily)
        df_final = classify_capacity_proxy(df_monthly)
        df_final = validate_and_persist(df_final, engine)
        
        # Print Report
        print_execution_report(df_daily, df_final)
        
    except Exception as e:
        print(f"\n[CRITICAL ERROR] Pipeline halted: {str(e)}")
        sys.exit(1)

if __name__ == "__main__":
    main()
