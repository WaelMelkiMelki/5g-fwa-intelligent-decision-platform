import pandas as pd
import numpy as np
from sqlalchemy import create_engine

DB_CONNECTION_STRING = __import__("os").environ["FWA_DB_URL"]
engine = create_engine(DB_CONNECTION_STRING)

# Query Step 14 capacity simulation results
df14 = pd.read_sql('SELECT * FROM cleaned_data.step14_capacity_simulation', engine)
print(f'Step 14 rows: {len(df14):,}')
print()

# Cumulative per cell
cell_cum = df14.groupby('dominant_serving_cell_id').agg(
    subs=('subscriber_id', 'count'),
    baseline_p95=('p95_prb_utilisation_pct', 'mean'),
    cum_uplift=('expected_additional_prb_proxy', 'sum'),
    max_post_prb=('post_migration_prb_utilisation_proxy', 'max'),
    mean_post_prb=('post_migration_prb_utilisation_proxy', 'mean')
).reset_index()
cell_cum['cumulative_post_prb'] = cell_cum['baseline_p95'] + cell_cum['cum_uplift']
cell_cum = cell_cum.sort_values('cumulative_post_prb', ascending=False)

print('Cumulative cell PRB (top 15):')
print(cell_cum.head(15).to_string(index=False))
print()
exceed_80 = (cell_cum['cumulative_post_prb'] > 80).sum()
exceed_90 = (cell_cum['cumulative_post_prb'] > 90).sum()
print(f'Cells exceeding 80% cumulative: {exceed_80}')
print(f'Cells exceeding 90% cumulative: {exceed_90}')
print()

# Show CELL_TN_0125 detail
cell_0125 = df14[df14['dominant_serving_cell_id'] == 'CELL_TN_0125']
print('CELL_TN_0125 detail:')
print(f'  Candidate count: {len(cell_0125)}')
print(f'  Baseline P95 PRB (mean): {cell_0125["p95_prb_utilisation_pct"].mean():.4f}')
print(f'  Baseline P95 PRB (each): {cell_0125["p95_prb_utilisation_pct"].unique()}')
print(f'  Each subscriber uplift:')
for _, r in cell_0125.iterrows():
    print(f'    {r["subscriber_id"]}: uplift={r["expected_additional_prb_proxy"]:.6f}%, post={r["post_migration_prb_utilisation_proxy"]:.6f}%')
cum_uplift_0125 = cell_0125["expected_additional_prb_proxy"].sum()
baseline_0125 = cell_0125["p95_prb_utilisation_pct"].mean()
max_post_0125 = cell_0125["post_migration_prb_utilisation_proxy"].max()
print(f'  Sum of uplifts: {cum_uplift_0125:.6f}%')
print(f'  Cumulative post PRB: {baseline_0125 + cum_uplift_0125:.6f}%')
print(f'  Max individual post PRB: {max_post_0125:.6f}%')
print(f'  Difference (cumulative - max individual): {(baseline_0125 + cum_uplift_0125) - max_post_0125:.6f}%')
print()

# Distinct cells
print(f'Distinct cells in Step 14: {df14["dominant_serving_cell_id"].nunique()}')

# Query ABT eligible
query_abt = """
    SELECT subscriber_id, dominant_serving_cell_id, monthly_total_gb, 
           p95_prb_utilisation_pct, avg_dl_throughput_mbps, fwa_suitability_score
    FROM cleaned_data.abt_subscriber_month
    WHERE fwa_suitability_score > 0
"""
df_abt = pd.read_sql(query_abt, engine)
print(f'Distinct cells in ABT eligible: {df_abt["dominant_serving_cell_id"].nunique()}')
print(f'ABT eligible total: {len(df_abt):,}')
