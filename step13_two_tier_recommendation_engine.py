"""
Step 13: Two-Tier Service Recommendation Engine
Project: 5G FWA Migration Analytics Pipeline
Objective: Generate a personalized, two-tier FWA service recommendation for the 
           2,923 FWA-eligible subscribers based on deterministic commercial and 
           behavioural rules.
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

# Required columns for the recommendation engine
REQUIRED_COLS = [
    'subscriber_id', 'contract_type', 'num_active_lines', 
    'coverage_5g_flag', 'iptv_active_flag', 
    'streaming_heavy_flag', 'gaming_heavy_flag', 'high_voip_usage_flag',
    'fwa_suitability_score'
]

# ==============================================================================
# 2. DATA EXTRACTION & FILTERING
# ==============================================================================
def load_eligible_subscribers():
    print("=" * 70)
    print("STEP 13: TWO-TIER SERVICE RECOMMENDATION ENGINE")
    print("=" * 70)
    print("\n[1/6] Extracting FWA-eligible subscribers from the ABT...")

    cols_str = ', '.join(REQUIRED_COLS)
    query = f"SELECT {cols_str} FROM cleaned_data.abt_subscriber_month"
    df = pd.read_sql(query, engine)

    total_subs = len(df)
    print(f"   -> Total subscribers in ABT: {total_subs:,}")

    # Filter strictly to the 2,923 FWA-eligible subscribers (Score > 0)
    df_eligible = df[df['fwa_suitability_score'] > 0].copy().reset_index(drop=True)
    eligible_count = len(df_eligible)
    print(f"   -> FWA-eligible subscribers (Score > 0): {eligible_count:,}")

    if eligible_count == 0:
        raise ValueError("No FWA-eligible subscribers found. Check Step 9 scoring output.")

    return df_eligible

# ==============================================================================
# 3. TIER 1 LOGIC: BASE PLAN ASSIGNMENT
# ==============================================================================
def assign_tier1_base_plan(df):
    print("\n[2/6] Assigning Tier 1 Base Plans based on contract type...")

    # Mapping logic: Prepaid -> Prepaid, Postpaid/Hybrid -> Postpaid
    tier1_map = {
        'Prepaid': '5G FWA Prepaid',
        'Postpaid': '5G FWA Postpaid',
        'Hybrid': '5G FWA Postpaid'
    }
    
    df['tier1_base_plan'] = df['contract_type'].map(tier1_map).fillna('5G FWA Postpaid')
    
    # Validation
    assert df['tier1_base_plan'].notna().all(), "Tier 1 mapping produced nulls!"
    
    plan_counts = df['tier1_base_plan'].value_counts()
    for plan, count in plan_counts.items():
        pct = count / len(df) * 100
        print(f"   -> {plan:<20} : {count:>5,} ({pct:.1f}%)")

    return df

# ==============================================================================
# 4. TIER 2 LOGIC: VALUE-ADD BUNDLE ASSIGNMENT
# ==============================================================================
def assign_tier2_addons(df):
    print("\n[3/6] Evaluating Tier 2 Value-Add Bundle rules...")

    # Ensure boolean flags are strictly boolean for safe comparison
    bool_cols = ['coverage_5g_flag', 'iptv_active_flag', 
                 'streaming_heavy_flag', 'gaming_heavy_flag', 'high_voip_usage_flag']
    for col in bool_cols:
        df[col] = df[col].astype(bool)

    # Rule 1: IPTV Upsell (Heavy Streamers without active IPTV)
    rule1_iptv = (df['streaming_heavy_flag'] == True) & (df['iptv_active_flag'] == False)
    
    # Rule 2: Low-Latency Gaming (Heavy Gamers with 5G Coverage)
    rule2_gaming = (df['gaming_heavy_flag'] == True) & (df['coverage_5g_flag'] == True)
    
    # Rule 3: Convergent Fixed-Mobile (Heavy VoIP with Multi-line households)
    rule3_convergent = (df['high_voip_usage_flag'] == True) & (df['num_active_lines'] > 1)

    # Generate individual addon columns
    df['addon_iptv'] = np.where(rule1_iptv, '5G FWA + IPTV Bundle', '')
    df['addon_gaming'] = np.where(rule2_gaming, '5G FWA Low-Latency/Gaming Add-on', '')
    df['addon_convergent'] = np.where(rule3_convergent, 'Convergent Fixed-Mobile Add-on', '')

    # Generate reason codes for traceability
    df['reason_iptv'] = np.where(rule1_iptv, 'STR_HEAVY;NO_IPTV', '')
    df['reason_gaming'] = np.where(rule2_gaming, 'GAM_HEAVY;5G_COV', '')
    df['reason_convergent'] = np.where(rule3_convergent, 'VOIP_HEAVY;MULTI_LINE', '')

    # Print rule hit rates
    print(f"   -> Rule 1 (IPTV Upsell) triggered for:       {rule1_iptv.sum():>5,} subscribers ({rule1_iptv.mean()*100:.1f}%)")
    print(f"   -> Rule 2 (Gaming Add-on) triggered for:     {rule2_gaming.sum():>5,} subscribers ({rule2_gaming.mean()*100:.1f}%)")
    print(f"   -> Rule 3 (Convergent) triggered for:        {rule3_convergent.sum():>5,} subscribers ({rule3_convergent.mean()*100:.1f}%)")

    return df

# ==============================================================================
# 5. OFFER COMPOSITION & CATEGORIZATION
# ==============================================================================
def compose_final_offer(df):
    print("\n[4/6] Composing final recommended offers and categories...")

    # Combine Tier 2 addons into a single comma-separated string
    df['tier2_addons'] = df[['addon_iptv', 'addon_gaming', 'addon_convergent']].apply(
        lambda x: ', '.join([i for i in x if i != '']), axis=1
    )
    
    # Combine reason codes
    df['reason_codes'] = df[['reason_iptv', 'reason_gaming', 'reason_convergent']].apply(
        lambda x: ';'.join([i for i in x if i != '']), axis=1
    )

    # Create the full recommended offer string
    df['recommended_offer'] = df.apply(
        lambda row: row['tier1_base_plan'] if row['tier2_addons'] == '' 
        else f"{row['tier1_base_plan']} + {row['tier2_addons']}", 
        axis=1
    )

    # Determine high-level offer category
    def get_category(row):
        addons = [row['addon_iptv'], row['addon_gaming'], row['addon_convergent']]
        active_addons = [a for a in addons if a != '']
        count = len(active_addons)
        
        if count == 0:
            return 'Base Only'
        elif count == 1:
            # Extract short name for category (e.g., "IPTV", "Gaming", "Convergent")
            short_name = active_addons[0].split('/')[-1].split('+')[-1].strip().replace(' Bundle', '')
            return f"Base + {short_name}"
        else:
            return 'Multi-Addon Bundle'

    df['offer_category'] = df.apply(get_category, axis=1)

    # Drop intermediate helper columns
    drop_cols = ['addon_iptv', 'addon_gaming', 'addon_convergent', 
                 'reason_iptv', 'reason_gaming', 'reason_convergent']
    df = df.drop(columns=drop_cols)

    return df

# ==============================================================================
# 6. VALIDATION & EXECUTION SUMMARY
# ==============================================================================
def validate_and_summarize(df):
    print("\n[5/6] Validating recommendation outputs...")

    # Assertions
    assert df['tier1_base_plan'].notna().all(), "Missing Tier 1 plans!"
    assert df['recommended_offer'].notna().all(), "Missing recommended offers!"
    assert df['offer_category'].notna().all(), "Missing offer categories!"
    assert (df['fwa_suitability_score'] > 0).all(), "Ineligible subscribers leaked into recommendations!"
    
    print("   -> All 5 validation assertions PASSED.")

    print("\n" + "=" * 70)
    print("EXECUTION SUMMARY: STEP 13 RECOMMENDATION RESULTS")
    print("=" * 70)

    print(f"\n[Data Scope]")
    print(f"   -> FWA-Eligible Subscribers Processed: {len(df):,}")

    print(f"\n[Offer Category Distribution]")
    print("-" * 50)
    cat_counts = df['offer_category'].value_counts().sort_index()
    for cat, count in cat_counts.items():
        pct = count / len(df) * 100
        print(f"   -> {cat:<25} : {count:>5,} ({pct:>5.1f}%)")

    print(f"\n[Tier 2 Bundle Penetration]")
    print("-" * 50)
    # Count how many subscribers got at least one addon
    multi_addon = (df['tier2_addons'] != '').sum()
    base_only = (df['tier2_addons'] == '').sum()
    print(f"   -> Base Only (No Addons):      {base_only:>5,} ({base_only/len(df)*100:.1f}%)")
    print(f"   -> With >=1 Value-Add Addon:    {multi_addon:>5,} ({multi_addon/len(df)*100:.1f}%)")

    print(f"\n[Top 5 Recommended Offers (Sample)]")
    print("-" * 70)
    sample = df.head(5)
    for _, row in sample.iterrows():
        print(f"   {row['subscriber_id']} | FWA Score: {row['fwa_suitability_score']}")
        print(f"      Offer: {row['recommended_offer']}")
        print(f"      Category: {row['offer_category']} | Reasons: {row['reason_codes']}")
        print()

    print("=" * 70)
    print("PIPELINE STATUS")
    print("=" * 70)
    print("   -> Two-tier recommendations generated for {:,} eligible subscribers.".format(len(df)))
    print("   -> Results persisted to cleaned_data.step13_recommendations.")
    print("   -> Ready for Step 14 (Post-Migration Capacity Simulation).")
    print("=" * 70 + "\n")

# ==============================================================================
# MAIN EXECUTION
# ==============================================================================
if __name__ == "__main__":
    # 1. Load and Filter
    df_eligible = load_eligible_subscribers()

    # 2. Tier 1 Assignment
    df_tier1 = assign_tier1_base_plan(df_eligible)

    # 3. Tier 2 Assignment
    df_tier2 = assign_tier2_addons(df_tier1)

    # 4. Offer Composition
    df_final = compose_final_offer(df_tier2)

    # 5. Validate and Summarize
    validate_and_summarize(df_final)

    # 6. Save to Database
    output_cols = [
        'subscriber_id', 'tier1_base_plan', 'tier2_addons', 
        'recommended_offer', 'offer_category', 'reason_codes', 
        'fwa_suitability_score'
    ]
    
    df_final[output_cols].to_sql(
        'step13_recommendations', engine, schema='cleaned_data', 
        if_exists='replace', index=False
    )
