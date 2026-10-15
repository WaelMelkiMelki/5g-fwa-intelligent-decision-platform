# Restored FWA project

Recovered from `FWA_project_COMBINED_DUMP.txt` into the original relative paths. The original archive, builder script, and `main.pdf` were left unchanged.

## Recovery status

- 251 archived files restored: 235 complete and 16 partial.
- All 148 Python files pass syntax compilation without executing project code.
- All 6 JSON files parse successfully.
- File counts, line counts, partial status, and SHA-256 checksums are recorded in `RESTORATION_MANIFEST.json`.
- UTF-8 text and LF line endings are used. Original byte encodings and terminal-newline details cannot be reconstructed exactly.
- Archive separator text and truncation notices were removed from restored source files. Partial files contain only available source lines.

## Project layout

- `app/`: Streamlit dashboard, services, business logic, tests, and documentation.
- Root Python scripts: data preparation, feature engineering, eligibility, segmentation, churn, recommendations, capacity, and campaigns.
- `report_v4/`: LaTeX report sources and figure/presentation generation scripts.
- `scripts/`: churn benchmarking and experiments.
- `correction_backup/`: historical results, corrections, and partial backup data.
- `main.pdf`: original compiled report supplied with the archive.

## What still needs the original environment

The archive contains source code, not a complete runnable environment. It does not include the full PostgreSQL database, real credentials, virtual environment, Git history, or binary assets such as report figures, saved model files, and generated slide decks. CSV excerpts are not full datasets. The SQL database backup is only 100 of 653,007 lines and must not be treated as a complete database restore.

Some scripts retain original Windows paths and redacted connection strings. These were preserved to avoid changing recovered program behavior. Update their configuration before running them. The report sources reference figure directories whose binary images were not archived.

## Dashboard setup after restoring the database

From the project root:

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r app/requirements.txt
cd app
cp .streamlit/secrets.toml.example .streamlit/secrets.toml
# Fill in the database settings in .streamlit/secrets.toml.
python -m streamlit run Home.py
```

The database must contain the expected `cleaned_data` schema and tables. See `app/SCHEMA_MAPPING.md` and the dashboard reports. The recovered dependency file covers the dashboard; analytics and presentation scripts also import additional packages.

After installing dependencies, dashboard tests can be run from the project root with `python -m pytest app/tests -q`. Runtime tests were not run during restoration because required packages and the original database are unavailable. No analytics scripts or SQL files were executed.

## Partial files

| File | Recovered lines | Original lines |
|---|---:|---:|
| `app/sql/verify_schema_mapping.sql` | 100 | 354 |
| `correction_backup/cleaned_data_pre_handset_cpe_correction.sql` | 100 | 653007 |
| `correction_backup/eligible_holdout_probs_20260830.csv` | 30 | 548 |
| `correction_backup/latex_compile_final_20260830.log` | 100 | 1264 |
| `correction_backup/latex_compile_xelatex_20260830.log` | 100 | 1266 |
| `correction_backup/step11_prioritization_20260830_184601.csv` | 30 | 2630 |
| `correction_backup/step12_churn_predictions_20260830_184601.csv` | 30 | 12413 |
| `correction_backup/step12_churn_predictions_NEW_20260830.csv` | 30 | 2630 |
| `correction_backup/step12_fullbase_trial_eligible_probs_20260830.csv` | 30 | 2630 |
| `correction_backup/step12_fullbase_trial_feature_importance_20260830.csv` | 30 | 51 |
| `correction_backup/step15_final_campaign_list_20260830_184601.csv` | 30 | 12413 |
| `correction_backup/step15_rerun_20260830.log` | 100 | 203 |
| `correction_backup/step15_rerun_final_20260830.log` | 100 | 203 |
| `report_v4/main.log` | 100 | 1421 |
| `step11_prioritization_output.csv` | 30 | 2630 |
| `step9_fwa_suitability_scores.csv` | 30 | 12413 |
