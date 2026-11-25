# Handoff 2026-11-24: ontology branch (merged 2026-11-25)

Read first: `docs/handouts/2026-11-24-ontology-roadmap.md` (rev 2, the plan).

## State

Merged into `main` on 2026-11-25, together with fixes for 11 tests that already failed on `main`. Next: roadmap step 0
(biometrics shared terms) in prism-specification; decisions D and E are made (see the roadmap). Full suite in a
worktree: `PRISM_SKIP_VENV_CHECK=1`, and the e2e accessibility tests need the repo's `node_modules`.

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

- **Step 0 (first priority, prism-specification repo):** biometrics shared terms, tag a patch release, sync here.
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
