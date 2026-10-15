import sqlalchemy, pandas as pd
e = sqlalchemy.create_engine('postgresql+psycopg2://postgres:[REDACTED]@localhost:5432/postgres')
q = lambda s: pd.read_sql(s, e)

r = q("""
SELECT signal_quality_class, coverage_4g_flag, coverage_5g_flag, fiber_coverage_flag, COUNT(*) as cnt
FROM cleaned_data.abt_subscriber_month
WHERE radio_feasibility_class = 'Infeasible'
  AND FWA_exclusion_reason IS NULL
GROUP BY 1,2,3,4
ORDER BY 5 DESC
""")
print('=== 294 Infeasible cases breakdown ===')
print(r.to_string(index=False))
