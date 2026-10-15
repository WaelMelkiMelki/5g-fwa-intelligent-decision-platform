"""
Step 11: Migration Prioritization (Suitability-Based Ranking)
Project: 5G FWA Migration Analytics Pipeline
Objective: Rank the 2,923 FWA-eligible subscribers using a deterministic Multi-Criteria 
           Decision Analysis (MCDA) approach combining Technical Suitability (Step 9), 
           Commercial Value (T2), Strategic Persona (Step 10), and Loyalty (T2).
Constraint: No supervised migration propensity model (no historical campaign labels).
"""

import pandas as pd
import numpy as np
from sqlalchemy import create_engine
import warnings
warnings.filterwarnings('ignore')

# ==============================================================================
# 1. CONFIGURATION & DATABASE CONNECTION
# ==============================================================================
DB_CONNECTION_STRING = __import__("os").environ["FWA_DB_URL"]
engine = create_engine(DB_CONNECTION_STRING)

# MCDA Weights (sum to 1.0)
W_TECH = 0.40    # Technical Suitability (Step 9 FWA Score)
W_COMM = 0.30    # Commercial Value (ARPU)
W_STRAT = 0.20   # Strategic Persona (Step 10 Cluster)
W_LOYAL = 0.10   # Loyalty / Tenure

# Strategic Persona Mapping (from Step 10 cluster profiles)
CLUSTER_STRATEGIC_WEIGHTS = {
    2: 1.0,   # Ultra-Heavy Postpaid Power-Users (10.7%)
    0: 0.8,   # High-Value Prepaid Streamers (36.7%)
    3: 0.6,   # Mid-Tier Prepaid Heavy-Users (2.0%)
    1: 0.4,   # Mass-Market Prepaid Base (50.6%)
}

# ==============================================================================
# 2. DATA EXTRACTION & FILTERING
# ==============================================================================
def load_eligible_subscribers():
    print("=" * 70)
    print("STEP 11: MIGRATION PRIORITIZATION (SUITABILITY-BASED RANKING)")
    print("=" * 70)
    print("\n[1/6] Extracting FWA-eligible subscribers from Step 10 output...")

    # Read from the Step 10 clustered table which contains:
    # subscriber_id, arpu_monthly_tnd, tenure_months, fwa_suitability_score, cluster_id, etc.
    query = """
        SELECT subscriber_id, 
               fwa_suitability_score, 
               arpu_monthly_tnd, 
               tenure_months, 
               cluster_id
        FROM cleaned_data.abt_subscriber_month_clustered
        WHERE fwa_suitability_score > 0
    """
    df = pd.read_sql(query, engine)

    total_in_table = pd.read_sql(
        "SELECT COUNT(*) as cnt FROM cleaned_data.abt_subscriber_month_clustered", engine
    )['cnt'].iloc[0]

    print(f"   -> Total subscribers in clustered ABT: {total_in_table:,}")
    print(f"   -> FWA-eligible subscribers (Score > 0): {len(df):,}")

    if len(df) == 0:
        raise ValueError("No FWA-eligible subscribers found. Check Step 9/10 outputs.")

    return df

# ==============================================================================
# 3. MIN-MAX NORMALIZATION
# ==============================================================================
def min_max_normalize(series):
    """Min-Max Normalization to [0, 1] range."""
    s_min = series.min()
    s_max = series.max()
    if s_max == s_min:
        return pd.Series(0.5, index=series.index)  # Avoid division by zero
    return (series - s_min) / (s_max - s_min)

def normalize_features(df):
    print("\n[2/6] Applying Min-Max Normalization to continuous features...")

    df_norm = df.copy()

    # Normalize Technical Suitability (FWA Score from Step 9)
    df_norm['S_tech'] = min_max_normalize(df_norm['fwa_suitability_score'])

    # Normalize Commercial Value (ARPU)
    df_norm['S_comm'] = min_max_normalize(df_norm['arpu_monthly_tnd'])

    # Normalize Loyalty (Tenure)
    df_norm['S_loyal'] = min_max_normalize(df_norm['tenure_months'])

    # Map Strategic Persona (Cluster ID -> Strategic Weight)
    df_norm['S_strat'] = df_norm['cluster_id'].map(CLUSTER_STRATEGIC_WEIGHTS)

    # Handle any unmapped cluster IDs (fallback to median weight)
    median_weight = np.median(list(CLUSTER_STRATEGIC_WEIGHTS.values()))
    unmapped_count = df_norm['S_strat'].isna().sum()
    if unmapped_count > 0:
        print(f"   -> Warning: {unmapped_count} subscribers with unmapped cluster_id. "
              f"Assigning median strategic weight ({median_weight}).")
        df_norm['S_strat'] = df_norm['S_strat'].fillna(median_weight)

    print(f"   -> S_tech  (FWA Score):  range [{df_norm['S_tech'].min():.4f}, {df_norm['S_tech'].max():.4f}]")
    print(f"   -> S_comm  (ARPU):      range [{df_norm['S_comm'].min():.4f}, {df_norm['S_comm'].max():.4f}]")
    print(f"   -> S_strat (Persona):   range [{df_norm['S_strat'].min():.4f}, {df_norm['S_strat'].max():.4f}]")
    print(f"   -> S_loyal (Tenure):    range [{df_norm['S_loyal'].min():.4f}, {df_norm['S_loyal'].max():.4f}]")

    return df_norm

# ==============================================================================
# 4. MCDA PRIORITY SCORE COMPUTATION
# ==============================================================================
def compute_priority_score(df_norm):
    print("\n[3/6] Computing MCDA candidate_prioritization_score...")

    df_scored = df_norm.copy()

    # Weighted Linear Combination (scaled to 0-100)
    df_scored['candidate_prioritization_score'] = (
        W_TECH  * df_scored['S_tech'] +
        W_COMM  * df_scored['S_comm'] +
        W_STRAT * df_scored['S_strat'] +
        W_LOYAL * df_scored['S_loyal']
    ) * 100

    # Clip to [0, 100] for safety
    df_scored['candidate_prioritization_score'] = df_scored['candidate_prioritization_score'].clip(0, 100)

    print(f"   -> Weights: Tech={W_TECH}, Comm={W_COMM}, Strat={W_STRAT}, Loyal={W_LOYAL}")
    print(f"   -> Score range: [{df_scored['candidate_prioritization_score'].min():.2f}, "
          f"{df_scored['candidate_prioritization_score'].max():.2f}]")
    print(f"   -> Score mean:  {df_scored['candidate_prioritization_score'].mean():.2f}")
    print(f"   -> Score std:   {df_scored['candidate_prioritization_score'].std():.2f}")

    return df_scored

# ==============================================================================
# 5. RANKING WITH DETERMINISTIC TIE-BREAKING
# ==============================================================================
def generate_ranking(df_scored):
    print("\n[4/6] Generating suitability_based_ranking (1 = highest priority)...")

    df_ranked = df_scored.copy()

    # Sort by priority score (descending), then by subscriber_id (ascending) for tie-breaking
    df_ranked = df_ranked.sort_values(
        by=['candidate_prioritization_score', 'subscriber_id'],
        ascending=[False, True]
    ).reset_index(drop=True)

    # Assign rank (1 = highest priority)
    df_ranked['suitability_based_ranking'] = range(1, len(df_ranked) + 1)

    # Check for ties
    unique_scores = df_ranked['candidate_prioritization_score'].nunique()
    total_subs = len(df_ranked)
    tied_count = total_subs - unique_scores

    print(f"   -> Total ranked subscribers: {total_subs:,}")
    print(f"   -> Unique priority scores:   {unique_scores:,}")
    print(f"   -> Tied scores (resolved by subscriber_id): {tied_count:,}")
    print(f"   -> Ranking range: [1, {total_subs:,}]")

    return df_ranked

# ==============================================================================
# 6. VALIDATION & PROFILING
# ==============================================================================
def validate_and_profile(df_ranked):
    print("\n[5/6] Validating results and profiling top decile...")

    # Validation Assertions
    assert df_ranked['candidate_prioritization_score'].between(0, 100).all(), \
        "Score out of [0, 100] bounds!"
    assert df_ranked['suitability_based_ranking'].min() == 1, \
        "Ranking must start at 1!"
    assert df_ranked['suitability_based_ranking'].max() == len(df_ranked), \
        "Ranking must end at N!"
    assert df_ranked['suitability_based_ranking'].is_unique, \
        "Ranking must be strictly unique!"
    assert df_ranked[['candidate_prioritization_score', 'suitability_based_ranking']].isnull().sum().sum() == 0, \
        "No nulls allowed in score or ranking!"

    print("   -> All 5 validation assertions PASSED.")

    # Top Decile Profiling
    top_n = max(1, len(df_ranked) // 10)
    top_decile = df_ranked.head(top_n)

    print(f"\n   [Top 10% Profile (Rank 1-{top_n})]")
    print(f"      -> Mean Priority Score:  {top_decile['candidate_prioritization_score'].mean():.2f}")
    print(f"      -> Mean FWA Suitability: {top_decile['fwa_suitability_score'].mean():.2f}")
    print(f"      -> Mean ARPU (TND):      {top_decile['arpu_monthly_tnd'].mean():.2f}")
    print(f"      -> Mean Tenure (months): {top_decile['tenure_months'].mean():.1f}")

    # Cluster distribution in top decile
    cluster_dist = top_decile['cluster_id'].value_counts().sort_index()
    print(f"      -> Cluster Distribution in Top 10%:")
    for cid, count in cluster_dist.items():
        pct = count / len(top_decile) * 100
        label = {2: "Ultra-Heavy Postpaid", 0: "High-Value Prepaid",
                 3: "Mid-Tier Prepaid", 1: "Mass-Market Prepaid"}.get(cid, f"Cluster {cid}")
        print(f"         Cluster {cid} ({label}): {count} ({pct:.1f}%)")

    # Spearman Rank Correlation with individual components
    from scipy.stats import spearmanr
    corr_tech, _ = spearmanr(df_ranked['suitability_based_ranking'],
                              df_ranked['fwa_suitability_score'])
    corr_comm, _ = spearmanr(df_ranked['suitability_based_ranking'],
                              df_ranked['arpu_monthly_tnd'])

    print(f"\n   [Rank Correlation (Spearman)]")
    print(f"      -> Ranking vs FWA Suitability Score: {corr_tech:.4f} "
          f"({'strong' if abs(corr_tech) > 0.6 else 'moderate'} inverse, expected)")
    print(f"      -> Ranking vs ARPU:                  {corr_comm:.4f} "
          f"({'strong' if abs(corr_comm) > 0.6 else 'moderate'} inverse, expected)")
    print(f"      (Negative correlation expected: rank 1 = highest score)")

    return True

# ==============================================================================
# 7. EXECUTION SUMMARY & OUTPUT
# ==============================================================================
def print_summary(df_ranked):
    print("\n" + "=" * 70)
    print("EXECUTION SUMMARY: STEP 11 MIGRATION PRIORITIZATION")
    print("=" * 70)

    print(f"\n[Data Scope]")
    print(f"   -> FWA-Eligible Subscribers Ranked: {len(df_ranked):,}")
    print(f"   -> MCDA Dimensions: 4 (Tech, Commercial, Strategic, Loyalty)")
    print(f"   -> Weights: Tech={W_TECH}, Comm={W_COMM}, Strat={W_STRAT}, Loyal={W_LOYAL}")

    print(f"\n[Score Distribution]")
    print(f"   -> Min Score:   {df_ranked['candidate_prioritization_score'].min():.2f}")
    print(f"   -> Max Score:   {df_ranked['candidate_prioritization_score'].max():.2f}")
    print(f"   -> Mean Score:  {df_ranked['candidate_prioritization_score'].mean():.2f}")
    print(f"   -> Median Score:{df_ranked['candidate_prioritization_score'].median():.2f}")
    print(f"   -> Std Dev:     {df_ranked['candidate_prioritization_score'].std():.2f}")

    print(f"\n[Ranking Quartiles]")
    q1 = df_ranked['candidate_prioritization_score'].quantile(0.25)
    q2 = df_ranked['candidate_prioritization_score'].quantile(0.50)
    q3 = df_ranked['candidate_prioritization_score'].quantile(0.75)
    print(f"   -> Q1 (25th pct): {q1:.2f}")
    print(f"   -> Q2 (50th pct): {q2:.2f}")
    print(f"   -> Q3 (75th pct): {q3:.2f}")

    print(f"\n[Top 5 Highest-Priority Subscribers]")
    print("-" * 70)
    top5 = df_ranked.head(5)
    for _, row in top5.iterrows():
        print(f"   Rank {row['suitability_based_ranking']}: {row['subscriber_id']}")
        print(f"      Score: {row['candidate_prioritization_score']:.2f} | "
              f"FWA: {row['fwa_suitability_score']:.0f} | "
              f"ARPU: {row['arpu_monthly_tnd']:.2f} TND | "
              f"Cluster: {row['cluster_id']}")

    print(f"\n[Bottom 5 Lowest-Priority Subscribers]")
    print("-" * 70)
    bot5 = df_ranked.tail(5)
    for _, row in bot5.iterrows():
        print(f"   Rank {row['suitability_based_ranking']}: {row['subscriber_id']}")
        print(f"      Score: {row['candidate_prioritization_score']:.2f} | "
              f"FWA: {row['fwa_suitability_score']:.0f} | "
              f"ARPU: {row['arpu_monthly_tnd']:.2f} TND | "
              f"Cluster: {row['cluster_id']}")

    print("\n" + "=" * 70)
    print("PIPELINE STATUS")
    print("=" * 70)
    print("   -> candidate_prioritization_score computed (0-100 scale).")
    print("   -> suitability_based_ranking assigned (1 = highest priority).")
    print("   -> Results persisted to cleaned_data.step11_prioritization.")
    print("   -> Ready for Step 12 (Supervised Churn Model) &")
    print("      Step 15 (Final Prioritization with XGBoost + Household Multiplier).")
    print("=" * 70 + "\n")

# ==============================================================================
# MAIN EXECUTION
# ==============================================================================
if __name__ == "__main__":
    # 1. Load and Filter
    df_eligible = load_eligible_subscribers()

    # 2. Normalize Features
    df_norm = normalize_features(df_eligible)

    # 3. Compute MCDA Priority Score
    df_scored = compute_priority_score(df_norm)

    # 4. Generate Ranking
    df_ranked = generate_ranking(df_scored)

    # 5. Validate and Profile
    validate_and_profile(df_ranked)

    # 6. Save Outputs
    output_cols = [
        'subscriber_id', 'fwa_suitability_score', 'arpu_monthly_tnd',
        'tenure_months', 'cluster_id',
        'S_tech', 'S_comm', 'S_strat', 'S_loyal',
        'candidate_prioritization_score', 'suitability_based_ranking'
    ]
    df_output = df_ranked[output_cols].copy()

    df_output.to_sql(
        'step11_prioritization', engine, schema='cleaned_data',
        if_exists='replace', index=False
    )

    # Also save as CSV for reporting
    df_output.to_csv('step11_prioritization_output.csv', index=False)

    # 7. Print Summary
    print_summary(df_ranked)
