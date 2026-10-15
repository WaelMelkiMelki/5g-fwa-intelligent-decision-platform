import sqlalchemy, pandas as pd
e = sqlalchemy.create_engine('postgresql+psycopg2://postgres:[REDACTED]@localhost:5432/postgres')
q = lambda s: pd.read_sql(s, e)

print("=== Validation 1: No Fiber_Competitor has another exclusion reason ===")
v1 = q("""
SELECT radio_feasibility_class, FWA_exclusion_reason, count(*) as cnt
FROM cleaned_data.abt_subscriber_month
WHERE radio_feasibility_class = 'Fiber_Competitor'
GROUP BY radio_feasibility_class, FWA_exclusion_reason
""")
print(v1.to_string(index=False))
print()

print("=== Validation 2: No Infeasible record remains eligible ===")
v2 = q("""
SELECT radio_feasibility_class, fwa_suitability_score, FWA_exclusion_reason, count(*) as cnt
FROM cleaned_data.abt_subscriber_month
WHERE radio_feasibility_class = 'Infeasible'
GROUP BY radio_feasibility_class, fwa_suitability_score, FWA_exclusion_reason
""")
print(v2.to_string(index=False))
print()

print("=== Validation 3: Only 4G_Fallback and 5G_Feasible may be eligible ===")
v3 = q("""
SELECT radio_feasibility_class, 
       SUM(CASE WHEN fwa_suitability_score > 0 THEN 1 ELSE 0 END) as eligible,
       SUM(CASE WHEN fwa_suitability_score = 0 THEN 1 ELSE 0 END) as excluded,
       count(*) as total
FROM cleaned_data.abt_subscriber_month
GROUP BY radio_feasibility_class
ORDER BY 1
""")
print(v3.to_string(index=False))
print()

print("=== Validation 4: Every excluded row has exactly one reason ===")
v4 = q("""
SELECT 
    COUNT(*) as total_excluded,
    COUNT(FWA_exclusion_reason) as with_reason,
    COUNT(*) - COUNT(FWA_exclusion_reason) as without_reason
FROM cleaned_data.abt_subscriber_month
WHERE fwa_suitability_score = 0
""")
print(v4.to_string(index=False))
print()

print("=== Full cross-tab: radio_feasibility_class x exclusion_reason ===")
v5 = q("""
SELECT radio_feasibility_class, FWA_exclusion_reason, count(*) as cnt
FROM cleaned_data.abt_subscriber_month
GROUP BY radio_feasibility_class, FWA_exclusion_reason
ORDER BY radio_feasibility_class, FWA_exclusion_reason
""")
print(v5.to_string(index=False))
print()

print("=== Invariant check ===")
v6 = q("""
SELECT count(*) as total,
       SUM(CASE WHEN fwa_suitability_score = 0 THEN 1 ELSE 0 END) as excluded,
       SUM(CASE WHEN fwa_suitability_score > 0 THEN 1 ELSE 0 END) as eligible
FROM cleaned_data.abt_subscriber_month
""")
print(v6.to_string(index=False))
