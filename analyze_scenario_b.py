import pandas as pd
import numpy as np
from sqlalchemy import create_engine

DB_CONNECTION_STRING = __import__("os").environ["FWA_DB_URL"]
engine = create_engine(DB_CONNECTION_STRING)

# Query Step 15 for cluster/suitability info
df15 = pd.read_sql('SELECT subscriber_id, cluster_id, fwa_suitability_band, fwa_suitability_score, campaign_action FROM cleaned_data.step15_final_campaign_list', engine)
df_eligible = df15[df15['fwa_suitability_score'] > 0]

# Query Step 14 for uplift
df14 = pd.read_sql('SELECT * FROM cleaned_data.step14_capacity_simulation', engine)

# Merge
df = df_eligible.merge(df14, on='subscriber_id', how='inner')
print(f'Merged: {len(df):,}')
print()

# Mean uplift by cluster
print('Mean uplift by cluster:')
for c in sorted(df['cluster_id'].unique()):
    sub = df[df['cluster_id'] == c]
    print(f'  Cluster {c}: {len(sub)} subs, mean uplift={sub["expected_additional_prb_proxy"].mean()*100:.6f}%, sum={sub["expected_additional_prb_proxy"].sum():.4f}%')

print()
# Mean uplift by suitability band
print('Mean uplift by suitability band:')
for b in sorted(df['fwa_suitability_band'].unique()):
    sub = df[df['fwa_suitability_band'] == b]
    print(f'  {b}: {len(sub)} subs, mean uplift={sub["expected_additional_prb_proxy"].mean()*100:.6f}%, sum={sub["expected_additional_prb_proxy"].sum():.4f}%')

# Take-rate mapping for Scenario B
# Using Contact Now rates per cluster as take-rates
print('\n--- SCENARIO B: Cluster-based take-rates ---')
take_rates_cluster = {}
for c in sorted(df['cluster_id'].unique()):
    sub = df[df['cluster_id'] == c]
    cn = sub[sub['campaign_action'] == 'Contact Now']
    rate = len(cn) / len(sub)
    take_rates_cluster[c] = rate
    print(f'  Cluster {c}: take-rate = {rate:.4f} ({len(cn)}/{len(sub)})')

print('\nTake-rate mapping (cluster):', take_rates_cluster)

# Apply take-rates to compute expected uplift
df['take_rate_cluster'] = df['cluster_id'].map(take_rates_cluster)
df['expected_uplift_cluster'] = df['take_rate_cluster'] * df['expected_additional_prb_proxy']

# Cumulative per cell for cluster-based Scenario B
cell_b_cluster = df.groupby('dominant_serving_cell_id').agg(
    subs=('subscriber_id', 'count'),
    baseline_p95=('p95_prb_utilisation_pct', 'mean'),
    cum_uplift=('expected_uplift_cluster', 'sum')
).reset_index()
cell_b_cluster['cumulative_post_prb'] = cell_b_cluster['baseline_p95'] + cell_b_cluster['cum_uplift']
cell_b_cluster = cell_b_cluster.sort_values('cumulative_post_prb', ascending=False)
print(f'\nCluster-based Scenario B cumulative cell PRB (top 15):')
print(cell_b_cluster.head(15).to_string(index=False))
print(f'Cells exceeding 80%: {(cell_b_cluster["cumulative_post_prb"] > 80).sum()}')
print(f'Cells exceeding 90%: {(cell_b_cluster["cumulative_post_prb"] > 90).sum()}')

# Total expected subscribers
total_expected = df['take_rate_cluster'].sum()
print(f'\nTotal expected migrating subscribers (cluster take-rates): {total_expected:.0f}')

# Suitability band take-rates
print('\n--- SCENARIO B: Suitability-band take-rates ---')
take_rates_band = {}
for b in sorted(df['fwa_suitability_band'].unique()):
    sub = df[df['fwa_suitability_band'] == b]
    cn = sub[sub['campaign_action'] == 'Contact Now']
    rate = len(cn) / len(sub)
    take_rates_band[b] = rate
    print(f'  {b}: take-rate = {rate:.4f} ({len(cn)}/{len(sub)})')

df['take_rate_band'] = df['fwa_suitability_band'].map(take_rates_band)
df['expected_uplift_band'] = df['take_rate_band'] * df['expected_additional_prb_proxy']

cell_b_band = df.groupby('dominant_serving_cell_id').agg(
    subs=('subscriber_id', 'count'),
    baseline_p95=('p95_prb_utilisation_pct', 'mean'),
    cum_uplift=('expected_uplift_band', 'sum')
).reset_index()
cell_b_band['cumulative_post_prb'] = cell_b_band['baseline_p95'] + cell_b_band['cum_uplift']
cell_b_band = cell_b_band.sort_values('cumulative_post_prb', ascending=False)
print(f'\nBand-based Scenario B cumulative cell PRB (top 15):')
print(cell_b_band.head(15).to_string(index=False))
print(f'Cells exceeding 80%: {(cell_b_band["cumulative_post_prb"] > 80).sum()}')
print(f'Cells exceeding 90%: {(cell_b_band["cumulative_post_prb"] > 90).sum()}')

total_expected_band = df['take_rate_band'].sum()
print(f'\nTotal expected migrating subscribers (band take-rates): {total_expected_band:.0f}')
