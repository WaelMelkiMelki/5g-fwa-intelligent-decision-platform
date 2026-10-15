# coding: utf-8
"""
Trial B — post-hoc correction trial (full-base training)
Purpose: Compare eligible-only (2,629 / 4.6%) vs full-base (12,412 / 8.4%) training
         for churn prediction, to decide (a) vs (b) before Step 5 re-runs.

Parity: XGB constructor matches step12_supervised_churn_model.py EXACTLY
        parameter-for-parameter. Only permitted differences: population
        (unfiltered 12,412) and scale_pos_weight (11370/1042 ≈ 10.91).

Step12 actual constructor (quoted for auditability, from step12_supervised_churn_model.py:116-126):
    base_xgb = xgb.XGBClassifier(
        n_estimators=300,
        max_depth=6,
        learning_rate=0.05,
        subsample=0.8,
        colsample_bytree=0.8,
        scale_pos_weight=scale_pos_weight,  # 20.73 eligible-only vs 10.91 full-base
        eval_metric='logloss',
        random_state=42,
        n_jobs=-1
    )
    calibrated_model = CalibratedClassifierCV(
        estimator=base_xgb,
        method='sigmoid',
        cv=5
    )
    # PLUS: train_test_split(test_size=0.20, random_state=42, stratify=y)

Artifacts: ALL to correction_backup/ only; NO overwrite of cleaned_data.step12_churn_predictions
"""

import pandas as pd
import numpy as np
from pathlib import Path
from sqlalchemy import create_engine
import xgboost as xgb
from sklearn.model_selection import train_test_split, StratifiedKFold, cross_val_predict
from sklearn.metrics import roc_auc_score, average_precision_score, recall_score, precision_score, f1_score
from sklearn.calibration import CalibratedClassifierCV
import warnings
warnings.filterwarnings('ignore')

DB_CONNECTION_STRING = __import__("os").environ["FWA_DB_URL"]
engine = create_engine(DB_CONNECTION_STRING)

EXCLUDE_COLS = [
    'subscriber_id', 'snapshot_month', 'address_id', 'msisdn',
    'activation_date',
    'fwa_suitability_score', 'fwa_suitability_band', 'fwa_exclusion_reason',
    'candidate_prioritization_score', 'suitability_based_ranking'
]
TARGET_COL = 'churn'

# For parity audit, log exact constructor used
CONSTRUCTOR_QUOTE = """base_xgb = xgb.XGBClassifier(
    n_estimators=300,
    max_depth=6,
    learning_rate=0.05,
    subsample=0.8,
    colsample_bytree=0.8,
    scale_pos_weight=10.91,  # full-base: 11370/1042
    eval_metric='logloss',
    random_state=42,
    n_jobs=-1
)"""

def load_unfiltered():
    print("="*70)
    print("TRIAL B: FULL-BASE (12,412) CHURN MODEL")
    print("="*70)
    print("\n[1] Loading UNFILTERED ABT (12,412)...")
    query = "SELECT * FROM cleaned_data.abt_subscriber_month"
    df = pd.read_sql(query, engine)
    print(f"   -> Rows: {len(df):,}")
    df[TARGET_COL] = pd.to_numeric(df[TARGET_COL], errors='coerce').fillna(0).astype(int)
    pos = df[TARGET_COL].sum()
    neg = len(df) - pos
    rate = pos/len(df)*100
    spw = neg/pos if pos>0 else 1.0
    print(f"   -> Positives: {pos:,} ({rate:.2f}%) Negatives: {neg:,} SPW: {spw:.2f}")
    # Eligible slice for diagnostic
    df_elig = df[df['fwa_suitability_score'] > 0]
    print(f"   -> Eligible slice: {len(df_elig):,} (churn {df_elig[TARGET_COL].sum()} / {df_elig[TARGET_COL].mean()*100:.2f}%)")
    # Feature prep identical to step12
    feature_cols = [c for c in df.columns if c not in EXCLUDE_COLS and c != TARGET_COL]
    X = df[feature_cols].copy()
    y = df[TARGET_COL].copy()
    cat_cols = X.select_dtypes(include=['object','category','bool']).columns.tolist()
    print(f"   -> Feature cols: {len(feature_cols)} (num {len(X.select_dtypes(include=['number']).columns)} cat {len(cat_cols)})")
    X = pd.get_dummies(X, columns=cat_cols, drop_first=True, dtype=int)
    print(f"   -> After OHE: {X.shape[1]} features")
    X = X.fillna(-999)
    # Keep df with eligibility flag for later scoring
    df['is_eligible'] = df['fwa_suitability_score'] > 0
    return X, y, df, spw

def main():
    X, y, df_full, spw = load_unfiltered()
    # Verify parity SPW
    expected_spw = 11370/1042
    print(f"\n[Parity] Expected SPW full-base 11370/1042={expected_spw:.4f}, computed {spw:.4f} (use computed)")
    # Use computed (10.91) which matches 11370/1042 within rounding
    spw = float(spw)

    print("\n[2] Stratified 80/20 split (random_state=42)...")
    X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.20, random_state=42, stratify=y)
    print(f"   -> Train {len(X_train):,} (churn {y_train.mean()*100:.2f}%) Test {len(X_test):,} (churn {y_test.mean()*100:.2f}%)")

    print("\n[3] Training XGB + Platt (parity constructor)...")
    print("   Constructor:")
    print(CONSTRUCTOR_QUOTE)
    base_xgb = xgb.XGBClassifier(
        n_estimators=300,
        max_depth=6,
        learning_rate=0.05,
        subsample=0.8,
        colsample_bytree=0.8,
        scale_pos_weight=spw,
        eval_metric='logloss',
        random_state=42,
        n_jobs=-1
    )
    base_xgb.fit(X_train, y_train)
    print("   -> Base fit done")
    # Feature importances
    feat_imp = pd.Series(base_xgb.feature_importances_, index=X.columns).sort_values(ascending=False)
    print("\n   [Top10 Feature Importances (Gain)]")
    for i,(f,v) in enumerate(feat_imp.head(10).items(),1):
        print(f"      {i:2d}. {f:<45} {v:.4f}")

    calibrated = CalibratedClassifierCV(estimator=base_xgb, method='sigmoid', cv=5)
    print("\n   -> Fitting CalibratedClassifierCV (5-fold, this may take a moment)...")
    calibrated.fit(X_train, y_train)
    print("   -> Calibration done")

    print("\n[4] Holdout evaluation...")
    y_prob_test = calibrated.predict_proba(X_test)[:,1]
    roc = roc_auc_score(y_test, y_prob_test)
    pr = average_precision_score(y_test, y_prob_test)
    baseline = y_test.mean()
    print(f"   ROC-AUC: {roc:.4f}")
    print(f"   PR-AUC : {pr:.4f} (baseline {baseline:.4f} x{pr/baseline:.2f})")

    # Threshold sweep
    taus = [0.05,0.10,0.15,0.20,0.25,0.30,0.35,0.50]
    rows=[]
    print("\n   Threshold sweep (test):")
    print("   tau    recall   prec    f1      flagged  TP  FP  TN  FN")
    for tau in taus:
        y_pred = (y_prob_test >= tau).astype(int)
        rec = recall_score(y_test, y_pred, zero_division=0)
        prec = precision_score(y_test, y_pred, zero_division=0)
        f1 = f1_score(y_test, y_pred, zero_division=0)
        flagged = int(y_pred.sum())
        tp = int(((y_test==1)&(y_pred==1)).sum())
        fp = int(((y_test==0)&(y_pred==1)).sum())
        tn = int(((y_test==0)&(y_pred==0)).sum())
        fn = int(((y_test==1)&(y_pred==0)).sum())
        print(f"   {tau:.2f}   {rec:.4f}  {prec:.4f}  {f1:.4f}  {flagged:4d}    {tp:3d} {fp:3d} {tn:4d} {fn:3d}")
        rows.append({"tau":tau,"recall":rec,"precision":prec,"f1":f1,"flagged":flagged,"tp":tp,"fp":fp,"tn":tn,"fn":fn})

    # Train vs test gap
    y_prob_train = calibrated.predict_proba(X_train)[:,1]
    roc_train = roc_auc_score(y_train, y_prob_train)
    pr_train = average_precision_score(y_train, y_prob_train)
    print(f"\n   Train ROC {roc_train:.4f} PR {pr_train:.4f} | Gap ROC {roc_train-roc:.4f} PR {pr_train-pr:.4f}")

    # 5-fold CV pooled
    print("\n[5] 5-fold CV pooled (cross_val_predict, this will take a moment)...")
    cv = StratifiedKFold(n_splits=5, shuffle=True, random_state=42)
    # Use base_xgb calibrated? For CV we need to replicate same pipeline: base + calibration inside CV is expensive.
    # Instead, use calibrated estimator inside cross_val_predict (will redo calibration per fold)
    # Simpler: use cross_val_predict on calibrated wrapper
    from sklearn.model_selection import cross_val_predict as cvp
    # For pooled, predict on full X via CV (calibrated inside each fold)
    y_prob_cv = cvp(calibrated, X, y, cv=cv, method='predict_proba')[:,1]
    roc_cv = roc_auc_score(y, y_prob_cv)
    pr_cv = average_precision_score(y, y_prob_cv)
    baseline_full = y.mean()
    print(f"   CV pooled ROC {roc_cv:.4f} PR {pr_cv:.4f} (baseline {baseline_full:.4f} x{pr_cv/baseline_full:.2f})")
    print(f"   Holdout vs CV gap: ROC {abs(roc-roc_cv):.4f} PR {abs(pr-pr_cv):.4f}")

    # Eligible-slice diagnostic (score eligible subset with full-base model)
    print("\n[6] Eligible-slice diagnostic (full-base model scoring eligible 2,629)...")
    mask_elig = df_full['is_eligible'].values
    # X_elig is subset of X where is_eligible True
    X_elig = X[mask_elig]
    y_elig = y[mask_elig]
    y_prob_elig = calibrated.predict_proba(X_elig)[:,1]
    roc_elig = roc_auc_score(y_elig, y_prob_elig)
    pr_elig = average_precision_score(y_elig, y_prob_elig)
    base_elig = y_elig.mean()
    print(f"   Eligible slice ROC {roc_elig:.4f} PR {pr_elig:.4f} (baseline {base_elig:.4f} x{pr_elig/base_elig:.2f}) n={len(y_elig)} pos={y_elig.sum()}")
    print("   (Noisy diagnostic — model trained on different population)")

    # Persist trial scored probabilities for eligible subset
    out_dir = Path(r"C:\Users\w50057230\Downloads\FWA project\correction_backup")
    out_dir.mkdir(parents=True, exist_ok=True)
    df_elig_probs = pd.DataFrame({
        'subscriber_id': df_full.loc[mask_elig, 'subscriber_id'].values,
        'snapshot_month': df_full.loc[mask_elig, 'snapshot_month'].values,
        'churn_probability_trialB': y_prob_elig,
        'churn_true': y_elig.values,
        'fwa_suitability_score': df_full.loc[mask_elig, 'fwa_suitability_score'].values,
    })
    # Add risk bands on trial probabilities (same bins as step12)
    bins = [0.0, 0.15, 0.35, 0.60, 1.0]
    labels = ['Low Risk','Medium Risk','High Risk','Critical Risk']
    df_elig_probs['churn_risk_band_trialB'] = pd.cut(df_elig_probs['churn_probability_trialB'], bins=bins, labels=labels, include_lowest=True)
    elig_csv = out_dir / "step12_fullbase_trial_eligible_probs_20260830.csv"
    df_elig_probs.to_csv(elig_csv, index=False)
    print(f"\n   -> Eligible probs CSV: {elig_csv} rows={len(df_elig_probs)}")

    # Persist metrics
    thresh_df = pd.DataFrame(rows)
    thresh_csv = out_dir / "step12_fullbase_trial_thresholds_20260830.csv"
    thresh_df.to_csv(thresh_csv, index=False)
    print(f"   -> Thresholds CSV: {thresh_csv}")

    feat_csv = out_dir / "step12_fullbase_trial_feature_importance_20260830.csv"
    feat_imp.head(50).to_csv(feat_csv, header=True)
    print(f"   -> Feature importance CSV: {feat_csv}")

    # Write summary JSON
    import json, datetime
    summary = {
        "trial": "B_fullbase_12412",
        "timestamp": datetime.datetime.now().isoformat(),
        "constructor_quote": CONSTRUCTOR_QUOTE,
        "population": {"total": int(len(df_full)), "positives": int(y.sum()), "rate": float(y.mean()), "spw": float(spw)},
        "split": {"test_size": 0.20, "random_state": 42, "stratify": True, "train_n": int(len(X_train)), "test_n": int(len(X_test)), "test_pos": int(y_test.sum()), "test_rate": float(y_test.mean())},
        "holdout": {"roc_auc": float(roc), "pr_auc": float(pr), "baseline": float(baseline), "pr_x_baseline": float(pr/baseline), "roc_train": float(roc_train), "pr_train": float(pr_train)},
        "cv_pooled": {"roc_auc": float(roc_cv), "pr_auc": float(pr_cv), "baseline_full": float(baseline_full), "pr_x_baseline": float(pr_cv/baseline_full)},
        "eligible_slice": {"n": int(len(y_elig)), "positives": int(y_elig.sum()), "rate": float(base_elig), "roc_auc": float(roc_elig), "pr_auc": float(pr_elig), "pr_x_baseline": float(pr_elig/base_elig)},
        "gates": {
            "roc_ge_0_65": bool(roc >= 0.65),
            "pr_ge_2x_baseline": bool(pr >= 2*baseline),
            "cv_consistent_within_0_05": bool(abs(roc-roc_cv) <= 0.05 and abs(pr-pr_cv) <= 0.05),
            "roc_gap": float(abs(roc-roc_cv)),
            "pr_gap": float(abs(pr-pr_cv))
        },
        "thresholds": rows,
        "top10_features": feat_imp.head(10).to_dict()
    }
    summary_path = out_dir / "step12_fullbase_trial_summary_20260830.json"
    with open(summary_path, "w", encoding="utf-8") as f:
        json.dump(summary, f, indent=2)
    print(f"   -> Summary JSON: {summary_path}")

    print("\n" + "="*70)
    print("TRIAL B COMPLETE")
    print("="*70)
    print(f"Holdout ROC {roc:.4f} PR {pr:.4f} baseline {baseline:.4f} x{pr/baseline:.2f}")
    print(f"CV      ROC {roc_cv:.4f} PR {pr_cv:.4f}")
    print(f"Gates: ROC>=0.65 {roc>=0.65} | PR>=2x {pr>=2*baseline} | CV consistent {abs(roc-roc_cv)<=0.05 and abs(pr-pr_cv)<=0.05}")
    return summary

if __name__ == "__main__":
    main()
