import pandas as pd
from sqlalchemy import create_engine

DB_CONNECTION_STRING = __import__("os").environ["FWA_DB_URL"]
engine = create_engine(DB_CONNECTION_STRING)

# Check cells in ABT with score > 0
df_abt = pd.read_sql('SELECT COUNT(DISTINCT dominant_serving_cell_id) as cnt FROM cleaned_data.abt_subscriber_month WHERE fwa_suitability_score > 0', engine)
print('ABT eligible distinct cells:', df_abt.iloc[0]['cnt'])

# All cells in ABT
df_abt_all = pd.read_sql('SELECT COUNT(DISTINCT dominant_serving_cell_id) as cnt FROM cleaned_data.abt_subscriber_month', engine)
print('ABT all distinct cells:', df_abt_all.iloc[0]['cnt'])

# Total cells in t3_cell_monthly_kpi
df_t3 = pd.read_sql('SELECT COUNT(DISTINCT cell_id) as cnt FROM cleaned_data.t3_cell_monthly_kpi', engine)
print('t3_cell_monthly_kpi distinct cells:', df_t3.iloc[0]['cnt'])

# Step 14 cells
df14 = pd.read_sql('SELECT COUNT(DISTINCT dominant_serving_cell_id) as cnt FROM cleaned_data.step14_capacity_simulation', engine)
print('Step 14 distinct cells:', df14.iloc[0]['cnt'])
