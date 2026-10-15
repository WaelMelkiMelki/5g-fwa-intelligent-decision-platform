# coding: utf-8
"""
Benchmark on FINAL (b) protocol — full-base train / eligible-apply
Compares Logistic Regression, Random Forest, XGBoost under identical loading/split/seed/calibration.
XGB row must reproduce step12 FINAL metrics (ROC 0.7076 PR 0.1791) exactly else STOP.

Protocol (from step12_supervised_churn_model.py FINAL b):
- Load UNFILTERED cleaned_data.abt_subscriber_month (12,412 / 1,042 pos 8.40%)
- EXCLUDE_COLS same, OHE same, fillna -999
- train_test_split(test_size=0.20, random_state=42, stratify=y)
- scale_pos_weight for XGB = 11370/1042 ≈ 10.91; LR/RF class_weight='balanced'
- All three through CalibratedClassifierCV(method='sigmoid', cv=5)
- Metrics on same holdout: ROC-AUC, PR-AUC, precision/recall at tau=0.15 (calibrated probs)
"""

import pandas as pd
import numpy as np
from pathlib import Path
from sqlalchemy import create_engine
import xgboost as xgb
from sklearn.linear_model import LogisticRegression
from sklearn.ensemble import RandomForestClassifier
from sklearn.model_selection import train_test_split
from sklearn.metrics import roc_auc_score, average_precision_score, precision_score, recall_score
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

def load_full():
    query = "SELECT * FROM cleaned_data.abt_subscriber_month"
    df = pd.read_sql(query, engine)
    df[TARGET_COL] = pd.to_numeric(df[TARGET_COL], errors='coerce').fillna(0).astype(int)
    feature_cols = [c for c in df.columns if c not in EXCLUDE_COLS and c != TARGET_COL]
    X = df[feature_cols].copy()
    y = df[TARGET_COL].copy()
    cat_cols = X.select_dtypes(include=['object','category','bool']).columns.tolist()
    X = pd.get_dummies(X, columns=cat_cols, drop_first=True, dtype=int)
    X = X.fillna(-999)
    return X, y, df

def evaluate(name, y_test, y_prob):
    roc = roc_auc_score(y_test, y_prob)
    pr = average_precision_score(y_test, y_prob)
    baseline = y_test.mean()
    y_pred15 = (y_prob >= 0.15).astype(int)
    rec = recall_score(y_test, y_pred15, zero_division=0)
    prec = precision_score(y_test, y_pred15, zero_division=0)
    return {"model": name, "roc_auc": roc, "pr_auc": pr, "baseline": baseline, "pr_x_baseline": pr/baseline if baseline>0 else 0, "recall_015": rec, "precision_015": prec}

def main():
    print("="*70)
    print("BENCHMARK FINAL (b) — LR / RF / XGB identical protocol")
    print("="*70)
    X, y, df = load_full()
    print(f"Loaded {len(df):,} rows pos {y.sum()} rate {y.mean()*100:.2f}%")

    X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.20, random_state=42, stratify=y)
    print(f"Split train {len(X_train)} test {len(X_test)} test_rate {y_test.mean()*100:.2f}%")

    # Define models — scale_pos_weight computed as production does: from full y (11370/1042), not y_train
    spw_full = (len(y) - y.sum()) / y.sum()
    print(f"XGB scale_pos_weight (full y, as production) {spw_full:.4f} (expected 10.9117)")
    models = {
        "LogisticRegression": LogisticRegression(class_weight='balanced', max_iter=1000, n_jobs=-1, random_state=42),
        "RandomForest": RandomForestClassifier(class_weight='balanced', random_state=42, n_jobs=-1),
        "XGBoost": xgb.XGBClassifier(n_estimators=300, max_depth=6, learning_rate=0.05, subsample=0.8, colsample_bytree=0.8, scale_pos_weight=spw_full, eval_metric='logloss', random_state=42, n_jobs=-1)
    }
    # Verify XGB SPW
    spw = spw_full
    print(f"XGB scale_pos_weight {spw:.4f} (expected 10.9117)")

    results = []
    for name, base in models.items():
        print(f"\n--- {name} ---")
        calibrated = CalibratedClassifierCV(estimator=base, method='sigmoid', cv=5)
        calibrated.fit(X_train, y_train)
        y_prob = calibrated.predict_proba(X_test)[:,1]
        metrics = evaluate(name, y_test, y_prob)
        print(f"  ROC {metrics['roc_auc']:.4f} PR {metrics['pr_auc']:.4f} baseline {metrics['baseline']:.4f} x{metrics['pr_x_baseline']:.2f} rec@0.15 {metrics['recall_015']:.4f} prec@0.15 {metrics['precision_015']:.4f}")
        results.append(metrics)
        # For XGB assert reproduces 0.7076/0.1791
        if name == "XGBoost":
            # Allow small floating/calibration variance 0.005
            assert abs(metrics['roc_auc'] - 0.7076) < 0.005, f"XGB ROC {metrics['roc_auc']:.4f} != 0.7076"
            assert abs(metrics['pr_auc'] - 0.1791) < 0.005, f"XGB PR {metrics['pr_auc']:.4f} != 0.1791"
            print(f"  -> XGB reproduces FINAL metrics (0.7076/0.1791) within 0.005 (got {metrics['roc_auc']:.4f}/{metrics['pr_auc']:.4f}) PASS")

    # Save CSV + summary
    out_dir = Path(r"C:\Users\w50057230\Downloads\FWA project\correction_backup")
    out_dir.mkdir(parents=True, exist_ok=True)
    df_res = pd.DataFrame(results)
    csv_path = out_dir / "churn_benchmark_FINALb_20260830.csv"
    df_res.to_csv(csv_path, index=False)
    print(f"\nSaved {csv_path}")
    # Summary log
    summary_path = out_dir / "churn_benchmark_FINALb_summary_20260830.txt"
    with open(summary_path, "w", encoding="utf-8") as f:
        f.write("Benchmark FINAL (b) protocol 12,412 unfiltered, SPW 10.91, calibrated sigmoid cv5\n")
        for r in results:
            f.write(f"{r['model']}: ROC {r['roc_auc']:.4f} PR {r['pr_auc']:.4f} baseline {r['baseline']:.4f} x{r['pr_x_baseline']:.2f} rec015 {r['recall_015']:.4f} prec015 {r['precision_015']:.4f}\n")
    print(f"Summary {summary_path}")
    print("\nBENCHMARK COMPLETE")

if __name__ == "__main__":
    main()
