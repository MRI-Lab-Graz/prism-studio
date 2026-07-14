---
orphan: true
---

# Documentation Rewrite Roadmap (2026-07-14)

## Why This Exists

Two prior rewrite passes (`_archive/DOCUMENTATION_REWRITE_ROADMAP_2026-03-09.md` and
`_archive/READTHEDOCS_AUDIT_2026-04-14.md`) already diagnosed drift and fixed pieces
of it, but the product has kept moving faster than the docs. `docs/` currently holds
**59 files at the top level** plus `_archive/` (50 files) and `specs/` (4 files), most
written at different times against different app states. Nobody can tell which of the
59 are current, which are half-superseded, and which are pure historical noise without
opening each one.

This roadmap starts over: a small, deliberately-scoped IA matching what was asked for,
a page-by-page audit of what to keep/merge/kill, and a fresh screenshot pass. It
supersedes the two prior roadmaps above (leave them in `_archive/` for history; do not
delete them).

## Target Information Architecture

Five top-level sections, in this order, nothing else:

1. **Installation** — one page. Prebuilt app first, source install second, CLI-only
   third. Windows notes inline, not a separate page per platform.
2. **Quick Start** — one page. Zero to "first validated dataset" in the shortest
   correct path, Studio-first.
3. **Studio Guide** — one page per app page/screen, in the order a user encounters
   them. This is the "explain every page in detail" section.
4. **CLI** — one reference page (`prism.py`, `prism_tools.py`, `prism-studio.py`) plus
   one workflows/cookbook page.
5. **Tutorial** — one hands-on walkthrough using the existing workshop demo data
   (`docs/_archive/workshop`, exercise screenshots already in `_static/screenshots`
   suggest a workshop already exists — audit and fold it in rather than rewriting from
   scratch).

Everything else currently in `docs/` (schema specs, LimeSurvey integration, DataLad,
FAIR policy, release process, Windows build/test docs, assessments) either becomes a
cross-linked appendix under one of the five sections or gets archived/deleted — it does
not get its own top-level toctree entry. Keeping the nav to five entries is the point;
resist the urge to grow a sixth "Reference" bucket, which is exactly how the current
59-file sprawl happened.

## Section 3 detail: "Studio Guide" page inventory

Mapped from `app/templates/*.html` (21 distinct screens, excluding `base.html` /
`index.html` shells). Proposed one-page-per-screen, grouped as sub-sections so the
toctree doesn't read as 21 flat siblings:

| Screen group | Templates | New doc page |
|---|---|---|
| Home | `home.html` | `studio/home.md` |
| Projects | `projects.html` | `studio/projects.md` |
| File Management | `file_management.html` | `studio/file_management.md` |
| Converter (hub) | `converter.html` | `studio/converter.md` |
| Converter tabs | `converter_survey.html`, `converter_participants.html`, `converter_biometrics.html`, `converter_environment.html`, `converter_eyetracking.html`, `converter_physio.html` | `studio/converter_survey.md`, `studio/converter_participants.md`, `studio/converter_biometrics.md`, `studio/converter_environment.md`, `studio/converter_eyetracking.md`, `studio/converter_physio.md` |
| Validator | `results.html` | `studio/validator.md` |
| JSON Editor | `json_editor.html` | `studio/json_editor.md` |
| Survey Library | `library.html`, `library_editor.html` | `studio/survey_library.md` |
| Template Editor | `template_editor.html` | `studio/template_editor.md` |
| Survey Customizer | `survey_customizer.html` | `studio/survey_customizer.md` |
| Survey Generator | `survey_generator.html` | `studio/survey_generator.md` |
| Recipe Builder | `recipe_builder.html`, `recipes.html` | `studio/recipe_builder.md` |
| Share / Export | `share.html` | `studio/export.md` |
| Specifications viewer | `specifications.html` | `studio/specifications.md` |
| PRISM App Runner | `prism_app_runner.html` | `studio/app_runner.md` |

Each page: goal, UI path/screenshot, required inputs, step-by-step, expected output,
common failures — same template the 2026-03-09 roadmap already specified for workflow
pages (keep that convention, it's good).

## Current docs/ inventory: keep / merge / archive / delete

### Keep, rewrite in place (maps directly to new IA)

- `INSTALLATION.md` → Section 1 (rewrite: CLI names drifted per 2026-04-14 audit)
- `QUICK_START.md` → Section 2 (rewrite)
- `CLI_REFERENCE.md`, `CLI_WORKFLOWS.md` → Section 4 (verify commands against current `prism.py`/`prism_tools.py` argparse output)
- `WORKSHOP.md` + `_archive/workshop/SCREENSHOTS_QUICK_START.md` → Section 5 tutorial base (the exercise screenshots already in `_static/screenshots` — exercise-0 through exercise-5 — line up with a demo-data walkthrough; confirm this is still the intended demo dataset)

### Merge into the Studio Guide page for their screen, then delete the standalone file

- `PROJECTS.md` → `studio/projects.md`
- `CONVERTER.md`, `SURVEY_IMPORT.md` → `studio/converter*.md`
- `PARTICIPANTS_MAPPING.md` → `studio/converter_participants.md`
- `VALIDATOR.md` → `studio/validator.md`
- `TEMPLATE_EDITOR.md`, `TEMPLATES.md` (non-LimeSurvey parts) → `studio/template_editor.md`
- `RECIPE_BUILDER.md` (workflow parts) → `studio/recipe_builder.md`
- `ANALYSIS_OUTPUT.md`, `ANC_EXPORT.md` → `studio/export.md`
- `WEB_INTERFACE.md`, `STUDIO_OVERVIEW.md`, `TOOLS.md` → dissolve; content redistributed across `studio/*.md` pages, then delete these three umbrella files (this is the "under-explain by hiding behind umbrella pages" problem the 2026-04-14 audit already flagged twice). `TOOLS.md`'s entire premise — a unified "Tools" menu — turned out not to exist at all; real nav is three stage-based dropdowns (Prepare Data / Modify in PRISM / Export Derivatives), confirmed 2026-07-14.

**Correction (2026-07-14):** `SURVEY_LIBRARY.md` was not merged into the Studio Guide.
A follow-up audit found the `/library` route it documents (checkout → edit →
"Submit" a draft into `merge_requests/`) has no receiving end — nothing in the app
ever reads that folder — and is unreachable from any nav link. Removed outright
(route, blueprint, `SurveyManager` class, templates, JS, tests, doc — 7 files) rather
than migrated. The Template Editor's read-only global-template-picker-with-fork-to-
project model, documented in `studio/template_editor.md`, is the real, actively-used
equivalent and needs no separate page.

### Keep as linked reference (not top-level nav), under an "Appendix" or cross-link from the relevant Studio page

- `RECIPES.md` (engine/spec, keep as reference from `studio/recipe_builder.md`)
- `specs/survey.md`, `specs/biometrics.md`, `specs/events.md`, `specs/environment.md`
- `SPECIFICATIONS.md`, `SCHEMA_VERSIONING.md`, `ERROR_CODES.md`, `QUICK_REFERENCE_BIDS.md`
- `TEMPLATE_VALIDATION.md`
- `WHAT_IS_PRISM.md`, `PROJECT_OVERVIEW.md` (short "concepts" primer, link from Quick Start intro rather than a full top-level section)
- `SURVEY_VERSION_PLAN.md` (cross-link from `studio/template_editor.md` / `studio/survey_library.md`)
- `DATALAD.md`, `FAIR_POLICY.md`
- `LIMESURVEY_INTEGRATION.md`, `LIMESURVEY_VERSION_DIFFERENCES.md` (leave untouched, per explicit prior scope exclusion — cross-link only from `studio/converter_survey.md`)
- `PAVLOVIA_EXPORT.md`

### Delete (developer/release process, not end-user docs — decided 2026-07-14: delete outright, not archive)

- `CHANGELOG.md`, `RELEASE_GUIDE.md`, `RELEASE_NOTES_TEMPLATE.md`, `RELEASE_NOTES_v1.14.0.md` through `v1.16.0.md`
- `GITHUB_SIGNING.md`
- `WINDOWS_BUILD.md`, `WINDOWS_SETUP.md`, `WINDOWS_TESTING.md`, `WINDOWS_TEST_QUICKREF.md`, `WINDOWS_TEST_SUMMARY.md`, `WINDOWS_VM_BUILD_TESTING.md`, `COMPLETE_WINDOWS_SUMMARY.md` (six overlapping Windows files — collapse to at most one archived internal runbook, the rest are redundant snapshots)
- `BIDS_AUTO_MAPPING_COMPLETE.md`, `BIDS_COMPLIANCE_IMPLEMENTATION.md` (implementation-history, not user docs)
- `EYETRACKING_TSV_NORMALIZATION.md` (verify still accurate; if kept, moves to a `studio/converter_eyetracking.md` cross-link, not archive)
- `ASSESSMENT.md`, `ROADMAP_HISTORY_2026.md`

**Correction (2026-07-14, caught during Phase 1 execution):** `SURVEY_VERSION_PLAN.md`
was originally listed here by mistake. It is real reference content (explains
`Study.Versions`/`Study.Version`/`acq-<version>` variant selection) actively linked
from `SCHEMA_VERSIONING.md` and `SURVEY_LIBRARY.md`, not planning noise. Moved to the
"keep as linked reference" bucket below instead; a first Sphinx build after the Phase 1
deletions caught the two dangling cross-references and it was restored via
`git restore`.

### Already archived correctly — leave as-is

Everything already under `docs/_archive/` (50 files). No action needed beyond
confirming nothing in the "keep" list above still secretly links to an archived page as
if it were live.

### Housekeeping

- `docs/.DS_Store` — delete, add `.DS_Store` to `.gitignore` if not already there
- `docs/DEEPL_TRANSLATION_COMMANDS.txt` — determine owner/purpose; archive or delete
- `docs/pavlovia/survey.json`, `docs/examples/*.xlsx` — keep only if actively linked from a kept page; otherwise move under the tutorial/demo-data folder for Section 5

## Screenshot Plan

Current `_static/screenshots` (30 PNGs) already covers Home, Projects, Converter,
File Management, Recipes, Specifications, Survey Library, Workshop exercises 0-5, in
light and dark variants — that's a solid base, not a rebuild from zero. Gaps against
the full 21-screen Studio Guide inventory above: **Validator/results, JSON Editor,
Template Editor, Survey Customizer, Survey Generator, Share/Export, PRISM App Runner,
and the individual converter tabs (participants/biometrics/environment/eyetracking/
physio)** have no current screenshot.

Rules (carried over from the 2026-03-09 roadmap, they were correct):
- One screenshot per major action step, light + dark.
- Naming: `prism-studio-<page>-<step>-<light|dark>.png` (matches current convention).
- Recapture anything referenced in a page being rewritten, even if a screenshot already
  exists — the point of this pass is "no doc ships an image of a UI that no longer
  looks like that."

## Phased Plan

### Phase 0 — Audit sign-off (this document)

Confirm the IA and the keep/merge/archive/delete table above before touching files.
Open questions below need answers first.

### Phase 1 — Structure and cleanup

1. Create `docs/studio/` directory for the 21-page Studio Guide.
2. Move Windows-build/release/implementation-history files into `_archive/`.
3. Delete `.DS_Store`, resolve `DEEPL_TRANSLATION_COMMANDS.txt`.
4. Rebuild `docs/index.rst` toctree to the five-section IA.
5. Update `docs/conf.py` `exclude_patterns` to match the new file set.

### Phase 2 — Section 1 + 2 (Installation, Quick Start)

Rewrite both against current `prism.py` / `prism_tools.py` / `prism-studio.py`
behavior and current setup scripts. Verify every command by running it.

### Phase 3 — Section 3 (Studio Guide, 21 pages)

Write/merge each page per the mapping table. This is the largest chunk of work —
suggest tackling in the priority order the 2026-04-14 audit already established
(export/analysis output was rated "critical drift", projects/survey-import/template-
editor/recipe-builder/participants "high drift").

### Phase 4 — Section 4 (CLI)

One reference page generated/verified against actual `--help` output for each entry
point, one workflows/cookbook page with copy-paste examples, each verified by running.

### Phase 5 — Section 5 (Tutorial)

Audit `WORKSHOP.md` and `_archive/workshop/SCREENSHOTS_QUICK_START.md` against current
demo data and current UI; rewrite as the single guided walkthrough using the existing
exercise-0..5 screenshot set (recapture any that are stale).

### Phase 6 — Screenshot pass

Capture the 8 missing screens (see Screenshot Plan gap list) in light + dark, recapture
any screenshot embedded in a page that changed in Phases 2-5.

### Phase 7 — QA pass

- Full local Sphinx build with `fail_on_warning: true` (already enforced in
  `.readthedocs.yaml`) — must pass clean.
- Link check across all five sections.
- Command verification pass (every CLI example actually run).
- Confirm nothing outside the five sections is reachable from primary nav.

## Decisions (2026-07-14)

- **Deletion vs. archive**: delete outright (not archive) for the "Delete" category
  above — release notes, Windows build/test snapshots, implementation-history files.
  Still recoverable via `git log` if ever needed. Everything in the "Merge" category
  is deleted only after its content lands in the corresponding Studio Guide page.
- **Execution mode**: phase-by-phase with a review checkpoint after each phase.

## Decisions (2026-07-14, continued)

- **Tutorial demo dataset**: the existing workshop dataset is *not* reused. New demo
  data must be created for Section 5. Scope/shape of that new dataset is still open —
  see below.
- **`specs/*.md` and other reference material**: stays as linked appendices,
  cross-linked from the relevant Studio Guide page rather than folded in.

- **New demo dataset shape**: survey + sociodemographics/participants (not
  biometrics/eyetracking/physio). Synthetic, fabricated for docs purposes — no real
  anonymized source data. This keeps Phase 5 scoped to: a small synthetic survey
  export + a synthetic participants mapping source file, walking Project creation →
  Survey Import (`studio/converter_survey.md`) → Participants/Sociodemographics
  Import (`studio/converter_participants.md`) → Validation → Recipe Builder scoring →
  Export. Exact participant/session counts and survey instrument choice to be decided
  when Phase 5 is executed.
