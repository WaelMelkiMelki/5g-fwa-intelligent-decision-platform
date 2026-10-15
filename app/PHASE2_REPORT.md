# PHASE 2 REPORT — Decision-Support Extension (Pages 6-10)

Date: 2026-08-08 · Schema: `cleaned_data` only · Snapshot: 2026-01-01 · Read-only.

## 1. What Phase 2 adds

| Page | Focus |
|---|---|
| 6 Data Quality | App-level re-verification of the Phase-1 schema contract (row baselines, null fields, value domains, join integrity). |
| 7 Coverage & Eligibility | Eligibility funnel, coverage classes, signal quality, exclusion reasons, cell risk table, verified geo map (grid + centroids). |
| 8 Customer Segmentation | Cluster summary per persona label, cross-tab by verified dimensions (allowlisted), segment-level metrics. |
| 9 Offer Recommendations | Offer-category and tier1/addon distributions, paginated masked recommendation table, drill-down to profile, reason-code presence overview. |
| 10 What-If Simulation | Deterministic in-memory capacity + campaign-action scenario engine mirroring step14/step15 (see `SIMULATION_CONTRACT.md`). |

## 2. New/modified files

- `app/services/data_quality_service.py` — rewritten: `STAGE_ROW_BASELINES` (10 tables),
  `ZERO_NULL_FIELDS`, `BY_DESIGN_NULLS`, `ALLOWED_TABLES`, case-safe `_qq()` quoting;
  91 checks (row counts, nulls, domains, snapshot, join integrity, baselines).
- `app/services/coverage_service.py` — eligibility KPIs, suitability bands, exclusion
  reasons, cell risk table, centroid overlay, grid summary, `is_geo_join_verified()`.
- `app/services/segmentation_service.py` — cluster summary + cross-tab
  (`CROSS_TAB_DIMENSIONS` allowlist), display aliases for `cluster_id = -1`.
- `app/services/recommendation_service.py` — offer/tier1/addon distributions,
  paginated masked rows, overview (with-offer / with-reason-code counts),
  `'N/A' → 'No Offer'` display mapping.
- `app/services/simulation_service.py` — eligible-base loader (SELECT-only, snapshot
  pinned), scenario runner glue, defaults, clean multiplier overrides.
- `app/business_logic/simulation.py` — pure deterministic engine (unchanged core,
  used by page 10; documented in `SIMULATION_CONTRACT.md`).
- `app/pages/6_Data_Quality.py` … `app/pages/10_What_If_Simulation.py` — new pages
  (global filters shared via `F.render_global_filters()`; session helpers via `S`).
- `app/Home.py` — page table extended to all 10 pages.
- `app/tests/test_phase2_services.py` — 15 unit tests (mocked DB, engine purity).
- `app/tests/test_phase2_pages.py` — 12 live-DB UAT tests (AppTest + independent SQL
  reconciliation).

## 3. Verified live results (snapshot 2026-01-01)

- Data quality: **91 checks — 90 PASS, 1 intentional WARN, overall PASS** (WARN =
  historical trend table empty by design; documented).
- Eligibility: 12,412 subscribers → 2,923 eligible / 9,489 excluded; suitability
  bands 1,579 feasible · 1,036 marginal · 308 poor; exclusion reasons:
  9,449 radio feasibility, 40 fiber coverage, 2,923 excluded (score ≤ 0) rows.
- Coverage: address grid 12,412 points · 731 serving cells · 24 governorates;
  geo join verified 12,412/12,412; coverage classes (eligible): 4G_Fallback 2,338 ·
  Infeasible 294 · 5G_Feasible 291; signal quality Acceptable 2,154 · Excellent 769.
- Segmentation: 4 clusters (0 = 1,074 · 1 = 1,478 · 2 = 314 · 3 = 57), 2 business
  persona labels + Not Segmented bucket; cross-tabs verified for contract type,
  ARPU band, tenure band, segment tier, 5G-ready flag, multi-line flag.
- Recommendations: offer categories 1,912 Base Only · 498 Base + IPTV · 343
  Base + Convergent · 118 Multi-Addon · 52 Base + Gaming; tier1 1,932 Prepaid ·
  991 Postpaid; reason codes present on 1,011 rows; table paginated at 50 rows,
  IDs masked (`SUB_...`).
- What-If identity: defaults → Contact Now 731, changed actions **0**, cells 400,
  cells at risk 0/0, mean post-PRB 40.49 (baseline = scenario).

## 4. Test results

- `pytest app/tests`: **124 passed** (77 Phase-1 + 15 Phase-2 unit + 12 Phase-2 UAT +
  20 Phase-1 UAT) — includes live-DB AppTest runs of all 10 pages, 0 exceptions.
- All Phase-2 queries are aggregate/count/allowlist SELECTs; no subscriber
  coordinates in service outputs; IDs masked at display; engine never writes.

## 5. Design guardrails retained

- Guards (`guards.py`) run before every subscriber-join in Phase-2 services
  (single snapshot, unique keys) — same contract as Phase 1.
- No hard-coded dashboard KPI totals; DQ baselines are documented constants
  (SCHEMA_MAPPING.md §5) asserted by the DQ page, not displayed as KPIs.
- Read-only DB enforced at connection level (`default_transaction_read_only=on`).

## 6. Open items / notes

- `use_container_width` deprecation warnings on streamlit 1.57 (cosmetic, console only).
- Historical DQ-trend chart intentionally absent (no historical snapshots); page
  states this explicitly.
- Engine exploration is explicitly non-persistent by design (see SIMULATION_CONTRACT).
