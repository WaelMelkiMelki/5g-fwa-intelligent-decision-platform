# Project Documentation

This directory is the canonical documentation entry point for the public portfolio repository.

## Documents

- [Project journey](PROJECT_JOURNEY.md): objectives, phases, completed work, evidence, and open risks.
- [Data contract](DATA_CONTRACT.md): synthetic source tables, grains, keys, relationships, and validation rules.
- [Decision log](DECISION_LOG.md): important technical and publication decisions with their rationale.
- [Technology stack](TECHNOLOGY_STACK.md): adopted technologies, stages, roles, and rationale.

## Documentation rule

Every implementation milestone must update the relevant documentation before the next milestone begins. Each update must state:

1. objective and scope;
2. files added or changed;
3. technique and processing flow;
4. technical decisions and assumptions;
5. validation commands and observed results;
6. failure modes and data-quality controls;
7. known limitations and the next step.

Documentation must explain how the system works, not only report final numbers. For every transformation or model, describe the inputs, grain, keys, algorithm or SQL logic, feature derivation, parameter choices, leakage controls, validation method, and interpretation limits.

Historical Huawei results and reconstructed public experiments must always be labelled separately.
