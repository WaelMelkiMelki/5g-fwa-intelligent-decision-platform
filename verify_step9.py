import sqlalchemy, pandas as pd
e = sqlalchemy.create_engine('postgresql+psycopg2://postgres:[REDACTED]@localhost:5432/postgres')
q = lambda s: pd.read_sql(sqlalchemy.text(s), e)
print('ABT band counts:', q("SELECT fwa_suitability_band, count(*) FROM cleaned_data.abt_subscriber_month GROUP BY 1 ORDER BY 1").to_dict('records'))
print()
print('Eligible score describe:', q("SELECT fwa_suitability_score FROM cleaned_data.abt_subscriber_month WHERE fwa_suitability_score > 0").fwa_suitability_score.describe().round(4).to_dict())
print()
print('Score values:', q("SELECT fwa_suitability_score, count(*) FROM cleaned_data.abt_subscriber_month WHERE fwa_suitability_score > 0 GROUP BY 1 ORDER BY 1").to_dict('records'))
