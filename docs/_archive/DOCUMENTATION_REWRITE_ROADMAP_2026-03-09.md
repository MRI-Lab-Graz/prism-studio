# Documentation Rewrite Roadmap (2026-03-09)

## Why This Exists

The current documentation is outdated, fragmented, and too long at the repository entry point.
This roadmap defines a two-layer documentation strategy:

1. A short, straight-forward README for first-time users.
2. Detailed docs for real project work, with frontend-first explanations plus full terminal commands.

PRISM principle remains unchanged: PRISM is an add-on to BIDS, not a replacement.

---

## Scope

### In scope

- Complete rewrite of `README.md`.
- Reorganization of `docs/` around user workflows.
- Frontend-first documentation structure (PRISM Studio as main narrative).
- Full terminal command coverage for CLI users.
- Heroshot-driven visual walkthroughs in relevant pages.

### Out of scope

- Changing validation business logic.
- Schema redesign.
- New product features that are not required for documentation clarity.

---

## Target Information Architecture

### Layer 1: Repository README (short)

Keep only:

- What is PRISM (2-4 short paragraphs).
- Core features (short list).
- Installation (one-time setup, macOS/Linux + Windows).
- How to run (Studio + CLI minimal examples).
- Link to docs for everything else.

Must not include:

- Deep architecture details.
- Long command catalogs.
- Internal implementation notes.
- Repeated content already in docs.

### Layer 2: Detailed docs (`docs/`)

Primary navigation should be:

1. Frontend workflows (Studio)
2. Terminal workflows (CLI)
3. Reference and advanced topics

Proposed top-level sections:

- `Getting Started`
- `Studio Workflows (Frontend First)`
- `CLI Workflows`
- `Reference`
- `Advanced / Integration`
- `Developer and Release Docs`

---

## Phased Plan

## Phase 0 - Audit and Freeze (0.5-1 day)

### Tasks

- Inventory all current docs and assign each file: keep, merge, rewrite, archive.
- Identify duplicate/conflicting instructions.
- Freeze README edits in parallel branches during rewrite window.

### Deliverables

- Doc inventory table with owner and decision.
- Canonical command source list (single truth for each command).

### Exit criteria

- No undocumented overlap remains unassigned.

## Phase 1 - Rewrite README (1 day)

### Tasks

- Replace current README with a concise version focused on onboarding.
- Keep only basics: identity, features, install, run, links.
- Add explicit link to detailed docs index and quick start page.

### Deliverables

- New `README.md` under target length (recommended: 120-220 lines max).

### Exit criteria

- A new user can install and run Studio or CLI without opening additional files except linked docs.
- README has no low-level technical deep dive.

## Phase 2 - Frontend-First Detailed Docs (2-3 days)

### Tasks

- Rebuild the docs narrative around PRISM Studio workflows:
	- Create/open project
	- Convert/import data
	- Validate
	- Fix issues
	- Export/report
- For each workflow page, include:
	- Goal
	- UI path
	- Required inputs
	- Expected outputs
	- Common failures
- Add Heroshot image blocks at each major step.

### Deliverables

- Updated `docs/index.rst` to reflect new navigation order.
- New or rewritten Studio workflow pages.
- Heroshot asset map (screenshot filename -> doc section).

### Exit criteria

- Frontend users can complete standard validation workflow from docs only.
- Every major Studio page includes at least one current screenshot.

## Phase 3 - CLI and Terminal Coverage (1-2 days)

### Tasks

- Create command-driven docs section for terminal users.
- Provide copy-paste command blocks for:
	- Setup
	- Run Studio
	- Run validator
	- Use `prism_tools.py`
	- Run tests and quality checks
- Add OS notes where behavior differs (macOS/Linux vs Windows).
- Ensure all commands are verified against current repo scripts.

### Deliverables

- `CLI Workflows` doc section with validated command examples.
- Quick command cheat sheet page.

### Exit criteria

- A terminal user can execute end-to-end validation and conversion flows from docs without guessing flags.

## Phase 4 - Consolidation and Cleanup (1 day)

### Tasks

- Remove duplicated text across README and docs.
- Archive stale pages into `docs/_archive/` with clear labels.
- Standardize terminology (`survey`, `biometrics`, `PRISM Studio`, `BIDS compatibility`).
- Link-check and command-check pass.

### Deliverables

- Clean docs tree with reduced duplication.
- Redirect notes in archived files pointing to new canonical pages.

### Exit criteria

- No obvious contradictory instructions between README, Studio docs, and CLI docs.

---

## Heroshot Plan

Use heroshots as first-class assets in workflow docs.

### Rules

- One screenshot per major action step.
- Use consistent naming: `heroshot-<page>-<step>.png`.
- Keep screenshots current with UI labels and tab names.
- Prefer cropped, task-focused captures over full-screen dumps.

### Minimum heroshot coverage

- Home and project selection
- Converter flow
- Validator results with issue details
- Tools dropdown key views
- JSON/template editing where critical

---

## Command Coverage Matrix (Must Be Documented)

- Environment setup (`setup.sh`, `setup.ps1`)
- Launch Studio (`python prism-studio.py`)
- Run CLI validation (`python prism.py /path/to/dataset`)
- Run conversion tools (`python prism_tools.py ...`)
- Test suite (`pytest`)
- Formatting/linting (`black .`, `flake8 .`)

Each command needs:

- Purpose (one line)
- Example invocation
- Expected output or artifact
- Common error and fix

---

## Ownership and Tracking

## Status board

- [x] README rewritten and merged
- [x] Docs navigation rebuilt (frontend-first)
- [x] CLI workflows completed
- [ ] Heroshot coverage added
- [ ] Duplicate/stale pages archived
- [ ] Final docs QA pass complete

## Solved issues log

- Replaced oversized README with a concise onboarding version (what PRISM is, features, install, quick usage, docs links).
- Added an `Examples` section in ReadTheDocs and placed `WORKSHOP` there as the walk-through entry.
- Added `docs/CLI_WORKFLOWS.md` with command-driven setup, validation, conversion, scoring, test, and lint flows.
- Rewrote `docs/STUDIO_OVERVIEW.md` into a frontend-first workflow guide with heroshot references.
- Updated key onboarding docs (`INSTALLATION.md`, `QUICK_START.md`, `WINDOWS_SETUP.md`) to remove stale hardcoded old-repository links.
- Ran local Sphinx builds after each rewrite batch; build is successful and the introduced cross-reference warning was fixed.

## Lessons learned

- Keep this section updated during execution.
- Record only actionable lessons (what failed, what changed, what standard is now adopted).
- Full-file replacement is safer than partial patching when shrinking very large markdown files.
- Avoid terminal heredoc for long markdown rewrites in this repo context; file tool edits are more reliable.
- Keep roadmap and operational/private docs out of primary toctree to avoid exposing internal maintenance pages to end users.

---

## Definition of Done

- README is short, accurate, and onboarding-focused.
- Detailed docs are complete for both Studio and terminal workflows.
- Heroshots are integrated and current.
- Commands are tested and copy-paste safe.
- PRISM/BIDS positioning is consistent everywhere: extension, not replacement.

