# SIMULATION CONTRACT — What-If Engine (Pages 10 / Step 14-15 Mirror)

Scope: `app/business_logic/simulation.py` + `app/services/simulation_service.py` +
page `app/pages/10_What_If_Simulation.py`. Date: 2026-08-08 · Snapshot `2026-01-01`.

## 1. Purpose

The in-memory what-if engine mirrors the verified Phase-1 pipeline math
(`step14_post_migration_capacity_simulation.py`, `step15_final_prioritization_campaign_action.py`)
so business users can probe parameter scenarios **without re-running the pipeline**
and **without any risk of persisting changed data** (DECISION: in-memory only).

## 2. Engine guarantees

1. **Pure & deterministic** — no DB access, no randomness; identical inputs →
   identical outputs (identity verified live + unit-tested).
2. **Identity property** — default parameters (take rate 100%, verified multiplier
   map, uplift cap 15%, safe 80, waitlist 90) reproduce `step14_capacity_simulation`
   and `step15_final_campaign_list` exactly for the 2,923 eligible subscribers
   (verified against the live DB on page 10: Contact Now baseline 731, changed actions 0).
3. **Read-only.** The engine never writes to PostgreSQL; the page holds results in
   session state (`fwa.whatif`), explicitly captioned "not persisted".
4. **Clamped params.** Validated bounds (spec §10.2): take rate 0–100 %, uplift cap
   0–30 %, safe 40–95, waitlist ≤ 100 (≥ safe).
5. **Prefer DB baseline.** When the input already carries the verified
   `campaign_action` (step15), the baseline is taken from the DB column, not recomputed.

## 3. Math (verified constants)

| Quantity | Formula / value |
|---|---|
| `T_req_mbps` | `monthly_total_gb * 1024 * 8 / 30-day seconds` (2,592,000) |
| `M_offer` | verified category multiplier: Base Only 1.0 · +IPTV 1.25 · +Gaming 1.25 · +Convergent 1.25 · Multi-Addon 1.50 (UI-overridable per category) |
| `uplift_full` | `min(T_req * M_offer / throughput * 100, cap 15%)` |
| `uplift_scenario` | `uplift_full * take_rate / 100` (take rate scales demand) |
| `post_prb` | `cell p95 + uplift` |
| Risk | `<= safe` → Safe/Approved · `<= wait` → High Risk/Waitlist · else Blocked/Exclude |
| Action gate | Exclude → Waitlist → Manual Review → Contact Now → Contact Later (step15 order) |
| Contact Now | `gated_priority >= eligible p75 + post-risk Safe` (priority zeroed when Blocked) |
| Throughput imputation | zero/null cell throughput replaced with eligible-pool median (step14 mirror) |

## 4. Scope & bounds of the result set

- Runs on the **eligible** subscriber base only (`fwa_suitability_score > 0`,
  2,923 rows at snapshot 2026-01-01) — Excluded subscribers are never simulated.
- Outputs: clamped params, per-subscriber frame (`subscriber_rows`), per-cell frame
  (`cells`, sorted by scenario post-PRB desc), scenario action counts, baseline/
  scenario deltas (contact-now, changed actions, cells at risk, mean/median post-PRB).
- Subscriber masks are applied at display time; engine frames contain no PII beyond
  masked subscriber IDs.

## 5. Verified live values (defaults, snapshot 2026-01-01)

Eligible 2,923 · Contact Now baseline 731 · Contact Now scenario 731 ·
**changed actions 0** · cells 400 · cells at risk baseline 0 · scenario 0 ·
mean post-PRB 40.49 (baseline = scenario). Identity holds exactly.

## 6. Test coverage

- Unit: `app/tests/test_phase2_services.py` — empty input stability, param clamping,
  multiplier override, identity (defaults → no changed actions).
- UAT: `app/tests/test_phase2_pages.py::test_data10_run_identity_and_reset` —
  live run → ok, param change → stale, rerun → ok, reset → idle/None.

## 7. Intended use

Single-scenario exploration of one or more parameters at a time. Every change
re-marks the result stale; Run re-executes the deterministic engine. Results are
explicitly "exploratory, not persisted" (user-visible caption + in-session guard).
