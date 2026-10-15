# 5G FWA Intelligent Decision & Agentic AI Platform

## 1. Purpose and scope

This project develops a local-first decision-support platform for Fixed Wireless Access (FWA) planning. It combines telecom data engineering, eligibility rules, customer analytics, network-capacity simulation, a dashboard, and later a grounded AI assistant.

The public repository is a portfolio reconstruction. The original internship datasets are unavailable, so new experiments must use synthetic or legally reusable data. New metrics must never be presented as reproductions of confidential historical results.

## 2. Starting point: original project audit

The original workspace contained:

- a multi-step Python/PostgreSQL analytics pipeline;
- a 50-column subscriber-month Analytical Base Table (ABT);
- eligibility and suitability scoring;
- behavioural/commercial clustering;
- XGBoost churn modelling;
- offer recommendation rules;
- PRB-based capacity simulation;
- final campaign prioritisation;
- a Streamlit dashboard and a LaTeX technical report.

The original source code expects a PostgreSQL schema named `cleaned_data`. The original raw CRM, usage, coverage, service-consumption, and RAN datasets are not present in the public workspace.

### Historical results from the original project

These values are retained only as historical context and are not public reconstructed results:

- approximately 12,412 subscribers;
- approximately 731 cells;
- historical eligible-population figures reported as 2,629 in the report and 2,923 in the later dashboard mapping;
- historical XGBoost ROC-AUC around 0.71;
- historical maximum cumulative PRB proxy around 68.26%.

The conflicting eligibility figures are an unresolved historical-version issue. The reconstructed pipeline must recompute all results from its own generated data.

## 3. Repository and publication preparation

### Completed actions

- Initialized a local Git repository on branch `main`.
- Connected the repository to the GitHub remote.
- Added a public-facing README and ignore rules.
- Excluded the original report, combined data dump, backups, generated PDF, and internship-specific material.
- Replaced hard-coded database credentials in legacy scripts with environment variables.
- Published the reviewed repository contents to GitHub.

### Evidence

- Scaffold commit: `6ff7f93`.
- Publication-boundary commit: `6e3ec3d`.
- Reviewed platform publication commit: `b6e409e`.
- Synthetic-data milestone commit: `1c7e4fa`.
- The latest local validation confirmed `main` tracks `origin/main`.

### Public-repository boundary

The repository must not contain:

- real database passwords, tokens, or private connection strings;
- original customer data or MSISDN values;
- confidential Huawei documents or internship report material;
- unreviewed database dumps or local credentials.

Environment configuration uses `FWA_DB_*` variables or local Streamlit secrets. Secrets must never be committed.

## 4. Existing dashboard documentation

The existing dashboard implementation is documented in:

- `app/IMPLEMENTATION_REPORT.md`;
- `app/PHASE2_REPORT.md`;
- `app/SCHEMA_MAPPING.md`;
- `app/SIMULATION_CONTRACT.md`;
- `app/REPORT_DASHBOARD_RECONCILIATION.md`.

Those documents describe a read-only Streamlit application, SELECT-only database access, masked identifiers, schema guards, data-quality checks, coverage views, segmentation, recommendations, and deterministic what-if simulation.

The dashboard remains dependent on the unavailable PostgreSQL snapshot and is therefore not yet the primary reproducible demo path.

## 5. Reproducible synthetic-data milestone

### Objective

Create a deterministic, relationship-consistent replacement for the unavailable source datasets.

### Implemented files

- `data_generation/synthetic_fwa.py`: configuration, generation, anomaly injection, and validation.
- `data_generation/__init__.py`: public generator exports.
- `tests/test_synthetic_data.py`: focused tests.
- `requirements-dev.txt`: development dependency entry.

### Current behaviour

The generator creates five tables:

1. CRM subscriber attributes;
2. monthly usage and device/cell dominance;
3. address-level coverage and radio quality;
4. service consumption;
5. cell-level RAN KPIs.

The generator uses `numpy.random.default_rng` with an explicit seed. It validates grain uniqueness, complete subscriber relationships, valid cell references, non-negative measures, PRB bounds, and non-null coordinates. It can inject a missing usage value and a duplicate usage row to exercise quality checks.

The default dimensions now match the historical project volume: 12,412 synthetic subscribers and 731 synthetic cells. This matches structural scale only and must not be interpreted as reconstruction of the original data.

### Validation evidence

- Python syntax compilation passed for the generator and tests.
- Focused tests: **4 passed**.
- Deterministic runtime smoke check: **passed**.
- Existing application tests: **92 passed, 68 skipped** in the local environment.

## 6. Local dataset persistence milestone

### Objective

Persist a generated dataset locally in a portable format without committing generated data to Git.

### Implemented files

- `data_generation/synthetic_fwa.py`: validated Parquet writer and manifest generation.
- `scripts/generate_synthetic_data.py`: configurable command-line entry point.
- `tests/test_synthetic_data.py`: Parquet round-trip and manifest test.
- `README.md`: local generation command.

### Output contract

The command writes five `{table_name}.parquet` files and one `manifest.json` under `data/processed/`. The directory is ignored by Git; the seed, configuration, row counts, and columns are recorded in the manifest for reproducibility.

### Validation status

This milestone is complete when the focused test suite passes and the generated Parquet files reload with the same rows and columns as the in-memory tables.

## 7. Analytical Base Table milestone

### Objective

Create one validated subscriber-month analytical table from the five generated source domains.

### Implemented files

- `data_pipeline/abt.py`: source loading, explicit joins, feature derivation, validation, and persistence.
- `data_pipeline/__init__.py`: transformation exports.
- `scripts/build_abt.py`: command-line ABT builder.
- `tests/test_abt.py`: grain, join, feature, persistence, and failure-path tests.

### Validation evidence

- Focused ABT tests: **4 passed**.
- Join cardinality is enforced by Pandas merge validation.
- The output contract is one row per synthetic subscriber and snapshot.

## 8. Current limitations

- The public synthetic source tables are now connected to the public ABT builder; the legacy PostgreSQL pipeline remains separate.
- The dashboard still expects PostgreSQL tables rather than generated DataFrames or Parquet files.
- Public model results have not yet been retrained on reconstructed data.
- The project has no FastAPI service or grounded agent yet.
- The exact reason for skipped application tests should be recorded when database-dependent UAT is run with a test database.

## 9. Ordered roadmap

1. Add a data-quality report for source and ABT tables.
2. Rebuild eligibility and capacity logic against reconstructed data.
3. Add reproducible segmentation and churn training.
4. Add model evaluation artifacts and experiment metadata.
5. Add FastAPI decision endpoints.
6. Adapt the dashboard to the public local data path.
7. Add a read-only grounded agent with controlled tools.
8. Add observability, CI, and final portfolio documentation.

Each step must update this document and the relevant contract/decision document before the next step starts.
