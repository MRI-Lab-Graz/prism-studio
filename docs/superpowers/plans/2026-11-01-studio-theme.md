# Studio theme Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** The project page's field heading, section header with tally, readiness bar and flat field body become shared theme parts; the template editor uses them instead of its own look.

**Architecture:** One JS module `app/static/js/studio-theme.js` (`window.StudioTheme`, also `module.exports` for node) builds the markup; one Jinja macro per part emits the same markup server-side; styles live in `studio-theme.css`. Existing class names that already carry state (`bg-success`, `bg-danger`, `badge-tier-core`, `bg-warning`) are kept, not renamed: they are the theme's vocabulary today and `metadata.js`/`validation.js` toggle them.

**Tech Stack:** Jinja, vanilla JS, Bootstrap 5, pytest (+ `node` for the parity test; Playwright e2e stays as is).

**Spec:** `docs/superpowers/specs/2026-11-01-studio-theme-design.md` (user answers: editor fields become flat; REQ/FAIR rings are replaced by the readiness bar and tally badges).

## Global Constraints

- The project page is the reference: no visual change on it (only where its markup moves into the theme).
- No new colours, fonts or tokens; reuse `studio-theme.css` variables and the existing badge classes.
- Tier names are exactly `required`, `core`, `optional`. Tally order is exactly Required, Core, FAIR (as on the project page).
- Tip text is always HTML-escaped into the `title` attribute (plain text tooltip, as the project page does now).
- `CLAUDE.md` "One theme for every page" stays true; do not add page-local copies of themed parts.
- TDD, one commit per task, on branch `feat/studio-theme`. Targeted tests per task; full suite is nightly.

## Review Focus

- A tip containing `"`, `<`, `&` or a newline is escaped in both macro and builder (editor tips contain "Example: {...}" JSON and newlines).
- A section with no required fields shows no tally (editor: `hasRequired` false), not "Required 0/0".
- A complete tier turns green (`bg-success`) and an empty one is not shown red when its total is 0.
- Tooltips added by the builder after page load work (editor calls `enableTooltips()` after rendering; the builder must not rely on a one-time page init).
- The editor still tracks missing required fields (`renderMissingSummary`, `data-field-path`) after the red `*` and the green-edged tile are gone.

---

### Task 1: StudioTheme builder, macro and parity test

**Files:**
- Create: `app/static/js/studio-theme.js`, `tests/test_studio_theme_parity.py`
- Modify: `app/templates/includes/ui/macros.html`, `app/static/css/studio-theme.css`, `app/templates/base.html` (load script before page scripts)

**Interfaces:**
- Produces (JS): `StudioTheme.fieldLabel({text, tier, tip}) -> HTMLLabelElement` (`tier` optional; `tip` optional); `StudioTheme.tally({required, core, fair}) -> string` (HTML; each arg `[filled, total]` or omitted; entries with total 0 are skipped; returns `''` if none).
- Produces (Jinja): `field_label(text, tier='', tip='')`, `tally(required=none, core=none, fair=none)`.
- Markup, fieldLabel: `<label class="form-label studio-field-label">[<span class="badge {tierclass}">REQUIRED|CORE|OPTIONAL</span> ]text[ <span class="info-tip text-muted" data-bs-toggle="tooltip" title="tip">&#9432;</span>]</label>`; `tierclass` = `bg-danger` / `badge-tier-core` / `bg-secondary`.
- Markup, tally: lifted unchanged from `metadata.js` (~lines 3640-3690): `<span class="badge {bg-success if filled==total else danger/core/warning-class} bg-opacity-75">Required 3/3</span>` etc.

- [ ] **Step 1: Write the failing test** in `tests/test_studio_theme_parity.py`: render each macro with Jinja (`FileSystemLoader('app/templates')`), run the same input through `studio-theme.js` with `node -e` (fake minimal `document` is not needed: the module exposes `fieldLabelHtml`/`tally` string functions used by the DOM wrapper), normalise whitespace, assert equal. Cases: `test_field_label_required_with_tip`, `test_field_label_no_tier_no_tip`, `test_tip_is_escaped` (tip `a "b" <c> & d\ne`), `test_tally_complete_is_green`, `test_tally_skips_zero_total`.
- [ ] **Step 2: Run** `python3 -m pytest tests/test_studio_theme_parity.py -q`; expect FAIL (files missing).
- [ ] **Step 3: Implement** `studio-theme.js` (string builders `fieldLabelHtml`, `tally`; `fieldLabel` wraps the string in an element via `template.innerHTML`), the two macros, and `.studio-field-label { font-weight: 700; font-size: .875em; text-transform: uppercase; color: var(--bs-secondary-color); margin-bottom: .25rem; }` (the project page's current look of `fw-bold small text-muted text-uppercase mb-1`). Load the script in `base.html`.
- [ ] **Step 4: Run** the parity test; expect PASS.
- [ ] **Step 5: Commit** `feat(theme): StudioTheme field label and tally, macro parity test`.

### Task 2: Project page uses the theme parts

**Files:**
- Modify: `app/templates/includes/projects/study_metadata.html`, `app/static/js/modules/projects/metadata.js` (tally at ~3640-3690 calls `StudioTheme.tally`)
- Test: `tests/test_projects_workflow_wiring.py`

**Interfaces:** Consumes Task 1.

- [ ] **Step 1: Write the failing tests**: `test_study_metadata_labels_use_theme_class` (no `fw-bold small text-muted text-uppercase mb-1` left in `study_metadata.html`; `studio-field-label` count equals the old count of 11 plus the other converted labels) and `test_metadata_js_tally_comes_from_theme` (`metadata.js` has no `` `Core ${`` template; contains `StudioTheme.tally(`).
- [ ] **Step 2: Run both; expect FAIL.**
- [ ] **Step 3: Replace** the label class string with `studio-field-label` in the template (same look) and the inline tally string in `metadata.js` with `StudioTheme.tally({required, core, fair})` using the existing totals.
- [ ] **Step 4: Run** `tests/test_projects_workflow_wiring.py` and `tests/test_projects_compact_view_wiring.py`; expect PASS. Open the project page once and compare the Study Metadata tally and labels with the screenshots: no visible change.
- [ ] **Step 5: Commit** `refactor(projects): project page uses StudioTheme label and tally`.

### Task 3: Template editor field headings

**Files:**
- Modify: `app/static/js/template-editor.js` (`makeLabel`, ~line 998), `app/static/css/template-editor.css`
- Test: `tests/test_template_editor_theme.py` (create)

**Interfaces:** Consumes `StudioTheme.fieldLabel`.

- [ ] **Step 1: Write the failing tests**: `test_make_label_delegates_to_theme` (`makeLabel` body contains `StudioTheme.fieldLabel(` and no `createElement('label')`, no `text-danger` star) and `test_editor_loads_theme_script` (`template_editor.html` extends `base.html`, which already loads it; assert via `base.html` source).
- [ ] **Step 2: Run; expect FAIL.**
- [ ] **Step 3: Rewrite** `makeLabel(name, fieldSchema, isRequired, text)` to `return StudioTheme.fieldLabel({text, tier: isRequired ? 'required' : 'optional', tip: infoHtml(fieldSchema)})`. Drop the `schema-hint` span and the red `*`.
- [ ] **Step 4: Run tests; expect PASS.** Manual: open a template, headings read `REQUIRED  FILE ID ⓘ`; hover shows the schema info.
- [ ] **Step 5: Commit** `feat(template-editor): field headings use the theme label`.

### Task 4: Template editor section headers with tally

**Files:**
- Modify: `app/static/js/template-editor.js` (`te-subgroup` summary ~3165-3190, `paintCompleteness` ~552-590), `app/static/css/template-editor.css`
- Test: `tests/test_template_editor_theme.py`

**Interfaces:** Consumes `StudioTheme.tally`; the backend's `completeness` object (`required.filled/total`, `recommended.filled/total`) is unchanged (CLI parity untouched).

- [ ] **Step 1: Write the failing test** `test_section_header_uses_tally_not_complete_badge` (`template-editor.js` has no `te-section-badge`, no `'✓ complete'`; contains `StudioTheme.tally(`).
- [ ] **Step 2: Run; expect FAIL.**
- [ ] **Step 3: Replace** the `<summary>` content with the section title (project page `sm-section-toggle__title` style) and a tally container `.sm-section-group__badges` filled by `StudioTheme.tally({required:[filled,total], fair:[filled,total]})`; sections without required fields get no tally. `paintCompleteness` updates the containers instead of `te-section-badge`. Delete `.te-section-badge*` CSS.
- [ ] **Step 4: Run tests; expect PASS.** Manual: leave a required field empty, the section shows `Required 2/3`, fill it, it turns green.
- [ ] **Step 5: Commit** `feat(template-editor): section headers show the Required/FAIR tally`.

### Task 5: Readiness bar replaces the rings

**Files:**
- Modify: `app/templates/includes/ui/macros.html` (`readiness_row(prefix, label)`), `app/templates/template_editor.html` (~195-206), `app/templates/includes/projects/study_metadata.html` (Methods Readiness row), `app/static/js/template-editor.js` (`setRing` ~540, `paintCompleteness`), `app/static/css/template-editor.css`
- Test: `tests/test_template_editor_theme.py`

**Interfaces:** `readiness_row(prefix, label)` emits `<div class="d-flex align-items-center gap-3 mb-2 sm-readiness-row"><strong class="small text-uppercase text-muted">label</strong><div class="progress flex-grow-1" style="height: 12px;"><div class="progress-bar" role="progressbar" id="{prefix}Bar" style="width: 0%"></div></div></div>` (the project page's current markup); the editor uses prefixes `teRequired` and `teFair`.

- [ ] **Step 1: Write the failing test** `test_editor_has_no_rings` (`template_editor.html` and `template-editor.js` contain no `te-ring`, `completionRings`; `template_editor.html` uses `readiness_row`).
- [ ] **Step 2: Run; expect FAIL.**
- [ ] **Step 3: Implement** the macro, use it on both pages, change `paintCompleteness` to set bar width and colour class (`bg-success` at 100, else the existing amber/blue used by `smMainProgressBar`); delete `.te-ring*` CSS.
- [ ] **Step 4: Run tests incl. `tests/test_projects_workflow_wiring.py`; expect PASS.** Manual: both pages show the same bar.
- [ ] **Step 5: Commit** `feat(theme): shared readiness row; template editor drops the rings`.

### Task 6: Flat editor fields and the guard test

**Files:**
- Modify: `app/static/js/template-editor.js` (`renderFieldInRow` ~2123 drops the tile wrapper), `app/static/css/template-editor.css` (delete `.te-field`, `.te-field-required`, `.te-item-field` borders)
- Test: `tests/test_theme_guard.py` (create)

- [ ] **Step 1: Write the failing tests** in `tests/test_theme_guard.py`: `test_editor_fields_are_flat` (no `te-field` in JS or CSS) and `test_themed_parts_have_no_page_copies` (for `template-editor.js`, `template_editor.html`, `template-editor.css`: none of `te-ring`, `te-section-badge`, `te-field`, `class = 'form-label'` for field headings; list is the allow-set to extend per later page).
- [ ] **Step 2: Run; expect FAIL.**
- [ ] **Step 3: Remove** the tile wrapper (keep `data-field-path` on the column, `renderMissingSummary` relies on it) and the CSS.
- [ ] **Step 4: Run** `python3 -m pytest tests -q -k "template_editor or theme or projects"`; expect PASS. Run the template-editor Playwright tests if present.
- [ ] **Step 5: Commit** `feat(template-editor): flat fields; guard against page-local themed parts`.

### Task 7: Finish the branch

- [ ] Run `ponytail:ponytail-audit` on the branch, apply what is worth it, re-run the tests above, then merge to `main` (repo rule). Update the "pages still to move" list in the spec: converters, recipes, survey customizer, survey generator.

## Self-review notes

- Spec coverage: field heading (T1-3), section header and tally (T1,2,4), readiness (T5), flat fields (T6), guard test (T6), repo note (done on the branch before this plan), macro/builder parity (T1). The spec's `studio-section` card and `studio-tier` renames are deliberately not done: the existing classes already carry state and are reused (Architecture note).
- Not in this plan: other pages, the "Items" tab fields beyond the shared `makeLabel` path.
