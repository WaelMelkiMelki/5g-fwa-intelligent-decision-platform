# IMPLEMENTATION REPORT — 5G FWA Decision-Support Dashboard (Phase 1 + Phase 2)

Date: 2026-08-08 · Schema: `cleaned_data` only · PostgreSQL 18.3 (`localhost:5432`)

Phase 2 report: `app/PHASE2_REPORT.md` · Simulation contract: `app/SIMULATION_CONTRACT.md`

## 1. Files created

| File | Purpose |
|---|---|
| `app/Home.py` | Entry point — drift banner (live counts vs verified baselines), page links. |
| `app/pages/1_Executive_Overview.py` | KPIs, campaign-action funnel, churn/coverage/offer distributions (entire population incl. Excluded). |
| `app/pages/2_Campaign_Operations.py` | Searchable/sortable/paginated campaign table (all campaign actions), masked display + masked CSV export (I6), drill-down navigation. |
| `app/pages/3_Subscriber_Drill_Down.py` | Full masked profile (step15 ⋈ abt ⋈ step13 ⋈ step14), sentinel-aware display, single-row masked export. |
| `app/pages/4_Network_Capacity.py` | Cell KPIs, PRB histograms, cell selection + subscriber mix, paginated table, folium map with verified geo join. |
| `app/pages/5_Model_Performance.py` | Precomputed metrics with conflict registry + source names (never a single "correct" pick), confusion matrix, training metadata, feature importance, step15 surrogate. |
| `app/components/charts.py` | `kpi_row`, `donut_chart`, `bar_chart`, `histogram_chart`, `funnel_chart`, `heatmap_chart`. |
| `app/components/filters.py` | Sidebar filter bar — population scope, snapshot, verified vocabularies, reset. |
| `app/components/messages.py` | Drift banner, empty/error states, warnings. |
| `app/components/tables.py` | Paginated tables, export button. |
| `app/services/database.py` | Pooled SQLAlchemy; SELECT-only guard; explicit columns; row cap; no sensitive logging. |
| `app/services/executive_service.py` | Base subset, KPIs, campaign distribution, live filter options. |
| `app/services/campaign_service.py` | Paginated campaign query, export rows, CSV bytes (UTF-8 BOM, spec I6 filename). |
| `app/services/subscriber_service.py` | Masked profile join, masked search. |
| `app/services/capacity_service.py` | Cell summary, paginated cells ⋈ step14 counts, cell subscribers, centroids. |
| `app/services/model_service.py` | Verified metric metadata, conflict registry, live snapshot churn stats. |
| `app/business_logic/filtering.py` | Allowlisted predicates, population scope pushdown, param binding. |
| `app/business_logic/metrics.py` | Pure aggregation helpers (funnel, bands, pivots). |
| `app/business_logic/masking.py` | Subscriber-ID masking, forbidden/allowlisted export columns. |
| `app/business_logic/guards.py` | Single-snapshot + join-key uniqueness runtime guards (DECISION 5). |
| `app/business_logic/normalize.py` | Type-normalization registry (DECISION 8). |
| `app/business_logic/display.py` | Sentinel display aliases (DECISION 2). |
| `app/state/session.py` | Typed session state (`fwa.filters/selection/ui`, population scope). |
| `app/tests/` | 77 unit tests (database, filters, metrics, masking, services, guards, normalize, display). |
| Phase 2 extras | See `PHASE2_REPORT.md`: services `data_quality/coverage/segmentation/recommendation/simulation_service.py`, pages 6–10, `business_logic/simulation.py`, `tests/test_phase2_services.py` (15), `tests/test_phase2_pages.py` (12). |
| `app/SCHEMA_MAPPING.md` | Verified schema mapping + decisions 1–13 documentation + verification instructions. |
| `app/sql/verify_schema_mapping.sql` | SELECT-only reproducible evidence script (DECISION 7). |
| `app/.streamlit/secrets.toml.example` | Config template (placeholders only). |
| `app/requirements.txt` | Valid pip syntax; optional packages marked with `#`. |

## 2. Database objects used (all `cleaned_data`, SELECT-only)

Approved: `step15_final_campaign_list`, `abt_subscriber_month`, `step12_churn_predictions`,
`step13_recommendations`, `step14_capacity_simulation`, `t3_cell_monthly_kpi`,
`t4_coverage_features`, `t4_coverage_address_grid`.
Supporting audited objects: `abt_subscriber_month_clustered`, `step11_prioritization`
(marked "Supporting audited objects" in SCHEMA_MAPPING.md; used only for verified
dashboard fields unavailable from the eight approved objects; SELECT-only; set capped
at ten objects — DECISION 6).
`msisdn` is absent from all approved tables and is never queried from daily T1 (DECISION 10).

## 3. Pages and interactions completed

| Page | Interactions |
|---|---|
| 1 Executive | Global filters (incl. population scope), snapshot, KPI cards, funnel, distributions. |
| 2 Campaign | Search, sort, pagination, masked table, row → drill-down, full-population masked CSV export. |
| 3 Drill-Down | Masked-ID search, full profile, sentinel labels, masked export. |
| 4 Capacity | Population scope, cell selection, subscriber mix, PRB views, paginated table, map. |
| 5 Model | Conflict warning, metric table with sources, confusion matrix, training metadata, features. |
| 6 Data Quality | Live re-verification of the schema contract — 91 checks, 90 PASS / 1 WARN, overall PASS. |
| 7 Coverage & Eligibility | Eligibility funnel, suitability/exclusion/signal distributions, cell risk table, verified geo map (12,412 points · 731 cells · 24 governorates). |
| 8 Customer Segmentation | Persona cluster summary, cross-tabs (allowlisted dimensions), aliased Not Segmented bucket. |
| 9 Offer Recommendations | Offer/tier1/addon distributions, masked paginated table, reason-code overview, drill-down. |
| 10 What-If Simulation | Deterministic step14/step15 engine: identity (731/731, changed 0), stale-on-change, reset. |

## 4. Verification results

- `app/sql/verify_schema_mapping.sql` executed with `default_transaction_read_only=on`: all
  27 row/snapshot/uniqueness checks, 7 null/sentinel checks, 7 join-cardinality checks and
  5 baseline checks **OK — zero FAILs**; single snapshot (2026-01-01) and 1:1
  subscriber_id joins confirmed (DECISION 5 guards pass).
- Unit tests: **77 passed** (incl. new guard failure-path, normalization and sentinel tests).
- Phase 2: **124 passed** total — 77 Phase-1 unit + 15 Phase-2 unit + 12 Phase-2 UAT
  (live DB, AppTest + independent SQL reconciliation) + 20 Phase-1 UAT.
- Streamlit AppTest: **all 10 pages run with 0 exceptions** (live DB; DQ overall PASS).
- Headless smoke test: health endpoint 200, root page 200, log clean, server stopped,
  port released (DECISION 12 process followed).
- `python -m pip install --dry-run -r app/requirements.txt`: exit 0 (syntax validated).
- No modifications to PostgreSQL objects or pipeline scripts; credentials exist only in
  local env/secrets template placeholders.

## 5. Known technical debt (documented per DECISIONS 5 and 9)

1. `step13_recommendations`, `step14_capacity_simulation`, `abt_subscriber_month_clustered`
   have no `snapshot_month`; joined on `subscriber_id` only. Accepted for Phase 1 (single
   snapshot, 1:1 verified) with mandatory runtime guards in `business_logic/guards.py`
   that fail safely with a schema-compatibility error and never perform an ambiguous join.
2. No PK/FK/UNIQUE/NOT NULL constraints; the single verified index is `idx_abt_sub_month`.
   Phase 1 enforces uniqueness and join cardinality at the application layer; no
   database migrations are performed.
3. Type heterogeneity (int8 vs int4 `cluster_id`, `text` vs `varchar`, `real` vs `float8`)
   is handled by the Python normalization registry (DECISION 8); DB types unchanged.

## 6. Startup

From `app/` with the project venv:

```
streamlit run Home.py
```

Configuration (environment variables or `app/.streamlit/secrets.toml` `[database]` section):

| Variable | Example |
|---|---|
| `FWA_DB_HOST` | `localhost` |
| `FWA_DB_PORT` | `5432` |
| `FWA_DB_NAME` | `postgres` |
| `FWA_DB_USER` | `postgres` |
| `FWA_DB_PASSWORD` | (set locally; never committed) |

Optional: `FWA_DB_SCHEMA` (defaults to `cleaned_data`). All sessions open with
`default_transaction_read_only=on`.

## 7. Blockers / open items

- None blocking. Remaining knowns: metric conflicts in report sources (displayed
  with sources, never resolved in-app — DECISION 3); `use_container_width` deprecation
  warnings on streamlit 1.57 (cosmetic, console only); historical DQ trend chart
  intentionally absent (no historical snapshots — stated on page 6).
