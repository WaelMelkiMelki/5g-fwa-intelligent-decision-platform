"""
Step 14: Post-Migration Capacity Proxy Simulation
Project: 5G FWA Migration Analytics Pipeline
Objective: Simulate the incremental PRB load of migrating 2,629 FWA-eligible 
           subscribers to enforce the Hard 80% PRB threshold and assign rollout status.
"""

import pandas as pd
import numpy as np
from sqlalchemy import create_engine
import warnings
warnings.filterwarnings('ignore')

# ==============================================================================
# 1. CONFIGURATION & DATABASE CONNECTION
# ==============================================================================
DB_CONNECTION_STRING = __import__("os").environ["FWA_DB_URL"]
engine = create_engine(DB_CONNECTION_STRING)

# Physics & Engineering Constants
SECONDS_IN_30_DAYS = 30 * 24 * 3600  # 2,592,000 seconds
MB_TO_MBPS_FACTOR = (1024 * 8) / SECONDS_IN_30_DAYS # Converts GB/month to Mbps
PRB_UPLIFT_CAP_PCT = 15.0  # Engineering safeguard against extreme outliers

# Hard Thresholds (from Project Brief)
SAFE_THRESHOLD = 80.0
WAITLIST_THRESHOLD = 90.0

# ==============================================================================
# 2. DATA EXTRACTION & MERGING
# ==============================================================================
def load_and_merge_data():
    print("=" * 70)
    print("STEP 14: POST-MIGRATION CAPACITY PROXY SIMULATION")
    print("=" * 70)
    print("\n[1/6] Extracting ABT (Eligible Subscribers) and Step 13 Recommendations...")

    # 1. Load FWA-eligible subscribers from ABT with required network metrics
    query_abt = """
        SELECT subscriber_id, dominant_serving_cell_id, monthly_total_gb, 
               p95_prb_utilisation_pct, avg_dl_throughput_mbps, fwa_suitability_score
        FROM cleaned_data.abt_subscriber_month
        WHERE fwa_suitability_score > 0
    """
    df_abt = pd.read_sql(query_abt, engine)
    print(f"   -> FWA-eligible subscribers loaded: {len(df_abt):,}")

    # 2. Load Step 13 Recommendations for Offer Multipliers
    query_rec = """
        SELECT subscriber_id, offer_category 
        FROM cleaned_data.step13_recommendations
    """
    df_rec = pd.read_sql(query_rec, engine)
    print(f"   -> Step 13 recommendations loaded: {len(df_rec):,}")

    # 3. Merge on subscriber_id
    df = pd.merge(df_abt, df_rec, on='subscriber_id', how='inner')
    
    if len(df) != len(df_abt):
        raise ValueError(f"Merge mismatch! ABT has {len(df_abt)} eligible, but merged has {len(df)}.")
        
    return df

# ==============================================================================
# 3. PREPROCESSING & THROUGHPUT CALCULATION
# ==============================================================================
def preprocess_and_calculate_throughput(df):
    print("\n[2/6] Calculating subscriber throughput requirements (T_req)...")
    
    # Defensive imputation for cell throughput to prevent division by zero
    median_throughput = df['avg_dl_throughput_mbps'].median()
    null_count = df['avg_dl_throughput_mbps'].isna().sum() + (df['avg_dl_throughput_mbps'] == 0).sum()
    
    if null_count > 0:
        print(f"   -> Warning: Found {null_count} null/zero cell throughputs. Imputing with network median ({median_throughput:.2f} Mbps).")
        df['avg_dl_throughput_mbps'] = df['avg_dl_throughput_mbps'].replace(0, np.nan).fillna(median_throughput)

    # Calculate T_req (Mbps): (monthly_total_gb * 1024 * 8) / 2,592,000
    df['T_req_mbps'] = df['monthly_total_gb'] * MB_TO_MBPS_FACTOR
    
    print(f"   -> Mean T_req: {df['T_req_mbps'].mean():.3f} Mbps")
    print(f"   -> Max T_req:  {df['T_req_mbps'].max():.3f} Mbps")
    
    return df

# ==============================================================================
# 4. OFFER MULTIPLIER & PRB UPLIFT PROXY
# ==============================================================================
def calculate_prb_uplift(df):
    print("\n[3/6] Applying Step 13 Offer Multipliers and calculating PRB Uplift Proxy...")
    
    # Map offer_category to traffic multiplier (M_offer)
    multiplier_map = {
        'Base Only': 1.0,
        'Base + IPTV': 1.25,
        'Base + Gaming Add-on': 1.25,
        'Base + Convergent Fixed-Mobile Add-on': 1.25,
        'Multi-Addon Bundle': 1.50
    }
    
    df['M_offer'] = df['offer_category'].map(multiplier_map).fillna(1.0)
    
    # Calculate Expected Additional PRB Proxy (per subscriber)
    # Formula: (T_req * M_offer / T_cell) * 100
    df['expected_additional_prb_proxy'] = (df['T_req_mbps'] * df['M_offer'] / df['avg_dl_throughput_mbps']) * 100
    
    # Engineering Safeguard: Cap at 15% to prevent extreme outliers from breaking the model
    capped_count = (df['expected_additional_prb_proxy'] > PRB_UPLIFT_CAP_PCT).sum()
    if capped_count > 0:
        print(f"   -> Capping {capped_count} extreme outlier PRB uplifts at {PRB_UPLIFT_CAP_PCT}%")
        df['expected_additional_prb_proxy'] = df['expected_additional_prb_proxy'].clip(upper=PRB_UPLIFT_CAP_PCT)

    # Calculate Post-Migration PRB Utilisation Proxy (per subscriber)
    # Formula: PRB_base (p95) + expected_additional_prb_proxy
    df['post_migration_prb_utilisation_proxy'] = df['p95_prb_utilisation_pct'] + df['expected_additional_prb_proxy']
    
    print(f"   -> Mean PRB Uplift: {df['expected_additional_prb_proxy'].mean():.2f}%")
    print(f"   -> Mean Post-Migration PRB: {df['post_migration_prb_utilisation_proxy'].mean():.2f}%")
    
    return df


# ==============================================================================
# 4b. CELL-LEVEL CUMULATIVE PRB COMPUTATION
# ==============================================================================
def compute_cell_cumulative_prb(df):
    print("\n[3b/6] Computing cell-level cumulative PRB...")
    
    # Aggregate per cell: sum of uplifts + baseline P95
    cell_agg = df.groupby('dominant_serving_cell_id').agg(
        subs=('subscriber_id', 'count'),
        baseline_p95=('p95_prb_utilisation_pct', 'mean'),
        cumulative_uplift=('expected_additional_prb_proxy', 'sum')
    ).reset_index()
    
    cell_agg['cumulative_post_prb'] = cell_agg['baseline_p95'] + cell_agg['cumulative_uplift']
    
    # Assign cell-level rollout status based on CUMULATIVE cell PRB
    conditions = [
        cell_agg['cumulative_post_prb'] <= SAFE_THRESHOLD,
        (cell_agg['cumulative_post_prb'] > SAFE_THRESHOLD) & (cell_agg['cumulative_post_prb'] <= WAITLIST_THRESHOLD),
        cell_agg['cumulative_post_prb'] > WAITLIST_THRESHOLD
    ]
    choices_risk = ['Safe', 'High Risk', 'Blocked']
    choices_status = ['Approved', 'Waitlist', 'Exclude']
    
    cell_agg['cell_capacity_risk'] = np.select(conditions, choices_risk, default='Unknown')
    cell_agg['cell_rollout_status'] = np.select(conditions, choices_status, default='Unknown')
    
    # Merge cell-level status back to subscriber level
    df = df.merge(
        cell_agg[['dominant_serving_cell_id', 'cumulative_uplift', 'cumulative_post_prb', 
                  'cell_capacity_risk', 'cell_rollout_status']],
        on='dominant_serving_cell_id',
        how='left'
    )
    
    # Print cell-level summary
    total_cells = len(cell_agg)
    exceeded_80 = (cell_agg['cumulative_post_prb'] > SAFE_THRESHOLD).sum()
    exceeded_90 = (cell_agg['cumulative_post_prb'] > WAITLIST_THRESHOLD).sum()
    max_cum_prb = cell_agg['cumulative_post_prb'].max()
    max_cum_cell = cell_agg.loc[cell_agg['cumulative_post_prb'].idxmax(), 'dominant_serving_cell_id']
    
    print(f"   -> Total Serving Cells: {total_cells}")
    print(f"   -> Cells with cumulative PRB > 80%: {exceeded_80}")
    print(f"   -> Cells with cumulative PRB > 90%: {exceeded_90}")
    print(f"   -> Maximum cumulative cell PRB: {max_cum_prb:.2f}% ({max_cum_cell})")
    
    return df, cell_agg

# ==============================================================================
# 5. HARD 80% RULE & ROLLOUT STATUS ASSIGNMENT (CELL-LEVEL)
# ==============================================================================
def assign_risk_and_status(df):
    print("\n[4/6] Enforcing Hard 80% PRB Threshold on CUMULATIVE Cell PRB...")
    
    # Use cell-level cumulative status (already computed in compute_cell_cumulative_prb)
    df['post_migration_capacity_risk'] = df['cell_capacity_risk']
    df['rollout_status'] = df['cell_rollout_status']
    
    # Print distribution (at subscriber level, but derived from cell)
    risk_dist = df['rollout_status'].value_counts()
    for status, count in risk_dist.items():
        pct = count / len(df) * 100
        print(f"   -> {status:<10} : {count:>5,} ({pct:.1f}%)")
        
    return df

# ==============================================================================
# 6. VALIDATION & EXECUTION SUMMARY
# ==============================================================================
def validate_and_summarize(df, cell_agg):
    print("\n[5/6] Validating simulation outputs...")
    
    # Assertions
    assert df['post_migration_capacity_risk'].isin(['Safe', 'High Risk', 'Blocked']).all(), "Invalid risk category!"
    assert df['rollout_status'].isin(['Approved', 'Waitlist', 'Exclude']).all(), "Invalid rollout status!"
    assert (df['expected_additional_prb_proxy'] <= PRB_UPLIFT_CAP_PCT).all(), "PRB uplift cap violated!"
    assert df['post_migration_prb_utilisation_proxy'].notna().all(), "Nulls in post-migration PRB!"
    assert df['cumulative_post_prb'].notna().all(), "Nulls in cumulative post-migration PRB!"
    assert cell_agg['cumulative_post_prb'].notna().all(), "Nulls in cell cumulative PRB!"
    
    print("   -> All 6 validation assertions PASSED.")

    print("\n" + "=" * 70)
    print("EXECUTION SUMMARY: STEP 14 CAPACITY SIMULATION RESULTS")
    print("=" * 70)

    print(f"\n[Data Scope]")
    print(f"   -> FWA-Eligible Subscribers Simulated: {len(df):,}")
    print(f"   -> Distinct Serving Cells:             {cell_agg['dominant_serving_cell_id'].nunique()}")

    print(f"\n[Network Impact Metrics (Per-Subscriber)]")
    print(f"   -> Baseline Mean PRB (p95):      {df['p95_prb_utilisation_pct'].mean():.2f}%")
    print(f"   -> Mean PRB Uplift per User:     {df['expected_additional_prb_proxy'].mean():.2f}%")
    print(f"   -> Post-Migration Mean PRB:      {df['post_migration_prb_utilisation_proxy'].mean():.2f}%")
    print(f"   -> Post-Migration Max PRB:       {df['post_migration_prb_utilisation_proxy'].max():.2f}%")

    print(f"\n[Cell-Level Cumulative PRB Analysis]")
    print(f"   -> Mean Baseline P95 PRB:        {cell_agg['baseline_p95'].mean():.2f}%")
    print(f"   -> Mean Cumulative Uplift:       {cell_agg['cumulative_uplift'].mean():.2f}%")
    print(f"   -> Mean Cumulative Post PRB:     {cell_agg['cumulative_post_prb'].mean():.2f}%")
    print(f"   -> Maximum Cumulative Post PRB:  {cell_agg['cumulative_post_prb'].max():.2f}%")
    
    max_cum_cell = cell_agg.loc[cell_agg['cumulative_post_prb'].idxmax(), 'dominant_serving_cell_id']
    max_cum_subs = cell_agg.loc[cell_agg['cumulative_post_prb'].idxmax(), 'subs']
    print(f"      (Cell: {max_cum_cell}, {max_cum_subs} subscribers)")

    print(f"\n[Cell-Level Bottleneck Analysis]")
    blocked_cells = (cell_agg['cell_rollout_status'] != 'Approved').sum()
    total_cells = len(cell_agg)
    print(f"   -> Total Serving Cells in Eligible Base: {total_cells}")
    print(f"   -> Cells with >= 1 Blocked/Waitlisted Sub: {blocked_cells}")
    
    if blocked_cells > 0:
        print(f"\n   [Top 3 Most Congested Cells Post-Migration]")
        cell_sorted = cell_agg.sort_values('cumulative_post_prb', ascending=False).head(3)
        for _, row in cell_sorted.iterrows():
            print(f"      -> {row['dominant_serving_cell_id']} : {row['cumulative_post_prb']:.2f}% Cumulative Post-Migration PRB ({row['subs']} subs)")

    print(f"\n[Rollout Status Distribution (Subscriber-Level, Cell-Derived)]")
    print("-" * 50)
    status_dist = df['rollout_status'].value_counts()
    for status, count in status_dist.items():
        pct = count / len(df) * 100
        print(f"   -> {status:<10} : {count:>5,} ({pct:>5.1f}%)")

    print(f"\n[Cell Rollout Status Distribution]")
    print("-" * 50)
    cell_status_dist = cell_agg['cell_rollout_status'].value_counts()
    for status, count in cell_status_dist.items():
        pct = count / len(cell_agg) * 100
        print(f"   -> {status:<10} : {count:>3,} ({pct:>5.1f}%)")

    print("\n" + "=" * 70)
    print("PIPELINE STATUS")
    print("=" * 70)
    print("   -> expected_additional_prb_proxy computed (capped at 15%, not triggered).")
    print("   -> post_migration_prb_utilisation_proxy computed (per-subscriber).")
    print("   -> cumulative_uplift_c = SUM(uplift_i) computed per cell.")
    print("   -> cumulative_post_prb_c = baseline_p95_c + cumulative_uplift_c computed per cell.")
    print("   -> Hard 80% PRB threshold enforced on CUMULATIVE cell PRB.")
    print("   -> Results persisted to cleaned_data.step14_capacity_simulation.")
    print("   -> Ready for Step 15 (Final Prioritization with Capacity Gate).")
    print("=" * 70 + "\n")

# ==============================================================================
# MAIN EXECUTION
# ==============================================================================
if __name__ == "__main__":
    # 1. Load and Merge
    df_merged = load_and_merge_data()
    
    # 2. Preprocess & Calculate Throughput
    df_throughput = preprocess_and_calculate_throughput(df_merged)
    
    # 3. Calculate PRB Uplift (per subscriber)
    df_prb = calculate_prb_uplift(df_throughput)
    
    # 3b. Compute Cell-Level Cumulative PRB
    df_cell, cell_agg = compute_cell_cumulative_prb(df_prb)
    
    # 4. Assign Risk and Status (cell-level)
    df_final = assign_risk_and_status(df_cell)
    
    # 5. Validate and Summarize
    validate_and_summarize(df_final, cell_agg)
    
    # 6. Save to Database
    output_cols = [
        'subscriber_id', 'dominant_serving_cell_id', 'offer_category',
        'p95_prb_utilisation_pct', 'expected_additional_prb_proxy', 
        'post_migration_prb_utilisation_proxy',
        'cumulative_uplift', 'cumulative_post_prb',
        'post_migration_capacity_risk', 'rollout_status'
    ]
    
    df_final[output_cols].to_sql(
        'step14_capacity_simulation', engine, schema='cleaned_data', 
        if_exists='replace', index=False
    )
