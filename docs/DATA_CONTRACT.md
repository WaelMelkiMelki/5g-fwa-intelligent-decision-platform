# Synthetic Data Contract

## 1. Contract status

Status: **implemented and tested for the generator layer**.

The contract describes a single monthly snapshot. It is intentionally independent of PostgreSQL so that generation, validation, and transformation can run locally.

Default generator configuration:

| Parameter | Default |
|---|---:|
| subscribers | 1,000 |
| cells | 40 |
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
- The generator does not attempt to reproduce historical Huawei row counts or metrics.

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
