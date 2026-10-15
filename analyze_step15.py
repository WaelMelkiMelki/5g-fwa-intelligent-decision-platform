import pandas as pd
import numpy as np
from sqlalchemy import create_engine

DB_CONNECTION_STRING = __import__("os").environ["FWA_DB_URL"]
engine = create_engine(DB_CONNECTION_STRING)

# Query Step 15 final prioritization results
df15 = pd.read_sql('SELECT * FROM cleaned_data.step15_final_prioritization', engine)
print(f'Step 15 rows: {len(df15):,}')
print()
print('Campaign action distribution (all):')
print(df15['campaign_action'].value_counts())
print()

# Filter to only eligible subscribers (2,629)
df_eligible = df15[df15['fwa_suitability_score'] > 0]
print(f'Eligible subscribers (fwa_suitability_score > 0): {len(df_eligible):,}')
print('Campaign action distribution (eligible only):')
print(df_eligible['campaign_action'].value_counts())
print()

# Contact Now
contact_now = df_eligible[df_eligible['campaign_action'] == 'Contact Now']
print(f'Contact Now subscribers: {len(contact_now):,}')
print(f'Contact Now percent: {len(contact_now)/len(df_eligible)*100:.2f}%')
print()

# Contact Later
contact_later = df_eligible[df_eligible['campaign_action'] == 'Contact Later']
print(f'Contact Later subscribers: {len(contact_later):,}')
print(f'Contact Later percent: {len(contact_later)/len(df_eligible)*100:.2f}%')
print()

# Waitlist
waitlist = df_eligible[df_eligible['campaign_action'] == 'Waitlist']
print(f'Waitlist subscribers: {len(waitlist):,}')

# Excluded
excluded = df_eligible[df_eligible['campaign_action'] == 'Excluded']
print(f'Excluded subscribers: {len(excluded):,}')

# Manual Review
manual = df_eligible[df_eligible['campaign_action'] == 'Manual Review']
print(f'Manual Review subscribers: {len(manual):,}')

print()
# Check priority score threshold
p75 = df_eligible['final_priority_score'].quantile(0.75)
print(f'P75 priority score: {p75:.2f}')
threshold_mask = df_eligible['final_priority_score'] >= p75
print(f'Subs >= P75 threshold: {threshold_mask.sum():,}')
print(f'Contact Now count: {len(contact_now):,}')

# Get Contact Now subscriber IDs
cn_ids = contact_now['subscriber_id'].tolist()
print(f'\nContact Now IDs sample: {cn_ids[:10]}')
