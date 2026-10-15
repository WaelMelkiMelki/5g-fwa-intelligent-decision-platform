# 5G FWA Intelligent Decision & Agentic AI Platform

This repository is being prepared as a public, reproducible portfolio version of a 5G Fixed Wireless Access decision-support project.

## Publication status

The current workspace contains legacy project material and is **not yet ready for public publication**. Before the first push:

- remove credentials and connection strings from legacy scripts;
- remove confidential Huawei-specific material and identifiers;
- separate historical internship results from newly reconstructed experiments;
- regenerate results from legally reusable or synthetic data;
- review the staged files for secrets and personal or proprietary information.

The original datasets are unavailable. Reconstructed experiments must not claim to reproduce the original Huawei results.

## Current contents

- `app/`: read-only Streamlit decision-support dashboard;
- root Python scripts: original batch analytics pipeline and validation utilities;
- `step*_*.csv`: derived validation/output artifacts, not source datasets.

The original report, combined dumps, internship material, and backup artifacts are intentionally excluded from the public repository until they have been reviewed for confidentiality.

## Planned public architecture

The public version will use seeded synthetic data, validated data contracts, local analytical storage, reproducible ML training, FastAPI services, the dashboard, and a read-only grounded agent. Local execution will remain the primary deployment target.

## Development

The dashboard currently expects a PostgreSQL database configured through `FWA_DB_*` environment variables or `app/.streamlit/secrets.toml`. Do not commit either configuration or any real credentials.

The reconstructed public pipeline and setup instructions will be added after the data contract is approved.

## Synthetic data generator

The first reproducible data slice is available in `data_generation/`. It creates linked CRM, monthly usage, address coverage, service-consumption, and cell-KPI tables without requiring PostgreSQL.

After installing the development dependencies, run the focused tests with:

```bash
python -m pip install -r requirements-dev.txt
python -m pytest tests/test_synthetic_data.py -q
```

The generator uses a configurable random seed and can inject duplicate and missing-value anomalies for data-quality testing.
