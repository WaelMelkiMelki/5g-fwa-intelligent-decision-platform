import pandas as pd
from sqlalchemy import create_engine

DB_CONNECTION_STRING = __import__("os").environ["FWA_DB_URL"]
engine = create_engine(DB_CONNECTION_STRING)

# Check abt_subscriber_month_clustered
df10 = pd.read_sql('SELECT * FROM cleaned_data.abt_subscriber_month_clustered', engine)
print('Rows:', len(df10))
print('Columns:', list(df10.columns))
print('Distinct cells:', df10['dominant_serving_cell_id'].nunique())
eligible_mask = df10['fwa_suitability_score'] > 0
print('Distinct cells in eligible:', df10[eligible_mask]['dominant_serving_cell_id'].nunique())
print()

# Check cells in ABT with score > 0
df_abt = pd.read_sql('SELECT COUNT(DISTINCT dominant_serving_cell_id) as cnt FROM cleaned_data.abt_subscriber_month WHERE fwa_suitability_score > 0', engine)
print('ABT eligible distinct cells:', df_abt.iloc[0]['cnt'])

# All cells in ABT
df_abt_all = pd.read_sql('SELECT COUNT(DISTINCT dominant_serving_cell_id) as cnt FROM cleaned_data.abt_subscriber_month', engine)
print('ABT all distinct cells:', df_abt_all.iloc[0]['cnt'])

# Total cells in t3_cell_monthly_kpi
df_t3 = pd.read_sql('SELECT COUNT(DISTINCT cell_id) as cnt FROM cleaned_data.t3_cell_monthly_kpi', engine)
print('t3_cell_monthly_kpi distinct cells:', df_t3.iloc[0]['cnt'])
