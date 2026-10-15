import pandas as pd
import numpy as np
from sqlalchemy import create_engine

DB_CONNECTION_STRING = __import__("os").environ["FWA_DB_URL"]
engine = create_engine(DB_CONNECTION_STRING)

# Query Step 15 final campaign list
df15 = pd.read_sql('SELECT * FROM cleaned_data.step15_final_campaign_list', engine)

# Filter to eligible only
df_eligible = df15[df15['fwa_suitability_score'] > 0]
print(f'Eligible subscribers: {len(df_eligible):,}')

# Contact Now
contact_now = df_eligible[df_eligible['campaign_action'] == 'Contact Now']
cn_ids = contact_now['subscriber_id'].tolist()
print(f'Contact Now: {len(cn_ids):,}')

# Contact Later
contact_later = df_eligible[df_eligible['campaign_action'] == 'Contact Later']
cl_ids = contact_later['subscriber_id'].tolist()
print(f'Contact Later: {len(cl_ids):,}')

# Query Step 14 for cell info and uplift
df14 = pd.read_sql('SELECT * FROM cleaned_data.step14_capacity_simulation', engine)

# Merge Contact Now with Step 14
cn_14 = df14[df14['subscriber_id'].isin(cn_ids)]
print(f'\nContact Now in Step 14: {len(cn_14):,}')
print(f'  Distinct cells: {cn_14["dominant_serving_cell_id"].nunique()}')
print(f'  Mean post_migration_prb: {cn_14["post_migration_prb_utilisation_proxy"].mean():.4f}%')
print(f'  Max post_migration_prb: {cn_14["post_migration_prb_utilisation_proxy"].max():.4f}%')
print(f'  Sum uplift: {cn_14["expected_additional_prb_proxy"].sum():.6f}%')
print(f'  Mean uplift: {cn_14["expected_additional_prb_proxy"].mean()*100:.6f}%')

# Cumulative for Contact Now
cn_cell = cn_14.groupby('dominant_serving_cell_id').agg(
    subs=('subscriber_id', 'count'),
    baseline_p95=('p95_prb_utilisation_pct', 'mean'),
    cum_uplift=('expected_additional_prb_proxy', 'sum'),
    max_post_prb=('post_migration_prb_utilisation_proxy', 'max')
).reset_index()
cn_cell['cumulative_post_prb'] = cn_cell['baseline_p95'] + cn_cell['cum_uplift']
cn_cell = cn_cell.sort_values('cumulative_post_prb', ascending=False)
print(f'\nContact Now cumulative cell PRB (all):')
print(cn_cell.to_string(index=False))
print(f'Contact Now cells exceeding 80%: {(cn_cell["cumulative_post_prb"] > 80).sum()}')
print(f'Contact Now cells exceeding 90%: {(cn_cell["cumulative_post_prb"] > 90).sum()}')

# Contact Later
cl_14 = df14[df14['subscriber_id'].isin(cl_ids)]
print(f'\nContact Later in Step 14: {len(cl_14):,}')
print(f'  Distinct cells: {cl_14["dominant_serving_cell_id"].nunique()}')
print(f'  Sum uplift: {cl_14["expected_additional_prb_proxy"].sum():.6f}%')

# Cumulative for Contact Later
cl_cell = cl_14.groupby('dominant_serving_cell_id').agg(
    subs=('subscriber_id', 'count'),
    baseline_p95=('p95_prb_utilisation_pct', 'mean'),
    cum_uplift=('expected_additional_prb_proxy', 'sum'),
    max_post_prb=('post_migration_prb_utilisation_proxy', 'max')
).reset_index()
cl_cell['cumulative_post_prb'] = cl_cell['baseline_p95'] + cl_cell['cum_uplift']
cl_cell = cl_cell.sort_values('cumulative_post_prb', ascending=False)
print(f'\nContact Later cumulative cell PRB (top 15):')
print(cl_cell.head(15).to_string(index=False))
print(f'Contact Later cells exceeding 80%: {(cl_cell["cumulative_post_prb"] > 80).sum()}')

# Combined Contact Now + Contact Later (Scenario B)
both_ids = cn_ids + cl_ids
both_14 = df14[df14['subscriber_id'].isin(both_ids)]
print(f'\nCombined (Contact Now + Later): {len(both_14):,}')
both_cell = both_14.groupby('dominant_serving_cell_id').agg(
    subs=('subscriber_id', 'count'),
    baseline_p95=('p95_prb_utilisation_pct', 'mean'),
    cum_uplift=('expected_additional_prb_proxy', 'sum'),
    max_post_prb=('post_migration_prb_utilisation_proxy', 'max')
).reset_index()
both_cell['cumulative_post_prb'] = both_cell['baseline_p95'] + both_cell['cum_uplift']
both_cell = both_cell.sort_values('cumulative_post_prb', ascending=False)
print(f'Combined cumulative cell PRB (top 15):')
print(both_cell.head(15).to_string(index=False))
print(f'Combined cells exceeding 80%: {(both_cell["cumulative_post_prb"] > 80).sum()}')
print(f'Combined cells exceeding 90%: {(both_cell["cumulative_post_prb"] > 90).sum()}')
