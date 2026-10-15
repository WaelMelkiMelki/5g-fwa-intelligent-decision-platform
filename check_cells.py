import pandas as pd
from sqlalchemy import create_engine

DB_CONNECTION_STRING = __import__("os").environ["FWA_DB_URL"]
engine = create_engine(DB_CONNECTION_STRING)

# Check Step 10 clustering table
df10 = pd.read_sql('SELECT * FROM cleaned_data.step10_kprototypes_clustering', engine)
print(f'Step 10 rows: {len(df10):,}')
print(f'Distinct cells: {df10["dominant_serving_cell_id"].nunique()}')
print(f'Distinct cells in eligible (score>0): {df10[df10["fwa_suitability_score"] > 0]["dominant_serving_cell_id"].nunique()}')
print()
print(f'Total cells in t3_cell_monthly_kpi: ')
df_t3 = pd.read_sql('SELECT COUNT(DISTINCT cell_id) as cnt FROM cleaned_data.t3_cell_monthly_kpi', engine)
print(df_t3)
print()

# Check cells in ABT with score > 0
df_abt = pd.read_sql('SELECT COUNT(DISTINCT dominant_serving_cell_id) as cnt FROM cleaned_data.abt_subscriber_month WHERE fwa_suitability_score > 0', engine)
print(f'ABT eligible distinct cells: {df_abt.iloc[0]["cnt"]}')

# All cells in ABT
df_abt_all = pd.read_sql('SELECT COUNT(DISTINCT dominant_serving_cell_id) as cnt FROM cleaned_data.abt_subscriber_month', engine)
print(f'ABT all distinct cells: {df_abt_all.iloc[0]["cnt"]}')
