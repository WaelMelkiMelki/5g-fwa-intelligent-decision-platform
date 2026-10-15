-- ============================================================================
-- app/sql/verify_schema_mapping.sql
-- READ-ONLY schema-verification script for app/SCHEMA_MAPPING.md (Phase 1).
--
-- Reproduces, via SELECT/WITH/EXPLAIN (no ANALYZE) only:
--   * table and column metadata + data types
--   * row counts, snapshot counts, uniqueness checks
--   * distinct filter values, NULL and sentinel counts
--   * join-cardinality checks, baseline dashboard counts
--
-- FORBIDDEN in this file: INSERT, UPDATE, DELETE, CREATE, ALTER, DROP,
-- TRUNCATE, GRANT, REVOKE, COPY to server files, function calls with
-- side effects. No credentials. No raw subscriber identifiers (counts only).
--
-- Safe execution (read-only role / session):
--   psql -d postgres -v ON_ERROR_STOP=1 -f app/sql/verify_schema_mapping.sql
--   or wrap the run in BEGIN / SET default_transaction_read_only=on / COMMIT
--   within a single read-only session.
-- ============================================================================

WITH all_checks AS (
  -- --------------------------------------------------------------------------
  -- SECTION 1: row counts per allowed object (SCHEMA_MAPPING.md sections 1/5)
  -- --------------------------------------------------------------------------
  SELECT '1.rows' AS section, 'row_count step15_final_campaign_list' AS check_name,
         CASE WHEN n = 12412 THEN 'OK' ELSE 'FAIL' END AS result, 'count=' || n AS detail
  FROM (SELECT count(*) AS n FROM cleaned_data.step15_final_campaign_list) t
  UNION ALL
  SELECT '1.rows', 'row_count abt_subscriber_month',
         CASE WHEN n = 12412 THEN 'OK' ELSE 'FAIL' END, 'count=' || n
  FROM (SELECT count(*) AS n FROM cleaned_data.abt_subscriber_month) t
  UNION ALL
  SELECT '1.rows', 'row_count step12_churn_predictions',
         CASE WHEN n = 12412 THEN 'OK' ELSE 'FAIL' END, 'count=' || n
  FROM (SELECT count(*) AS n FROM cleaned_data.step12_churn_predictions) t
  UNION ALL
  SELECT '1.rows', 'row_count step13_recommendations',
         CASE WHEN n = 2923 THEN 'OK' ELSE 'FAIL' END, 'count=' || n
  FROM (SELECT count(*) AS n FROM cleaned_data.step13_recommendations) t
  UNION ALL
  SELECT '1.rows', 'row_count step14_capacity_simulation',
         CASE WHEN n = 2923 THEN 'OK' ELSE 'FAIL' END, 'count=' || n
  FROM (SELECT count(*) AS n FROM cleaned_data.step14_capacity_simulation) t
  UNION ALL
  SELECT '1.rows', 'row_count t3_cell_monthly_kpi',
         CASE WHEN n = 731 THEN 'OK' ELSE 'FAIL' END, 'count=' || n
  FROM (SELECT count(*) AS n FROM cleaned_data.t3_cell_monthly_kpi) t
  UNION ALL
  SELECT '1.rows', 'row_count t4_coverage_features',
         CASE WHEN n = 12412 THEN 'OK' ELSE 'FAIL' END, 'count=' || n
  FROM (SELECT count(*) AS n FROM cleaned_data.t4_coverage_features) t
  UNION ALL
  SELECT '1.rows', 'row_count t4_coverage_address_grid',
         CASE WHEN n = 12412 THEN 'OK' ELSE 'FAIL' END, 'count=' || n
  FROM (SELECT count(*) AS n FROM cleaned_data.t4_coverage_address_grid) t
  UNION ALL
  SELECT '1.rows', 'row_count abt_subscriber_month_clustered (supporting)',
         CASE WHEN n = 2923 THEN 'OK' ELSE 'FAIL' END, 'count=' || n
  FROM (SELECT count(*) AS n FROM cleaned_data.abt_subscriber_month_clustered) t
  UNION ALL
  SELECT '1.rows', 'row_count step11_prioritization (supporting)',
         CASE WHEN n = 2923 THEN 'OK' ELSE 'FAIL' END, 'count=' || n
  FROM (SELECT count(*) AS n FROM cleaned_data.step11_prioritization) t

  -- --------------------------------------------------------------------------
  -- SECTION 2: snapshot counts (single-snapshot guard, DECISION 5)
  -- --------------------------------------------------------------------------
  UNION ALL
  SELECT '2.snapshot', 'distinct snapshot_month in step15',
         CASE WHEN n = 1 THEN 'OK' ELSE 'FAIL' END, 'distinct=' || n
  FROM (SELECT count(DISTINCT snapshot_month) AS n FROM cleaned_data.step15_final_campaign_list) t
  UNION ALL
  SELECT '2.snapshot', 'distinct snapshot_month in abt_subscriber_month',
         CASE WHEN n = 1 THEN 'OK' ELSE 'FAIL' END, 'distinct=' || n
  FROM (SELECT count(DISTINCT snapshot_month) AS n FROM cleaned_data.abt_subscriber_month) t
  UNION ALL
  SELECT '2.snapshot', 'distinct snapshot_month in step12_churn_predictions',
         CASE WHEN n = 1 THEN 'OK' ELSE 'FAIL' END, 'distinct=' || n
  FROM (SELECT count(DISTINCT snapshot_month) AS n FROM cleaned_data.step12_churn_predictions) t
  UNION ALL
  SELECT '2.snapshot', 'distinct snapshot_month in t3_cell_monthly_kpi',
         CASE WHEN n = 1 THEN 'OK' ELSE 'FAIL' END, 'distinct=' || n
  FROM (SELECT count(DISTINCT snapshot_month) AS n FROM cleaned_data.t3_cell_monthly_kpi) t
  UNION ALL
  SELECT '2.snapshot', 'step15 snapshot value',
         CASE WHEN v = '2026-01-01' THEN 'OK' ELSE 'FAIL' END, 'value=' || COALESCE(v, 'NULL')
  FROM (SELECT DISTINCT snapshot_month::text AS v FROM cleaned_data.step15_final_campaign_list) t
  UNION ALL
  SELECT '2.snapshot', 'step13 has NO snapshot_month column',
         CASE WHEN n = 0 THEN 'OK' ELSE 'FAIL' END, 'columns=' || n
  FROM (SELECT count(*) AS n FROM information_schema.columns
        WHERE table_schema = 'cleaned_data' AND table_name = 'step13_recommendations'
          AND column_name = 'snapshot_month') t
  UNION ALL
  SELECT '2.snapshot', 'step14 has NO snapshot_month column',
         CASE WHEN n = 0 THEN 'OK' ELSE 'FAIL' END, 'columns=' || n
  FROM (SELECT count(*) AS n FROM information_schema.columns
        WHERE table_schema = 'cleaned_data' AND table_name = 'step14_capacity_simulation'
          AND column_name = 'snapshot_month') t

