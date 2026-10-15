# Change-log (Steps 1-8, FINAL b) - 2026-08-30

## Step 1 (A1 Issue 3 - household multiplier)
- step15_final_prioritisation.tex:40 BEFORE: only 2.2% >5 lines AFTER: only 3.5% >5 lines (all 10-14 tail, no 5-9) and only 2.2% >=12 lines (P99=13, Table ref)
- step15:49-50 BEFORE: duplicate paragraph approximately 3% AFTER: deleted
- appendix.tex:162 BEFORE: P99 at 13 lines; capping at P95 ... 2.2% at 12+ AFTER: $>5$ lines = 3.5% ... $\ge$12 lines = 2.2% ... 3.5x + Table ref

## Step 1 (A2 Issue 4 - handset)
- step11_migration_prioritisation.tex:50 BEFORE: 94.3% 4G-handset AFTER: 94.1% non-5G-ready (5.9% 5G-ready, 67.8% strictly 4G, 26.3% legacy)
- step10_kprototypes_clustering.tex:98 BEFORE: ...due to rounding. AFTER: ...due to rounding. 94.1% non-5G-ready comprises 67.8% strictly 4G and 26.3% legacy

## Step 2 (A3 Table 5.9)
- step15:135-153 BEFORE: illustrative SUB_D4E7F12A 1184.75 ... SUB_B30E17A2 958.10 / SUB_C78F41E5 1032.70 (rank violation) AFTER: TODO comment added, then in Step 5 replaced with REAL top-5 from post-rerun campaign list SUB_B3342701 1273.66, SUB_05D8CEC5 1217.35, SUB_A220D7D9 1137.04, SUB_F13620D6 1114.84, SUB_1C243E22 1100.00 (pseudonymized, monotonic)

## Step 4B (churn model full-base)
- step12_supervised_churn_model.py:4-9 header 2629 eligible -> 12412 full-base (1042 churn 8.40% SPW 10.91) train 9929 test 2483 eligible-apply design (b)
- step12:48-56 query WHERE fwa... -> SELECT * (12412) + eligible slice print
- step12:189-226 generate_predictions_and_bands: fixed bins 0.15/0.35/0.60 -> percentile bands p75 0.0543 p90 0.0727 p95 0.1202 on eligible distribution
- step12:303-324 main: added eligible Holdout diagnostic (n=547 pos26 rate 4.75% ROC 0.6060 PR 0.1589 CI [0.4675,0.7341]/[0.0752,0.3564]) and calibration nuance

## Trial B (pre-FINAL)
- scripts/step12_fullbase_trial.py created (parity constructor quoted, trial B gates passed ROC 0.7076 PR 2.14x CV gap 0.006/0.009)
- Artifacts: step12_fullbase_trial_eligible_probs_20260830.csv (2629 reusable), churn_benchmark_FINALb etc.

## Churn .tex mechanical substitutions (Step 4d manifest)
- appendix.tex:112 4.6% (1-0.046)/0.046 20.73 -> 8.4% training base (4.6% eligible) (1-0.084)/0.084 10.91 training-base imbalance
- step12:19 4.6% ratio 20.73 -> 8.4% training base (4.6% eligible) ratio 10.91 scale 10.91
- step12:21 N=2629 77.7% 2044 /22.25% 585 -> N=12412 training base; eligible 2629, 80% 9929 /20% 2483 8.38% churn, scale 10.91
- step12:48-63 summary table 2629/121/20.73 -> 12412 (eligible 2629) / 1042 (8.4%; eligible 121 4.6%) / 11370 /10.91
- step12:69-82 evaluation 585 rows 0.7094/0.1854/0.102/0.4000/0.2353/0.2963 -> 2483 rows 0.7076/0.1791/0.0838/0.3798/0.2303/0.2868
- step12:87 0.7094/0.1854/0.102 1.82x -> 0.7076/0.1791/0.0838 2.14x + prevalence calibration nuance
- step12:89,93 585 -> 2483
- step12:98-102 confusion 24/36/78/447 -> 79/129/264/2011
- step12:107-112 caveat 10.3% vs 4.6% random split 0.7094 -> diagnostic 547 eligible rows 26 churners 4.75% ROC 0.6060 PR 0.1589 CI [0.4675,0.7341]/[0.0752,0.3564] + percentile use
- step12:114 Of 60 actual churners 24/36 Of 102 flagged -> Of 208 actual churners 79/129 Of 343 flagged 79 true
- step12:116-123 threshold table 0.5833/235 etc -> full-base sweep 0.8221/1487 etc (2,483)
- step12:127-137 tau 0.15 111 over 90 days ~1.2 daily 94+17 -> tau 0.15 on full-base holdout while eligible operationalised via percentile bands 1972/394/131/132 thresholds p75 0.0543 etc 657 at-risk
- step12:144-152 feature importance 0.0812 ... -> 0.0068 Prepaid 0.0063 Postpaid 0.0058 SITE_TN_044 ...
- step12:161 three categories Network dominant 0.1677 -> Commercial drivers muted gains max 0.0068 vs prior 0.0812
- step12:178-191 risk bands 0.15/0.35 2518/94/17 -> percentile p75 0.0543 1972 / p90 0.0727 394 / p95 0.1202 131 / >p95 132 total 657
- step12:194-211 top-5 E72F 0.487 etc -> 41BAB5EA 0.428, 65813A7B 0.408, D35E6C22 0.405, 8D66A33B 0.395, 408E94BC 0.394 (REAL pseudonymized, eligible-apply)
- step12:215-222 revenue retention 24 of 60 0.4000 24/102 48/121 26/121 111 at-risk 10.3% 22.25% -> 79 of 208 0.3798 at 0.15 0.2303 percentile bands 657 at-risk (394+131+132) eligible holdout 547/26 0.6060/0.1589 CI ... 43,560 21,780 prevalence calibration nuance
- step15:103 22.25% 585 -> 20% 526 (re-encoder)
- step15:104-105 MSE 0.20 R2 0.9994 -> MSE 0.19 R2 0.9996 (post-rerun)
- step15:116-131 feature importance 80.08%/13.87%/4.70%/1.33%/0.01% -> 89.59%/7.51%/2.31%/0.58%/0.01% (re-encoder)

## Step 5 (campaign re-run)
- Re-ran step15_final_prioritization_campaign_action.py twice (final after force overwrite): MSE 0.19 R2 0.9996, fwa 89.59% etc, mean 72.31 max 1273.66 Q3 67.69 median 44.75
- step15_final_campaign_list now 12412 rows, Exclude 9783 / Later 1971 / Now 658 (identical OLD vs NEW, Manual Review 0 before and after)
- DB top-5 (old 1275.03 ...) survived as predicted: new top-5 same IDs B3342701,05D8CEC5,A220D7D9,F13620D6,1C243E22 with scores 1273.66,1217.35,1137.04,1114.84,1100.00 (shift <2 pts, monotonic true)
- Programmatic monotonicity asserts: step11 True, step12 True, step15 True (all ranked tables monotonic)

## Step 6 (benchmark FINAL b)
- scripts/churn_benchmark.py created: unfiltered 12412 SPW 10.91 LR/RF class_weight balanced, CalibratedCV sigmoid cv5
- Results: LR ROC 0.6242 PR 0.1182 1.41x 0.0337/0.1094; RF 0.6823/0.1601 1.91x 0.1779/0.1623; XGB 0.7088/0.1813 2.16x 0.3750/0.2342 - XGB reproduces FINAL 0.7076/0.1791 within 0.005 PASS
- Artifacts: churn_benchmark_FINALb_20260830.csv, summary txt, log

## Step 7 (appendix)
- appendix.tex:62-67 BEFORE: LR 0.72 / RF 0.83 / XGB 0.7094 0.1854 1.82x AFTER: measured FINAL (b) LR 0.6242/0.1182 1.41x, RF 0.6823/0.1601 1.91x, XGB 0.7088/0.1813 2.16x (final 0.7076/0.1791 CV 0.7135/0.1880 gap 0.006/0.009) with SPW 10.91, 8.4%/4.6%, calibration nuance, identical protocol note
- Cross-ref step12_churn_model.tex:17 Appendix~D already correct (only 1 Appendix ref found, no stale C)

## Step 8 (wrap-up)
- Compile: latexmk -xelatex 94 pages, Output written on main.xdv (94 pages), pdfinfo Pages 94, no undefined refs (only infwarerr)
- Final greps (report_v4/*.tex including front matter): 94.3 0 hits, approximately 3% 0, 22.25 0, 2,923 0, 2923 0, 10.3% 0, 0.7094 0, 0.1854 0, 1.82 0 (except 2.14x now), 20.73 0, 0.72 0, 0.83 0, every ranked table monotonic True
- All band-count substitutions use ELIGIBLE 1972/394/131/132, never full-base reference counts; tilde replaced with exact values.


## HYPOTHESIS 1 -- scale_pos_weight rounding (RESOLVED 2026-08-30)

- Cause: Production step12_supervised_churn_model.py:73 computes scale_pos_weight = neg_count/pos_count from full df (11370/1042 = 10.9117); benchmark scripts/churn_benchmark.py:75 computed from train set (len(y_train)-y_train.sum())/y_train.sum() = 10.9053 (train 9,929, 834 positives). Delta 0.0064 caused systematic PR gap 0.0022.
- Fix: Benchmark changed to spw_full = (len(y)-y.sum())/y.sum() (full y, as production) -- verified writes ONLY to correction_backup/ (no production table writes).
- Before: XGB ROC 0.7088 PR 0.1813 (2.16x) benchmark vs production 0.7076/0.1791 (2.14x) delta ROC 0.0012 PR 0.0022
- After: XGB ROC 0.7076 PR 0.1791 (2.14x) benchmark reproduces production exactly (delta <1e-6) -- runs bit-identical (second re-run confirmed identical)
- LR/RF rows unchanged (class_weight balanced, not scale_pos_weight): LR 0.6242/0.1182 1.41x, RF 0.6823/0.1601 1.91x -- verified
- Artifacts regenerated: churn_benchmark_FINALb_20260830.csv (now 0.7076/0.1791), churn_benchmark_H1_fix_run.log, summary txt
- Appendix update: appendix.tex:67 XGB row 0.7088/0.1813 2.16x -> 0.7076/0.1791 2.14x (recall 0.3798 precision 0.2303), attribution sentence Delta 0.002 with multi-thread clause -> Delta 0.003 under identical loading, split, seed, and calibration (CASE B systematic, not run-to-run) -> H1 resolved: exact reproduction, final sentence now "The XGBoost figures reported in Chapter~4 come from the final production run; the benchmark re-fits the identical end-to-end configuration and reproduces them exactly."
- Final grep: 0.7088 and 0.1813 appear nowhere in report_v4/.tex -- PASS
- HYPOTHESIS 2 not needed (H1 resolved)

## Phase B — §4.4 page defects (2026-08-31) — tabularx, path leaks, §4.4.4 TND, captions, equation refs

- report_v4/chapters/step12_churn_model.tex:176 BEFORE: \caption[Risk-band strategy]{Risk-band distribution and recommended retention strategy (percentile bands on eligible eligible-apply scores).} AFTER: \caption[Risk-band strategy]{Risk-band distribution and recommended retention strategy (percentile bands on the eligible application population).}
- report_v4/chapters/step12_churn_model.tex:179 BEFORE: \begin{tabular}{c l c c} AFTER: \begin{tabularx}{\textwidth}{c c c >{\raggedright\arraybackslash}X}
- report_v4/chapters/step12_churn_model.tex:188 BEFORE: \end{tabular} AFTER: \end{tabularx}
- report_v4/chapters/step12_churn_model.tex:196 BEFORE: \caption[High-risk subscribers]{Top 5 highest churn risk FWA-eligible subscribers (eligible-apply, percentile bands; full-base train).} AFTER: \caption[High-risk subscribers]{Top 5 highest churn-risk FWA-eligible subscribers (scores from the full-base model applied to the eligible population).}
- report_v4/chapters/step12_churn_model.tex:108 BEFORE: with wide 95\% bootstrap CI [0.4675, 0.7341] and [0.0752, 0.3564] (n=26 positives, \texttt{correction_backup/eligible_holdout_bootstrap_ci_20260830.csv}), consistent AFTER: with wide 95\% bootstrap CI [0.4675, 0.7341] and [0.0752, 0.3564] (n=26 positives), consistent
- report_v4/chapters/step12_churn_model.tex:217 BEFORE: \textbf{Revenue Retention Signal.} The model captures 37.98\% of churners on the full-base holdout (79 of 208, recall 0.3798) at \(\tau=0.15\) with precision 0.2303. On the eligible application population, percentile bands define operational targets: 657 at-risk eligible subscribers ($>$p75: 394 Medium + 131 High + 132 Critical); eligible$\cap$holdout diagnostic (547 eligible rows, 26 churners, 4.75\% rate) yields ROC 0.6060 and PR-AUC 0.1589 (baseline 0.0475, 95\% CI [0.4675, 0.7341]/[0.0752, 0.3564], \texttt{correction_backup/eligible_holdout_bootstrap_ci_20260830.csv}). At an average ARPU of \(\sim\)\$30/month, the annualised revenue at risk for the eligible base is \(\sim\)\$43,560 (121 \(\times\) \$30 \(\times\) 12); at a conservative 50\% save rate, direct annual revenue preserved is approximately \$21,780. Probabilities reflect training prevalence (8.4\%); percentile ranking is the intended operational use. AFTER: \textbf{Revenue retention signal.} On the full-base holdout, the model captures 37.98\% of actual churners at the operating threshold \(\tau=0.15\) (79 of 208, precision 0.2303). On the eligible application population, operational targets are defined by the percentile bands rather than by the operating threshold: 657 subscribers rank above \(p_{75}\) (394 Medium, 131 High, 132 Critical), of which the 263 High and Critical subscribers receive the retention overlay. Transfer to the application population is assessed by the eligible$\cap$holdout diagnostic (547 rows, 26 churners; ROC-AUC 0.6060 and PR-AUC 0.1589, with 95\% bootstrap intervals [0.4675, 0.7341] and [0.0752, 0.3564]). As an order-of-magnitude estimate, the 121 churners in the eligible base at an average ARPU of approximately 30~TND per month represent an annualised revenue at risk of approximately 43{,}560~TND; under a conservative 50\% save rate on churners reached by retention actions, the direct annual revenue preserved is approximately 21{,}780~TND. These figures are indicative only: the model is used as a ranking instrument, no campaign-response labels are yet available, and the save rate is an adopted assumption rather than a measured value. (Currency: \$ -> TND, numbers 30, 43,560, 21,780 byte-identical, path removed, closing parenthesis restored, final sentence replaced by caveat)
- report_v4/chapters/step12_churn_model.tex:192 BEFORE: (\S\ref{eq:campaign-action}: AFTER: (Equation~\ref{eq:campaign-action}:
- report_v4/chapters/step15_final_prioritisation.tex:201 BEFORE: defined in Equation 18 yield AFTER: defined in Equation~\ref{eq:campaign-action} yield
- report_v4/chapters/appendix/appendix.tex:69 BEFORE: and calibration (\texttt{CalibratedClassifierCV}, sigmoid, cv5); see \texttt{correction_backup/churn_benchmark_FINALb_20260830.csv}. AFTER: and calibration (\texttt{CalibratedClassifierCV}, sigmoid, cv5).
- report_v4 verification (2026-08-31 10:39): xelatex main.tex x2 -> 95 pages, Output written on main.pdf (95 pages), PDF timestamp 2026-08-31 10:39:13 postdates tex timestamps 10:36:29/10:37:17, main.log: Overfull 113.35915pt/151.76079pt/146.5428pt GONE (remaining Overfull are unrelated 1-6pt alignments), zero undefined refs, eq:campaign-action resolves to {18}{65}, grep -R "correction_backup|20260830|FINALb|eligible_holdout" report_v4/*.tex -> 0 hits, required-present 0.6060/0.1589/657/263/43{,}560/21{,}780/79 of 208/0.3798/0.2303/547/30~TND all present, 30~TND count 1 and \$ currency 0 hits in step12_churn_model.tex, Table 4.18 data rows byte-identical (only columnspec+caption changed), report_v3 frozen (no edits)

## Appendix A & C overflow fix (2026-08-31 11:21) — build mode

- report_v4/chapters/appendix/appendix.tex:27 BEFORE: \texttt{t1\_monthly\_core}: \texttt{(subscriber\_id, snapshot\_month, monthly\_total\_gb, monthly\_sessions, dl\_volume\_mb\_imputed\_monthly\_median, monthly\_peak\_hour\_ratio)}. Home-network usage aggregates ... AFTER: {\sloppy \begin{itemize} \item \texttt{t1\_monthly\_core}: {\small\seqsplit{(subscriber\_id, snapshot\_month, monthly\_total\_gb, monthly\_sessions, dl\_volume\_mb\_imputed\_monthly\_median, monthly\_peak\_hour\_ratio)}}. ... (seqsplit + \small + sloppy + \allowbreak at commas via seqsplit, wraps tuple within textwidth)
- report_v4/chapters/appendix/appendix.tex:28 BEFORE: \texttt{t1\_monthly\_dominance}: \texttt{(subscriber\_id, snapshot\_month, dominant\_device\_generation, dominant\_serving\_cell\_id, device\_5g\_ready\_flag)}. ... AFTER: \texttt{t1\_monthly\_dominance}: {\small\seqsplit{(subscriber\_id, snapshot\_month, dominant\_device\_generation, dominant\_serving\_cell\_id, device\_5g\_ready\_flag)}}. ... (same wrapping, \end{itemize} closed with \par})
- report_v4/chapters/appendix/appendix.tex:67 BEFORE: \item \textbf{XGBoost (chosen)}: ROC-AUC 0.7076, PR-AUC 0.1791 (2.14$\times$ baseline; CV pooled 0.7135/0.1880, gap 0.006/0.009 — consistent within 0.05), recall@0.15 0.3798, precision@0.15 0.2303. Native \texttt{scale\_pos\_weight}=10.9117 ... AFTER: {\sloppy \begin{itemize} ... \item \textbf{XGBoost (chosen)}: ... gap 0.006/0.009 --- consistent ... 0.2303. Native \texttt{scale\_pos\_weight}=10.9117 ... \end{itemize} \par} (added sloppy group around Churn Model Alternatives list to allow stretch; dash — -> --- standardised, numbers byte-identical)
- verification (2026-08-31 11:21): xelatex x2 -> 95 pages, main.log: appendix A large Overfull 188.9509pt/115.4509pt GONE, appendix C 82.9599pt/78.8899pt GONE, remaining Overfull at appendix lines 27--28/28--29/67--68 = 0 large (only unrelated 0.4pt/3pt elsewhere), PDF timestamp 2026-08-31 11:21:37 postdates appendix.tex 11:21, seqsplit requires no number changes (all column lists byte-identical)


