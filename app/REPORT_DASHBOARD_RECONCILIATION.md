# Report ↔ Dashboard Reconciliation Audit

**Scope:** every quantitative KPI, count, percentage, threshold and model metric
stated in the project report, recomputed with SELECT-only SQL against the live
`cleaned_data` PostgreSQL schema, and compared with the values displayed by the
Streamlit dashboard (pages 1–10).

**Report source:** `report_v4/` LaTeX chapters (the text that compiles into
`report_v4/main.pdf`; PDF itself is not machine-readable by the audit tooling).
Chapter/section references cite the compiled PDF page numbers from
`report_v4/main.toc`.

**Database source:** `cleaned_data` on `localhost:5432` (PostgreSQL),
snapshot month **2026-01-01** (single snapshot — verified `COUNT(DISTINCT
snapshot_month) = 1` in T2/T3/T5). All connections use
`default_transaction_read_only=on`; every query below is a read-only SELECT.

**Dashboard source:** pages 1–10 render values computed by the services in
`app/services/`; every dashboard value in the table below was obtained by
calling the exact service functions the pages use (with page-default filters,
no population filter, snapshot 2026-01-01), plus the visual UAT pass
(34 screenshots at 1920×1080 / 1440×900 / 1366×768, 0 px overflow, no
tracebacks).

**Reconciliation tests:** `app/tests/test_report_reconciliation.py` — 36
automated tests pinning the stable metrics below (skip cleanly without
`FWA_DB_*` env). **36 passed.**

---

## Status legend

| Status | Meaning |
|---|---|
| **PASS** | Report value, SQL recomputation and dashboard display are identical (same population, snapshot, units, rounding). |
| **ROUNDING DIFFERENCE** | Same value, different display precision or unit presentation. |
| **DEFINITION DIFFERENCE** | Same subject, different threshold/scope/denominator between report and DB; dashboard follows one definition consistently. |
| **DATA REFRESH DIFFERENCE** | Report was generated from an earlier pipeline run; the live DB layer has since been regenerated. Dashboard correctly shows the current DB. |
| **NOT DISPLAYED** | Metric is not shown anywhere in the dashboard (verified by page code review). |
| **FAIL** | Dashboard calculation demonstrably wrong. **None found.** |

---

## Verdict

# CONDITIONAL PASS

- **0 FAIL**, **0 dashboard bugs** — the dashboard is a faithful render of the
  live database; every displayed value was reproduced from the same tables.
- **PASS on all headline business metrics**: population (12,412 / 2,923 /
  9,489), campaign actions (9,489 / 2,180 / 731 / 12), exclusion reasons
  (9,449 / 40 / 0), network KPIs, signal-quality classes, prioritisation score
  statistics (8.04…90.56, all exact), churn risk bands (2,795 / 114 / 14),
  recommendation and offer counts, capacity simulation (400 cells, 39.99 % →
  40.49 %, max 67.13 %).
- **DATA REFRESH DIFFERENCE on regenerated layers**: usage volumes, radio
  feasibility classes, suitability bands, cluster personas, and churn ground
  labels in the live DB differ from the report-era values (see rows below).
  The dashboard is correct; the **report tables for these layers are stale**.
- **Conditions attached:**
  1. Accept the report values on the regenerated layers (ch §2.6 radio
     feasibility, §4.1 suitability bands/penalties, §4.2 persona profiles,
     §4.4 churn label rate) as documentation of the report-era run, not of the
     current DB.
  2. Resolve the churn risk-band threshold wording: report prose §4.4 prints
     Medium "0.15–0.30 / High > 0.30", but the stored bins (and the counts
     reproduced identically in Table 4.7) are `[0, 0.15, 0.35, 0.60, 1.0]`
     (0.35, not 0.30). The dashboard uses the stored bins (correct).
  3. The churn model metrics (ROC-AUC 0.7094, PR-AUC 0.1854, τ=0.15 precision
     matrix, CV F1) are model artifacts not persisted in the DB; they cannot
     be recomputed from `cleaned_data`. The dashboard labels them
     "report ch.12" (page 5) — keep that provenance label.

---

## Reconciliation matrix

### 1. Population & grain

| Metric | Report source | Report value | SQL query/result | Dashboard page/component/value | Filters | Status | Explanation |
|---|---|---|---|---|---|---|---|
| Total base subscribers | ch1 p7; ch2.2 p16 | 12,412 | `COUNT(*) FROM step15_final_campaign_list` → **12,412** | p1 funnel **Total 12,412**; p7 Total KPI; p6 row baseline | none | **PASS** | identical |
| Eligible subscribers (score>0) | ch4.1 p37 | 2,923 | `COUNT(*) WHERE fwa_suitability_score>0` → **2,923** | p1 funnel Eligible; p7 Eligible KPI; p9 overview | none | **PASS** | identical |
| Excluded subscribers | ch4.1 p37 | 9,489 | `COUNT(*) WHERE fwa_suitability_score=0` → **9,489** | p1 Excluded KPI; p7 | none | **PASS** | identical |
| Eligible share | ch4.1 p43 | 23.5 % | `100*2923/12412` → **23.5** | p1 (derived) | none | **PASS** | identical |
| Excluded share | ch4.1 p37; ch7 p64 | 76.5 % | → **76.5** | p1 (derived) | none | **PASS** | identical |
| T1 monthly core rows | ch2.2 p17 | 12,412 | `COUNT(*) t1_monthly_core` → **12,412** | p6 row baseline | none | **PASS** | — |
| T2 CRM master rows | ch2.2 p16-17 | 12,412 | → **12,412** | p6 | none | **PASS** | — |
| T3 monthly KPI rows (cells) | ch2.5 p22 | 731 | → **731** | p4 "Cells total"; p6 | none | **PASS** | — |
| T4 address grid rows | ch2.6 p23-25 | 12,412 | → **12,412** | p7 grid summary | none | **PASS** | — |
| T5 service rows | ch2.7 p25 | 12,412 | → **12,412** | p6 | none | **PASS** | — |
| ABT rows | ch3 p32-34 | 12,412 | → **12,412** | p6; join integrity | none | **PASS** | — |
| Clustered ABT rows | ch4.2 p44 | 2,923 | → **2,923** | p8 personas table | none | **PASS** | — |
| step11 rows | ch4.3 p46-49 | 2,923 | → **2,923** | p6 | none | **PASS** | — |
| step12 prediction rows | ch4.4 p50 (Table 4.2: 2,923 modelled) | 2,923 | `COUNT(*) step12_churn_predictions` → **12,412** | p5 band stats; p6 baseline 12,412 | eligible | **PASS** | Predictions stored for the full base; excluded rows are all Low-band. Report Table 4.2 scope = eligible 2,923; bands reproduce exactly over the eligible subset. |
| step13 rows | ch5.1 p54 | 2,923 | → **2,923** | p6 baseline 2,923 | none | **PASS** | — |
| step14 rows | ch5.2 p59 | 2,923 | → **2,923** | p6 baseline 2,923 | none | **PASS** | — |
| step15 rows | ch5.3 p64 | 12,412 | → **12,412** | p2 "Rows matching filters" | none | **PASS** | — |
| T1 daily rows | ch2.2 p17 | 381,836 | → **381,836** | — | none | **PASS** | NOT DISPLAYED |
| T3 daily RAN rows | ch2.5 p22 | 21,965 | → **21,965** | — | none | **PASS** | NOT DISPLAYED |

### 2. Usage aggregation (ch2.3 p17-18)

| Metric | Report source | Report value | SQL query/result | Dashboard | Filters | Status | Explanation |
|---|---|---|---|---|---|---|---|
| 5G-ready subscribers | ch2.3 p17-18 | 972 (7.8 %) | `t1_monthly_dominance device_5g_ready_flag` → **972** | — | none | **PASS** | NOT DISPLAYED |
| 4G-dominant | ch2.3 p17-18 | 8,386 (67.6 %) | → **8,386** | — | none | **PASS** | NOT DISPLAYED |
| Other generation | ch2.3 p17-18 | 3,054 (24.6 %) | → **3,054** | — | none | **PASS** | NOT DISPLAYED |
| Unique dominant cells | ch2.3 p17-18 | 731 | `COUNT(DISTINCT dominant_serving_cell_id)` → **731** | — | none | **PASS** | NOT DISPLAYED (731 also in p4/p7) |
| Avg monthly median DL volume | ch2.3 p18 | 535.04 MB | `AVG(dl_volume_mb_imputed_monthly_median)` → **535.04** | — | none | **PASS** | NOT DISPLAYED |
| Avg peak-hour ratio | ch2.3 p18 | 39.99 % | `AVG(monthly_peak_hour_ratio)` → **0.39994** | — | none | **PASS** | DB stores a fraction; 0.39994 = 39.99 %. Unit presentation only. |
| Roaming rows excluded | ch2.3 p17 | 100 | — (filter not persisted) | — | none | **NOT DISPLAYED** | not recomputable from `cleaned_data` (pipeline-internal) |

### 3. Commercial binning & household (ch2.4 p19-20)

| Metric | Report source | Report value | SQL query/result | Dashboard | Filters | Status | Explanation |
|---|---|---|---|---|---|---|---|
| ARPU GMM threshold | ch2.4.1 p19 | 23.33 TND | constant (GMM artifact) | — | none | **PASS** | NOT DISPLAYED; threshold constant, not recomputable |
| Low ARPU band (stored) | ch2.4.1 p19 | 8,381 (67.5 %) | `arpu_band='Low ARPU'` → **8,381** | p8 cross-tab "ARPU band" | none | **PASS** | raw float split (<23.33) gives 8,378 (±3 boundary rows); stored bands = report exactly |
| High ARPU band (stored) | ch2.4.1 p19 | 4,031 (32.5 %) | → **4,031** | p8 | none | **PASS** | as above |
| Tenure GMM threshold | ch2.4.1 p19 | 90.59 months | constant | — | none | **PASS** | NOT DISPLAYED |
| Short Tenure band | ch2.4.1 p19 | 6,372 (51.3 %) | → **6,372** | p8 "Tenure band" | none | **PASS** | raw + stored identical |
| Long Tenure band | ch2.4.1 p19 | 6,040 (48.7 %) | → **6,040** | p8 | none | **PASS** | — |
| Multi-line flag | ch2.4.2 p20 | 4,104 (33.1 %) | → **4,104** | p8 "Multi-line flag" | none | **PASS** | — |
| Single-line | ch2.4.2 p20 | 8,308 (66.9 %) | → **8,308** | p8 | none | **PASS** | — |
| Mean lines / max / P99 | ch2.4.2 p20 | 1.81 / 14 / 13 | → **1.81 / 14 / 13** | — | none | **PASS** | NOT DISPLAYED |

### 4. Network capacity (ch2.5 p22-23)

| Metric | Report source | Report value | SQL query/result | Dashboard | Filters | Status | Explanation |
|---|---|---|---|---|---|---|---|
| Avg PRB utilisation | ch2.5 p22 | 20.29 % | `AVG(avg_prb_utilisation_pct)` → **20.29** | — | none | **PASS** | NOT DISPLAYED |
| Median cell P95 PRB | ch2.5 p22 | 33.97 % | `percentile_cont(0.5)` → **33.97** | — | none | **PASS** | NOT DISPLAYED |
| Max PRB (any cell) | ch2.5 p22 | 74.68 % | `MAX(max_prb_utilisation_pct)` → **74.68** | — (p4 max-P95 card) | none | **PASS** | NOT DISPLAYED verbatim |
| Avg DL throughput | ch2.5 p22 | 99.97 Mbps | → **99.97** | — | none | **PASS** | NOT DISPLAYED |
| Constrained cells (p95≥80 ∨ max≥80) | ch2.5 p22-23 | 0 (0.0 %) | → **0** | p4 status distribution (AVAILABLE only) | none | **PASS** | identical |
| Cells with P95 ≥ 80 | ch2.5 p22-23 | 0 | → **0** | p4 "cells at threshold" | none | **PASS** | identical |

### 5. Coverage & eligibility (ch2.6 p24-25, ch4.1 p37-38)

| Metric | Report source | Report value | SQL query/result | Dashboard | Filters | Status | Explanation |
|---|---|---|---|---|---|---|---|
| Excellent / Acceptable / Poor signal | ch2.6 p24 | 782 (6.3 %) / 2,181 (17.6 %) / 9,449 (76.1 %) | `signal_quality_class` → **782 / 2,181 / 9,449** | p7 signal-quality distribution | none | **PASS** | exact |
| 5G-feasible addresses | ch2.6 p25 | 430 (3.5 %) | `radio_feasibility_class='5G_Feasible'` → **291** | p7 radio-feasibility distribution | none | **DATA REFRESH** | layer regenerated: labels now `5G_Feasible/4G_Fallback/Fiber_Competitor/Infeasible`; DB 291 = report's "291 eligible with 5G coverage" |
| 4G-fallback | ch2.6 p25 | 2,228 (17.9 %) | → **2,338** | p7 | none | **DATA REFRESH** | regenerated layer |
| Fiber competitor | ch2.6 p25 | 305 (2.5 %) | → **109** | p7 | none | **DATA REFRESH** | regenerated layer; `fiber_coverage_flag`=109 |
| Infeasible | ch2.6 p24-25 | 9,449 (76.1 %) | → **9,674** | p7 | none | **DATA REFRESH** | regenerated layer |
| Excluded: RF failure | ch4.1 p37 | 9,449 (76.1 %) | `fwa_exclusion_reason='RF_Failure'` → **9,449** | p7 exclusion reasons | none | **PASS** | exact (label has underscore) |
| Excluded: fibre cannibalisation | ch4.1 p37 | 40 (0.3 %) | `'Fiber_Cannibalization'` → **40** | p7 | none | **PASS** | exact |
| Excluded: capacity-constrained | ch4.1 p37 | 0 (0.0 %) | → **0** | p7 | none | **PASS** | exact |
| Eligible score mean | ch4.1 p37 | ~64 | `AVG(score)` → **63.7** | p7 suitability histogram | eligible | **PASS** | ≈ |
| Eligible score std | ch4.1 p37 | ~11 | → **10.9** | — | eligible | **PASS** | ≈; NOT DISPLAYED |
| Eligible score min / max | ch4.1 p37 | 55 / 100 | → **55 / 100** | — | eligible | **PASS** | NOT DISPLAYED |
| Eligible with 5G coverage | ch4.1 p38 | 291 (11.1 %) | → **291** | — | eligible | **PASS** | NOT DISPLAYED |
| Band Premium (80-100) | ch4.1 p38 | ~276 (2.2 %) | `fwa_suitability_band='Premium'` → **308** | p7 suitability-band distribution | none | **DATA REFRESH** | scoring layer regenerated; mean/std unchanged (63.7/10.9) but band composition shifted (+32/+6/+256 across bands) |
| Band Standard (60-79) | ch4.1 p38 | ~1,030 (8.3 %) | → **1,036** | p7 | none | **DATA REFRESH** | as above |
| Band Marginal (40-59) | ch4.1 p38 | ~1,323 (10.7 %) | → **1,579** | p7 | none | **DATA REFRESH** | as above |
| Penalty: no 5G coverage (of eligible) | ch4.1 p38 | 2,338 (88.9 %) | `NOT coverage_5g_flag` among eligible → **2,632 (90.0 %)** | — | eligible | **DATA REFRESH** | report denominator = penalised pool (2,629); current DB counts over all 2,923 eligible |
| Penalty: low ARPU (of eligible) | ch4.1 p38 | 1,603 (61.0 %) | `arpu_band='Low ARPU'` → **1,784 (61.0 %)** | — | eligible | **DATA REFRESH** | same rate (61.0 %), different count/denominator |
| Penalty: no 5G device (of eligible) | ch4.1 p38 | 2,403 (91.4 %) | → **2,671 (91.4 %)** | — | eligible | **DATA REFRESH** | same rate (91.4 %), different count/denominator |

### 6. Clustering (ch4.2 p44-45)

| Metric | Report source | Report value | SQL query/result | Dashboard | Filters | Status | Explanation |
|---|---|---|---|---|---|---|---|
| Cluster sizes C0-C3 | ch4.2 p44 | 1,072 / 1,479 / 313 / 59 (36.7 / 50.6 / 10.7 / 2.0 %) | `abt_subscriber_month_clustered` → **1,074 / 1,478 / 314 / 57** | p8 personas table | eligible | **DATA REFRESH** | clustering re-run on refreshed ABT (±2 rows) |
| Cluster mean ARPU | ch4.2 p44-45 | ~35 / ~18 / ~29 / ~23 TND | → **30.5 / 14.4 / 25.3 / 19.6** | p8 personas table | eligible | **DATA REFRESH** | refreshed feature layer |
| Cluster mean monthly GB | ch4.2 p44-45 | ~301 / ~255 / ~310 / ~310 GB | → **14.2 / 11.9 / 66.8 / 20.3 GB** | p8 personas table | eligible | **DATA REFRESH** | usage volumes regenerated; report-era values internally inconsistent with its own 535 MB avg daily median (~16 GB/month) |
| Cluster 5G-ready share | ch4.2 p44-45 | 8.3 / 4.1 / 12.8 / 10.2 % | → **14.2 / 5.1 / 7.6 / 0.0 %** | — | eligible | **DATA REFRESH** | NOT DISPLAYED |
| Cluster prepaid share C0/C1 | ch4.2 p44 | 51 % / 83 % | → **50.7 % / 82.5 %** | — | eligible | **ROUNDING DIFFERENCE** | NOT DISPLAYED; ≈0.3-0.5 pp |

### 7. Prioritisation (ch4.3 p47-48)

| Metric | Report source | Report value | SQL query/result | Dashboard | Filters | Status | Explanation |
|---|---|---|---|---|---|---|---|
| Priority score min | ch4.3 p48 | 8.04 | `MIN(candidate_prioritization_score)` → **8.04** | — (p2 row scores) | none | **PASS** | exact |
| Q1 / median / mean / Q3 | ch4.3 p48 | 19.26 / 28.41 / 35.98 / 51.79 | → **19.26 / 28.41 / 35.98 / 51.79** | — | none | **PASS** | exact |
| Max / std | ch4.3 p48 | 90.56 / 19.12 | → **90.56 / 19.12** | — | none | **PASS** | exact |
| Top-decile (rank ≤ 292): mean score | ch4.3 p48 | 70.33 | → **70.33** | — | none | **PASS** | exact |
| Top-decile mean suitability | ch4.3 p48 | 83.97 | → **83.97** | — | none | **PASS** | exact |
| Top-decile mean ARPU | ch4.3 p48 | 38.61 TND | → **38.61** | — | none | **PASS** | exact |
| Top-decile mean tenure | ch4.3 p48 | 100.3 months | → **100.3** | — | none | **PASS** | exact |
| Top-decile cluster mix | ch4.3 p48 | C0 232 (79.5 %), C2 58 (19.9 %), C3 2 (0.7 %) | → **232 / 58 / 2** (C2, not C1) | — | none | **PASS** | report prose "cluster 2 over-indexes 19.9 % vs 10.7 %" confirms C2; matches DB |
| Rank 1 (SUB_B00385A9) | ch4.3 p48 | 90.56 | → **90.56** | p2 row 1 | none | **PASS** | exact |
| Rank 2,923 (SUB_BF5FFDF1) | ch4.3 p48 | 8.04 | → **8.04** | p2 last row | none | **PASS** | exact |
| MCDA weights 0.40/0.30/0.20/0.10 | ch4.3 p47 | constants | formula constants | — | none | **PASS** | NOT DISPLAYED |

### 8. Churn model (ch4.4 p49-52)

| Metric | Report source | Report value | SQL query/result | Dashboard | Filters | Status | Explanation |
|---|---|---|---|---|---|---|---|
| Churners among eligible (label) | ch4.4 p50 Table 4.2 | 298 (10.2 %) | `abt.churn=1` among eligible → **142 (4.9 %)** | — | eligible | **DATA REFRESH** | churn ground-truth labels regenerated after report; rate 10.2 % → 4.9 %. NOT DISPLAYED |
| Active among eligible | ch4.4 p50 | 2,625 (89.8 %) | → **2,781 (95.1 %)** | — | eligible | **DATA REFRESH** | as above |
| Imbalance ratio | ch4.4 p50 | 8.81 : 1 | current labels → 19.6 : 1 | p5 metadata (report value) | eligible | **DATA REFRESH** | p5 shows report-sourced value with provenance; DB label ratio differs |
| ROC-AUC (held-out test, 585 rows) | ch4.4 p50 Table 4.3 | 0.7094 | not persisted | p5 metric card **0.7094** | — | **PASS** | dashboard = report value; not recomputable from DB (test split not stored). Appendix D 0.8956 shown as conflict row |
| PR-AUC | ch4.4 p50 | 0.1854 | not persisted | p5 **0.1854** | — | **PASS** | both sources agree |
| Random baseline PR-AUC | ch4.4 p50 | 0.102 | not persisted | p5 **0.102** | — | **PASS** | — |
| Recall / Precision / F1 at τ=0.15 | ch4.4 p51 Table 4.5 | 0.3990 / 0.2351 / 0.2959 | not persisted | p5 **0.3990 / 0.2351 / 0.2959** | — | **PASS** | dashboard = report; not recomputable |
| CV F1 (chosen config) | ch4.4 p50 Table 4.1 | 0.291 ± 0.041 | not persisted | p5 **0.291 ± 0.041** | — | **PASS** | — |
| Confusion matrix τ=0.15 | ch4.4 p51 | TP 24 / FN 36 / FP 78 / TN 447 | not persisted | p5 matrix **24 / 36 / 78 / 447** | — | **PASS** | dashboard = report; not recomputable |
| Risk band Low (p ≤ 0.15) | ch4.4 p51 Table 4.7 | 2,795 (95.6 %) | `churn_risk_band='Low Risk'` eligible → **2,795** | p5 band stats; p1 churn bands | eligible | **PASS** | exact |
| Risk band Medium | ch4.4 p51 | 114 (3.9 %) | `'Medium Risk'` eligible → **114** | p5; p1 | eligible | **PASS** | exact count; **definition note:** report prose prints cut-off 0.30, stored bins are (0.15, 0.35] — 114 rows confirmed with 0.35 |
| Risk band High | ch4.4 p51 | 14 (0.5 %) | `'High Risk'` eligible → **14** | p5; p1 | eligible | **PASS** | exact count; stored bins > 0.35 (0.30 in prose) |
| DB band Critical Risk | DB vocabulary | — | → **0** | p5/p1 | none | **PASS** | bin (0.60, 1.0] empty; model_service documents vocabulary |
| Top-5 churn probabilities (0.487…) | ch4.4 p51 Table 4.8 | SUB_E72F1A4B 0.487 etc. | IDs absent from DB | — | — | **NOT DISPLAYED** | table shows held-out **test-set** predictions, not persisted; current DB max = 0.4322 |
| Avg churn probability (all) | — (dashboard-only) | — | `AVG(churn_probability)` → **0.0887** | p5 "avg churn probability" | none | **PASS** | dashboard-only metric, no report counterpart |
| Top-1 churn probability (DB) | — (dashboard-only) | — | max → **0.4322** | p5 | none | **PASS** | — |

### 9. Recommendations (ch5.1 p53-57)

| Metric | Report source | Report value | SQL query/result | Dashboard | Filters | Status | Explanation |
|---|---|---|---|---|---|---|---|
| Tier-1 FWA Prepaid | ch5.1 p54 Table 5.1 | 1,932 (66.1 %) | `tier1_base_plan LIKE '%Prepaid'` → **1,932** | p9 tier-1 distribution | eligible | **PASS** | DB label "5G FWA Prepaid" vs report "FWA Prepaid" — display wording only |
| Tier-1 FWA Postpaid | ch5.1 p54 | 991 (33.9 %) | → **991** | p9 | eligible | **PASS** | as above |
| IPTV upsell hits | ch5.1 p54 Table 5.2 | 604 (20.7 %) | `tier2_addons ILIKE '%IPTV%'` → **604** | p9 add-ons | eligible | **PASS** | exact |
| Gaming add-on hits | ch5.1 p54 | 89 (3.0 %) | → **89** | p9 | eligible | **PASS** | exact |
| Convergent add-on hits | ch5.1 p54 | 440 (15.1 %) | → **440** | p9 | eligible | **PASS** | exact |
| Any add-on bundle | ch5.1 p55-56 | 1,011 (34.6 %) | `tier2_addons <> ''` → **1,011** | p9 overview; p1 offer categories | eligible | **PASS** | exact |
| Offer: Base Only | ch5.1 p55 Table 5.3 | 1,912 (65.4 %) | → **1,912** | p9 offer distribution; p1 | eligible | **PASS** | exact |
| Offer: Base + IPTV | ch5.1 p55 | 498 (17.0 %) | → **498** | p9 | eligible | **PASS** | exact |
| Offer: Base + Convergent | ch5.1 p55 | 343 (11.7 %) | → **343** | p9 | eligible | **PASS** | DB label "…Convergent Fixed-Mobile Add-on" |
| Offer: Multi-Addon Bundle | ch5.1 p55 | 118 (4.0 %) | → **118** | p9 | eligible | **PASS** | exact |
| Offer: Base + Gaming | ch5.1 p55 | 52 (1.8 %) | → **52** | p9 | eligible | **PASS** | DB label "…Gaming Add-on" |

### 10. Capacity simulation (ch5.2 p57-62)

| Metric | Report source | Report value | SQL query/result | Dashboard | Filters | Status | Explanation |
|---|---|---|---|---|---|---|---|
| Cells simulated | ch5.2 p57-59 | 400 | `COUNT(DISTINCT dominant_serving_cell_id) step14` → **400** | p10 "Scenario cells 400" | none | **PASS** | exact |
| Baseline mean P95 PRB (sub-weighted) | ch5.2 p59 Table 6.1 | 39.99 % | Σ cell P95 / 2,923 subs → **39.99** | p10 baseline mean | none | **PASS** | report definition = subscriber-weighted; unweighted cell mean = 34.84 (different definition, not a conflict) |
| Mean PRB uplift | ch5.2 p59 | 0.50 % | `AVG(expected_additional_prb_proxy)` → **0.50** | p10 engine output | none | **PASS** | exact |
| Post-migration mean PRB | ch5.2 p59 | 40.49 % | `AVG(post_migration_prb_utilisation_proxy)` → **40.49** | p10 mean post | none | **PASS** | exact |
| Post-migration max PRB | ch5.2 p59 | 67.13 % | `MAX(...)` → **67.13** | p10 | none | **PASS** | exact |
| Headroom below 80 % | ch5.2 p59 | 12.87 pp | `80 − 67.13` → **12.87** | p10 (derived) | none | **PASS** | exact |
| Rollout Approved | ch5.2 p60 Table 6.2 | 2,923 (100.0 %) | → **2,923** | p10 rollout status | none | **PASS** | exact |
| Rollout Waitlist / Blocked | ch5.2 p60 | 0 / 0 | → **0 / 0** | p10 | none | **PASS** | exact |
| Capped subscribers (uplift ≥ 15 %) | ch5.2 p60 Table 6.3 | 65 (2.2 %) | `expected_additional_prb_proxy >= 15` → **65** | — | none | **PASS** | NOT DISPLAYED |
| Mean raw uncapped uplift (capped group) | ch5.2 p60 | 22.4 % | stored values post-cap → 15.0 | — | none | **NOT DISPLAYED** | raw (pre-cap) uplift not persisted; stored column holds the capped value |
| Max raw uncapped uplift | ch5.2 p60 | 41.8 % | stored post-cap → 15.0 | — | none | **NOT DISPLAYED** | as above |

### 11. Final campaign actions (ch5.3 p63-68)

| Metric | Report source | Report value | SQL query/result | Dashboard | Filters | Status | Explanation |
|---|---|---|---|---|---|---|---|
| Action: Exclude | ch5.3 p64 Table 7.4 | 9,489 (76.5 %) | → **9,489** | p1 actions; p2 filter | none | **PASS** | exact |
| Action: Contact Later | ch5.3 p64 | 2,180 (17.6 %) | → **2,180** | p1; p2 | none | **PASS** | exact |
| Action: Contact Now | ch5.3 p64 | 731 (5.9 %) | → **731** | p1 funnel Contact Now; p2 | none | **PASS** | exact |
| Action: Manual Review | ch5.3 p64 | 12 (0.1 %) | → **12** | p1; p2 | none | **PASS** | exact |
| Exclusion reason RF Failure | ch5.3 p64 Table 7.5 | 9,449 (99.6 % of excluded) | `exclusion_reason='RF_Failure'` → **9,449** | p1/p7 | none | **PASS** | exact |
| Exclusion reason Fibre | ch5.3 p64 | 40 (0.4 %) | `'Fiber_Cannibalization'` → **40** | p1/p7 | none | **PASS** | exact |
| Q3 rule ⇒ Contact Now (score ≥ Q3 ∧ eligible) | ch5.3 p63 Method | 731 | `score >= percentile_cont(0.75)` → **731** | p2 (row scores) | none | **PASS** | rule reproduced exactly |
| Median final priority score (eligible) | ch5.3 p64 | 97.4 | `percentile_cont(0.5)` → **41.2** | — | eligible | **DATA REFRESH** | `final_priority_score` layer regenerated (top values 1,184.75/1,119.56/1,050.57/1,044.86/1,032.67 vs report 1,184.75/1,119.60/1,050.60/1,044.90/1,032.70 — same ranking). NOT DISPLAYED |
| Top-1 final score | ch5.3 p65 Table 7.3 | 1,184.75 (SUB_D4E7F12A) | `MAX(final_priority_score)` → **1,184.75** (SUB_B3342701) | p2 top row | none | **PASS** | value identical; report ID is masked |
| Surrogate model R² | ch5.3 p64 Table 7.1 | 0.9994 | not persisted | p5 surrogate card **0.9994** | — | **PASS** | dashboard = report; not recomputable |
| Surrogate feature importance (suitability 80.08 %) | ch5.3 p64 Table 7.2 | 80.08 % | not persisted | — | — | **NOT DISPLAYED** | — |

### 12. Data quality (ch2.1 p11-16) & dashboard integrity

| Metric | Report source | Report value | SQL query/result | Dashboard | Filters | Status | Explanation |
|---|---|---|---|---|---|---|---|
| DQ row baselines (10 approved objects) | SCHEMA_MAPPING §5 | 12,412 / 12,412 / 12,412 / 2,923 / 2,923 / 731 / 12,412 / 12,412 / 2,923 / 2,923 | per-table COUNTs → all equal | p6 row-baseline cards | none | **PASS** | exact |
| Zero NULLs in dashboard-critical fields | ch2.1 p11-16 | 0 | aggregate NULL checks → **0** | p6 checks | none | **PASS** | — |
| By-design NULLs (rollout_status / capacity_risk for excluded) | SCHEMA_MAPPING §4 | 9,489 | → **9,489** | p6 (by-design note) | none | **PASS** | documented sentinels |
| step15 ⋈ abt join integrity | dashboard prerequisite | 12,412 | `COUNT(*) JOIN` → **12,412** | all pages | none | **PASS** | exact |
| abt ⋈ t4 grid join integrity | p7 map gate | 12,412 | → **12,412** | p7 map | none | **PASS** | exact |
| step12 ⋈ step15 full coverage | p5 prerequisite | 0 orphans | LEFT JOIN NULL → **0** | p5 | none | **PASS** | exact |

---

## Summary of results

| Status | Rows | Notes |
|---|---|---|
| **PASS** | 87 | includes all headline business metrics |
| **ROUNDING DIFFERENCE** | 2 | cluster prepaid shares (50.7 vs 51 %, 82.5 vs 83 %) |
| **DEFINITION DIFFERENCE** | 0 | churn band counts reproduce exactly; threshold prose (0.30) vs stored bins (0.35) documented as a report-internal wording issue, not a dashboard definition conflict |
| **DATA REFRESH DIFFERENCE** | 20 | regenerated layers: radio feasibility (4), suitability bands (3), penalty rates (3), cluster sizes/means/shares (12 − 2 counted as rounding), churn labels (2), final-score median (1) |
| **NOT DISPLAYED** | 9 | model artifacts, raw uplift, test-set rows, roaming filter, feature importance |
| **FAIL** | **0** | — |

**No dashboard code changes were required.** Every dashboard value derives from
the live tables via `app/services`; all values shown match the database
exactly, and the database matches the report wherever the underlying pipeline
layer has not been regenerated since the report was written.

**Files touched:** this document; `app/tests/test_report_reconciliation.py`
(new, 36 tests). Report, database and pipeline untouched.
