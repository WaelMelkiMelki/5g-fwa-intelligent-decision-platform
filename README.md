# 5G FWA Intelligent Decision & Agentic AI Platform

This repository is a public, reproducible portfolio version of a 5G Fixed Wireless Access decision-support project.

## Publication status

The public repository contains a reviewed baseline, while the reconstructed end-to-end platform is still under development. Before adding new material:

- remove credentials and connection strings from legacy scripts;
- remove confidential Huawei-specific material and identifiers;
- separate historical internship results from newly reconstructed experiments;
- regenerate results from legally reusable or synthetic data;
- review the staged files for secrets and personal or proprietary information.

The original datasets are unavailable. Reconstructed experiments must not claim to reproduce the original Huawei results.

## Documentation

Start with the [documentation index](docs/README.md). The [project journey](docs/PROJECT_JOURNEY.md) records completed work and validation evidence, the [data contract](docs/DATA_CONTRACT.md) defines the public reconstruction rules, the [decision log](docs/DECISION_LOG.md) records architectural choices, and the [technology stack](docs/TECHNOLOGY_STACK.md) explains the adopted tools.

## Current contents

- `app/`: read-only Streamlit decision-support dashboard;
- root Python scripts: original batch analytics pipeline and validation utilities;
- `step*_*.csv`: derived validation/output artifacts, not source datasets.

The original report, combined dumps, internship material, and backup artifacts are intentionally excluded from the public repository until they have been reviewed for confidentiality.

## Planned public architecture

The public version will use seeded synthetic data, validated data contracts, local analytical storage, reproducible ML training, FastAPI services, the dashboard, and a read-only grounded agent. Local execution will remain the primary deployment target.

## Development

The dashboard currently expects a PostgreSQL database configured through `FWA_DB_*` environment variables or `app/.streamlit/secrets.toml`. Do not commit either configuration or any real credentials.

The reconstructed public pipeline is being added incrementally after each documented data-contract milestone.

## Synthetic data generator

The first reproducible data slice is available in `data_generation/`. It creates linked CRM, monthly usage, address coverage, service-consumption, and cell-KPI tables without requiring PostgreSQL.

After installing the development dependencies, run the focused tests with:

```bash
python -m pip install -r requirements-dev.txt
python -m pytest tests/test_synthetic_data.py -q
```

The generator uses a configurable random seed and can inject duplicate and missing-value anomalies for data-quality testing.

To create a local Parquet dataset and manifest:

```bash
python scripts/generate_synthetic_data.py --output-dir data/processed --subscribers 12412 --cells 731 --seed 42
```

Generated files are local artifacts and are excluded from Git.

To build the subscriber-month ABT from those files:

```bash
python scripts/build_abt.py --source-dir data/processed --output-dir data/processed
```

This writes `abt_subscriber_month.parquet` and `abt_manifest.json` locally.

To run the source and ABT quality checks:

```bash
python scripts/run_quality_checks.py --source-dir data/processed --abt-path data/processed/abt_subscriber_month.parquet
```

The report is written to `data/processed/quality_report.json` and is ignored as a generated local artifact.

To score FWA eligibility and suitability:

```bash
python scripts/score_eligibility.py --abt-path data/processed/abt_subscriber_month.parquet --output-dir data/processed
```

This writes `fwa_eligibility.parquet` and `eligibility_manifest.json` locally.

To fit mixed-type customer segments on eligible subscribers:

```bash
python scripts/fit_segmentation.py --abt-path data/processed/abt_subscriber_month.parquet --eligibility-path data/processed/fwa_eligibility.parquet --output-dir data/processed --clusters 4 --seed 42
```

This writes `subscriber_segments.parquet`, `segment_profiles.parquet`, and `segmentation_manifest.json` locally.

To train the CPU-native churn baseline:

```bash
python scripts/train_churn.py --abt-path data/processed/abt_subscriber_month.parquet --output-dir data/processed --seed 42
```

This writes `churn_predictions.parquet` and `churn_metrics.json` locally.

## Local DuckDB exploration

The pipeline uses the **Python `duckdb` package** inside `.venv`. The **standalone
DuckDB CLI** is a separate executable providing the `duckdb` command and `-ui`.
Installing the Python package alone does not provide that command. The verified
local workflow uses version **1.5.6** for both, without changing pipeline code.

### Install the CLI locally

For Linux x86_64 (the validated environment), download the pinned official release
and verify its SHA-256 before installing. Run these commands in Bash; no `sudo`
or shell-profile changes are needed. They refuse to overwrite an existing CLI.

```bash
(
  set -euo pipefail
  archive_dir=$(mktemp -d)
  trap 'rm -rf "$archive_dir"' EXIT
  curl --fail --location --proto '=https' --proto-redir '=https' \
    https://github.com/duckdb/duckdb/releases/download/v1.5.6/duckdb_cli-linux-amd64.gz \
    -o "$archive_dir/duckdb.gz"
  (cd "$archive_dir" && echo 'cce2687a38681db644c248198b99ecd86170ff47e324c5f33e50c0042f142839  duckdb.gz' | sha256sum -c -)
  gzip -dc "$archive_dir/duckdb.gz" > "$archive_dir/duckdb"
  cli_dir="$HOME/.duckdb/cli/1.5.6"
  if [[ -e "$cli_dir/duckdb" || -L "$cli_dir/duckdb" ]]; then
    echo "Already exists: $cli_dir/duckdb; inspect it before replacing." >&2
    exit 1
  fi
  mkdir -p "$cli_dir"
  install -m 755 "$archive_dir/duckdb" "$cli_dir/duckdb"
  "$cli_dir/duckdb" --version
)
```

For other platforms, use the [official user-local installer](https://duckdb.org/docs/stable/operations_manual/installing_duckdb/install_script)
with `DUCKDB_VERSION=1.5.6`; download and inspect the installer before running it.
The [official release](https://github.com/duckdb/duckdb/releases/tag/v1.5.6) lists
platform-specific binaries and checksums. Keep downloads outside the repository.

The launcher finds a CLI on `PATH`, then checks `~/.duckdb/cli/1.5.6/duckdb`,
`~/.local/bin/duckdb`, and `~/.duckdb/cli/latest/duckdb`. To use `duckdb` directly
in the current shell, run:

```bash
export PATH="$HOME/.duckdb/cli/1.5.6:$PATH"
duckdb --version
```

### Launch and query

With the generated ABT present, run from the repository root:

```bash
./scripts/open_duckdb_ui.sh
```

The script also works by absolute path from another directory, including paths
containing spaces. Use `DUCKDB_CLI=/absolute/path/to/duckdb` to select an executable.
It opens the browser at `http://localhost:4213`, creates an in-memory catalog,
and exposes each `data/processed/*.parquet` file as a view named after the file:
`abt_subscriber_month`, `cell_kpis`, `coverage_addresses`, `crm_subscribers`,
`service_consumption`, and `usage_monthly` for the current generated dataset.
It reads existing files without rebuilding the ABT or copying data into a database.

Keep the terminal running. Enter `.quit` there to stop the UI. If automatic browser
opening is unavailable, run `./scripts/open_duckdb_ui.sh --no-browser` and open
the URL manually. If port 4213 is occupied, use
`ui_local_port=4214 ./scripts/open_duckdb_ui.sh` and open `http://localhost:4214`.
Restart the launcher after adding files or changing their schema.

In a UI notebook, run SQL such as:

```sql
SELECT count(*) FROM abt_subscriber_month;
DESCRIBE abt_subscriber_month;
SELECT count(*) FROM read_parquet('data/processed/cell_kpis.parquet');
```

[Example queries](docs/example_queries.sql) cover counts, columns, duplicate/null
subscriber-month keys, PRB utilisation, and radio feasibility. They distinguish
subscriber-weighted PRB summaries from equal-weight serving-cell summaries.
Run the complete examples without the UI (also works offline after CLI installation):

```bash
duckdb -init /dev/null -bail :memory: < docs/example_queries.sql
.venv/bin/python -m pytest tests -q
```

### Local execution and limitations

No account, paid service, PostgreSQL, or cloud upload is required. Queries over
these files execute locally. The [DuckDB UI](https://duckdb.org/docs/stable/extensions/ui)
downloads its signed extension on first use and fetches frontend assets from
`https://ui.duckdb.org`; the graphical workflow therefore requires internet access.
The launcher uses the official HTTPS extension repository and does not enable
unsigned extensions or connect to MotherDuck.

The launcher skips `~/.duckdbrc` for a predictable session. Its catalog is temporary;
save reusable SQL in source files. DuckDB stores UI notebook state and extension
files under the user's `~/.duckdb` directory. The UI is an interactive SQL tool,
not a restricted read-only application: avoid write/export statements over source
files. Generated data, local databases, history, and binaries must stay out of Git.
`data/processed/` remains ignored. See [validation evidence](docs/DUCKDB_VALIDATION.md)
for commands, observed results, and remaining limits.
