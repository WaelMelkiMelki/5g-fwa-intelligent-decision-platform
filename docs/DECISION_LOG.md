# Decision Log

## D-001: Use synthetic data as the public primary source

**Decision:** Build the public pipeline around seeded synthetic data.

**Reason:** The original datasets are unavailable and may contain confidential operator/customer information. Generic public churn data cannot represent the required subscriber, address, cell, coverage, service, and PRB relationships without distortion.

**Consequence:** Reconstructed metrics are new experiments and must be labelled separately from historical internship results.

## D-002: Keep the original batch logic as a reference during reconstruction

**Decision:** Preserve the legacy scripts for auditability, but do not make the new public pipeline depend on the unavailable PostgreSQL snapshot.

**Reason:** The original scripts document the business rules and feature semantics that the reconstructed implementation should preserve where technically justified.

**Consequence:** The legacy scripts remain a reference surface and require database credentials/configuration to run. The public path will progressively replace direct database assumptions with local contracts.

## D-003: Use local-first dependencies

**Decision:** Prefer Python, pandas, NumPy, Parquet/local analytical storage, PostgreSQL only when useful for production-style integration, and local models/services.

**Reason:** The project must remain usable with zero budget and without a payment card or hosted API.

**Consequence:** Cloud services and hosted LLMs are optional demonstrations, never hard dependencies.

## D-004: Treat database access as read-only in the dashboard

**Decision:** Retain the dashboard's SELECT-only query guard, read-only session setting, parameter binding, row cap, and masked identifiers.

**Reason:** The dashboard is a decision-support surface and must not mutate source data or expose subscriber identifiers.

**Consequence:** Write operations belong in controlled pipeline jobs, not interactive dashboard services.

## D-005: Document before advancing

**Decision:** No milestone is considered complete until its objective, files, assumptions, validation evidence, limitations, and next step are recorded.

**Reason:** This project is both an engineering portfolio and a learning artifact. Reproducibility and interview-defensible reasoning require an evidence trail.

**Consequence:** Documentation updates are part of the implementation definition of done.

## D-006: Keep historical and reconstructed results separate

**Decision:** Never overwrite historical claims with generated values or tune generated data to match historical metrics.

**Reason:** Matching historical values without the original data would create unsupported claims and potential leakage.

**Consequence:** Reports and dashboards must label the data source, seed/configuration, run date, and result status.
