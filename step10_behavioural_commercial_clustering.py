"""
Step 10: Behavioural & Commercial Clustering (K-Prototypes)
Project: 5G FWA Migration Analytics Pipeline
Objective: Partition the 2,923 FWA-eligible subscribers into distinct behavioural 
           and commercial personas to drive Step 13 (Recommendation) and Step 15 (Prioritization).
"""

import pandas as pd
import numpy as np
from sqlalchemy import create_engine
from sklearn.preprocessing import StandardScaler
from kmodes.kprototypes import KPrototypes
from sklearn.metrics import silhouette_score
import warnings
warnings.filterwarnings('ignore')

# ==============================================================================
# 1. CONFIGURATION & DATABASE CONNECTION
# ==============================================================================
# TODO: Update with your actual PostgreSQL connection string
DB_CONNECTION_STRING = __import__("os").environ["FWA_DB_URL"]
engine = create_engine(DB_CONNECTION_STRING)

# Define feature sets based on Phase 1 Theory
NUMERICAL_FEATURES = [
    'arpu_monthly_tnd', 'monthly_total_gb', 'streaming_vol_gb', 
    'gaming_vol_gb', 'voip_minutes', 'tenure_months', 'fwa_suitability_score'
]

CATEGORICAL_FEATURES = [
    'contract_type', 'arpu_band', 'tenure_band', 
    'segment_tier', 'handset_5g_ready_flag', 'multi_line_flag'
]

ALL_FEATURES = NUMERICAL_FEATURES + CATEGORICAL_FEATURES

# ==============================================================================
# 2. DATA EXTRACTION & FILTERING
# ==============================================================================
def load_and_filter_data():
    print("="*60)
    print("STEP 10: BEHAVIOURAL & COMMERCIAL CLUSTERING")
    print("="*60)
    print("\n[1/6] Extracting Analytical Base Table (ABT)...")
    
    query = f"SELECT subscriber_id, {', '.join(ALL_FEATURES)} FROM cleaned_data.abt_subscriber_month"
    df = pd.read_sql(query, engine)
    
    total_subscribers = len(df)
    print(f"   -> Total subscribers in ABT: {total_subscribers:,}")
    
    # Filter to FWA-eligible subscribers only (Score > 0)
    df_eligible = df[df['fwa_suitability_score'] > 0].copy()
    eligible_count = len(df_eligible)
    print(f"   -> FWA-eligible subscribers (Score > 0): {eligible_count:,}")
    
    if eligible_count == 0:
        raise ValueError("No FWA-eligible subscribers found. Check Step 9 scoring output.")
        
    return df_eligible

# ==============================================================================
# 3. PREPROCESSING (FIXED FOR NaN HANDLING)
# ==============================================================================
def preprocess_data(df):
    print("\n[2/6] Preprocessing features for K-Prototypes...")
    
    # DEFENSIVE NaN HANDLING: Ensure absolutely no NaNs exist before scaling/encoding
    df = df.copy()
    for col in NUMERICAL_FEATURES:
        if df[col].isnull().any():
            print(f"   -> Warning: Found {df[col].isnull().sum()} NaNs in {col}. Imputing with median.")
            df[col] = df[col].fillna(df[col].median())
            
    for col in CATEGORICAL_FEATURES:
        if df[col].isnull().any():
            print(f"   -> Warning: Found {df[col].isnull().sum()} NaNs in {col}. Imputing with 'Unknown'.")
            df[col] = df[col].fillna('Unknown')
    
    # 3.1 Numerical Scaling (Z-score Standardization)
    scaler = StandardScaler()
    X_num_scaled = scaler.fit_transform(df[NUMERICAL_FEATURES])
    
    # 3.2 Categorical Encoding (Native String/Category - NO One-Hot Encoding)
    # Force strict string conversion to prevent float NaNs from leaking into kmodes
    df_cat = df[CATEGORICAL_FEATURES].astype(str)
    
    # 3.3 Combine into a single DataFrame for KPrototypes
    df_processed = pd.DataFrame(X_num_scaled, columns=NUMERICAL_FEATURES)
    for col in CATEGORICAL_FEATURES:
        df_processed[col] = df_cat[col].values
        
    # Identify categorical column indices for KPrototypes
    cat_indices = [df_processed.columns.get_loc(c) for c in CATEGORICAL_FEATURES]
    
    # Final NaN check - KPrototypes cannot handle NaN values
    nan_count = df_processed.isnull().sum().sum()
    if nan_count > 0:
        print(f"   -> WARNING: {nan_count} NaN values remain after preprocessing. Filling with defaults.")
        df_processed = df_processed.fillna(0)
        
    print(f"   -> Numerical features scaled: {len(NUMERICAL_FEATURES)}")
    print(f"   -> Categorical features cast to string: {len(CATEGORICAL_FEATURES)}")
    print(f"   -> Categorical indices mapped: {cat_indices}")
    print(f"   -> NaN Validation: PASSED (0 missing values)")
    
    return df_processed, cat_indices, scaler

# ==============================================================================
# 4. OPTIMAL K DETERMINATION
# ==============================================================================
def find_optimal_k(df_processed, cat_indices, k_range=range(2, 11)):
    print("\n[3/6] Determining optimal number of clusters (K)...")
    
    costs = []
    sil_scores = []
    models = {}
    
    for k in k_range:
        # Fit K-Prototypes with Cao initialization
        km = KPrototypes(n_clusters=k, init='Cao', n_init=5, verbose=0, random_state=42)
        clusters = km.fit_predict(df_processed, categorical=cat_indices)
        
        costs.append(km.cost_)
        models[k] = (km, clusters)
        
        # Calculate Silhouette Score using numerical features as a proxy for mixed data
        num_data = df_processed[NUMERICAL_FEATURES].values
        if k < len(df_processed): 
            sil = silhouette_score(num_data, clusters, metric='euclidean')
            sil_scores.append(sil)
        else:
            sil_scores.append(-1)
            
        print(f"   -> K={k} | Cost: {km.cost_:.2f} | Silhouette (Num Proxy): {sil:.4f}")
        
    # Heuristic to find optimal K: 
    # We look for the "elbow" in the cost function, constrained by business logic (K between 3 and 6)
    target_k_range = [k for k in k_range if 3 <= k <= 6]
    
    best_k = target_k_range[0]
    min_diff_idx = 0
    cost_diffs = np.diff(costs)
    
    for i, k in enumerate(target_k_range[:-1]):
        idx = k - 2 
        if idx < len(cost_diffs):
            if cost_diffs[idx] > cost_diffs[min_diff_idx] * 0.5: 
                min_diff_idx = idx
                best_k = k

    best_sil_k = k_range[np.argmax(sil_scores)]
    
    if best_k not in target_k_range:
        best_k = max(target_k_range, key=lambda x: sil_scores[x-2])
        
    print(f"\n   -> Selected Optimal K: {best_k} (Business constraint: 3-6 personas)")
    
    return best_k, models[best_k][0], models[best_k][1], costs, sil_scores

# ==============================================================================
# 5. CLUSTER PROFILING & LABELING
# ==============================================================================
def profile_and_label_clusters(df_original, df_processed, km, clusters, scaler):
    print("\n[4/6] Profiling clusters and generating business labels...")
    
    df_final = df_original.copy()
    df_final['cluster_id'] = clusters
    
    profiles = []
    
    for k in sorted(df_final['cluster_id'].unique()):
        cluster_data = df_final[df_final['cluster_id'] == k]
        profile = {'cluster_id': k, 'size': len(cluster_data), 'pct': len(cluster_data)/len(df_final)*100}
        
        # Numerical profiling (inverse transform to get original scales)
        num_means_scaled = cluster_data[NUMERICAL_FEATURES].mean()
        num_means_original = scaler.inverse_transform([num_means_scaled])[0]
        for i, col in enumerate(NUMERICAL_FEATURES):
            profile[f'mean_{col}'] = num_means_original[i]
            
        # Categorical profiling (mode)
        for col in CATEGORICAL_FEATURES:
            profile[f'mode_{col}'] = cluster_data[col].mode()[0]
            profile[f'dom_{col}'] = (cluster_data[col] == profile[f'mode_{col}']).mean() * 100
            
        profiles.append(profile)
        
    df_profiles = pd.DataFrame(profiles)
    
    # Heuristic Business Labeling
    labels = []
    for _, row in df_profiles.iterrows():
        tags = []
        if row['mode_handset_5g_ready_flag'] == 'True' and row['dom_handset_5g_ready_flag'] > 60:
            tags.append("5G-Handset")
        else:
            tags.append("4G-Handset")
            
        if row['mode_multi_line_flag'] == 'True' and row['dom_multi_line_flag'] > 60:
            tags.append("Household/B2B")
        else:
            tags.append("Individual")
            
        if row['mode_arpu_band'] == 'High ARPU':
            tags.append("High-Value")
        elif row['mean_arpu_monthly_tnd'] < df_final['arpu_monthly_tnd'].median():
            tags.append("Mass-Market")
            
        if row['mean_streaming_vol_gb'] > df_final['streaming_vol_gb'].quantile(0.75):
            tags.append("Heavy-Streamers")
        elif row['mean_gaming_vol_gb'] > df_final['gaming_vol_gb'].quantile(0.75):
            tags.append("Gamers")
            
        labels.append(" | ".join(tags))
        
    df_profiles['business_label'] = labels
    df_final = df_final.merge(df_profiles[['cluster_id', 'business_label']], on='cluster_id', how='left')
    
    return df_final, df_profiles

# ==============================================================================
# 6. EXECUTION SUMMARY & OUTPUT
# ==============================================================================
def print_summary(df_final, df_profiles, optimal_k, costs, sil_scores):
    print("\n" + "="*60)
    print("EXECUTION SUMMARY: STEP 10 CLUSTERING RESULTS")
    print("="*60)
    
    print(f"\n[Data Scope]")
    print(f"   -> Processed FWA-Eligible Subscribers: {len(df_final):,}")
    print(f"   -> Selected Features: {len(ALL_FEATURES)} ({len(NUMERICAL_FEATURES)} Num, {len(CATEGORICAL_FEATURES)} Cat)")
    
    print(f"\n[Model Performance]")
    print(f"   -> Optimal K: {optimal_k}")
    print(f"   -> Final K-Prototypes Cost: {costs[optimal_k-2]:.2f}")
    print(f"   -> Silhouette Score (Num Proxy): {sil_scores[optimal_k-2]:.4f}")
    
    print(f"\n[Cluster Distribution & Business Interpretation]")
    print("-" * 60)
    for _, row in df_profiles.iterrows():
        print(f"\n   Cluster {row['cluster_id']}: {row['business_label']}")
        print(f"   Size: {row['size']:,} ({row['pct']:.1f}%)")
        print(f"   Key Traits:")
        print(f"      - ARPU: {row['mean_arpu_monthly_tnd']:.2f} TND (Mode Band: {row['mode_arpu_band']})")
        print(f"      - Usage: {row['mean_monthly_total_gb']:.1f} GB/mo | Stream: {row['mean_streaming_vol_gb']:.1f} GB")
        print(f"      - Contract: {row['mode_contract_type']} ({row['dom_contract_type']:.0f}% dominant)")
        print(f"      - Handset: {row['mode_handset_5g_ready_flag']} ({row['dom_handset_5g_ready_flag']:.0f}% dominant)")
        print(f"      - Suitability Score: {row['mean_fwa_suitability_score']:.1f}")
        
    print("\n" + "="*60)
    print("PIPELINE STATUS")
    print("="*60)
    print("   -> Cluster IDs and Labels assigned to ABT.")
    print("   -> Ready for Step 11 (Migration Prioritization) & Step 13 (Recommendation Engine).")
    print("="*60 + "\n")

# ==============================================================================
# MAIN EXECUTION
# ==============================================================================
if __name__ == "__main__":
    # 1. Load and Filter
    df_eligible = load_and_filter_data()
    
    # 2. Preprocess
    df_processed, cat_indices, scaler = preprocess_data(df_eligible)
    
    # 3. Find Optimal K
    optimal_k, final_km, final_clusters, costs, sil_scores = find_optimal_k(df_processed, cat_indices)
    
    # 4. Profile and Label
    df_final, df_profiles = profile_and_label_clusters(df_eligible, df_processed, final_km, final_clusters, scaler)
    
    # 5. Save Outputs for Downstream Steps
    df_final.to_sql('abt_subscriber_month_clustered', engine, schema='cleaned_data', 
                    if_exists='replace', index=False)
    
    df_profiles.to_csv('step10_cluster_profiles.csv', index=False)
    
    # 6. Print Summary
    print_summary(df_final, df_profiles, optimal_k, costs, sil_scores)
