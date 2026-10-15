# Synthetic Data Contract

## 1. Contract status

Status: **implemented and tested for the generator layer**.

The contract describes a single monthly snapshot. It is intentionally independent of PostgreSQL so that generation, validation, and transformation can run locally.

Default generator configuration:

| Parameter | Default |
|---|---:|
| subscribers | 12,412 |
| cells | 731 |
| snapshot month | `2026-01-01` |
| random seed | 42 |
| anomaly injection | disabled |

## 2. Source tables

### `crm_subscribers`

Grain: one row per `subscriber_id` and `snapshot_month`.

Columns:

- `subscriber_id`: synthetic subscriber key, format `SUB_######`;
- `snapshot_month`: monthly observation date;
- `segment_tier`, `b2b_b2c_flag`, `contract_type`: categorical commercial attributes;
- `arpu_monthly_tnd`: non-negative monthly revenue;
- `tenure_months`: positive tenure;
- `address_id`: foreign key to `coverage_addresses.address_id`;
- `governorate`: synthetic geographic label;
- `num_active_lines`: active-line count;
- `churn`: binary training target generated from noisy commercial factors.

### `usage_monthly`

Grain: one row per `subscriber_id` and `snapshot_month`.

Columns:

- `monthly_sessions`;
- `monthly_total_gb`;
- `monthly_peak_hour_ratio`;
- `dominant_device_generation`;
- `dominant_serving_cell_id`: foreign key to `cell_kpis.cell_id`;
- `device_5g_ready_flag`.

### `coverage_addresses`

Grain: one row per `address_id`.

Columns:

- `address_id`, `serving_cell_id`, `governorate`;
- `latitude`, `longitude`;
- `predicted_rsrp_dbm`, `predicted_sinr_db`;
- `coverage_5g_flag`, `coverage_4g_flag`, `fiber_coverage_flag`;
- `signal_quality_class`;
- `radio_feasibility_class`.

### `service_consumption`

Grain: one row per `subscriber_id` and `snapshot_month`.

Columns:

- `streaming_vol_gb`, `streaming_session_count`;
- `iptv_active_flag`, `iptv_watch_hours`;
- `voip_minutes`, `gaming_vol_gb`.

### `cell_kpis`

Grain: one row per `cell_id` and `snapshot_month`.

Columns:

- `cell_id`, `site_id`, `snapshot_month`;
- `avg_prb_utilisation_pct`, `p95_prb_utilisation_pct`, `max_prb_utilisation_pct`;
- `avg_dl_throughput_mbps`.

## 3. Relationship rules

- Every CRM subscriber has exactly one usage row and one service-consumption row for the snapshot.
- Every CRM `address_id` has exactly one coverage row.
- Every usage and coverage serving-cell key exists in `cell_kpis`.
- Subscriber and address identifiers are synthetic and contain no source customer identifiers.
- All source tables use the same snapshot date for a generated dataset.
- The default dimensions match the historical project volume: 12,412 subscribers and 731 cells.
- Matching dimensions is a structural compatibility choice only; values, model metrics, and business outcomes are not historical reconstructions.

## 4. Validation rules

`validate_dataset()` rejects datasets with:

- missing required tables;
- duplicate grain keys;
- incomplete subscriber-level joins;
- unknown serving cells;
- negative ARPU or traffic;
- PRB values outside `[0, 100]`;
- null coverage coordinates.

`inject_anomalies=True` intentionally creates a duplicate usage grain and a missing traffic value. The current test suite confirms that the duplicate is detected. A later data-quality stage will report all defects together instead of stopping at the first defect.

## 5. Leakage and realism policy

The churn target is generated from noisy commercial factors rather than copied from a downstream eligibility or campaign decision. Eligibility, recommendations, and capacity outcomes must be computed after source generation. No downstream result may be used as an input to create the target.

Synthetic distributions are plausible engineering assumptions, not measurements of a real operator. Every public result must state that limitation.

## 6. Persistence contract

`save_dataset()` validates the in-memory tables before writing them to a caller-selected directory. It writes one `{table_name}.parquet` file per table and a `manifest.json` file containing:

- UTC generation timestamp;
- all generator configuration values;
- row counts for every table;
- ordered column names for every table.

The command-line entry point is `scripts/generate_synthetic_data.py`. Generated data belongs under `data/processed/`, which is ignored by Git because datasets are reproducible local artifacts rather than source code.

## 7. Analytical Base Table contract

`data_pipeline/abt.py` joins the five source tables into `abt_subscriber_month`, with grain one row per `subscriber_id` and `snapshot_month`.

The public ABT currently contains 45 columns. Duplicate dimension columns are excluded through explicit SQL projection; for example, the address-level `governorate` is not copied into a second `governorate_coverage` column.

The transformation uses:

- one-to-one validation for subscriber usage and service joins;
- one-to-one validation for address coverage joins;
- many-to-one validation for subscriber-to-cell KPI joins;
- deterministic ARPU and tenure bands;
- multi-line, service-intensity, and capacity-status flags.

The ABT is written to `abt_subscriber_month.parquet` with `abt_manifest.json`. The ABT is a public reconstructed analytical table and must not be confused with the unavailable historical Huawei ABT.

## 8. Quality-report contract

`data_pipeline/quality.py` checks the five source tables and the ABT for required tables, non-empty outputs, grain uniqueness, non-null keys, snapshot consistency, subscriber/address/cell relationships, row-count preservation, non-negative measures, and PRB ranges. The coverage table is address-grain and intentionally has no `snapshot_month`; snapshot checks apply only to tables that declare that column.

`scripts/run_quality_checks.py` writes `quality_report.json` and exits with status 1 when any check fails. The verified full-scale dataset currently produces **31 PASS checks and 0 FAIL checks**.
