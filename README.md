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
- `report_v4/`: original LaTeX report source;
- `step*_*.csv`: derived validation/output artifacts, not source datasets.

## Planned public architecture

The public version will use seeded synthetic data, validated data contracts, local analytical storage, reproducible ML training, FastAPI services, the dashboard, and a read-only grounded agent. Local execution will remain the primary deployment target.

## Development

The dashboard currently expects a PostgreSQL database configured through `FWA_DB_*` environment variables or `app/.streamlit/secrets.toml`. Do not commit either configuration or any real credentials.

The reconstructed public pipeline and setup instructions will be added after the data contract is approved.
