# Propose Changes Page Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make "Propose changes" a central, guided page (step-1 dropdown, then dropdown-driven forms) that works without an open project.

**Architecture:** One new backend module `src/spec_contribute.py` holds a project-less catalog and two stateless proposal builders that reuse `src/term_proposal.py` (`as_v2`, `issue_url`, `check_with_specification`, `slugify`) and the vendored `schema_patch.py`. A CLI (`spec catalog`, `spec propose-values`, `spec propose-metric`) and three thin Flask routes call them. The Contribute template and JS are rebuilt around a forced-choice dropdown; the existing project routes stay and back the "Use in my open project" button.

**Tech Stack:** Python 3 / Flask / pytest, vanilla JS (Bootstrap 5), Playwright e2e (`tests/e2e/`).

**Spec:** `docs/superpowers/specs/2026-10-23-propose-changes-page-design.md`

## Global Constraints

- Work on a feature branch (`feat/propose-changes-page`), in a worktree if the executing skill asks for one. TDD: every task starts with a failing test that has been run and seen to fail.
- Do not edit vendored files (`scripts/specification/`, `official/library/terms/`, `app/schemas/*` except those CLAUDE.md lists). Validity is decided only by the vendored scripts through `src/term_proposal.py` / `src/spec_overlay.py`.
- Validation-path code reads `current_specification()`; no hand-written lists of modalities. If `tests/test_specification_boundaries.py` lists files that must follow this, add `src/spec_contribute.py` to its list.
- New logic goes in top-level `src/` only (no `app/src/` twin). Routes and JS decide nothing. Run `python tests/verify_repo.py --check dual-tree-drift --no-fix` before the last commit.
- Page text from users or the project is written with `textContent` only, never as HTML.
- Plain wording in the page: "kind of data", "list", "choice", "measurement". The words modality, patch, TermID, enum do not appear in page text.
- Studio sends nothing: sharing is the existing dialog (prefilled GitHub link, `proposal.json` download).
- Without a project nothing is written to disk. Project-only buttons are hidden, not disabled, when no project is open.
- Before merging: run `/ponytail:ponytail-audit` on the branch (CLAUDE.md).

## Review Focus

- A value the official schema already allows: not proposed, reported as "already allowed" (task 2).
- Typed names or values with spaces, capitals, non-ASCII letters, a leading digit or empty text: a clear message, no crash, nothing proposed (tasks 2, 3).
- A measurement name that already matches an official term, alias or label: refused with the existing term named (task 3).
- Page opened with no project: no "Open a project first" warning anywhere, both Share buttons work, "Use in my open project" absent; with a project it is present (tasks 5, 6).
- Hostile text (`<img src=x onerror=alert(1)>`) typed as a value, name or description appears as text in the list and the proposal dialog (tasks 5, 6).
- A proposal larger than the form's size limit: the problems list shows it and the GitHub link is not offered (task 4 uses the existing check; covered by a route test).

---

### Task 1: Catalog (backend, CLI)

**Files:**
- Create: `src/spec_contribute.py`
- Modify: `app/src/cli/commands/spec.py`, `app/src/cli/parser.py` (spec subparsers, near line 1824), `app/src/cli/dispatch.py` (spec branch, line 73), `app/src/cli/entrypoint.py` (import line ~117, handler map ~169)
- Test: `tests/test_spec_contribute.py` (new), `tests/test_cli_dispatch_routing.py` (add rows), `tests/test_cli_spec.py`

**Interfaces:**
- Produces: `spec_catalog() -> dict` shaped
  `{"modalities": [{"name": str, "label": str, "lists": [{"field": str, "label": str, "values": [str]}], "metrics": [{"id": str, "label": str, "units": str | None}] | None}], "units": [str], "specimens": [str]}`.
  `modalities` holds every PRISM modality with at least one list in `current_specification().patchable_fields(name)` (today biometrics, biosample, environment, physio, survey; not events). `metrics` is the registry's analyte-level terms (`Level == "analyte"`) from `load_registry(name)` for a modality that has a term folder, else `None`. `label` of a modality is `name.capitalize()`; `label` of a list is the last dotted segment split on capitals, lowercased, first letter capitalized (`Technical.SpecimenType` -> `Specimen type`). `values` are the `enum` of that path in the official stable schema (walk `properties` per dotted segment; load with `src.schema_manager.load_schema(name, DEFAULT_SCHEMA_DIR, "stable")`). `units` is the sorted set of `Units` strings used by registry terms of every modality that has one. `specimens` is the biosample `Technical.SpecimenType` values.
- CLI: `spec catalog [--json]` prints the catalog (readable text, or JSON with `--json`); handler `cmd_spec_catalog(args)`; registered as `spec_catalog`.

- [ ] **Step 1: Write the failing tests** in `tests/test_spec_contribute.py`:
  `test_catalog_lists_biosample_with_specimen_types` (biosample entry has a list with `field == "Technical.SpecimenType"`, `label == "Specimen type"`, `"saliva" in values`, `metrics` non-empty and every entry has `id` starting `prism:`); `test_catalog_has_no_modality_without_lists` (`"events"` absent); `test_catalog_metrics_none_without_registry` (`survey` entry has `metrics is None`); `test_catalog_units_sorted_and_unique` (contains `"nmol/L"`, equals `sorted(set(...))`); `test_catalog_specimens_match_the_biosample_list`.
  In `tests/test_cli_dispatch_routing.py` add `(dict(command="spec", action="catalog"), "spec_catalog")` to the table. In `tests/test_cli_spec.py` add `test_spec_catalog_json_runs_without_a_project` (run `prism_tools.py spec catalog --json` the way the file's other tests do, assert `success` and a `biosample` modality).
- [ ] **Step 2: Run** `pytest tests/test_spec_contribute.py tests/test_cli_dispatch_routing.py tests/test_cli_spec.py -q`. Expected: FAIL (module / handler missing).
- [ ] **Step 3: Implement** `spec_catalog` in `src/spec_contribute.py` and the CLI wiring above. `spec catalog` takes no `--project`.
- [ ] **Step 4: Run** the same command. Expected: PASS.
- [ ] **Step 5: Commit** `feat: spec catalog (kinds of data, lists, known measurements) without a project`.

### Task 2: Propose a missing choice (backend, CLI)

**Files:**
- Modify: `src/spec_contribute.py`, `app/src/cli/commands/spec.py` (extract the delivery tail of `cmd_spec_propose`, lines ~110-128, into `_deliver_result(args, result)` and use it from both commands), `app/src/cli/parser.py`, `app/src/cli/dispatch.py`, `app/src/cli/entrypoint.py`
- Test: `tests/test_spec_contribute.py`, `tests/test_cli_spec.py`, `tests/test_cli_dispatch_routing.py`

**Interfaces:**
- Consumes: `spec_catalog()` (task 1) to validate `modality` and `field`.
- Produces: `proposal_for_values(modality: str, field: str, values: list[str]) -> dict` returning the shape of `proposal_for_local_terms` (`proposal`, `document`, `issue_url`, `problems`, `skipped`). The proposal is `{"modality", "terms": [], "patch": {"operations": [{"op": "add_enum_values", "path": field, "values": new}]}}` with `new` = values the official schema lacks (use `schema_patch.additions`, as `add_local_values` does); `skipped` = values already official. Raises `OverlayError` for: unknown modality or field (message lists the valid ones), empty `values`, a value not matching `^[a-z0-9][a-z0-9-]*$` (message: lowercase letters, digits and `-`), nothing new left (message names the already-allowed values). Writes nothing.
- CLI: `spec propose-values --modality M --field F --value V [--value V …] [--out FILE] [--open] [--json]`; handler `cmd_spec_propose_values`, registered `spec_propose_values`. Neither it nor `propose-metric` takes `--project`.

- [ ] **Step 1: Write the failing tests:** `test_values_proposal_builds_a_patch_document` (`("biosample", "Technical.SpecimenType", ["sweat"])` -> `document["files"]` has `patches/biosample.json`, `problems == []`, `issue_url` starts with `https://github.com/MRI-Lab-Graz/prism-specification/issues/new`); `test_values_proposal_works_for_another_kind_of_data` (`survey`, `Technical.Respondent`, a new lowercase value -> no problems; if the vendored check rejects non-biosample patches, stop and report instead of narrowing); `test_values_already_official_are_skipped` (`saliva` alone raises `OverlayError`; `["saliva", "sweat"]` gives `skipped == ["saliva"]`); `test_values_reject_bad_text` parametrised over `""`, `"Sweat"`, `"sw eat"`, `"1sweat"`, `"schweiß"`, `"<img src=x>"` -> `OverlayError`; `test_values_unknown_field_names_valid_ones`; `test_values_write_nothing` (tmp cwd stays empty). CLI: `test_spec_propose_values_json` (success, `issue_url`), `test_spec_propose_values_bad_value_exits_1`; routing row `(dict(command="spec", action="propose-values"), "spec_propose_values")`.
- [ ] **Step 2: Run** the three test files. Expected: FAIL.
- [ ] **Step 3: Implement** `proposal_for_values`, the `_deliver_result` extraction, and the CLI wiring. Keep `cmd_spec_propose` behaviour identical (its existing tests must still pass).
- [ ] **Step 4: Run** `pytest tests/test_spec_contribute.py tests/test_cli_spec.py tests/test_cli_dispatch_routing.py tests/test_spec_overlay_share.py -q`. Expected: PASS.
- [ ] **Step 5: Commit** `feat: spec propose-values (a missing choice in a list, no project)`.

### Task 3: Propose a missing measurement (backend, CLI)

**Files:**
- Modify: `src/spec_contribute.py`, `app/src/cli/commands/spec.py`, `app/src/cli/parser.py`, `app/src/cli/dispatch.py`, `app/src/cli/entrypoint.py`
- Test: `tests/test_spec_contribute.py`, `tests/test_cli_spec.py`, `tests/test_cli_dispatch_routing.py`

**Interfaces:**
- Consumes: `OverlayError`, `_vendored` patterns from `src/spec_overlay.py`; `slugify`, `as_v2`, `issue_url`, `check_with_specification`, `ProposalError` from `src/term_proposal.py`; `load_registry`, `find_term` from `src/term_registry.py`.
- Produces: `proposal_for_new_metric(name: str, description: str, units: str, specimen: str, aliases: list[str] | None = None, modality: str = "biosample", specimens: list[str] | None = None) -> dict`, same result shape as task 2. Builds the two terms exactly like the unknown-column branch of `build_proposal`: analyte `{"TermID": "prism:<slug>", "Level": "analyte", "Label": name, "Aliases": aliases, "Description": description}` (omit `Aliases` when empty) and child `{"TermID": "prism:<slug>.<specimen>", "Level": "analyte-specimen", "Parent": ..., "SpecimenType": specimen, "Units": units}`. `specimens` replaces the allowed specimen types for the check (a project's additions, as `check_with_specification` takes). Raises `OverlayError` when: `modality` has no term registry; `find_term(load_registry(modality), name)` or any alias matches (message names the existing `TermID`; a ponytail comment notes that a known measurement for a new sample type is not offered yet); name/description/units/specimen is empty; `slugify` fails (wrap `ProposalError`); the vendored check returns problems that block building (otherwise return them in `problems`).
- CLI: `spec propose-metric --name N --description D --units U --specimen S [--alias A …] [--modality biosample] [--out FILE] [--open] [--json]`; handler `cmd_spec_propose_metric`, registered `spec_propose_metric`.

- [ ] **Step 1: Write the failing tests:** `test_metric_proposal_builds_parent_and_child` (`("DHEA", "Steroid hormone, a marker of adrenal activity.", "pg/mL", "saliva", ["dehydroepiandrosterone"])` -> files `terms/biosample/dhea.json` and `terms/biosample/dhea.saliva.json`, `problems == []`, parent has `Aliases == ["dehydroepiandrosterone"]`); `test_metric_without_aliases_omits_the_field`; `test_metric_matching_an_official_term_is_refused` (`"cortisol"` and an official alias both -> `OverlayError` containing `prism:cortisol`); `test_metric_bad_input` parametrised over empty name, `"1abc"`, `"schweiß"`, empty units, empty specimen; `test_metric_unknown_specimen_is_a_problem_not_a_crash` (`specimen="sweat"` -> `problems` non-empty); `test_metric_accepts_extra_specimens` (`specimens=[*official, "sweat"]` and `specimen="sweat"` -> no problems); `test_metric_for_a_kind_without_measurements_is_refused` (`modality="survey"`). CLI: `test_spec_propose_metric_json`, routing row.
- [ ] **Step 2: Run** the three test files. Expected: FAIL.
- [ ] **Step 3: Implement** `proposal_for_new_metric` and the CLI wiring; reuse `_deliver_result` from task 2.
- [ ] **Step 4: Run** `pytest tests/test_spec_contribute.py tests/test_cli_spec.py tests/test_cli_dispatch_routing.py -q`. Expected: PASS.
- [ ] **Step 5: Commit** `feat: spec propose-metric (a missing measurement, no project)`.

### Task 4: Routes

**Files:**
- Modify: `app/src/web/blueprints/specification_contribute.py`
- Test: `tests/test_specification_contribute_routes.py`

**Interfaces:**
- Consumes: `spec_catalog`, `proposal_for_values`, `proposal_for_new_metric` (tasks 1-3); existing `_project()`, `_error()`, `_body()`, `_project_specimens` from `src.spec_overlay`.
- Produces (none checks for a project; all under `/api/spec/`, already gate-exempt):
  - `GET /api/spec/catalog` -> `{"success": True, **spec_catalog(), "project_open": bool}`.
  - `POST /api/spec/propose-values` body `{"modality"?: str (default "biosample"), "field": str, "values": [str]}` -> `{"success": True, **result}`; `OverlayError` -> `_error(str(exc))`.
  - `POST /api/spec/propose-metric` body `{"name", "description", "units", "specimen", "aliases"?: [str], "modality"?: str}` -> same; passes `specimens=_project_specimens(project, modality)` when a project is open and it returns a list.
  - Existing `_values_change` routes take an optional `"modality"` (default `"biosample"`) and pass it to `add_local_values` / `remove_local_values`; the existing `/api/spec/local/add-term` stays biosample-only.
  - Body validation: non-string or non-list inputs give a 400 `_error`, never a 500.

- [ ] **Step 1: Write the failing tests** (use the file's `client` fixture, with and without a project in the session): `test_catalog_without_a_project` (200, `project_open is False`, has `biosample`), `test_catalog_with_a_project` (`project_open is True`), `test_propose_values_without_a_project` (success, `issue_url` startswith `FORM`, nothing written to disk), `test_propose_values_rejects_bad_body` (values not a list; field missing -> 400), `test_propose_values_already_allowed_is_an_error_message`, `test_propose_metric_without_a_project`, `test_propose_metric_uses_the_projects_own_specimens` (project with a patch adding `sweat`; `specimen="sweat"` -> no problems), `test_propose_metric_official_name_is_an_error`, `test_new_routes_pass_the_project_gate` (`is_gate_exempt` for the three paths), `test_add_values_for_another_modality` (survey field, project open -> patch file `code/specification/patches/survey.json`), `test_oversized_proposal_reports_problems` (very long description -> `problems` mentions the size, success still True, as the existing propose route does).
- [ ] **Step 2: Run** `pytest tests/test_specification_contribute_routes.py -q`. Expected: FAIL.
- [ ] **Step 3: Implement** the three routes and the `modality` parameter.
- [ ] **Step 4: Run** the same command plus `tests/test_spec_overlay_values.py`. Expected: PASS.
- [ ] **Step 5: Commit** `feat: project-less routes for the propose page`.

### Task 5: The page shell and "A missing choice in a list"

**Files:**
- Modify: `app/templates/specifications_contribute.html`, `app/static/js/modules/specification/contribute.js`
- Test: `tests/e2e/test_specification_contribute_flows.py` (replace the tab-based flows that no longer exist; keep their intent), `tests/test_spec_docs.py` or `tests/test_specifications_workflow_wiring.py` if either asserts the old tab ids

**Interfaces:**
- Consumes: `/api/spec/catalog`, `/api/spec/propose-values`, existing `/api/spec/local` (for "Additions in this project" when a project is open), `/api/spec/local/add-values`, `/api/spec/local/remove-values`; the existing proposal dialog (`#spec-propose-dialog`, `propose()` rendering, download) is reused with the response of whichever propose route was called.
- Produces (ids the e2e tests and task 6 rely on): `#spec-what` (step-1 `<select>`, first option `value=""` "Choose what is missing…", then `new-modality` (disabled, "A whole new kind of data (coming soon)"), `values` "A missing choice in a list", `metric` "A missing measurement"); panels `#spec-panel-values`, `#spec-panel-metric` (hidden until chosen); in the values panel `#spec-v-modality`, `#spec-v-list`, `#spec-v-allowed` (the allowed values, shown as text), `#spec-v-input`, `#spec-v-add`, `#spec-v-mine` (collected choices, each with a Remove button), `#spec-v-share` ("Share with the PRISM community…"), `#spec-v-use` ("Use in my open project", hidden unless `project_open`).

- [ ] **Step 1: Write the failing e2e tests:** `test_nothing_but_the_choice_is_shown_at_first` (only `#spec-what` visible, both panels hidden, "coming soon" option disabled); `test_a_missing_choice_without_a_project` (no project open: choose "A missing choice in a list", pick Biosample, "Specimen type", `#spec-v-allowed` contains `saliva`, type `sweat`, Add, it shows in `#spec-v-mine`, Share opens the dialog with `sweat` in `#spec-propose-json` and an `href` starting with the GitHub issue URL; no element contains "Open a project first"; `#spec-v-use` not visible); `test_a_missing_choice_with_a_project` (project open: `#spec-v-use` visible, clicking it writes `code/specification/patches/biosample.json`, shows "Added to this project"); `test_hostile_value_is_text` (a value `<img src=x onerror=...>` is rejected by the server rule or shown literally, never executed: assert no `img` element appears and no dialog/alert); `test_already_allowed_value_is_explained` (`saliva` -> message "already allowed").
- [ ] **Step 2: Run** `pytest tests/e2e/test_specification_contribute_flows.py -q` (how the file's fixtures start Studio is unchanged). Expected: FAIL.
- [ ] **Step 3: Rebuild the template and JS.** Template: remove the three tabs; add `#spec-what` and the two panels; keep the dialog block and add `data-catalog-url`, `data-propose-values-url`, `data-propose-metric-url` to `#spec-contribute`. JS: fetch the catalog once, fill the dropdowns from it (modality dropdown from `catalog.modalities`, list dropdown from the chosen modality's `lists`, allowed values shown under the list dropdown); keep new choices in an in-page array when no project is open and share them with one call to `propose-values`; with a project open, "Use in my open project" posts to `add-values`, and the existing "Additions in this project" rendering is kept. Message text follows the spec's plain wording. All dynamic text via `textContent`.
- [ ] **Step 4: Run** the e2e file and `pytest tests/test_specifications_workflow_wiring.py tests/test_spec_docs.py -q`. Expected: PASS.
- [ ] **Step 5: Commit** `feat: propose page starts with one choice; missing choice in a list works without a project`.

### Task 6: "A missing measurement"

**Files:**
- Modify: `app/templates/specifications_contribute.html`, `app/static/js/modules/specification/contribute.js`
- Test: `tests/e2e/test_specification_contribute_flows.py`

**Interfaces:**
- Consumes: catalog (`modalities[].metrics`, `units`, `specimens`), `/api/spec/propose-metric`, `/api/spec/local` (`unknown_metrics`) and `/api/spec/local/add-term` with a project open, the dialog from task 5.
- Produces ids: `#spec-m-modality` (kinds with `metrics == null` rendered as disabled options "(no measurement list yet)"), `#spec-m-known` (the known measurements as text), `#spec-m-listed` (`<select>`: "Choose…" / "Yes, it is there" / "No, it is still missing"), `#spec-m-yes` (message shown for "Yes"), `#spec-m-form` (shown only for "No") with `#spec-m-name`, `#spec-m-aliases` (comma separated, optional), `#spec-m-description`, `#spec-m-units` (`<select>` of `catalog.units` plus "Other…" which reveals `#spec-m-units-other`), `#spec-m-specimen` (`<select>` of `catalog.specimens`, plus the project's own added values when a project is open), `#spec-m-share`, `#spec-m-use` (hidden unless `project_open`), `#spec-m-found` ("Found in your data" list, only with a project; choosing one fills name and units and the sample type).

- [ ] **Step 1: Write the failing e2e tests:** `test_a_missing_measurement_without_a_project` (choose "A missing measurement", Biosample, known list contains `cortisol`, answering "Yes, it is there" shows `#spec-m-yes` and no form, answering "No" shows the form; fill DHEA / one-sentence description / `pg/mL` / Saliva / alias; Share -> dialog contains `prism:dhea.saliva`, link href is the GitHub issue URL; no "Open a project first" text); `test_other_kinds_are_greyed_out` (the Survey option in `#spec-m-modality` is disabled); `test_official_name_is_refused` (`cortisol` -> message names `prism:cortisol`, no dialog); `test_unit_other_is_free_text`; `test_a_missing_measurement_with_a_project` (project with the DHEA data file from `add_biosample_data`: `#spec-m-found` lists `dhea_s`, clicking it fills the form, `#spec-m-use` writes `code/specification/terms/biosample/dhea-s.json`); `test_hostile_name_and_description_are_text` (`<b>x</b>` shows literally in the dialog text and no `b` element is created).
- [ ] **Step 2: Run** the e2e file. Expected: the new tests FAIL.
- [ ] **Step 3: Implement** the panel in template and JS. "Use in my open project" posts to `add-term` using the chosen found column; when the form was typed by hand (no found column) the button is hidden (a hand-typed measurement can be shared; using it in a project needs a column, which is what "Found in your data" is for). Record that choice as a one-line `ponytail:` comment in the JS.
- [ ] **Step 4: Run** the e2e file. Expected: PASS.
- [ ] **Step 5: Commit** `feat: propose page, missing measurement with and without a project`.

### Task 7: Entry points, docs, repo checks

**Files:**
- Modify: `app/templates/base.html` (Docs dropdown, after the Specs item at line ~558), `app/templates/specifications.html` (call-to-action card above `{{ body|safe }}` when `slug == 'overview'`), `docs/studio/specifications.md` (rewrite the "Propose changes" section for the new flow), `docs/CLI_REFERENCE.md` (document `spec catalog`, `spec propose-values`, `spec propose-metric`)
- Test: `tests/test_specifications_workflow_wiring.py`, `tests/e2e/test_specification_contribute_flows.py`

**Interfaces:** consumes `url_for('specifications', slug='contribute')`. Produces nothing later tasks use.

- [ ] **Step 1: Write the failing tests:** `test_docs_menu_links_to_propose_changes` (rendered `/` page contains a Docs-menu link to `/specifications/contribute` with the text "Propose changes", present with no project open); `test_overview_has_a_call_to_action` (`/specifications` contains a link to `/specifications/contribute`); an e2e check that clicking the Docs menu entry lands on a page showing `#spec-what`.
- [ ] **Step 2: Run** `pytest tests/test_specifications_workflow_wiring.py -q` and the e2e file. Expected: FAIL.
- [ ] **Step 3: Implement** the menu item (same markup pattern as the neighbouring `navbar-flow-item`s, hint text "Tell the PRISM community what is missing"), the overview card, and the two doc updates.
- [ ] **Step 4: Run** `pytest tests -q -k "spec or contribute or cli_dispatch or symlink or compat"`, `python tests/verify_repo.py --check dual-tree-drift --no-fix`, then the full e2e file. Expected: PASS.
- [ ] **Step 5: Commit** `feat: Propose changes in the Docs menu and on the Specs overview; docs`. Then run `/ponytail:ponytail-audit`, apply what is worth it, re-run the tests, and finish the branch (merge / PR choice by the user).
