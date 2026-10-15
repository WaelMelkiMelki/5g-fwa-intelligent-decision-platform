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
print()

# Campaign actions for eligible
print('Campaign action distribution (eligible):')
print(df_eligible['campaign_action'].value_counts())
print()

# Contact Now
contact_now = df_eligible[df_eligible['campaign_action'] == 'Contact Now']
print(f'Contact Now: {len(contact_now):,}')
print(f'Contact Now percent: {len(contact_now)/len(df_eligible)*100:.2f}%')
print()

# Contact Later
contact_later = df_eligible[df_eligible['campaign_action'] == 'Contact Later']
print(f'Contact Later: {len(contact_later):,}')
print(f'Contact Later percent: {len(contact_later)/len(df_eligible)*100:.2f}%')
print()

# Priority score threshold
p75 = df_eligible['final_priority_score'].quantile(0.75)
print(f'P75 final_priority_score: {p75:.2f}')

# Check what columns Contact Now has
print(f'\nContact Now columns check:')
print(f'  post_migration_capacity_risk: {contact_now["post_migration_capacity_risk"].unique()}')
print(f'  rollout_status: {contact_now["rollout_status"].unique()}')
print(f'  dominant_serving_cell_id: {contact_now["dominant_serving_cell_id"].nunique()} distinct cells')
print(f'  Mean post_migration_prb_utilisation_proxy: {contact_now["post_migration_prb_utilisation_proxy"].mean():.4f}%')
print(f'  Max post_migration_prb_utilisation_proxy: {contact_now["post_migration_prb_utilisation_proxy"].max():.4f}%')
print(f'  Mean expected_additional_prb_proxy: {contact_now["expected_additional_prb_proxy"].mean()*100:.6f}%')
print(f'  Sum expected_additional_prb_proxy: {contact_now["expected_additional_prb_proxy"].sum():.6f}%')

# Cumulative for Contact Now
cn_cell = contact_now.groupby('dominant_serving_cell_id').agg(
    subs=('subscriber_id', 'count'),
    baseline_p95=('p95_prb_utilisation_pct', 'mean'),
    cum_uplift=('expected_additional_prb_proxy', 'sum'),
    max_post_prb=('post_migration_prb_utilisation_proxy', 'max')
).reset_index()
cn_cell['cumulative_post_prb'] = cn_cell['baseline_p95'] + cn_cell['cum_uplift']
cn_cell = cn_cell.sort_values('cumulative_post_prb', ascending=False)
print(f'\nContact Now cumulative cell PRB (top 10):')
print(cn_cell.head(10).to_string(index=False))
print(f'Contact Now cells exceeding 80%: {(cn_cell["cumulative_post_prb"] > 80).sum()}')
print(f'Contact Now cells exceeding 90%: {(cn_cell["cumulative_post_prb"] > 90).sum()}')

# Contact Later
cl_cell = contact_later.groupby('dominant_serving_cell_id').agg(
    subs=('subscriber_id', 'count'),
    baseline_p95=('p95_prb_utilisation_pct', 'mean'),
    cum_uplift=('expected_additional_prb_proxy', 'sum'),
    max_post_prb=('post_migration_prb_utilisation_proxy', 'max')
).reset_index()
cl_cell['cumulative_post_prb'] = cl_cell['baseline_p95'] + cl_cell['cum_uplift']
cl_cell = cl_cell.sort_values('cumulative_post_prb', ascending=False)
print(f'\nContact Later cumulative cell PRB (top 10):')
print(cl_cell.head(10).to_string(index=False))
print(f'Contact Later cells exceeding 80%: {(cl_cell["cumulative_post_prb"] > 80).sum()}')

# Excluded (from eligible - should be 0 since eligible means score > 0)
excl = df_eligible[df_eligible['campaign_action'] == 'Exclude']
print(f'\nExcluded from eligible: {len(excl):,}')

# Get Contact Now subscriber IDs for joining with Step 14
cn_ids = contact_now['subscriber_id'].tolist()
print(f'\nContact Now IDs: {cn_ids[:10]}...')
