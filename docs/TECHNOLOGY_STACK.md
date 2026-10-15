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
| Local analytics | DuckDB | Current | SQL analytics directly over Parquet and registered DataFrames |
| DataFrames | Pandas | Current | Existing transformations and model-compatible tables |
| Numeric computing | NumPy | Current | Vectorized calculations and simulation logic |
| Database | PostgreSQL | Next platform stage | Production-style relational persistence |
| Transformations | dbt Core | Next platform stage | Tested SQL models, documentation, and lineage |
| Orchestration | Airflow | Later | Scheduled, retryable pipeline execution |
| Validation | Pytest + explicit quality contracts | Current | Automated tests and data-quality gates |
| ML | scikit-learn and XGBoost | Later | Segmentation and churn modelling |
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
- JSON manifests;
- GitHub for version control and documentation.

DuckDB is the next local analytics addition. PostgreSQL and dbt will be introduced after the public transformations are stable, so the same data contract can be tested in both local-file and database execution modes.

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
2. DuckDB: local SQL analytics over generated data.
3. PostgreSQL and dbt Core: relational serving and documented transformations.
4. Eligibility, capacity, segmentation, and churn modules.
5. MLflow and FastAPI: reproducible model lifecycle and APIs.
6. Docker Compose: one-command local platform startup.
7. Prometheus/Grafana: operational observability.
8. Ollama and a controlled agent: grounded natural-language decision support.
9. Airflow: scheduled production-style orchestration after pipeline stages are stable.
