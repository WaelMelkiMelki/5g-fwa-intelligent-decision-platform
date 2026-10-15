# SCHEMA MAPPING — 5G FWA Decision-Support Dashboard (Phase 1)

Read-only mapping of the database objects consumed by this application.
**Schema: `cleaned_data` only.** The legacy `analytics.*` schema is NOT used (audit §6.6, R5).

All facts below were verified via live `SELECT`/`information_schema` queries on
2026-08-08 (PostgreSQL 18.3, database `postgres`). Nothing here is assumed from
semantic meaning alone.

---

## 1. Objects allowed (task contract)

| Object | Grain | Verified rows | snapshot_month present? |
|---|---|---|---|
| `cleaned_data.step15_final_campaign_list` | 1 row / subscriber | 12,412 | YES (2026-01-01) |
| `cleaned_data.abt_subscriber_month` | 1 row / subscriber-month | 12,412 | YES (2026-01-01) |
| `cleaned_data.step12_churn_predictions` | 1 row / subscriber | 12,412 | YES (2026-01-01) |
| `cleaned_data.step13_recommendations` | 1 row / eligible subscriber | 2,923 | NO |
| `cleaned_data.step14_capacity_simulation` | 1 row / eligible subscriber | 2,923 | NO |
| `cleaned_data.t3_cell_monthly_kpi` | 1 row / cell-month | 731 | YES (2026-01-01) |
| `cleaned_data.t4_coverage_features` | 1 row / address | 12,412 | NO |
| `cleaned_data.t4_coverage_address_grid` | 1 row / address (only lat/lon source) | 12,412 | NO |

**Supporting audited objects** (read-only, allowed by audit §8/§10 as dimension sources).
May be used in runtime code ONLY when a verified dashboard field is not available from
the eight approved objects above; before use, document (a) the required field and
(b) why the eight original objects cannot supply it. SELECT-only access. The set of
allowed objects is capped at these ten — no expansion beyond them (DECISION 6).

- `cleaned_data.abt_subscriber_month_clustered` (2,923 rows) — persona labels/weights.
- `cleaned_data.step11_prioritization` (2,923 rows) — MCDA ranking.

---

## 2. Column inventory (verified)

### 2.1 `step15_final_campaign_list` (26 cols)
`subscriber_id` text, `snapshot_month` date, `arpu_monthly_tnd` float8, `tenure_months` int8,
`num_active_lines` int8, `contract_type` text, `segment_tier` text, `fwa_suitability_score` int8,
`fwa_suitability_band` text, `fwa_exclusion_reason` text, `cluster_id` int8, `business_label` text,
`candidate_prioritization_score` float8, `suitability_based_ranking` float8, `churn_probability` float8,
`churn_risk_band` text, `Base_Score` real, `final_priority_band` text, `final_priority_score` float8,
`campaign_action` text, `rollout_status` text, `recommended_offer` text, `offer_category` text,
`tier1_base_plan` text, `post_migration_capacity_risk` text, `exclusion_reason` text.

### 2.2 `abt_subscriber_month` (53 cols)
`subscriber_id`, `snapshot_month`, `segment_tier`, `b2b_b2c_flag`, `arpu_monthly_tnd`,
`tenure_months`, `address_id`, `governorate`, `contract_type`, `num_active_lines`,
`has_mobile_sub_flag`, `activation_date`, `audit_flag`, `churn`, `arpu_band`, `tenure_band`,
`multi_line_flag`, `monthly_sessions`, `monthly_total_gb`, `dl_volume_mb_imputed_monthly_median`,
`monthly_peak_hour_ratio`, `dominant_device_generation`, `dominant_serving_cell_id`,
`device_5g_ready_flag`, `serving_cell_id`, `predicted_rsrp_dbm`, `predicted_sinr_db`,
`coverage_5g_flag`, `coverage_4g_flag`, `fiber_coverage_flag`, `signal_quality_class`,
`radio_feasibility_class`, `streaming_vol_gb`, `streaming_session_count`, `iptv_active_flag`,
`iptv_watch_hours`, `voip_minutes`, `cloud_cam_flag`, `iot_traffic_share_pct`,
`social_media_vol_gb`, `gaming_vol_gb`, `streaming_heavy_flag`, `gaming_heavy_flag`,
`high_voip_usage_flag`, `site_id`, `avg_prb_utilisation_pct`, `p95_prb_utilisation_pct`,
`max_prb_utilisation_pct`, `avg_dl_throughput_mbps`, `current_capacity_proxy_status`,
`fwa_suitability_score`, `fwa_suitability_band`, `fwa_exclusion_reason`.
(No lat/lon, no msisdn — verified.)

### 2.3 `step12_churn_predictions` (4 cols)
`subscriber_id` text, `snapshot_month` date, `churn_probability` float8, `churn_risk_band` text.

### 2.4 `step13_recommendations` (7 cols)
`subscriber_id`, `tier1_base_plan`, `tier2_addons`, `recommended_offer`, `offer_category`,
`reason_codes`, `fwa_suitability_score`.

### 2.5 `step14_capacity_simulation` (8 cols)
`subscriber_id`, `dominant_serving_cell_id`, `offer_category`, `p95_prb_utilisation_pct`,
`expected_additional_prb_proxy`, `post_migration_prb_utilisation_proxy`,
`post_migration_capacity_risk`, `rollout_status`.

### 2.6 `t3_cell_monthly_kpi` (8 cols)
`cell_id` varchar, `site_id` varchar, `snapshot_month` date, `avg_prb_utilisation_pct` float8,
`p95_prb_utilisation_pct` float8, `max_prb_utilisation_pct` float8,
`avg_dl_throughput_mbps` float8, `current_capacity_proxy_status` varchar.

### 2.7 `t4_coverage_features` (9 cols)
`address_id` varchar, `serving_cell_id` varchar, `predicted_rsrp_dbm` float8, `predicted_sinr_db` float8,
`coverage_5g_flag` bool, `coverage_4g_flag` bool, `fiber_coverage_flag` bool,
`signal_quality_class` varchar, `radio_feasibility_class` varchar.

### 2.8 `t4_coverage_address_grid` (12 cols)
`address_id`, `serving_cell_id`, `latitude` float8, `longitude` float8, `governorate`,
`predicted_rsrp_dbm`, `predicted_sinr_db`, `coverage_5g_flag`, `coverage_4g_flag`,
`fwa_raw_score`, `fiber_coverage_flag`, `distance_to_cell_km`.
→ **Only table with lat/lon (verified).** lat/lon nulls: 0/0. All 12,412 addresses matched to ABT.

---

## 3. Join-key contract (verified)

| Join | Keys | Verified match |
|---|---|---|
| step15 ↔ abt | `subscriber_id` + `snapshot_month` | 12,412 / 12,412 |
| step15 ↔ step12 | `subscriber_id` | 12,412 / 12,412 |
| step15 ↔ step13 | `subscriber_id` | 2,923 / 2,923 (eligible only) |
| step15 ↔ step14 | `subscriber_id` | 2,923 / 2,923 |
| step15 ↔ clustered | `subscriber_id` | 2,923 / 2,923 |
| abt ↔ t4 grid | `address_id` | 12,412 / 12,412 |
| t4 grid ↔ t3 | `serving_cell_id` = `cell_id` | 731 distinct cells match 1:1 |
| abt ↔ t3 (cells) | `dominant_serving_cell_id` = `cell_id` | — |

### 3.1 Join contract — accepted technical debt and runtime guards (DECISION 5)

`step13_recommendations`, `step14_capacity_simulation` and
`abt_subscriber_month_clustered` have NO `snapshot_month` column; they join on
`subscriber_id` alone. This is accepted for Phase 1 because the verified current
data contains exactly one snapshot and the current matches are 1:1.

**Mandatory runtime guards (enforced before any of these joins execute):**
1. Verify the application is operating on exactly one snapshot (distinct
   `snapshot_month` count across step15/abt/step12 == 1).
2. Verify `subscriber_id` is unique in each joined eligible-level source
   (step13, step14, clustered).
3. Detect duplicate `subscriber_id` values (SQL-level `COUNT` vs
   `COUNT(DISTINCT ...)` comparison).
4. If multiple snapshots or duplicates exist, fail safely with a clear schema
   compatibility error — the ambiguous join is NEVER performed.

Documented as temporary technical debt in this file and in IMPLEMENTATION_REPORT.md.
No database schema or pipeline changes are made (DECISION 5).

---

## 4. Verified distinct values (filter vocabularies)

### 4.1 `step15_final_campaign_list`
| Column | Distinct values (count) |
|---|---|
| `campaign_action` | Exclude (9,489) / Contact Later (2,180) / Contact Now (731) / Manual Review (12) |
| `churn_risk_band` | Low Risk (10,465) / Medium Risk (1,771) / High Risk (176) — **no "Critical Risk" row exists in this snapshot** |
| `fwa_suitability_band` | Excluded (9,489) / Marginal (1,579) / Standard (1,036) / Premium (308) |
| `cluster_id` | −1 (9,489, Excluded) / 0 (1,074) / 1 (1,478) / 2 (314) / 3 (57) |
| `offer_category` | N/A (9,489) / Base Only (1,912) / Base + IPTV (498) / Base + Convergent Fixed-Mobile Add-on (343) / Multi-Addon Bundle (118) / Base + Gaming Add-on (52) |
| `rollout_status` | NULL (9,489) / Approved (2,923) |
| `post_migration_capacity_risk` | NULL (9,489) / Safe (2,923) |
| `final_priority_band` | Excluded (9,489) / Very Low (1,477) / Low (537) / Medium (784) / High (125) |
| `contract_type` | Prepaid (8,115) / Postpaid (3,672) / Hybrid (625) |
| `segment_tier` | High (4,127) / Mid (3,735) / LV (2,999) / Premium (1,551) |

### 4.2 `abt_subscriber_month`
| Column | Distinct values (count) |
|---|---|
| `signal_quality_class` | Poor (9,449) / Acceptable (2,181) / Excellent (782) |
| `radio_feasibility_class` | Infeasible (9,674) / 4G_Fallback (2,338) / 5G_Feasible (291) / Fiber_Competitor (109) |
| `current_capacity_proxy_status` | Available (12,412) — no Constrained rows in snapshot |
| `fwa_exclusion_reason` | RF_Failure (9,449) / Fiber_Cannibalization (40) / NULL (2,923 eligible) |

### 4.3 `t3_cell_monthly_kpi`
- `current_capacity_proxy_status`: Available (731) — no Constrained.
- PRB p95 range [20.98, 67.02]; PRB max range up to 74.68. **0 cells at/over 80.**

### 4.4 `step14_capacity_simulation`
- `post_migration_capacity_risk`: Safe (2,923). `rollout_status`: Approved (2,923).

### 4.5 Canonical UI values (DECISION 1)

**The exact live PostgreSQL values ARE the canonical values** — used internally and
in SQL predicates. Display labels are never translated back into guessed SQL values.

| Field | Canonical values (verified) |
|---|---|
| `churn_risk_band` | `Low Risk` / `Medium Risk` / `High Risk` — `Critical` is NOT offered (no current row has it) |
| `offer_category` | `Base Only` / `Base + IPTV` / `Base + Gaming Add-on` / `Base + Convergent Fixed-Mobile Add-on` / `Multi-Addon Bundle` / `N/A` |
| `campaign_action` | `Exclude` / `Contact Later` / `Contact Now` / `Manual Review` |
| `final_priority_band` | `Excluded` / `Very Low` / `Low` / `Medium` / `High` |
| `cluster_id` | −1 / 0 / 1 / 2 / 3 |
| `radio_feasibility_class` | `Infeasible` / `4G_Fallback` / `5G_Feasible` / `Fiber_Competitor` |
| `signal_quality_class` | `Poor` / `Acceptable` / `Excellent` |
| `current_capacity_proxy_status` | `Available` (present); `Constrained` (absent from this snapshot) |

### 4.6 Sentinel display mapping (DECISION 2)

Sentinel values are KEPT in global totals and campaign reporting; they are never
silently dropped. Excluded subscribers remain in Executive Overview (entire
population) and Campaign Operations (every campaign action). Segmentation,
recommendation and capacity analyses default to eligible subscribers only, via an
explicit population filter: **All subscribers / Eligible subscribers / Excluded subscribers**.

| Stored value | Displayed as |
|---|---|
| `cluster_id = -1` | `Not Segmented` |
| `offer_category = 'N/A'` | `No Offer` |
| `rollout_status IS NULL` | `Not Applicable` |
| `post_migration_capacity_risk IS NULL` | `Not Applicable` |

Aliases are applied ONLY for display, after SQL retrieval; SQL predicates stay bound
to the actual database values (DECISION 8).

### 4.7 Capacity status note (DECISION 4)

The capacity filter exposes only values currently present in the selected dataset.
`Constrained` is NOT shown merely because it is theoretically possible. When the
dataset contains no constrained cells, the UI shows:
"No constrained cells exist in the current snapshot."
No baseline count (e.g. 731 cells) is hard-coded anywhere — all counts are computed
live from the database.

---

## 5. Verified baseline counts (used for drift detection I8)

| Metric | Value | Source query |
|---|---|---|
| ABT subscribers | 12,412 | `COUNT(*) abt_subscriber_month` |
| Eligible (score > 0) | 2,923 | `COUNT(*) FILTER (fwa_suitability_score>0)` |
| Campaign list rows | 12,412 | `COUNT(*) step15_final_campaign_list` |
| Cells | 731 | `COUNT(*) t3_cell_monthly_kpi` |
| snapshot_month | 2026-01-01 | `SELECT DISTINCT snapshot_month` |

---

## 6. Metric-conflict registry (Model Performance page)

Verified values that conflict across authoritative sources; the page displays BOTH values
with sources and a "metric validation required" warning (never picks one as authoritative).

| Metric | Value A (source) | Value B (source) |
|---|---|---|
| Churn ROC-AUC | 0.7094 (`report_v4/chapters/step12_churn_model.tex` §Key Results table) | 0.8956 (`report_v4/chapters/appendix/appendix.tex` model comparison) |
| Churn base rate | 10.2% (step12 chapter: 298/2,923) | 6.7% (appendix D: scale_pos_weight≈13.93) |
| Churn PR-AUC | 0.1854 (step12 chapter) | 0.1854 (appendix — consistent) |
| Threshold-optimised τ=0.15 | Recall 0.3990 / Precision 0.2351 / F1 0.2959 (chapter) | — |
| CV F1 | 0.291 ± 0.041 (chapter, chosen config 300/5/0.05/0.8/0.8) | — |
| Confusion matrix (τ=0.15, 585 rows) | TP 24 / FP 78 / FN 36 / TN 447 (chapter) | — |
| Step15 surrogate R² (test) | 0.9994 (`step15_final_prioritisation.tex`) | — |

Pipeline-script configuration (verified from `step12_supervised_churn_model.py`):
`XGBClassifier(n_estimators=300, max_depth=6, lr=0.05, random_state=42)`, `scale_pos_weight≈8.81`,
test_size 0.2, 5-fold stratified CV, Platt (sigmoid) calibration; band bins
`[0.0, 0.15, 0.35, 0.60, 1.0]` → labels `Low Risk / Medium Risk / High Risk / Critical Risk`
(no Critical rows present in the snapshot — verified).

### 6.1 Churn source of truth (DECISION 3)

`cleaned_data.step12_churn_predictions` — and its exact database `churn_risk_band`
values — is the operational source for all dashboard churn displays, filters and
KPIs. The alternative eligible-pool thresholds (base rate 10.2%→6.7% discussion,
τ=0.15/0.30 band definitions) are NOT combined with the whole-ABT bands; the two
definitions are kept strictly separate. The Model Performance page shows the
warning **"Metric validation required: project sources contain conflicting churn
thresholds, base rates and AUC values"** and displays both conflicting values with
their source names; it never selects or calculates "the correct" one.

---

## 7. Design notes / decisions

1. `step13`/`step14`/clustered have NO `snapshot_month`; join on `subscriber_id` only —
   accepted Phase 1 tech debt with runtime guards (see §3.1), migrations deferred (DECISION 5).
2. `step15` already carries most joined facts (churn, offer, capacity risk, persona label); ABT is joined for
   `address_id`, `governorate`, `signal_quality_class`, `radio_feasibility_class`, `current_capacity_proxy_status`,
   `dominant_serving_cell_id`, usage/device columns used in drill-down.
3. `msisdn` exists ONLY in daily T1 tables; **this app never selects it** and never queries the daily T1
   source to recover it (audit §14.3, DECISION 10). `subscriber_id` is always masked in dashboard tables,
   drill-down headings, exports, logs and error messages (`SUB_…` pattern, masking.py contract).
4. Geo: `t4_coverage_address_grid` is the only lat/lon source; capacity map aggregates cell centroids from it.
5. All queries are parameterized, read-only (session `default_transaction_read_only=on`), with explicit column lists (no `SELECT *`).
6. **Missing constraints (DECISION 9):** none of the ten objects declare PRIMARY KEY, FOREIGN KEY,
   UNIQUE or NOT NULL constraints; the single verified index is `idx_abt_sub_month`. This is accepted
   for Phase 1 — no constraint/index migration is performed. Uniqueness and join-cardinality are
   enforced at application level (guards in §3.1).
7. **Source priority (DECISION 13):** (1) live `cleaned_data` structure/values for operational queries;
   (2) pipeline code for formulas/logic; (3) audit reports for architecture/risks/conflicts;
   (4) interaction spec for UI behaviour. Conflicts are preserved in documentation and never
   presented as an unverified interpretation.

---

## 8. Type normalization registry (DECISION 8)

Database types are NEVER changed. Normalization happens only in the Python service
layer, per column, and is documented here:

| Source column (type) | Normalized to | Where |
|---|---|---|
| `step15.cluster_id` (int8; −1 = Excluded) | nullable `int` (Python); −1 kept as is for predicates, aliased at display | `business_logic/masking.py` & services |
| numeric metric fields (float8/real/int8/int4) | pandas `numeric` (float) | services (read + `pd.to_numeric` where needed) |
| `abt.activation_date` (timestamp w/o tz) | pandas `datetime` | services / drill-down |
| `snapshot_month` (date) | string `YYYY-MM-DD` for filters, `datetime` internally | services |
| categorical NULL / sentinel values | explicit UI labels ONLY after SQL retrieval (§4.6), never in predicates | pages/components display layer |

SQL predicates always bind the actual database values; UI aliases are never
substituted into SQL.

---

## 9. Reproducible evidence (DECISION 7)

All mapping facts are reproducible via `app/sql/verify_schema_mapping.sql` —
a SELECT-only verification script covering: table/column metadata and data types,
row counts, snapshot counts, uniqueness checks, distinct filter values, NULL and
sentinel counts, join-cardinality checks and baseline dashboard counts.

**How to execute safely (read-only role / session):**
1. As a role with SELECT rights only on `cleaned_data` (no INSERT/UPDATE/DELETE/DDL),
   run: `psql -d postgres -v ON_ERROR_STOP=1 -f app/sql/verify_schema_mapping.sql`
   — or execute the pairs from a read-only session with `SET default_transaction_read_only=on`.
2. Statements allowed: `SELECT`, `WITH`, and `EXPLAIN` without `ANALYZE` when needed.
   Forbidden: INSERT/UPDATE/DELETE/CREATE/ALTER/DROP/TRUNCATE/GRANT/REVOKE,
   COPY to server files, and any function calls with side effects.
3. The script contains no credentials and outputs no raw subscriber identifiers
   (only counts of `subscriber_id`); do not modify it to print raw values.
4. Expected result: all `assert`-style checks return `OK`; any `FAIL` must be treated
   as a blocking schema-compatibility issue for this application.
