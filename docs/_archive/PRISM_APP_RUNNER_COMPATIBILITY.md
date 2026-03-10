# PRISM App Runner Compatibility Assessment

Date: 2026-03-03

## Goal

Integrate `MRI-Lab-Graz/bids_apps_runner` as a **derivatives-layer orchestration runner** for PRISM datasets while keeping PRISM core validation unchanged and BIDS-app compatibility intact.

## Compatibility Summary

- **Architecture fit**: Good. `bids_apps_runner` is GUI/CLI orchestration focused and aligns with PRISM core-vs-derivatives boundary.
- **Container support**: Good. Supports Docker and Apptainer/Singularity.
- **HPC support**: Good (SLURM-driven). Requires `sbatch`, `squeue`, `scancel`; DataLad optional depending on workflow.
- **Config model**: Compatible with PRISM derivatives integration via JSON (`common`, `app`, optional `hpc`, optional `datalad`).
- **BIDS compatibility risk**: Manageable if runner output is enforced under `derivatives/` and PRISM custom files remain ignored by BIDS apps as currently implemented.

## Implemented in PRISM Studio

- Added Derivatives page: `PRISM App Runner`.
- Added compatibility API endpoint: `POST /api/prism-app-runner/compatibility`.
- Added backend compatibility module in derivatives layer:
  - Environment/runtime checks (Docker/Apptainer/Singularity, SLURM, DataLad, git)
  - Runner repo file checks (optional path)
  - Config shape checks for runner JSON
  - BIDS derivatives path warning for output targets outside `derivatives/`

## Integration Roadmap

1. **Compatibility phase (completed)**
   - Add PRISM-native UI and API for compatibility checks
   - Validate host tools and config semantics

2. **Execution adapter phase**
   - Add derivatives adapter to invoke runner CLI (`scripts/prism_runner.py`) with controlled arguments
   - Persist execution logs under project-local derivatives logs

3. **HPC profile phase**
   - Add optional PRISM UI controls for HPC profile fields (`partition`, `time`, `mem`, `cpus`, modules/env)
   - Keep job submission semantics aligned with runner architecture

4. **Validation bridge phase**
   - Optional post-run output checks (runner check + PRISM validator summary)
   - Ensure no coupling of orchestration logic into core validator modules

## Solved Issues

- Added a dedicated derivatives integration point instead of introducing orchestration in core validation code.
- Added a PRISM-styled HTML workflow for compatibility checks.
- Added config and runtime checks that explicitly guard BIDS derivatives placement expectations.

## Lessons Learned

- Separating environment/config compatibility checks from execution reduces integration risk.
- A derivatives-first adapter keeps PRISM’s scientific validation responsibilities stable.
- Explicit checks for output path semantics (`derivatives/`) are essential to preserve interoperability with BIDS apps.
