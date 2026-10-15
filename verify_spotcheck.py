import sqlalchemy
import pandas as pd
import numpy as np
from scipy.stats import spearmanr

engine = sqlalchemy.create_engine('postgresql+psycopg2://postgres:[REDACTED]@localhost:5432/postgres')
q = lambda s: pd.read_sql(sqlalchemy.text(s), engine)

# Spot check - use exact column names from step11_prioritization
df = q("""SELECT subscriber_id, candidate_prioritization_score, fwa_suitability_score, arpu_monthly_tnd, tenure_months, cluster_id, suitability_based_ranking
          FROM cleaned_data.step11_prioritization""")

S_tech_min = df.fwa_suitability_score.min()
S_tech_max = df.fwa_suitability_score.max()
S_comm_min = df.arpu_monthly_tnd.min()
S_comm_max = df.arpu_monthly_tnd.max()
S_loyal_min = df.tenure_months.min()
S_loyal_max = df.tenure_months.max()

CLUSTER_STRATEGIC_WEIGHTS = {2: 1.0, 0: 0.8, 3: 0.6, 1: 0.4}
W_TECH, W_COMM, W_STRAT, W_LOYAL = 0.40, 0.30, 0.20, 0.10

# Pick 3: rank 1, middle, last
spot = df[df.suitability_based_ranking.isin([1, 1462, 2923])]
for _, row in spot.iterrows():
    S_tech = (row.fwa_suitability_score - S_tech_min) / (S_tech_max - S_tech_min)
    S_comm = (row.arpu_monthly_tnd - S_comm_min) / (S_comm_max - S_comm_min)
    S_loyal = (row.tenure_months - S_loyal_min) / (S_loyal_max - S_loyal_min)
    S_strat = CLUSTER_STRATEGIC_WEIGHTS.get(row.cluster_id, 0.5)
    
    recomputed = (W_TECH * S_tech + W_COMM * S_comm + W_STRAT * S_strat + W_LOYAL * S_loyal) * 100
    stored = row.candidate_prioritization_score
    print(f"  {row.subscriber_id}: rank={int(row.suitability_based_ranking)}")
    print(f"    FWA={row.fwa_suitability_score:.1f} ARPU={row.arpu_monthly_tnd:.2f} Tenure={int(row.tenure_months)} Cluster={int(row.cluster_id)}")
    print(f"    S_tech={S_tech:.4f} S_comm={S_comm:.4f} S_strat={S_strat:.1f} S_loyal={S_loyal:.4f}")
    print(f"    Recomputed={recomputed:.4f}, Stored={stored:.4f}, Match={abs(recomputed-stored)<0.01}")
    print()
