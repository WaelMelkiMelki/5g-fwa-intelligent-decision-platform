import pandas as pd
import numpy as np
from sqlalchemy import create_engine

DB_CONNECTION_STRING = __import__("os").environ["FWA_DB_URL"]
engine = create_engine(DB_CONNECTION_STRING)

# Query ABT eligible
query_abt = """
    SELECT subscriber_id, dominant_serving_cell_id, monthly_total_gb, 
           p95_prb_utilisation_pct, avg_dl_throughput_mbps, fwa_suitability_score
    FROM cleaned_data.abt_subscriber_month
    WHERE fwa_suitability_score > 0
"""
df_abt = pd.read_sql(query_abt, engine)

# Query Step 13 for offer category
df_rec = pd.read_sql('SELECT subscriber_id, offer_category FROM cleaned_data.step13_recommendations', engine)

# Merge
df = df_abt.merge(df_rec, on='subscriber_id', how='inner')
print(f'Merged: {len(df):,}')

# Constants
MB_TO_MBPS_FACTOR = (1024 * 8) / (30 * 24 * 3600)
multiplier_map = {
    'Base Only': 1.0,
    'Base + IPTV': 1.25,
    'Base + Gaming Add-on': 1.25,
    'Base + Convergent Fixed-Mobile Add-on': 1.25,
    'Multi-Addon Bundle': 1.50
}

# Compute raw uncapped uplift (reproduce Step 14 logic)
df['T_req_mbps'] = df['monthly_total_gb'] * MB_TO_MBPS_FACTOR
df['M_offer'] = df['offer_category'].map(multiplier_map).fillna(1.0)

# Check for zero/null throughput
median_throughput = df['avg_dl_throughput_mbps'].median()
df['avg_dl_throughput_mbps'] = df['avg_dl_throughput_mbps'].replace(0, np.nan).fillna(median_throughput)

df['raw_uplift'] = (df['T_req_mbps'] * df['M_offer'] / df['avg_dl_throughput_mbps']) * 100
df['capped_uplift'] = df['raw_uplift'].clip(upper=15.0)
df['post_migration_prb'] = df['p95_prb_utilisation_pct'] + df['capped_uplift']

print(f'Raw uplift > 15%: {(df["raw_uplift"] > 15).sum()} subscribers')
print(f'Max raw uplift: {df["raw_uplift"].max():.6f}%')
print(f'Mean raw uplift: {df["raw_uplift"].mean()*100:.6f}%')
print(f'Mean capped uplift: {df["capped_uplift"].mean()*100:.6f}%')
print(f'Sum raw uplift: {df["raw_uplift"].sum():.6f}%')
print(f'Sum capped uplift: {df["capped_uplift"].sum():.6f}%')
print()

# Sensitivity: No cap
df['post_migration_no_cap'] = df['p95_prb_utilisation_pct'] + df['raw_uplift']
cell_no_cap = df.groupby('dominant_serving_cell_id').agg(
    subs=('subscriber_id', 'count'),
    baseline_p95=('p95_prb_utilisation_pct', 'mean'),
    cum_uplift=('raw_uplift', 'sum')
).reset_index()
cell_no_cap['cumulative_post_prb'] = cell_no_cap['baseline_p95'] + cell_no_cap['cum_uplift']
cell_no_cap = cell_no_cap.sort_values('cumulative_post_prb', ascending=False)
print('--- SENSITIVITY: NO 15% CAP ---')
print(f'Cells exceeding 80%: {(cell_no_cap["cumulative_post_prb"] > 80).sum()}')
print(f'Cells exceeding 90%: {(cell_no_cap["cumulative_post_prb"] > 90).sum()}')
print(f'Max cumulative PRB: {cell_no_cap["cumulative_post_prb"].max():.6f}%')
print(f'Top cell: {cell_no_cap.iloc[0]["dominant_serving_cell_id"]} at {cell_no_cap.iloc[0]["cumulative_post_prb"]:.6f}%')
print()

# Sensitivity: Peak-demand factor 1.2
df['T_req_1.2'] = df['T_req_mbps'] * 1.2
df['raw_uplift_1.2'] = (df['T_req_1.2'] * df['M_offer'] / df['avg_dl_throughput_mbps']) * 100
df['capped_uplift_1.2'] = df['raw_uplift_1.2'].clip(upper=15.0)
df['post_migration_1.2'] = df['p95_prb_utilisation_pct'] + df['capped_uplift_1.2']

cell_1_2 = df.groupby('dominant_serving_cell_id').agg(
    subs=('subscriber_id', 'count'),
    baseline_p95=('p95_prb_utilisation_pct', 'mean'),
    cum_uplift=('capped_uplift_1.2', 'sum')
).reset_index()
cell_1_2['cumulative_post_prb'] = cell_1_2['baseline_p95'] + cell_1_2['cum_uplift']
cell_1_2 = cell_1_2.sort_values('cumulative_post_prb', ascending=False)
print('--- SENSITIVITY: PEAK-DEMAND FACTOR 1.2 (capped at 15%) ---')
print(f'Cells exceeding 80%: {(cell_1_2["cumulative_post_prb"] > 80).sum()}')
print(f'Cells exceeding 90%: {(cell_1_2["cumulative_post_prb"] > 90).sum()}')
print(f'Max cumulative PRB: {cell_1_2["cumulative_post_prb"].max():.6f}%')
print()

# Sensitivity: Peak-demand factor 1.5
df['T_req_1.5'] = df['T_req_mbps'] * 1.5
df['raw_uplift_1.5'] = (df['T_req_1.5'] * df['M_offer'] / df['avg_dl_throughput_mbps']) * 100
df['capped_uplift_1.5'] = df['raw_uplift_1.5'].clip(upper=15.0)
df['post_migration_1.5'] = df['p95_prb_utilisation_pct'] + df['capped_uplift_1.5']

cell_1_5 = df.groupby('dominant_serving_cell_id').agg(
    subs=('subscriber_id', 'count'),
    baseline_p95=('p95_prb_utilisation_pct', 'mean'),
    cum_uplift=('capped_uplift_1.5', 'sum')
).reset_index()
cell_1_5['cumulative_post_prb'] = cell_1_5['baseline_p95'] + cell_1_5['cum_uplift']
cell_1_5 = cell_1_5.sort_values('cumulative_post_prb', ascending=False)
print('--- SENSITIVITY: PEAK-DEMAND FACTOR 1.5 (capped at 15%) ---')
print(f'Cells exceeding 80%: {(cell_1_5["cumulative_post_prb"] > 80).sum()}')
print(f'Cells exceeding 90%: {(cell_1_5["cumulative_post_prb"] > 90).sum()}')
print(f'Max cumulative PRB: {cell_1_5["cumulative_post_prb"].max():.6f}%')
print()

# Sensitivity: Peak-demand 1.2, no cap
df['raw_uplift_1.2_nocap'] = (df['T_req_1.2'] * df['M_offer'] / df['avg_dl_throughput_mbps']) * 100
df['post_migration_1.2_nocap'] = df['p95_prb_utilisation_pct'] + df['raw_uplift_1.2_nocap']

cell_1_2_nocap = df.groupby('dominant_serving_cell_id').agg(
    subs=('subscriber_id', 'count'),
    baseline_p95=('p95_prb_utilisation_pct', 'mean'),
    cum_uplift=('raw_uplift_1.2_nocap', 'sum')
).reset_index()
cell_1_2_nocap['cumulative_post_prb'] = cell_1_2_nocap['baseline_p95'] + cell_1_2_nocap['cum_uplift']
cell_1_2_nocap = cell_1_2_nocap.sort_values('cumulative_post_prb', ascending=False)
print('--- SENSITIVITY: PEAK-DEMAND FACTOR 1.2, NO CAP ---')
print(f'Cells exceeding 80%: {(cell_1_2_nocap["cumulative_post_prb"] > 80).sum()}')
print(f'Cells exceeding 90%: {(cell_1_2_nocap["cumulative_post_prb"] > 90).sum()}')
print(f'Max cumulative PRB: {cell_1_2_nocap["cumulative_post_prb"].max():.6f}%')
print()

# Sensitivity: Peak-demand 1.5, no cap
df['raw_uplift_1.5_nocap'] = (df['T_req_1.5'] * df['M_offer'] / df['avg_dl_throughput_mbps']) * 100
df['post_migration_1.5_nocap'] = df['p95_prb_utilisation_pct'] + df['raw_uplift_1.5_nocap']

cell_1_5_nocap = df.groupby('dominant_serving_cell_id').agg(
    subs=('subscriber_id', 'count'),
    baseline_p95=('p95_prb_utilisation_pct', 'mean'),
    cum_uplift=('raw_uplift_1.5_nocap', 'sum')
).reset_index()
cell_1_5_nocap['cumulative_post_prb'] = cell_1_5_nocap['baseline_p95'] + cell_1_5_nocap['cum_uplift']
cell_1_5_nocap = cell_1_5_nocap.sort_values('cumulative_post_prb', ascending=False)
print('--- SENSITIVITY: PEAK-DEMAND FACTOR 1.5, NO CAP ---')
print(f'Cells exceeding 80%: {(cell_1_5_nocap["cumulative_post_prb"] > 80).sum()}')
print(f'Cells exceeding 90%: {(cell_1_5_nocap["cumulative_post_prb"] > 90).sum()}')
print(f'Max cumulative PRB: {cell_1_5_nocap["cumulative_post_prb"].max():.6f}%')
print()

# Top 5 cells for 1.5 no cap
print('Top 5 cells for 1.5 no cap:')
print(cell_1_5_nocap.head(5).to_string(index=False))
