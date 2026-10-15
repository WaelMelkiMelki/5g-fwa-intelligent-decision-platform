import pandas as pd
import numpy as np
from sqlalchemy import create_engine

DB_CONNECTION_STRING = __import__("os").environ["FWA_DB_URL"]
engine = create_engine(DB_CONNECTION_STRING)

# Query ABT eligible with cluster and suitability band
query_abt = """
    SELECT subscriber_id, dominant_serving_cell_id, monthly_total_gb, 
           p95_prb_utilisation_pct, avg_dl_throughput_mbps, fwa_suitability_score,
           cluster_id, fwa_suitability_band
    FROM cleaned_data.abt_subscriber_month
    WHERE fwa_suitability_score > 0
"""
df_abt = pd.read_sql(query_abt, engine)
print(f'ABT eligible: {len(df_abt):,}')
print()
print('Cluster distribution:')
print(df_abt['cluster_id'].value_counts().sort_index())
print()
print('Suitability band distribution:')
print(df_abt['fwa_suitability_band'].value_counts())
print()

# Query Step 14 for uplift
df14 = pd.read_sql('SELECT * FROM cleaned_data.step14_capacity_simulation', engine)

# Merge
df = df_abt.merge(df14[['subscriber_id', 'expected_additional_prb_proxy', 'offer_category', 'p95_prb_utilisation_pct']], on='subscriber_id', how='inner')
print(f'Merged: {len(df):,}')
print()

# Offer category distribution by cluster
print('Offer category by cluster:')
print(pd.crosstab(df['cluster_id'], df['offer_category']))
print()

# Suitability band by offer category
print('Suitability band by offer category:')
print(pd.crosstab(df['fwa_suitability_band'], df['offer_category']))
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

# Take-rate mapping from Step 13/15 documentation
# According to Appendix G: "Three migration waves: Wave 1 (top quartile, immediate), Wave 2 (remaining eligible), Wave 3 (capacity-dependent)"
# According to Step 15: Contact Now = top quartile (P75), Contact Later = remaining
# According to Step 13/14: Offer categories have multipliers

# Let's check if there's documented take-rate per cluster or suitability band
# From report: 
# Step 15 Appendix G: "Contact Now (5.9%): Top quartile of eligible, network-safe."
# But we see 25% Contact Now in Step 15 output (658/2629 = 25.03%)

print(f'\nContact Now rate: {25.03}%')
print(f'Contact Later rate: {74.97}%')
print(f'Excluded rate (from total 12412): {9783/12412*100:.2f}%')
