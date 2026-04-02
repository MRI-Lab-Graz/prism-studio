# Beginner Help Coverage Roadmap (2026-04-02)

## Goal
Provide Beginner Help coverage for all user-facing settings in PRISM Studio, while avoiding duplicate information where inline helper text already exists.

## Scope
- In scope: settings-like controls in web UI templates (inputs, selects, checkboxes, radio buttons, textareas) where users configure behavior, output, paths, processing, export, or metadata.
- Out of scope: read-only status displays, result summaries, static documentation pages.

## Existing Foundation (already present)
- Global toggle and persistence: `localStorage` key `prism_beginner_help_mode`.
- Global help script: `app/static/js/global-help-mode.js`.
- Duplicate suppression exists for auto-inline hints by comparing generated hints against nearby `.form-text`, `small.text-muted`, etc.
- Existing explicit beginner blocks already present in some pages (`.beginner-help-block`, `[data-help-panel]`).

## Rollout Strategy

### Phase 1: Inventory and Canonical Hint Model
Status: COMPLETED

1. Build a canonical inventory of all settings controls in templates.
2. Tag each control with a stable help key (`data-help-key`) where needed.
3. Create a single source of truth for beginner hint text (grouped by page/feature).
4. Mark fields that already have sufficient inline explanation to avoid duplicate helper output.

Deliverables:
- `app/static/js/beginner-help-registry.js` (new)
- Inventory matrix in this roadmap

### Phase 2: Help Engine Integration
Status: COMPLETED

1. Extend `global-help-mode.js` to:
   - Prefer registry text by `data-help-key`.
   - Fall back to current generic auto-hints.
   - Keep duplicate filtering against existing local help text.
2. Add support for field-level opt-out (`data-help-skip="true"`).
3. Ensure help toggling and panel collapse behavior is consistent across pages.

Deliverables:
- Updated `app/static/js/global-help-mode.js`
- Optional CSS refinement for consistent hint appearance

### Phase 3: Template Coverage Pass (All Settings)
Status: COMPLETED

Apply help key annotations and/or explicit help blocks to all settings pages:

- Projects:
  - `app/templates/includes/projects/create_form.html`
  - `app/templates/includes/projects/open_form.html`
  - `app/templates/includes/projects/study_metadata.html`
  - `app/templates/includes/projects/export_section.html`
  - `app/templates/includes/projects/settings_section.html`
- Converters:
  - `app/templates/converter_survey.html`
  - `app/templates/converter_biometrics.html`
  - `app/templates/converter_physio.html`
  - `app/templates/converter_eyetracking.html`
  - `app/templates/converter_environment.html`
  - `app/templates/converter_participants.html`
- Tools:
  - `app/templates/recipes.html`
  - `app/templates/recipe_builder.html`
  - `app/templates/survey_customizer.html`
  - `app/templates/template_editor.html`
  - `app/templates/prism_app_runner.html`
  - `app/templates/file_management.html`

### Phase 4: Duplicate-Info Audit and Cleanup
Status: COMPLETED

1. For each page, compare:
   - Existing static helper text (`.form-text`, `small.text-muted`, alerts)
   - Registry beginner hint text
2. Remove redundant duplicate phrasing where both are visible.
3. Keep detailed domain-specific text where it adds value; suppress generic duplicate hints.

### Phase 5: Validation and Regression Checks
Status: COMPLETED (lightweight)

1. Manual UI checklist with Beginner Help OFF/ON states.
2. Verify no layout breakage on desktop and mobile.
3. Verify forms remain functional and keyboard accessible.
4. Run project tests and repo checks.

## Initial Gap Inventory (from template scan)
Templates with settings controls but no explicit beginner help container (`.beginner-help-block` or `[data-help-panel]`):

- `app/templates/converter_biometrics.html`
- `app/templates/converter_environment.html`
- `app/templates/converter_participants.html`
- `app/templates/converter_physio.html`
- `app/templates/includes/projects/create_form.html`
- `app/templates/includes/projects/methods_section.html`
- `app/templates/includes/projects/open_form.html`
- `app/templates/includes/projects/settings_section.html`
- `app/templates/index.html`
- `app/templates/library_editor.html`
- `app/templates/projects.html`
- `app/templates/recipe_builder.html`
- `app/templates/recipes.html`
- `app/templates/results.html`
- `app/templates/survey_customizer.html`
- `app/templates/template_editor.html`

Notes:
- Some of these already include rich inline form help; they may not need extra blocks once registry-based per-field hints are active.
- Inventory will be refined to identify true missing beginner guidance vs already-sufficient pages.

## Solved Issues
- Created initial repo-wide roadmap and baseline gap inventory.
- Confirmed existing duplicate-avoidance mechanism in `global-help-mode.js` as a foundation.
- Added centralized hint registry: `app/static/js/beginner-help-registry.js`.
- Integrated registry lookup into `app/static/js/global-help-mode.js` (exact, prefix, regex rules).
- Added field-level opt-out support via `data-help-skip="true"`.
- Reduced duplicate/stacked guidance by suppressing inline beginner hints when contextual help text already exists (except invalid fields).
- Loaded registry globally in `app/templates/base.html` before `global-help-mode.js`.
- Added fallback help-key resolution for controls without ids (name, aria-label, class token).
- Added explicit `data-help-key` annotations for dynamic fields in `app/templates/library_editor.html`.
- Verified template controls without ids are covered through `data-help-key` (no uncovered controls found in template scan).
- Extended hint rendering to settings controls outside `<form>` elements.
- Added label-derived fallback hints so all settings controls receive contextual beginner guidance even without dedicated registry text.
- Completed automated template coverage audit: no control found without either `id` or `data-help-key`.

## lessions-learned
- A centralized beginner hint registry is required to avoid per-template drift and duplicate wording.
- Generic auto-hints are useful as fallback, but explicit keyed hints are needed for advanced settings pages (for example PRISM App Runner).
- Duplicate filtering must remain content-based (normalized text compare), not just CSS-class based, because existing help appears in multiple markup patterns.
