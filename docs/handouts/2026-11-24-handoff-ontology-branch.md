# Handoff 2026-11-24: ontology branch, merge pending

Read first: `docs/handouts/2026-11-24-ontology-roadmap.md` (rev 2, the plan).

## State

Branch `worktree-feat-mappings-in-specification` (worktree `.claude/worktrees/feat-mappings-in-specification`),
6 commits ahead of `main`, **NOT merged**. Review (`/code-review`) and `ponytail:ponytail-audit` are done and their
findings fixed (`0042fb9b`). Left to do before merging:

1. **Full test suite.** The first attempt crashed at collection (`tests/test_cli_bids_flags.py` imports
   `app/prism.py`, whose venv guard exits because the venv is `/Users/karl/work/github/prism-studio/.venv`, not inside
   the repo path; same on main, not caused by the branch). Run with the guard off:
   `PRISM_SKIP_VENV_CHECK=1 python3 -m pytest -q -p no:cacheprovider`
   A run was started in the background on 2026-11-24 evening; its result was NOT seen. Run it again.
   Before that, only the touched areas were run: 600 tests green (specification, spec_overlay, terms, mappings export,
   coverage, survey terms, CLI routing, CLI/Studio parity, sync, lock, vendored spec).
2. If green: merge into `main` (the user said "merge it if green"). If anything is red: fix it, say which test.
3. After merging: remove the worktree (`ExitWorktree`), and delete the older untracked roadmap draft in the main
   checkout (`docs/handouts/2026-11-24-ontology-roadmap.md` untracked there) so the merged one is not blocked.

## What the branch adds

- `Specification.mappings` / `mappings_for(id)` (official + the project's own links for that run, official wins; survey
  included) - `src/specification.py`, `src/spec_overlay.py::load_local_mappings`.
- `terms export-links [--project P] [--out F]`: SSSOM table - `src/mappings_export.py`.
- `terms coverage [--modality M] [--project P] [--missing]`: linked / via parent / none - `src/mappings_coverage.py`.
- Survey ID lifecycle, Studio half: `ids/survey-deprecated.json` read by `src/survey_terms.py::deprecated_ids`;
  sync maps it to `official/library/ids/survey-deprecated.json` (NOT in `survey/`, other readers take every `*.json`
  there for a template).
- Docs: `docs/CLI_REFERENCE.md` (both commands).

## Next (from the roadmap)

- **Step 0 (first priority, prism-specification repo):** biometrics = shared terms (`prism:resting-heart-rate`, ...).
  Add the `terms` declaration for `biometrics` in `entities.schema.json`, term files `terms/biometrics/`, tag a patch
  release, then `python scripts/sync_specification.py --tag <tag>` here. Then 0b: design note for physio / eyetracking /
  events. Needs the user's answer on **decision D** (who does the spec-repo work) and **E** (left/right and protocol as
  child terms or a context field).
- **Step 3 data:** with Barbara - which concepts first, then links in the spec repo, review the 63 DASS links.
- **Spec half of step 5:** create `ids/survey-deprecated.json`, `check_library` and `check_mappings` rules (listed in
  the roadmap).
- Open decisions: **A** fingerprint normalisation (recommend Studio's), **B** hash licensing, **C** why 23 survey
  templates ship when the 2026-11-14 decision said DASS only.
- Not done on purpose: SSSOM file not yet checked with an SSSOM tool; no `license` in its header; no Studio button for
  the new commands; `terms resolve` does not yet name the replacement of a deprecated item.

## Rules to remember (CLAUDE.md)

Spec files in `app/schemas`, `official/library/terms|mappings`, `docs/specs` are vendored: change them in
prism-specification, never here. Subagents: Sonnet 5.5 only. One chat per stream; this file is the handoff.
