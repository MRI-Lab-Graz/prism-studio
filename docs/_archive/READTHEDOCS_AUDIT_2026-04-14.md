# Read the Docs Audit - 2026-04-14

## Scope

This audit focuses on the current Read the Docs content for:

1. Installation
2. Project page
3. Sociodemographics import
4. Survey import
5. Template editor
6. Recipe builder
7. Analysis output

Out of scope for this audit:

- LimeSurvey-specific documentation rewrites
- LimeSurvey-specific implementation changes
- General specification pages unless they directly affect the user-facing workflow above

The goal here is not to rewrite everything at once. The goal is to identify where the published docs no longer match the current product and to define the shortest correct rewrite path.

## Executive Summary

The Read the Docs content is outdated in three different ways at once:

- Information architecture drift: important workflows exist in the product but are not exposed as first-class RTD pages.
- Behavioral drift: several pages describe older UI flows, older save semantics, or older output locations.
- Historical noise: some user-facing pages contain roadmap, handover, or implementation-history content that should not be in end-user docs.

Priority assessment:

- Critical: analysis output/export coverage
- High: projects page, survey import, template editor, recipe builder, sociodemographics import
- Medium: installation

Current impact on users:

- Users can still get started, but they cannot reliably infer what the current app actually does.
- The docs under-explain newer guided workflows in the Studio UI.
- Several pages teach legacy file locations or legacy folder expectations.
- Export and post-processing capabilities are materially under-documented.

## Cross-Cutting Findings

### 1. Navigation is incomplete for the workflows users actually use

Current RTD navigation in `docs/index.rst` exposes `PROJECTS`, `CONVERTER`, `TOOLS`, `RECIPES`, `PARTICIPANTS_MAPPING`, `TEMPLATES`, and `SURVEY_LIBRARY`, but it does not expose a dedicated page for:

- survey import as a standalone workflow
- recipe builder as a standalone workflow
- analysis/export outputs as a standalone workflow
- ANC export in the main toctree
- openMINDS export at all

Consequence:

- A user can reach some information only by already knowing the right page name or by reading broad, partially stale umbrella pages.

### 2. Several docs still describe a legacy library-management model

`docs/SURVEY_LIBRARY.md` and parts of `docs/TEMPLATES.md` still describe a `Checkout -> Drafts -> Submit -> merge_requests` workflow in `official/library/survey/`.

That is not the right mental model for the current everyday user workflow in Studio. The current UI centers on:

- browsing merged global + project templates
- editing project-local copies
- saving only to project library paths
- treating official/global templates as read-only reference material

Consequence:

- Users are told to think in terms of repository-maintainer workflows instead of the project-local workflow they actually have available in the app.

### 3. The docs still overuse `analysis/` as the main output concept

The current product uses multiple output surfaces:

- `derivatives/` for scored or derived dataset outputs
- `code/recipes/survey/` for saved project-local recipes
- export ZIPs for shareable/anonymized datasets
- `_anc_export` folders for ANC export
- optional `analysis/` inclusion in export, not default project structure creation

Consequence:

- The current docs blur analysis reports, derivatives, and share/export workflows.

### 4. Some docs describe capabilities that already moved from read-only to write-enabled workflows

The clearest example is the template editor. The public docs still partly describe it as validate/download-centric, while the current app supports server-side save and delete for project-local templates.

Consequence:

- Users are warned away from workflows that the current UI explicitly supports.

## Topic Assessment

## 1) Installation

Primary pages:

- `docs/INSTALLATION.md`
- `docs/QUICK_START.md`
- `docs/WEB_INTERFACE.md`
- `docs/CLI_REFERENCE.md`

### What is still okay

- The prebuilt-release path is still the right default recommendation.
- The page correctly centers PRISM Studio as the main entry point for most users.
- Platform-specific first-launch notes are still useful.

### What is outdated or incomplete

- `docs/INSTALLATION.md` still mixes current and legacy command examples. It references `python prism_tools.py recipes survey --prism /path/to/dataset`, while current CLI docs use `recipes surveys`.
- The page treats `.venv` activation more like troubleshooting than a normal part of source usage, even though the repo now assumes repo-local environment usage much more strongly.
- Source-install update guidance still points users toward a generic `pip install -r requirements.txt` refresh instead of steering them back through the setup script workflow.
- Installation pages do not clearly separate these user personas:
  - prebuilt app user
  - source user
  - CLI automation user
  - validator-only binary user

### Assessment

Status: Medium drift.

The page is not catastrophically wrong, but it is no longer clean or authoritative. Users can install successfully, yet the page is no longer the safest single source of truth for source-based operation.

### Rewrite direction

- Keep one short recommended path at the top: prebuilt Studio.
- Put source install into an explicit second path.
- Make `.venv` activation part of the standard source flow, not only troubleshooting.
- Align all command examples with current CLI names.
- Replace update guidance with a setup-script-first workflow.

## 2) Project Page

Primary pages:

- `docs/PROJECTS.md`
- `docs/STUDIO_OVERVIEW.md`

Primary current implementation:

- `app/src/project_manager.py`
- `app/src/web/blueprints/projects.py`
- `app/src/web/blueprints/projects_lifecycle_handlers.py`
- `app/templates/projects.html`
- `app/templates/includes/projects/export_section.html`

### What is outdated or wrong

- `docs/PROJECTS.md` still shows `analysis/` as part of the created scaffold, but project creation currently creates `sourcedata/`, `derivatives/`, `code/`, `project.json`, `contributors.json`, `CHANGES`, `.bidsignore`, and `.prismrc.json`.
- The page omits `contributors.json`, `.prismrc.json`, `.bidsignore`, `CHANGES`, `sourcedata/`, and `derivatives/`, even though these are part of the current project model.
- The page contains a very long roadmap, next sprint handover, and lessons section that belongs in internal engineering notes, not end-user documentation.
- The current page-level export surface now includes anonymized ZIP export, ANC export, and openMINDS export, but the user docs do not explain the full export surface coherently from the Projects page.

### What is current and should be preserved

- Accepting both project root and `project.json` is current and should remain documented.
- The idea of the Projects page as the main control center is still correct.

### Assessment

Status: High drift.

This page still points users to the right area of the app, but it no longer documents the actual project model cleanly. The mismatch between documented scaffold and actual scaffold is especially problematic.

### Rewrite direction

- Rewrite around current project lifecycle only.
- Remove roadmap/handover material from user docs.
- Document the real scaffold and why `sourcedata/`, `code/`, and `derivatives/` exist.
- Add a concise section for recent-project behavior and project-root vs `project.json` loading.
- Add a short overview of the export choices available inside Projects.

## 3) Sociodemographics Import

Primary pages:

- `docs/PARTICIPANTS_MAPPING.md`
- `docs/CONVERTER.md`

Primary current implementation:

- `src/participants_converter.py`
- `app/src/participants_backend.py`
- `app/src/participants_paths.py`
- `app/src/web/blueprints/conversion_participants_blueprint.py`
- `app/templates/converter_participants.html`

### What is outdated or inconsistent

- `docs/PARTICIPANTS_MAPPING.md` is internally inconsistent about file location. It recommends `code/library/` and `sourcedata/`, and later says web detection happens at root. Current path resolution supports project root, `code/`, `code/library/`, and `code/library/survey/`.
- The page still frames the workflow too much as passive auto-conversion during validation/upload. The current Studio UI is an explicit guided workflow with review, optional extra-column mapping, optional metadata draft save, and explicit file creation.
- The docs do not adequately explain that the current UI builds both `participants.tsv` and `participants.json` together as the normal outcome.
- The docs underplay current `participant_id` canonicalization behavior, which is now important for consistent output and schema alignment.
- The page does not reflect that draft metadata save in the UI is optional and that unsaved metadata edits are still included when creating participant files.

### What is current and should be preserved

- The overall concept of `participants_mapping.json` is still correct.
- The examples for value recoding are still useful.
- The emphasis on standardized variables remains correct.

### Assessment

Status: High drift.

This page has good conceptual material but the operational guidance is behind the current UI and current path rules.

### Rewrite direction

- Reframe the page around the current three-step Studio workflow.
- Document the current supported mapping-file discovery order.
- Explain that output is `participants.tsv` plus `participants.json`.
- Add a short section on optional NeuroBagel-style annotation draft save.
- Keep the mapping schema reference, but shorten repetitive examples.

## 4) Survey Import

Primary pages today:

- `docs/CONVERTER.md`
- `docs/STUDIO_OVERVIEW.md`
- `docs/CLI_REFERENCE.md`

Related implementation:

- `src/converters/survey.py`
- `app/src/web/blueprints/conversion_survey_handlers.py`
- `app/templates/converter_survey.html`

### Core problem

There is no good dedicated non-LimeSurvey survey-import page in RTD.

The current user-facing survey converter has much richer behavior than the docs reflect, including:

- preview dry-run before conversion
- explicit participant ID column selection
- session requirement and override handling
- run-column override
- optional ID mapping file
- language selection
- specific survey selection
- questionnaire version selection for multi-version templates
- project-template copy and follow-up completion workflow via Template Editor
- quick access from project `sourcedata/`

### What is outdated or insufficient

- `docs/CONVERTER.md` is still a generic, older-style converter overview and does not match the current survey converter UI.
- `docs/STUDIO_OVERVIEW.md` reduces import to a simple “convert and import data” step, which is too shallow for current survey workflows.
- Survey import is mixed together with LimeSurvey narratives in the broader docs, which makes it harder to maintain and harder to keep neutral while LimeSurvey docs remain off-limits.

### Assessment

Status: High drift.

This is one of the biggest documentation gaps. The product has a mature survey-conversion workflow, but RTD does not yet present it as a first-class page.

### Rewrite direction

- Add a dedicated `SURVEY_IMPORT.md` page that is explicitly non-LimeSurvey-centric.
- Keep LimeSurvey details in the existing LimeSurvey docs and only cross-link to them.
- Document the current survey converter screen in the order users see it.
- Include current advanced options and version selection.
- Explain the difference between preview, convert, and project-template follow-up.

## 5) Template Editor

Primary pages:

- `docs/TEMPLATES.md`
- `docs/WEB_INTERFACE.md`
- `docs/TOOLS.md`
- `docs/SURVEY_LIBRARY.md`

Primary current implementation:

- `app/src/web/blueprints/tools_template_editor_blueprint.py`
- `app/templates/template_editor.html`

### What is outdated or wrong

- `docs/WEB_INTERFACE.md` still says the editor supports validation and download with “no server-side overwrite”. Current implementation supports save and delete for project-local templates.
- `docs/TEMPLATES.md` still mixes the current project-copy model with the older `Checkout -> Edit -> Submit` model.
- `docs/SURVEY_LIBRARY.md` is still centered on `drafts/` and `merge_requests/`, which is not the main user-facing Studio workflow anymore.
- The docs do not explain clearly enough that global/official templates are read-only reference entries, while saves go to project-local library paths.
- The current editor also supports questionnaire export to Word (`.docx`), which is not reflected in the core editor docs.
- The docs do not clearly explain current validation semantics for global templates versus project-local templates.

### What is current and should be preserved

- The `Study` vs `Technical` distinction in `docs/TEMPLATES.md` is worth keeping.
- The explanation of official library template versus project copy is directionally correct.

### Assessment

Status: High drift.

The conceptual parts are strong, but the operational guidance is outdated enough that a user reading the docs will come away with the wrong expectations about what can be edited, where it is saved, and which workflows are supported directly in Studio.

### Rewrite direction

- Make project-local save behavior explicit.
- Mark official/global templates as read-only in Studio.
- Replace old checkout/draft language in user docs with current merged-library/project-copy language.
- Add the questionnaire `.docx` export capability.
- Keep the schema explanation, but shorten the historical process discussion.

## 6) Recipe Builder

Primary pages today:

- `docs/RECIPES.md`
- `docs/TOOLS.md`

Primary current implementation:

- `src/recipes_surveys.py`
- `app/src/recipe_validation.py`
- `app/src/web/blueprints/tools.py`
- `app/src/web/blueprints/tools_recipe_builder_handlers.py`
- `app/templates/recipe_builder.html`

### What is outdated or wrong

- RTD has no dedicated recipe-builder workflow page, even though the UI now has a dedicated builder screen.
- `docs/TOOLS.md` still describes an older “Recipes & Scoring” concept instead of the current Recipe Builder experience.
- `docs/RECIPES.md` has path drift. It still says recipes live under `recipes/surveys/` and that results are saved under `recipes/surveys/`, while the current project-local save path is `code/recipes/survey/` and computed outputs live under `derivatives/survey/`.
- `docs/RECIPES.md` also still documents output folders as `derivatives/surveys/` and `derivatives/biometrics/`, but the current survey engine writes to `derivatives/survey/`.
- The builder UI now includes template selection, optional inclusion of official library templates, inversion handling, and variation support via `VersionedScores`, but none of that is properly documented in a user-facing workflow page.

### What is current and should be preserved

- The conceptual explanation of `Transforms.Derived` versus `Scores` is valuable.
- The missing-data section is still useful.

### Assessment

Status: High drift.

The spec page is still helpful for recipe semantics, but it is not enough anymore. The actual builder workflow is under-documented, and parts of the path documentation are now wrong.

### Rewrite direction

- Keep `docs/RECIPES.md` as the engine/spec page.
- Add a dedicated `RECIPE_BUILDER.md` page for the Studio UI workflow.
- Correct all current paths to `code/recipes/survey/` and `derivatives/survey/`.
- Add coverage for template picker, inversion, save validation, and variation handling.
- Cross-link from `TOOLS.md`, `STUDIO_OVERVIEW.md`, and the new page.

## 7) Analysis Output

Primary pages today:

- `docs/ANC_EXPORT.md`
- `docs/PROJECTS.md`
- `docs/STUDIO_OVERVIEW.md`
- `docs/RECIPES.md`

Primary current implementation:

- `src/recipes_surveys.py`
- `app/src/web/export_project.py`
- `app/src/web/blueprints/projects_export_blueprint.py`
- `app/templates/includes/projects/export_section.html`

### What is outdated or missing

- `docs/ANC_EXPORT.md` exists but is not surfaced in the main RTD toctree.
- The current Projects export surface includes three distinct output workflows:
  - anonymized ZIP export
  - ANC export
  - openMINDS metadata export
  Only ANC has a dedicated page, and even that page is effectively hidden from main navigation.
- The current export UI supports masking copyrighted question text and randomizing participant IDs, but that workflow is not documented in the active RTD pages.
- `docs/RECIPES.md` does not adequately explain current survey-analysis outputs such as:
  - `derivatives/survey/<recipe_id>/...`
  - `derivatives/survey/survey_scores.tsv`
  - derivative `dataset_description.json`
  - methods boilerplate output
- `docs/PROJECTS.md` does not give users a coherent explanation of what “Data Export / Share” now contains.
- `docs/STUDIO_OVERVIEW.md` still talks loosely about keeping generated outputs in analysis/derivatives paths instead of describing the current concrete export surfaces.

### Assessment

Status: Critical drift.

This is currently the weakest documentation area relative to implementation maturity. The app now offers a real export/share surface, but RTD does not present it as a coherent system.

### Rewrite direction

- Add a dedicated `ANALYSIS_OUTPUT.md` or `EXPORTS.md` page.
- Move ANC export into the visible toctree.
- Add an export matrix that clearly separates:
  - scored derivatives
  - methods boilerplate
  - anonymized ZIP export
  - ANC export
  - openMINDS export
- Update `PROJECTS.md` to summarize export entry points and link to the dedicated output page.

## Recommended Rewrite Plan

## Phase 1 - User-critical pages

1. Rewrite `docs/INSTALLATION.md`
2. Rewrite `docs/PROJECTS.md`
3. Rewrite `docs/PARTICIPANTS_MAPPING.md`
4. Add `docs/SURVEY_IMPORT.md`
5. Rewrite `docs/TEMPLATES.md`
6. Add `docs/RECIPE_BUILDER.md`
7. Add `docs/ANALYSIS_OUTPUT.md`
8. Update `docs/index.rst` so those pages are visible in main navigation

## Phase 2 - Supporting pages

1. Update `docs/STUDIO_OVERVIEW.md` to match the new page structure
2. Update `docs/TOOLS.md` to stop acting as a substitute for real workflow docs
3. Update `docs/WEB_INTERFACE.md` so it reflects current save/export behavior
4. Keep `docs/RECIPES.md` as the technical reference page and remove user-workflow overload from it

## Phase 3 - Cleanup

1. Remove roadmap and handover content from `docs/PROJECTS.md`
2. Archive or rewrite legacy `drafts/merge_requests` language in active user docs
3. Ensure all output paths use current folder names
4. Reduce duplication between `TOOLS.md`, `WEB_INTERFACE.md`, and dedicated workflow pages

## Suggested Information Architecture

Recommended user-facing page set for this scope:

- `INSTALLATION.md`
- `PROJECTS.md`
- `SOCIODEMOGRAPHICS_IMPORT.md` or a rewritten `PARTICIPANTS_MAPPING.md`
- `SURVEY_IMPORT.md`
- `TEMPLATE_EDITOR.md` or a heavily rewritten `TEMPLATES.md`
- `RECIPE_BUILDER.md`
- `ANALYSIS_OUTPUT.md`

Recommended page roles:

- workflow pages explain what users do in Studio
- reference pages explain schema and file semantics
- integration pages stay separate for special systems like LimeSurvey and ANC

## Pages To Avoid Touching In This Pass

Do not update these as part of the current rewrite unless explicitly coordinated later:

- `docs/LIMESURVEY_INTEGRATION.md`
- `docs/LIMESURVEY_VERSION_DIFFERENCES.md`

The current survey-import rewrite should stay generic and should only cross-link to LimeSurvey-specific pages when needed.

## Solved In This Assessment

- Mapped the current RTD pages that cover the requested workflows.
- Mapped each requested workflow to current implementation files.
- Identified where the active docs are factually wrong versus merely incomplete.
- Identified which pages are missing from the visible RTD navigation.
- Isolated LimeSurvey-specific docs so they can remain untouched.

## Lessions-Learned

- Broad umbrella pages age badly when product workflows become more specialized.
- User docs should describe the current UI contract, not the internal development history.
- Export/output docs need to distinguish clearly between reproducibility artifacts, derivatives, and share/export packages.
- Template and recipe docs should separate project-local workflows from maintainer-only library workflows.
- Navigation drift is now a first-order docs problem in this repo, not just a wording problem.
