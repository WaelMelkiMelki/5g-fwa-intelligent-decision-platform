import pandas as pd
import numpy as np
import sqlalchemy
import logging
import sys

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s | %(levelname)-8s | %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)

def get_db_engine():
    """
    Initialize SQLAlchemy engine. 
    UPDATE THIS CONNECTION STRING to match your PostgreSQL environment.
    """
    # Example: postgresql+psycopg2://user:password@host:port/dbname
    DB_CONNECTION_STRING = __import__("os").environ["FWA_DB_URL"]
    return sqlalchemy.create_engine(DB_CONNECTION_STRING)

def run_step9():
    logging.info("Initializing Step 9: Rule-Based FWA Eligibility & Suitability Scoring")
    
    # ==========================================
    # 1. DATA EXTRACTION
    # ==========================================
    engine = get_db_engine()
    
    query = """
        SELECT 
            subscriber_id,
            current_capacity_proxy_status,
            fiber_coverage_flag,
            signal_quality_class,
            radio_feasibility_class,
            coverage_5g_flag,
            arpu_band
        FROM cleaned_data.abt_subscriber_month
    """
    
    logging.info("Extracting required features from cleaned_data.abt_subscriber_month...")
    try:
        df = pd.read_sql(query, engine)
    except Exception as e:
        logging.error(f"Database extraction failed: {e}")
        sys.exit(1)
        
    total_subscribers = len(df)
    logging.info(f"Successfully extracted {total_subscribers} subscriber records.")
    
    # ==========================================
    # 2. HARD STOPS (SCORE = 0)
    # ==========================================
    # Hierarchical priority for exclusion reasons (authoritative):
    # 1. Fiber_Competitor → Fiber_Cannibalization
    # 2. Infeasible → RF_Failure
    # 3. CONSTRAINED capacity → Cell_Overload
    # 4. Otherwise → eligible
    
    hard_stop_conditions = [
        df['radio_feasibility_class'].eq('Fiber_Competitor'),
        df['radio_feasibility_class'].eq('Infeasible'),
        df['current_capacity_proxy_status'].eq('CONSTRAINED')
    ]
    hard_stop_choices = [
        'Fiber_Cannibalization',
        'RF_Failure',
        'Cell_Overload'
    ]
    
    df['FWA_exclusion_reason'] = np.select(hard_stop_conditions, hard_stop_choices, default=None)
    df['is_hard_stop'] = df['FWA_exclusion_reason'].notna()
    
    # ==========================================
    # 3. PENALTY APPLICATION & BASE SCORE
    # ==========================================
    # Base score is 100
    df['FWA_suitability_score'] = 100.0
    
    # Calculate penalties vectorized
    penalty_5g_coverage = (df['coverage_5g_flag'] == False).astype(int) * -20
    penalty_arpu = (df['arpu_band'] == 'Low ARPU').astype(int) * -15
    
    total_penalty = penalty_5g_coverage + penalty_arpu
    df['FWA_suitability_score'] += total_penalty
    
    # Overwrite Hard Stops with 0
    df.loc[df['is_hard_stop'], 'FWA_suitability_score'] = 0.0
    
    # Clip to ensure bounds [0, 100]
    df['FWA_suitability_score'] = df['FWA_suitability_score'].clip(lower=0, upper=100)
    
    # ==========================================
    # 4. SUITABILITY BAND MAPPING
    # ==========================================
    band_conditions = [
        (df['FWA_suitability_score'] >= 80),
        (df['FWA_suitability_score'] >= 60),
        (df['FWA_suitability_score'] >= 40),
        (df['FWA_suitability_score'] < 40)
    ]
    band_choices = ['Premium', 'Standard', 'Marginal', 'Excluded']
    df['FWA_suitability_band'] = np.select(band_conditions, band_choices, default='Excluded')
    
    # Force Excluded for Hard Stops
    df.loc[df['is_hard_stop'], 'FWA_suitability_band'] = 'Excluded'
    
    # ==========================================
    # 5. VALIDATION CHECKS
    # ==========================================
    validation_results = {}
    
    # V1: Score bounds
    v1 = (df['FWA_suitability_score'] >= 0).all() and (df['FWA_suitability_score'] <= 100).all()
    validation_results['Score bounded [0, 100]'] = v1
    
    # V2: No nulls in score
    v2 = df['FWA_suitability_score'].notna().all()
    validation_results['No nulls in FWA_suitability_score'] = v2
    
    # V3: Excluded subscribers have exclusion reason
    excluded_mask = df['FWA_suitability_score'] == 0
    v3 = df.loc[excluded_mask, 'FWA_exclusion_reason'].notna().all()
    validation_results['Score=0 has FWA_exclusion_reason'] = v3
    
    # V4: Eligible subscribers have no exclusion reason
    eligible_mask = df['FWA_suitability_score'] > 0
    v4 = df.loc[eligible_mask, 'FWA_exclusion_reason'].isna().all()
    validation_results['Score>0 has NO FWA_exclusion_reason'] = v4
    
    # V5: Valid bands
    valid_bands = {'Premium', 'Standard', 'Marginal', 'Excluded'}
    v5 = df['FWA_suitability_band'].isin(valid_bands).all()
    validation_results['Valid FWA_suitability_band categories'] = v5
    
    all_passed = all(validation_results.values())
    
    # ==========================================
    # 6. EXECUTION SUMMARY PRINTOUT
    # ==========================================
    print("\n" + "="*60)
    print("STEP 9: FWA SUITABILITY SCORING - EXECUTION SUMMARY")
    print("="*60)
    
    print("\n[1] PROCESSED SUBSCRIBERS")
    print(f"Total Subscribers Processed: {total_subscribers:,}")
    
    print("\n[2] HARD STOP STATISTICS")
    hard_stop_count = df['is_hard_stop'].sum()
    eligible_count = total_subscribers - hard_stop_count
    print(f"Subscribers Blocked (Hard Stops): {hard_stop_count:,} ({hard_stop_count/total_subscribers*100:.2f}%)")
    print(f"Subscribers Eligible (Passed):    {eligible_count:,} ({eligible_count/total_subscribers*100:.2f}%)")
    
    print("\n[3] PENALTY DISTRIBUTIONS (Applied to Eligible Base)")
    eligible_df = df[~df['is_hard_stop']]
    p1 = (eligible_df['coverage_5g_flag'] == False).sum()
    p2 = (eligible_df['arpu_band'] == 'Low ARPU').sum()
    print(f"  -20 pts (No 5G Coverage):      {p1:,} ({p1/len(eligible_df)*100:.2f}% of eligible)")
    print(f"  -15 pts (Low ARPU Band):       {p2:,} ({p2/len(eligible_df)*100:.2f}% of eligible)")
    
    print("\n[4] SCORE DISTRIBUTIONS (Eligible Base Only)")
    print(eligible_df['FWA_suitability_score'].describe().to_string())
    
    print("\n[5] SUITABILITY BAND COUNTS")
    band_counts = df['FWA_suitability_band'].value_counts()
    for band in ['Premium', 'Standard', 'Marginal', 'Excluded']:
        count = band_counts.get(band, 0)
        print(f"  {band:<10}: {count:,} ({count/total_subscribers*100:.2f}%)")
        
    print("\n[6] EXCLUSION REASON FREQUENCIES")
    reason_counts = df['FWA_exclusion_reason'].value_counts()
    if reason_counts.empty:
        print("  No exclusions triggered.")
    else:
        for reason, count in reason_counts.items():
            print(f"  {reason:<25}: {count:,} ({count/total_subscribers*100:.2f}%)")
            
    print("\n[7] VALIDATION CHECKS")
    for check, status in validation_results.items():
        status_str = "PASSED" if status else "FAILED"
        print(f"  [{status_str}] {check}")
        
    if not all_passed:
        logging.error("Validation checks failed. Halting pipeline.")
        sys.exit(1)
        
    print("\n[8] BUSINESS INTERPRETATION")
    print("  - The scoring engine successfully isolated technically and commercially")
    print("    viable candidates from the broader subscriber base.")
    print("  - Hard stops (authoritative classification):")
    print("      Fiber_Competitor    -> Fiber_Cannibalization")
    print("      Infeasible          -> RF_Failure")
    print("      CONSTRAINED capacity -> Cell_Overload")
    print("  - The penalty structure correctly downgraded candidates lacking 5G")
    print("    coverage or high ARPU, reflecting the true cost-to-serve")
    print("    and revenue potential for the FWA migration campaign.")
    
    print("\n[9] READINESS FOR STEP 10")
    print("  - The FWA_suitability_score and FWA_suitability_band are now ready")
    print("    to be fed into the K-Prototypes clustering algorithm (Step 10).")
    print("  - The continuous score will serve as a numerical feature, while the")
    print("    band will serve as a categorical feature for persona segmentation.")
    print("="*60 + "\n")
    
    # ==========================================
    # 7. PERSISTENCE
    # ==========================================
    output_cols = [
        'subscriber_id', 'FWA_suitability_score', 'FWA_suitability_band', 'FWA_exclusion_reason'
    ]
    df_output = df[output_cols]
    
    # Save to CSV for inspection / next step input
    output_filename = "step9_fwa_suitability_scores.csv"
    df_output.to_csv(output_filename, index=False)
    logging.info(f"Scored dataset saved to {output_filename}")

    # Persist to database: update abt_subscriber_month with new scores
    logging.info("Persisting scores to cleaned_data.abt_subscriber_month...")
    df_persist = df_output.rename(columns={
        'FWA_suitability_score': 'fwa_suitability_score',
        'FWA_suitability_band': 'fwa_suitability_band',
        'FWA_exclusion_reason': 'fwa_exclusion_reason'
    })
    try:
        df_persist.to_sql('step9_scores_tmp', engine, schema='cleaned_data', if_exists='replace', index=False)
        with engine.begin() as conn:
            conn.execute(sqlalchemy.text("""
                UPDATE cleaned_data.abt_subscriber_month a
                SET fwa_suitability_score = s.fwa_suitability_score,
                    fwa_suitability_band = s.fwa_suitability_band,
                    fwa_exclusion_reason = s.fwa_exclusion_reason
                FROM cleaned_data.step9_scores_tmp s
                WHERE a.subscriber_id = s.subscriber_id
            """))
        logging.info("Scores successfully persisted to ABT.")
    except Exception as e:
        logging.error(f"Database persistence failed: {e}")
        sys.exit(1)

    logging.info("Step 9 completed successfully.")

if __name__ == "__main__":
    run_step9()
