import sqlalchemy
import pandas as pd
import numpy as np
from scipy.stats import spearmanr

engine = sqlalchemy.create_engine('postgresql+psycopg2://postgres:[REDACTED]@localhost:5432/postgres')
q = lambda s: pd.read_sql(sqlalchemy.text(s), engine)

# 1. Priority score distribution from step11 table
print("=== PRIORITY SCORE DISTRIBUTION ===")
df11 = q("""SELECT candidate_prioritization_score, suitability_based_ranking 
            FROM cleaned_data.step11_prioritization""")
print(f"Rows: {len(df11)}")
print(f"Mean: {df11.candidate_prioritization_score.mean():.4f}")
print(f"Median: {df11.candidate_prioritization_score.median():.4f}")
print(f"Std: {df11.candidate_prioritization_score.std():.4f}")
print(f"Min: {df11.candidate_prioritization_score.min():.4f}")
print(f"Max: {df11.candidate_prioritization_score.max():.4f}")
print(f"Q1: {df11.candidate_prioritization_score.quantile(0.25):.4f}")
print(f"Q3: {df11.candidate_prioritization_score.quantile(0.75):.4f}")
print()

# 2. ARPU scale from eligible input
print("=== ARPU SCALE (eligible, from abt_subscriber_month_clustered) ===")
arpu = q("""SELECT arpu_monthly_tnd FROM cleaned_data.abt_subscriber_month_clustered""")
print(f"Min: {arpu.arpu_monthly_tnd.min():.2f}")
print(f"Median: {arpu.arpu_monthly_tnd.median():.2f}")
print(f"Max: {arpu.arpu_monthly_tnd.max():.2f}")
print(f"Top 10 ARPU values:")
top10 = arpu.nlargest(10, 'arpu_monthly_tnd')
for i, row in top10.iterrows():
    print(f"  {row.arpu_monthly_tnd:.2f}")
print()

# 3. Top decile (ranks 1-292)
print("=== TOP DECILE (Ranks 1-292) ===")
top_decile = q("""SELECT subscriber_id, fwa_suitability_score, arpu_monthly_tnd, tenure_months, cluster_id, candidate_prioritization_score, suitability_based_ranking
                  FROM cleaned_data.step11_prioritization
                  WHERE suitability_based_ranking <= 292
                  ORDER BY suitability_based_ranking""")
print(f"Count: {len(top_decile)}")
print(f"Mean priority: {top_decile.candidate_prioritization_score.mean():.4f}")
print(f"Mean FWA: {top_decile.fwa_suitability_score.mean():.4f}")
print(f"Mean ARPU: {top_decile.arpu_monthly_tnd.mean():.4f}")
print(f"Mean tenure: {top_decile.tenure_months.mean():.4f}")
print(f"Cluster dist: {top_decile.cluster_id.value_counts().sort_index().to_dict()}")
print()

# 4. Top 5 and Bottom 5
print("=== TOP 5 ===")
top5 = q("""SELECT subscriber_id, candidate_prioritization_score, fwa_suitability_score, arpu_monthly_tnd, cluster_id, suitability_based_ranking
            FROM cleaned_data.step11_prioritization
            ORDER BY suitability_based_ranking ASC LIMIT 5""")
print(top5.to_string(index=False))
print()

print("=== BOTTOM 5 ===")
bot5 = q("""SELECT subscriber_id, candidate_prioritization_score, fwa_suitability_score, arpu_monthly_tnd, cluster_id, suitability_based_ranking
            FROM cleaned_data.step11_prioritization
            ORDER BY suitability_based_ranking DESC LIMIT 5""")
print(bot5.to_string(index=False))
print()

# 5. Uniqueness check
print("=== UNIQUENESS CHECK ===")
uniq = q("""SELECT COUNT(*) as cnt, COUNT(DISTINCT suitability_based_ranking) as uniq_rank, MIN(suitability_based_ranking) as min_r, MAX(suitability_based_ranking) as max_r
            FROM cleaned_data.step11_prioritization""")
print(uniq.to_string(index=False))
print()

# 6. Spearman correlations
print("=== SPEARMAN CORRELATIONS ===")
df_corr = q("""SELECT suitability_based_ranking, candidate_prioritization_score, fwa_suitability_score, arpu_monthly_tnd, tenure_months, cluster_id
               FROM cleaned_data.step11_prioritization""")
r1, p1 = spearmanr(df_corr.suitability_based_ranking, df_corr.fwa_suitability_score)
r2, p2 = spearmanr(df_corr.suitability_based_ranking, df_corr.arpu_monthly_tnd)
r3, p3 = spearmanr(df_corr.suitability_based_ranking, df_corr.tenure_months)
print(f"Ranking vs FWA Suitability: {r1:.6f} (p={p1:.2e})")
print(f"Ranking vs ARPU: {r2:.6f} (p={p2:.2e})")
print(f"Ranking vs Tenure: {r3:.6f} (p={p3:.2e})")
print()

# 7. Formula spot-check for 3 subscribers
print("=== FORMULA SPOT-CHECK (3 random subscribers) ===")
# Get the min/max for normalization
S_tech_min = df_corr.fwa_suitability_score.min()
S_tech_max = df_corr.fwa_suitability_score.max()
S_comm_min = df_corr.arpu_monthly_tnd.min()
S_comm_max = df_corr.arpu_monthly_tnd.max()
S_loyal_min = df_corr.tenure_months.min()
S_loyal_max = df_corr.tenure_months.max()

CLUSTER_STRATEGIC_WEIGHTS = {2: 1.0, 0: 0.8, 3: 0.6, 1: 0.4}
W_TECH, W_COMM, W_STRAT, W_LOYAL = 0.40, 0.30, 0.20, 0.10

# Pick 3 specific subscribers (top, middle, bottom)
spot = df_corr.iloc[[0, 1461, 2922]]  # rank 1, median-ish, last
for _, row in spot.iterrows():
    S_tech = (row.fwa_suitability_score - S_tech_min) / (S_tech_max - S_tech_min)
    S_comm = (row.arpu_monthly_tnd - S_comm_min) / (S_comm_max - S_comm_min)
    S_loyal = (row.tenure_months - S_loyal_min) / (S_loyal_max - S_loyal_min)
    S_strat = CLUSTER_STRATEGIC_WEIGHTS.get(row.cluster_id, 0.5)
    
    recomputed = (W_TECH * S_tech + W_COMM * S_comm + W_STRAT * S_strat + W_LOYAL * S_loyal) * 100
    stored = row.candidate_prioritization_score
    print(f"  {row.subscriber_id}: rank={row.suitability_based_ranking}")
    print(f"    FWA={row.fwa_suitability_score:.1f} ARPU={row.arpu_monthly_tnd:.2f} Tenure={row.tenure_months} Cluster={row.cluster_id}")
    print(f"    S_tech={S_tech:.4f} S_comm={S_comm:.4f} S_strat={S_strat:.1f} S_loyal={S_loyal:.4f}")
    print(f"    Recomputed={recomputed:.4f}, Stored={stored:.4f}, Match={abs(recomputed-stored)<0.01}")
    print()
