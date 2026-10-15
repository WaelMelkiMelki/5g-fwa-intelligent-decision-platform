import pandas as pd
from sqlalchemy import create_engine

engine = create_engine("postgresql+psycopg2://postgres:[REDACTED]@localhost:5432/postgres")
q = lambda s: pd.read_sql(s, engine)

# Get new cluster profiles from the newly written clustered table
cl_new = q("""SELECT subscriber_id, cluster_id, business_label, arpu_monthly_tnd, contract_type,
                 monthly_total_gb, streaming_vol_gb, tenure_months, handset_5g_ready_flag,
                 fwa_suitability_score
          FROM cleaned_data.abt_subscriber_month_clustered""")

def profile(df, score_col):
    g = df.groupby('cluster_id')
    p = pd.DataFrame({
        'size': g.size(),
        'pct': (g.size() / len(df) * 100).round(2),
        'mean_arpu': g.arpu_monthly_tnd.mean().round(2),
        'pct_postpaid': g.apply(lambda x: (x.contract_type == 'Postpaid').mean() * 100, include_groups=False).round(2),
        'mean_total_gb': g.monthly_total_gb.mean().round(1),
        'mean_streaming_gb': g.streaming_vol_gb.mean().round(1),
        'mean_tenure_months': g.tenure_months.mean().round(1),
        'pct_5g_handset': g.handset_5g_ready_flag.apply(lambda x: (x == True).mean() * 100, include_groups=False).round(2),
        'mean_suitability_score': g[score_col].mean().round(2),
    })
    if 'business_label' in df.columns:
        p['new_business_label'] = g.business_label.first()
    return p.reset_index()

new_profiles = profile(cl_new, 'fwa_suitability_score')
new_profiles.to_csv(r"C:\Users\w50057230\Downloads\FWA project\correction_backup\new_cluster_profiles.csv", index=False)

print("NEW CLUSTER PROFILES (from DB, correct):")
print(new_profiles.to_string(index=False))
print()

# Also load old profiles for comparison
old_profiles = pd.read_csv(r"C:\Users\w50057230\Downloads\FWA project\correction_backup\old_cluster_profiles.csv")
print("OLD CLUSTER PROFILES (from baseline snapshot):")
print(old_profiles.to_string(index=False))
