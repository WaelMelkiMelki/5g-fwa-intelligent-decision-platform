# UAT REPORT — 5G FWA Decision-Support Dashboard (Phase 1 + Phase 2)

Date: 2026-08-08 · Tester: execution editor (automated UAT) · App version: `app/` (Phase 1 MVP + Phase 2 pages 6–10)
Build: PostgreSQL 18.3 `localhost:5432` · schema `cleaned_data` · snapshot 2026-01-01
Environment: `.venv` Python 3.12.10 · streamlit 1.57.0 · playwright 1.62.0 (UAT tool only, not in `requirements.txt`)

## 1. Scope

Task 1–10 of the UAT instruction:

1. Start the app with the documented command (`streamlit run Home.py` from `app/`, port 8501, headless).
2. Test Home + all 5 dashboard pages.
3. Verify PostgreSQL remains SELECT-only.
4. Compare displayed KPIs with direct read-only SQL results.
5. Interaction tests (filters, charts, sorting/pagination, drill-down, cell selection, CSV export + masking, empty/invalid combinations, DB failure handling).
6. Layout at common desktop resolutions (1920×1080, 1440×900, 1366×768).
7. Screenshots of every page.
8. Fix only confirmed application defects inside `app/`.
9. Re-run all automated tests.
10. Clean smoke test on a fresh port; the server was stopped afterwards.

No new dashboards, no database writes, no live inference, no pipeline changes.

## 2. Test performed — summary

| # | Test | Method | Result |
|---|---|---|---|
| 1 | App start (documented command) | `streamlit run Home.py --server.port 8501 --server.headless true` | PASS (health 200, log clean) |
| 2 | Home + all 10 pages render | AppTest 10-page loop + headless Chromium | PASS (0 exceptions, correct page each) |
| 3 | PostgreSQL SELECT-only | code audit + `SHOW default_transaction_read_only` + live INSERT attempt | PASS (see §5) |
| 4 | KPI reconciliation | 32 AppTest cases vs independent SQL aggregates (§6, incl. Phase-2 pages) | PASS (see §6) |
| 5 | Interactions | AppTest walk-throughs (§7) | PASS (3 defects found & fixed, §9) |
| 6 | Layout / resolution | Playwright at 3 desktop resolutions | PASS (0 horizontal overflow) |
| 7 | Screenshots | 19 PNGs + 1 E2E (see §11) | PASS |
| 8 | Defect fixes | `app/` only | 3 fixed (§9) |
| 9 | Full automated suite | `pytest app/tests` | **124 passed** |
| 10 | Clean smoke + stop | fresh port 8514, health 200, root 200, then all servers stopped | PASS |

**Decision: PASS** (3 Phase-1 defects + 0 Phase-2 defects; all fixed and re-verified in `app/`; no remaining blocker).

## 3. Start command (documented in app/IMPLEMENTATION_REPORT.md §4)

```text
cd app
streamlit run Home.py --server.port 8501 --server.headless true
```

Credentials: `FWA_DB_*` env vars or `app/.streamlit/secrets.toml` (local, gitignored). App serves on `http://localhost:8501`; pages at `/Executive_Overview`, `/Campaign_Operations`, `/Subscriber_Drill_Down`, `/Network_Capacity`, `/Model_Performance` (Streamlit strips the numeric file prefixes for URLs; sidebar navigation shows the same URLs).

## 4. Page rendering checklist (browser-verified)

| Page | Verification | Expected vs Actual |
|---|---|---|
| Home | h1, success banner | `Connected. Snapshot 2026-01-01 · 12,412 subscribers · 731 cells · 12,412 campaign rows` |
| 1 Executive | KPIs + 4 collections | KPI values == SQL counts (see §6) |
| 2 Campaign | table, search, sort, pagination, drill-down, export | 50 rows/page, masked IDs, `2 / 249` pager (12,412 rows / 50) |
| 3 Drill-down | search + profile + masked export | masked header `SUB_XXXX…`, metrics identical to service values |
| 4 Capacity | KPI, PRB histograms, cell table, subscriber mix, map | `731` cells, `0` at/over 80%, mask in subscriber table |
| 5 Model | metrics + conflict warning + tables | conflict warning present (registry), values match SQL % |

No `st.exception` in any of the 6 AppTest runs at any resolution.

## 5. PostgreSQL remains SELECT-only — evidence

1. **Code audit** (`app/**/*.py`): no INSERT/UPDATE/DELETE/DDL statements — the only matches are the guard documentation line in `database.py` and test cases that assert non-SELECT statements are REJECTED.
2. **Session flag** (live, via app engine): `SHOW default_transaction_read_only` → `on`.
3. **Application-level guard**: `database.run_query("INSERT INTO …")` → `ReadOnlyQueryViolation: statement must start with SELECT`.
4. **Server-level enforcement** (real INSERT attempt into `cleaned_data.step15_final_campaign_list`): rejected with `ReadOnlySqlTransaction: cannot execute INSERT in a read-only transaction`; row count remained 12,412.
5. **No writes observed** — `pg_stat_activity` during page renders showed only SELECT/SET statements (idle sessions otherwise).

## 6. KPI reconciliation (displayed vs direct SQL)

Every displayed KPI in §4 was cross-checked against an independently written SQL aggregate (basis: the exact joins the app uses). The reconciliation is embedded in `app/tests/test_uat_pages.py` — 20 test cases:

| Page | Displayed KPI | SQL reference | Matches |
|---|---|---|---|
| 1 | Total subscribers 12,412 | `COUNT(*) step15 ⋈ abt` | ✓ |
| 1 | Eligible (score > 0) | `COUNT(*) WHERE fwa_suitability_score > 0` | ✓ |
| 1 | Contact Now 731 | `COUNT(*) WHERE campaign_action='Contact Now'` | ✓ |
| 1 | Filtered / baseline | = Total subscriber vs 12,412 | ✓ |
| 1 | Churn High Risk (filter) | `WHERE churn_risk_band='High Risk'` | ✓ |
| 1 | Excluded population | `WHERE cluster_id=-1` = 9489 | ✓ |
| 2 | Rows matching filters 12,412 | `SELECT COUNT(*) …` | ✓ |
| 3 | profile fields | `step15⋈ab_requests` row (score, band, priority) | ✓ |
| 4 | Cells 731 · over-80 0 · max p95 | t3 SQL aggregates | ✓ |
| 5 | Scored 12,412 · High 176 · Medium 1,771 · mean/max prob | step12 SQL aggregates | ✓ |

No displayed number differed from the SQL ground truth. Funnel (All → Eligible → Contact Now) matches `metrics.funnel_rows` expectations. Filter-driven numbers are re-run live for every test (never hard-coded).

## 7. Interaction test matrix (task item → result)

| Interaction | Tested via | Result |
|---|---|---|
| Global filters (population, churn, cluster, capacity, offer, campaign, snapshot, Reset) | AppTest sidebar widgets on 5 pages | ✓ (values change the data, counts match SQL) |
| Chart updates | AppTest `plotly_chart` re-render after filter change (p1/p4/p5) | ✓ (charts re-render without errors) |
| Sorting / pagination | p2 sort asc/desc rows differ; p2 and p4 page buttons loop | ✓ (page 1↔2↔1 round-trip, first row changes) |
| Subscriber drill-down | p2 row → `st.switch_page` → p3 profile (masked header + metrics) | ✓ (browser-verified live) |
| Cell selection | p4 select cell → subscriber-mix table + markdown | ✓ (masked IDs in table) |
| CSV export + masking | `export_csv_bytes` decoded; scan for `msisdn`, `latitude`, `longitude`, street | ✓ (no sensitive columns; masked `SUB_XXXX…`; filename `fwa_campaign_202601_<hash>.csv`) |
| Empty / invalid combinations | filter combo with 0 hits; search with «ZZZ_NO_MATCH» | ✓ (empty-state info, no errors) |
| Database failure | p2 (and sidebar) with wrong password | ✓ (`st.error`, Retry button; no traceback) |

Empty combos: page shows `No subscribers match …` info; dashboard never raises.

## 8. Layout at common desktop resolutions (Playwright)

| Resolution | Pages tested | Horizontal overflow (body.scrollWidth − innerWidth) |
|---|---|---|
| 1920×1080 | Home + all 10 pages | 0 px |
| 1440×900 | Home + all 10 pages | 0 px |
| 1366×768 | Home + all 10 pages | 0 px |

KPI cards, charts and tables render within the viewport (overflow measured programmatically in all 34 screenshots).

## 9. Defects discovered during UAT (all within `app/`, all fixed)

| # | Defect | Root cause | Fix (file) | Verified |
|---|---|---|---|---|
| 1 | Global filter bar never appeared on any page | `components/filters.py::render_global_filters()` was defined but never called | wired into Home + pages 1–5 | AppTest now shows Snapshot/Population + 6 multiselects, all live SQL-verified |
| 2 | «Search (masked subscriber ID)» field on page 2 had no effect | field declared, never applied to rows | in-memory filter applied on the current page; empty state on no match | test `test_campaign_search_…` |
| 3 | Drill-down from page 2 opened «Subscriber not found» | `campaign_service.get_subscribers` masked rows before returning → page 2 built `id_map` masked→masked (identity), so the real subscriber ID was looked up in the DB | removed masking from the service layer (page masks its own display copy) | pytest + live browser E2E (`e2e_drilldown_1440x900.png` shows full profile) |

(These are the "expected vs actual" — the first three UAT failures above.)

## 10. Remaining usability notes (non-blocking)

1. `use_container_width` deprecation warnings in logs (Streamlit ≥ 1.57 prints them); still functional — migrate to `width='stretch'` in a future pass.
2. Page-2 search is intentionally in-memory over the current page (50-row window); the help text says so. Full population search would need a server-side predicate (out of Phase 1 scope).
3. On Page-4, selecting a cell likely shows only a handful of eligible subscribers (2,923 eligible rows spread over 731 cells); the cell-panel view is data-driven.
4. Screenshots are static PNGs; interactive charts are verified by re-render counters (AppTest), not pixel diffs.
5. E2E drill-down flow (`st.switch_page`) is covered in the real browser (Playwright); the AppTest harness cannot register the multipage context.

## 11. Screenshots produced (`app/uat/screenshots/`)

| File | Page | Resolution |
|---|---|---|
| home_{1366x768,1440x900,1920x1080}.png | Home | 3 |
| p1_executive_{…}.png | Executive Overview | 3 |
| p2_campaign_{…}.png | Campaign Operations | 3 |
| p3_drilldown_{…}.png | Subscriber Drill-Down (empty) | 3 |
| p4_capacity_{…}.png | Network Capacity | 3 |
| p5_model_{…}.png | Model Performance | 3 |
| e2e_drilldown_1440x900.png | Campaign → Drill-down (loaded profile, headless browser) | 1 |
| p6_dataquality_{…}.png | Data Quality | 3 |
| p7_coverage_{…}.png | Coverage & Eligibility | 3 |
| p8_segmentation_{…}.png | Customer Segmentation | 3 |
| p9_recommendations_{…}.png | Offer Recommendations | 3 |
| p10_simulation_{…}.png | What-If Simulation | 3 |

All 34 PNGs + `results.json` (md5 per file, overflow/db-error flags) written during UAT; 0 database errors, 0 horizontal overflow (Phase 2 run: `results_phase2.json`, all 15 shots 0 px overflow, no tracebacks).

## 12. Automated test suite (re-run after ALL fixes)

```
python -m pytest app/tests -q
124 passed in 54.33s
```

- 77 pre-existing unit tests (database guard, filtering, metrics, masking, services, guards, normalize, display)
- +20 UAT page tests `app/tests/test_uat_pages.py` (reconciliation + interactions + failure path; zero-write; auto-skip when no `FWA_DB_*` envs, safe for CI)
- +15 Phase-2 unit tests `app/tests/test_phase2_services.py` (mocked DB; simulation purity/identity)
- +12 Phase-2 UAT tests `app/tests/test_phase2_pages.py` (live DB, AppTest + independent SQL reconciliation)

## 12b. Phase 2 UAT (pages 6–10)

| Page | Verified via | Result |
|---|---|---|
| 6 Data Quality | Overall PASS metric, 91 checks (90 PASS/1 WARN), table statuses subset, trend-info note | PASS |
| 7 Coverage & Eligibility | KPIs == SQL (12,412/2,923/9,489), feasibility focus filter == SQL count, grid 12,412 · cells 731 · 24 gov, map gate "verified" (no unavailable warning) | PASS |
| 8 Segmentation | Segmented subscribers == 12,412 (clustered), Personas == 4 cluster sums, cross-tab dimension switch (contract_type pivot index) | PASS |
| 9 Recommendations | With-offer 2,923, with-reason 1,011 == SQL; table 50 rows, masked `SUB_…`, reason_codes column, no "No Offer" in page table | PASS |
| 10 What-If | defaults → identity (731/731, changed 0), param change → stale, rerun → ok, reset → idle; panel caption "exploratory, not persisted" | PASS |

**Decision: PASS** — 0 defects found in Phase 2 pages/services during UAT.

## 13. Final clean smoke (task 10)

| Step | Result |
|---|---|
| fresh port 8514, documented command | PID 2516, health `200 ok`, root `200` |
| browser render on 8514 | `Connected … 12,412 subscribers · 731 cells` |
| log scan | no `Error`/`Traceback` |
| server shutdown | both app servers stopped; ports 8501/8510/8513/8514 released |

## 14. Verdict

**PASS** — Phase 1 MVP + Phase 2 extension are functional, accurate against the source of truth (`cleaned_data`, read-only), privacy-safe (masked exports, no `msisdn`), and cleanly tested. Non-blocking usability notes in §9 are tracked as future polish items; no open blocker.
