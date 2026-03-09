# PRISM Core vs Derivatives Boundary

## Status

- Proposed for trial on branch `feat/prism-core-derivatives-split`
- Goal: keep PRISM as a BIDS extension validator first, and move orchestration concerns to a separate derivatives layer.

## Why this split

PRISM should answer one primary question with high scientific reliability:

> Is this dataset structurally valid (BIDS + PRISM extensions), and if not, why?

Running pipelines, launching apps, and workflow orchestration are valuable, but they are a different responsibility and should not be coupled to the validator core.

This mirrors the BIDS ecosystem pattern where validation and pipeline execution are separate tools.

## `prism-core` (in-scope)

`prism-core` is the validation engine and compatibility layer.

- Dataset structure validation (BIDS-compatible + PRISM extensions)
- Filename/sidecar/schema checks
- Schema loading/versioning and compatibility safeguards
- `.bidsignore` interoperability support for BIDS apps
- Stable Python API used by CLI and web UI
- Stable machine-readable validation report + deterministic exit codes

Core must not require external orchestration runtimes.

## `prism-derivatives` (in-scope)

`prism-derivatives` consumes `prism-core` outputs and adds workflow execution.

- Pipeline/app launch integration
- Multi-step conversion workflows and post-validation actions
- Execution profile management, runtime adapters, and orchestration UX
- Optional convenience wrappers around core validation + next-step actions

Derivatives may evolve quickly; core must stay conservative and compatibility-focused.

## Contract between Core and Derivatives

Derivatives interact with core through a narrow, stable interface:

1. Input: dataset path + validation options
2. Output: machine-readable report (JSON) + deterministic exit code
3. Optional: structured warnings for BIDS-app compatibility

Minimum exit-code contract:

- `0`: validation passed
- `1`: validation failed (rule or schema violations)
- `2`: execution/configuration error (invalid path, internal/runtime issue)

## Current repository mapping

- Core lives in `src/` and is invoked via `prism.py`
- Web interface (`prism-studio.py`) remains a client of core logic (not a separate validation engine)
- Derivatives work should be added under a clearly separate package area first (for example `src/derivatives/`) and can later be split into a dedicated distribution if needed

## Trial roadmap

### Phase 1: Documentation and boundaries (this trial)

- Declare core/derivatives responsibility split
- Avoid adding new app-launch behavior inside core validation paths
- Keep web UI using the same core entrypoints

### Phase 2: Contract hardening

- Formalize validation report schema
- Add integration tests that assert report stability and exit-code semantics
- Add import-boundary checks that prevent orchestration dependencies in core modules

### Phase 3: Derivatives packaging

- Extract derivatives commands into separate namespace/package surface
- Keep backward-compatible shim commands during migration
- Document deprecation timeline for mixed concerns

## Solved issues (with this proposal)

- Clarifies architecture ownership: validation vs orchestration
- Reduces risk of coupling validator reliability to runtime launcher changes
- Preserves BIDS-first compatibility posture while still enabling higher-level workflows

## Lessons learned

- If validator and orchestration grow in the same layer, reliability and trust boundaries blur quickly
- A narrow interface (report + exit code) makes downstream tooling easier to evolve safely
- Explicit ownership boundaries reduce accidental architecture drift during feature work
