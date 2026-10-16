# Technology Stack

## 1. Adoption principle

The platform adopts technologies that are useful in production and visible in current engineering roles, but introduces them when they solve a real problem. A tool is not added only to make the stack look impressive.

The local-first design keeps the project fully usable without paid cloud services or hosted APIs.

## 2. Adopted stack

| Area | Technology | Adoption stage | Role |
|---|---|---|---|
| Language | Python 3.11 | Current | Data processing, rules, ML, services |
| Query language | SQL | Current/next | Relational transformations and analysis |
| File format | Parquet | Current | Versionable local data exchange |
| Local analytics | DuckDB Python + standalone CLI/UI | Current | ABT SQL transformations and graphical exploration of local Parquet |
| DataFrames | Pandas | Current | Existing transformations and model-compatible tables |
| Numeric computing | NumPy | Current | Vectorized calculations and simulation logic |
| Database | PostgreSQL | Next platform stage | Production-style relational persistence |
| Transformations | dbt Core | Next platform stage | Tested SQL models, documentation, and lineage |
| Orchestration | Airflow | Later | Scheduled, retryable pipeline execution |
| Validation | Pytest + explicit quality contracts | Current | Automated tests and data-quality gates |
| ML | scikit-learn HistGradientBoosting; XGBoost optional | Current | CPU-native churn baseline; later model comparison |
| Experiment tracking | MLflow | Later | Runs, metrics, artifacts, and model versions |
| API | FastAPI | Later | Decision and inference endpoints |
| Dashboard | Streamlit | Existing | Interactive decision-support interface |
| Containers | Docker Compose | Later | Reproducible local services |
| Monitoring | Prometheus and Grafana | Later | API, pipeline, and model observability |
| Local LLM | Ollama | Later | No-cost local language-model runtime |
| Agent workflow | LangGraph or equivalent | Later | Controlled, stateful agent tool orchestration |

## 3. Current implementation boundary

The current public pipeline uses:

- Python;
- Pandas and NumPy;
- Parquet and PyArrow;
- Pytest;
- DuckDB SQL for the ABT transformation;
- DuckDB standalone CLI and local browser UI for Parquet exploration;
- JSON manifests;
- GitHub for version control and documentation.

DuckDB is implemented for transformation and local exploration. PostgreSQL and dbt will be introduced after the public transformations are stable, so the same data contract can be tested in both local-file and database execution modes.

### DuckDB Python versus CLI/UI

The `.venv` Python package provides `import duckdb` to the existing ABT builder.
It does not install the standalone `duckdb` executable. The separate CLI provides
the SQL shell and `-ui` browser interface. Both were validated at version 1.5.6;
installing the CLI does not change the Python environment or public pipeline API.

Follow the [user-local setup in the README](../README.md#local-duckdb-exploration).
The pinned CLI lives at `~/.duckdb/cli/1.5.6/duckdb`, outside Git, with no system
package changes. Run `./scripts/open_duckdb_ui.sh` from the repository root, or use
its absolute path. The launcher checks the CLI and ABT, then exposes generated
Parquet as views in an in-memory catalog. `--no-browser` starts the same UI server
for manual access at `http://localhost:4213`. Keep the CLI running while browsing.

Use `SELECT count(*) FROM abt_subscriber_month` or query a file directly with
`SELECT count(*) FROM read_parquet('data/processed/abt_subscriber_month.parquet')`.
The [example SQL](example_queries.sql) also checks grain uniqueness, PRB utilisation,
and radio feasibility using the generated schema. Execute it from the repository
root with `duckdb -init /dev/null -bail :memory: < docs/example_queries.sql` after
adding the CLI directory to `PATH`.

Queries and data stay local by default; no account or paid service is needed.
The [UI extension](https://duckdb.org/docs/stable/extensions/ui) is downloaded and
cached under `~/.duckdb`, and UI assets are fetched from `https://ui.duckdb.org`.
Thus local-first does not mean a fully offline graphical interface; the standalone
SQL shell works offline on these Parquet files after installation. The launcher
does not attach MotherDuck or alter the ABT. Generated data remains ignored under
`data/processed/`; UI state and binaries are user-local artifacts, not source code.

## 4. Why Spark is not current

Spark remains a valuable market technology, but the current dataset has 12,412 subscribers and 731 cells. It fits comfortably in local processing. Adding Spark now would increase setup and operational complexity without improving the engineering result.

Spark becomes justified only if a later workload requires distributed processing, such as multi-year event-level network records at hundreds of gigabytes or more.

## 5. Zero-budget and security policy

- PostgreSQL, DuckDB, Airflow, MLflow, Prometheus, Grafana, Ollama, and the agent runtime are local-first options.
- Hosted LLMs and cloud services are optional and cannot be required for the demo.
- No billing-enabled cloud resource may be created without explicit approval.
- Credentials remain in environment variables or ignored local secrets files.
- The agent will use allowlisted read-only tools rather than unrestricted SQL.

## 6. Adoption order

1. Python, Parquet, Pandas, NumPy, Pytest: implemented.
2. DuckDB: ABT SQL transformation and local CLI/UI exploration implemented.
3. PostgreSQL and dbt Core: relational serving and documented transformations.
4. Eligibility, capacity, segmentation, and churn modules.
5. MLflow and FastAPI: reproducible model lifecycle and APIs.
6. Docker Compose: one-command local platform startup.
7. Prometheus/Grafana: operational observability.
8. Ollama and a controlled agent: grounded natural-language decision support.
9. Airflow: scheduled production-style orchestration after pipeline stages are stable.
