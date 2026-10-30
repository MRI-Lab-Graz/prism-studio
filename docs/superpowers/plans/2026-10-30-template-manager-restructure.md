# Template Manager Restructure Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** A survey template describes only the questionnaire (no export settings), required fields mean "filled in",
and the template editor shows questionnaire info and item work in two clean tabs.

**Architecture:** Specification change first (prism-specification repo, new tag), then Studio: one backend module
strips/maps export settings and is called by every save, import, sidecar write and export; `save_template` returns
missing required fields as warnings; everything that *uses* a template refuses an incomplete one; the editor only
regroups and hides, its logic stays in `src/`.

**Tech Stack:** Python 3.12, jsonschema (Draft 7), pytest; vanilla JS ES modules + vitest; Bootstrap 5 (Flask/Jinja).

**Spec:** `docs/superpowers/specs/2026-10-30-template-manager-restructure-design.md`

## Global Constraints

- THE RULE (`CLAUDE.md`): logic lives in `src/` (or the `app/src/` module that is already the live one), the CLI runs
  it, Studio routes and JS only call it. Check dual-tree resolution (`python3 -c "import src.X as m; print(m.__file__)"`)
  before editing any non-route module under `app/src/`.
- TDD for every task: failing test first, watched failing.
- Vendored specification files (`app/schemas/stable|v0.1|v0.2` except project/recipe/tool/registry schemas,
  `docs/specs/`) are never edited here; they arrive via `python scripts/sync_specification.py --tag <tag>`.
- `LimeSurvey.columnName` and `LimeSurvey.answerCodes` stay in templates untouched.
- Official templates: `Metadata.Creator = "PRISM Studio"`. `Respondent` required for project templates only.
- `Technical.Language` = the instrument's original publication language (one tag, never `""`).
- Questionnaire info (Study text fields given as language objects) requires an `en` value; items any language.
- Session labels and other existing invariants in `CLAUDE.md` are untouched by this work.
- Before merging into `main`: run `/ponytail:ponytail-audit`, apply what is worth it, re-run tests.

## Review Focus

1. **Official template used in a project with empty `Respondent`**: survey convert refuses with "Technical/Respondent
   is missing in code/library/survey/survey-x.json – set who answered the questionnaire", not a stack trace or a
   generic schema dump. Test in Task 8.
2. **Old template (with a full `LimeSurvey` block) exported without ever being re-saved**: exports the same `.lss` as
   its stripped twin, including mandatory/min/max/relevance/help. Test in Task 7.
3. **Language object with only an empty `en` and a filled `de`** (`{"en": "", "de": "Text"}`): counts as missing
   English, both in the schema check and in the editor. Tests in Tasks 1 and 10.
4. **Template file with no `Technical` / `Study` / `Metadata` object at all** (fresh Excel import of a sparse sheet):
   `missing_required_fields` lists the section's required fields instead of crashing. Test in Task 5.
5. **Item that is not a dict** (`"note": "free text"` at top level) or `LimeSurvey` that is not a dict: the strip
   function leaves it alone. Test in Task 4.

---

## Part 1 — prism-specification repository

### Task 1: Stricter survey schema, Creator, Help/OtherOption, English questionnaire info

**Repo:** clone `https://github.com/MRI-Lab-Graz/prism-specification` (separate PR, own tag). Locate the stable survey
schema (the file vendored here as `app/schemas/stable/survey.schema.json`) and the survey spec page (vendored as
`docs/specs/survey.md`); follow that repo's own version-bump and check scripts (vendored copies:
`scripts/specification/`).

**Files:**
- Modify: stable `survey.schema.json`, `survey.md`, that repo's changelog
- Test: that repo's schema tests (add cases as below in its test style)

**Interfaces:**
- Produces: tag `v1.5.0` (or the next minor that repo's version rules give) consumed by Task 2.

- [ ] **Step 1: Write failing schema cases** (valid/invalid instance fixtures, in that repo's style):
  - invalid: `Technical.Respondent: ""`, `Technical.Language: ""`, `Technical.AdministrationMethod: ""`,
    `Technical.SoftwarePlatform: ""`, `Study.TaskName: ""`, `Study.Citation: ""`, `Study.LicenseID: ""`,
    `Study.OriginalName: ""`, `Study.OriginalName: {"en": "", "de": "Fragebogen"}`,
    `Study.Description: {"de": "Nur Deutsch"}`, `Metadata` without `Creator`, `Metadata.Creator: ""`
  - valid: `Study.OriginalName: "Perceived Stress Scale"`, `Study.OriginalName: {"en": "PSS", "de": "PSS"}`,
    item with `"Help": {"en": "Pick one"}` and `"OtherOption": {"enabled": true}`
- [ ] **Step 2: Run that repo's tests, confirm the invalid cases currently pass validation (test fails)**
- [ ] **Step 3: Edit the schema**
  - Remove `""` from the enums of `StimulusType`, `FileFormat`, `SoftwarePlatform`, `Respondent`,
    `AdministrationMethod`; `Language`: pattern `^[a-z]{2}(-[A-Z]{2})?$` (no empty alternative), description
    "Language the instrument was originally published in".
  - `TaskName`, `Citation`, `LicenseID`: `minLength: 1` (LicenseID is an enum, already non-empty).
  - Study text fields typed `["string", "object"]` (`OriginalName`, `ShortName`, `Description`, `Instructions`,
    `Construct`, `License`, `Version`, and any other in `Study`): string branch `minLength: 1` when required; object
    branch `"required": ["en"], "properties": {"en": {"type": "string", "minLength": 1}}`.
  - `Metadata.required`: add `"Creator"`; `Creator`: `minLength: 1`, description "Who built this template (official
    library: PRISM Studio)".
  - Item schema: add `Help` (`["string", "object"]`, "Help text shown with the question") and `OtherOption`
    (`object`, `properties: {enabled: boolean, label: [string, object]}`).
- [ ] **Step 4: Run that repo's tests and checks, all pass**
- [ ] **Step 5: Update `survey.md` (Technical.Language meaning, English rule, Creator, Help, OtherOption), changelog;
  commit, PR, merge, tag**

---

### Task 1b: Declared languages in the schema (added 2026-10-30, after Task 1)

**Repo:** same clone and branch as Task 1; new commit; move the local tag again (still unpublished).

- [ ] **Step 1: Failing cases:** `I18n` absent → invalid; `I18n: {}` → invalid; `I18n.Languages: []` → invalid;
  `["en", ""]` → invalid; `["en", "de"]` → valid; `Languages` pattern without the empty alternative.
- [ ] **Step 2: Run, confirm they fail**
- [ ] **Step 3:** Add `"I18n"` to the top-level `required`; `I18n.required: ["Languages"]`; `Languages`:
  `minItems: 1`, item pattern `^[a-z]{2}(-[A-Z]{2})?$`, `uniqueItems: true`; same for `DefaultLanguage` (no empty
  alternative, optional). Update `specs/survey.md`, regenerate the reference.
- [ ] **Step 4:** full suite and checks pass; commit; move tag `v1.6.0`
- After it: re-run `python scripts/sync_specification.py --tag v1.6.0 --source <clone>` in Studio (Task 2b) and
  commit the new lock.

## Part 2 — Studio (this repository, branch `feat/template-manager-restructure`)

### Task 2: Sync the new specification; Respondent optional for library templates

**Files:**
- Modify: `src/prism_template_validation.py:22` (`LIBRARY_RELAXED_TECHNICAL_REQUIRED`)
- Modify (by script): vendored schemas, `specification.lock.json`
- Test: `tests/test_template_save.py`

**Interfaces:**
- Produces: `LIBRARY_RELAXED_TECHNICAL_REQUIRED == {"SoftwarePlatform", "AdministrationMethod", "Respondent"}`

- [ ] **Step 1: Failing tests** in `tests/test_template_save.py`:
  - `test_library_template_may_leave_respondent_out`: `relax_schema_for_library_template(load_schema("survey"))`
    has no `"Respondent"` in `properties.Technical.required`.
  - `test_project_template_needs_respondent`: the unrelaxed schema still requires it.
- [ ] **Step 2: Run** `pytest tests/test_template_save.py -v` → the first fails.
- [ ] **Step 3:** `python scripts/sync_specification.py --tag <Task 1 tag>`; add `"Respondent"` to the set.
- [ ] **Step 4: Run** `pytest tests/test_template_save.py -v` → pass. Run the full suite once
  (`pytest -q -x`) and note which tests fail because fixtures carry `""` / no `Creator`; those are fixed in the task
  that owns that code, not here (record the list in the commit message).
- [ ] **Step 5: Commit** `feat(spec): sync <tag>; Respondent optional for library templates`

### Task 3: Official survey library passes the new schema

**Files:**
- Modify: `official/library/survey/survey-*.json` (104 files; not `index.json`)
- Test: `tests/test_official_survey_library_valid.py` (create)

- [ ] **Step 1: Failing test** `test_every_official_survey_template_is_a_valid_library_template`: for each
  `official/library/survey/survey-*.json`, `validate_template_against_schema(instance=t,
  schema=relax_schema_for_library_template(load_schema("survey", ...)))` returns `[]`; parametrize by file name so
  each failure names its file.
- [ ] **Step 2: Run** → fails for ~104 files.
- [ ] **Step 3: Fix the data, never by guessing:**
  - `Metadata.Creator = "PRISM Studio"` in all.
  - `I18n.Languages` = `detect_languages_from_template(template)` (a fact from the texts; list files where it finds none).
  - Remove `Technical.Respondent` where it is `""` (library may omit it; Task 2).
  - `Technical.Language`: the instrument's original publication language, from its `Study.Citation`/`DOI`/source.
    Where it cannot be established from the file and its citation, **stop and list those files for Karl**; do not
    commit a guess.
  - Missing `en` in a Study language object: add the English text from the citation/original publication; if it
    cannot be established, list it for Karl as above.
  - `""` in other required Technical enums: remove the key when the library relaxation allows it, else list for Karl.
- [ ] **Step 4: Run** the test → pass.
- [ ] **Step 5: Commit** `fix(library): official survey templates meet the stricter specification (Creator, original language)`

### Task 4: `strip_export_settings` — templates hold no export settings

**Files:**
- Create: `src/survey_export_settings.py`
- Test: `tests/test_survey_export_settings.py`

**Interfaces:**
- Produces: `strip_export_settings(template: dict) -> tuple[dict, list[str]]` — returns a new dict (input untouched)
  and a list of human-readable removals, one per item, e.g. `"pss_01: questionType, inputWidth"`. Module constant
  `KEPT_LIMESURVEY_KEYS = ("columnName", "answerCodes")`.

- [ ] **Step 1: Failing tests** (one per row of the spec's mapping table):
  - `{"q1": {"Description": "x", "LimeSurvey": {"mandatory": False}}}` → `q1.Mandatory is False`, no `LimeSurvey`.
  - `validation: {"min": 1, "max": 7, "integerOnly": True}` → `MinValue == 1`, `MaxValue == 7`, integerOnly dropped.
  - `relevance: "q0 == 1"` → `Relevance == "q0 == 1"`; `relevance: "1"` → no `Relevance`.
  - `helpText: {"en": "h"}` → `Help == {"en": "h"}`; `other: True` → `OtherOption == {"enabled": True}`.
  - `questionType`, `inputWidth`, `displayRows`, `hidden`, `equation`, every key of `LS_DESIGN_ATTRIBUTES` → dropped.
  - existing generic value wins: item with `Mandatory: True` and `LimeSurvey.mandatory: False` keeps `True`.
  - `columnName`/`answerCodes` kept: `LimeSurvey == {"columnName": "Q1[SQ001]"}` after strip.
  - non-dict item (`"note": "text"`) and non-dict `LimeSurvey` left as they are; reserved sections untouched.
  - report: `strip_export_settings(t)[1] == ["q1: questionType, inputWidth"]`; `[]` for a clean template.
  - input dict is not mutated.
- [ ] **Step 2: Run** `pytest tests/test_survey_export_settings.py -v` → fail (module missing).
- [ ] **Step 3: Implement** in `src/survey_export_settings.py`; items = top-level keys not in the reserved sections
  (reuse the reserved set the codebase already has for survey items, e.g. the one `normalize_survey_template_for_validation`
  or `survey_customizer` uses; do not add a third list). Import `LS_DESIGN_ATTRIBUTES` from
  `app/src/limesurvey_exporter.py` only if it does not create an import cycle; otherwise move that constant into this
  module and have the exporter import it from here.
- [ ] **Step 4: Run** → pass.
- [ ] **Step 5: Commit** `feat(survey): one function strips export settings from a template (mapping to generic fields)`

### Task 5: `save_template` strips, and returns missing required fields as warnings

**Files:**
- Modify: `src/template_save.py`, `src/prism_template_validation.py`
- Modify: `app/src/cli/commands/library.py:93` (print warnings and removals), 
  `app/src/web/blueprints/tools_template_editor_blueprint.py:469` (return them in the JSON)
- Test: `tests/test_template_save.py`, `tests/test_cli_studio_parity.py`

**Interfaces:**
- Consumes: `strip_export_settings` (Task 4).
- Produces:
  - `missing_required_fields(template: dict, schema: dict) -> list[dict]` in `src/prism_template_validation.py`:
    one `{"path": "Technical/Respondent", "message": "Technical/Respondent is missing"}` per required field of
    `Technical`, `Study`, `Metadata` (per the given, possibly relaxed, schema) whose value is missing. Missing =
    absent, `None`, `""`/whitespace, or a language object whose `en` is empty.
  - `@dataclass class SavedTemplate: path: Path; missing: list[dict]; removed: list[str]` in `src/template_save.py`;
    `save_template(...) -> SavedTemplate` (same parameters as today).
  - Studio save JSON gains `"missing": [...]`, `"removed": [...]`.

- [ ] **Step 1: Failing tests:**
  - `test_saving_with_an_empty_respondent_writes_and_warns`: project save of a template with `Respondent: ""` returns
    `SavedTemplate` whose `missing` contains path `Technical/Respondent`, and the file exists.
  - `test_saving_strips_export_settings`: saved file has no `LimeSurvey.questionType`; `removed` names the item.
  - `test_other_schema_errors_still_refuse`: `Technical.Respondent: "robot"` raises `TemplateInvalid`.
  - `test_missing_required_fields_without_sections`: `missing_required_fields({}, schema)` lists `Study/TaskName`,
    `Technical/Respondent`, `Metadata/Creator` (and the rest), no exception.
  - `test_missing_english`: `Study.OriginalName == {"en": "", "de": "x"}` → `Study/OriginalName` listed.
  - Parity in `tests/test_cli_studio_parity.py`: CLI `library template-save` and the Studio save route on identical
    copies, template with a `LimeSurvey` block and empty `Respondent` → identical files and identical
    missing/removed lists.
  - `test_language_consistency`: `validate_language_consistency_from_data` (extended per spec B.5) reports an item without a `de` text when `I18n.Languages == ["en","de"]`; an undeclared `fr` key; `Technical.Language` not in Languages; Study texts only in `en` with Languages `["de"]` is fine. Its findings are part of `SavedTemplate.missing` as warnings.
- [ ] **Step 2: Run** → fail.
- [ ] **Step 3: Implement.** In `save_template`: strip right after `strip_template_editor_internal_keys`; validate;
  partition errors: an error whose `path` equals a `missing_required_fields` path (or whose message is a jsonschema
  "is a required property" for one of them) is a warning, anything else still raises `TemplateInvalid`; write; return
  `SavedTemplate`. Update both callers and existing tests that used the returned `Path` (`.path`).
- [ ] **Step 4: Run** `pytest tests/test_template_save.py tests/test_cli_studio_parity.py -v` → pass.
- [ ] **Step 5: Commit** `feat(templates): saving strips export settings and reports missing required fields instead of refusing`

### Task 6: Importers and the fixer stop inventing answers and stop writing export settings

**Files:**
- Modify: `app/src/converters/excel_to_survey.py:2063-2095` (sidecar build), `:1521`
- Modify: `app/src/converters/survey_io.py:455-475`
- Modify: `src/converters/limesurvey.py:857, :1522` and wherever it writes item `LimeSurvey` export keys
- Modify: `src/converters/pavlovia_import.py:185`, `src/converters/phenotype_import.py:108`,
  `src/survey_template_sources.py:120-130`, `app/src/fixer.py:~491`
- Modify: `app/src/converters/survey.py:204` (`_strip_internal_keys`, the dataset sidecar writer)
- Test: `tests/test_importers_do_not_invent_answers.py` (create)

**Interfaces:**
- Consumes: `strip_export_settings` (Task 4).

- [ ] **Step 1: Failing tests**, one per importer, each building a template from a minimal fixture (reuse fixtures
  already used by that importer's existing tests):
  - Excel sheet without a Respondent cell → `Technical.get("Respondent", "") == ""`; with a Respondent cell `parent`
    → `"parent"`. `Metadata.Creator == ""` (or absent); `Study.LicenseID` absent or `""`; `Study.OriginalName` not
    copied from `TaskName`.
  - every importer sets `I18n.Languages` to the languages found in its source (Excel: the sheet's language columns; `.lss`: the survey's languages; Pavlovia/phenotype: the one language it has).
  - LimeSurvey `.lss` import → no `Respondent: "self"`; items carry no `questionType`/`inputWidth`; an item that was
    mandatory in the `.lss` has `Mandatory: True`; `columnName` still present.
  - Pavlovia and phenotype import → no `Respondent: "self"`.
  - `survey_io` localization path → no `Respondent: "self"`, no `LicenseID: "Other"`, no `OriginalName = TaskName`.
  - fixer → does not write `Respondent` or `Language`; it reports them as missing instead (assert its returned
    messages mention both).
  - dataset sidecar written by `_strip_internal_keys` has no `LimeSurvey.questionType`.
  - Kept facts: Excel output still has `StimulusType: "Questionnaire"`, `FileFormat: "tsv"`, today's `CreationDate`.
- [ ] **Step 2: Run** `pytest tests/test_importers_do_not_invent_answers.py -v` → fail.
- [ ] **Step 3: Implement**: delete the presets; call `strip_export_settings` on each importer's output template and in
  `_strip_internal_keys`. Fix the existing tests listed in Task 2's commit that relied on the presets (assert the new
  behavior, do not re-add presets).
- [ ] **Step 4: Run** the new test file and `pytest -q -x` → pass.
- [ ] **Step 5: Commit** `fix(import): importers no longer invent Respondent, Creator, license or names, and write no export settings`

### Task 7: The export derives its settings; the user overrides per export

**Files:**
- Modify: `app/src/limesurvey_exporter.py` (`_ls_settings`, `item_is_mandatory`, `item_has_other`, `item_help`,
  `_determine_ls_question_type`, `generate_lss`, `generate_lss_from_customization`)
- Modify: `src/survey_customizer.py:115-150` (stop seeding `tool_overrides` from the template; add `questionType`)
- Modify: `app/static/js/survey-customizer.js:244-289` (`detectQuestionType`)
- Modify: `app/src/questionnaire_renderer.py:61-75`, `app/static/js/template-editor.js:4127-4136`
  (`detectQuestionType`: delete the "Explicit LimeSurvey questionType" branch)
- Test: `tests/test_limesurvey_export_derives.py` (create), `tests/test_cli_studio_parity.py`

**Interfaces:**
- Consumes: `strip_export_settings` (Task 4).
- Produces: `ls_question_type(q_data: dict) -> str` in `app/src/limesurvey_exporter.py` (public; the question type the
  export would use with no override). Each question in the customizer payload gains `"questionType": <that value>`.

- [ ] **Step 1: Failing tests:**
  - `test_old_block_exports_like_stripped`: `generate_lss` on a template with
    `LimeSurvey: {mandatory: False, validation: {min: 1, max: 5}, relevance: "q0==1", helpText: "h", questionType: "!"}`
    and on `strip_export_settings(template)[0]` → identical `.lss` text.
  - `test_question_type_is_derived`: item with 4 `Levels` → `ls_question_type == "L"`; 12 Levels → `"!"`;
    `DataType: "integer"` without Levels → `"N"`; a template `LimeSurvey.questionType` is ignored.
  - `test_customizer_payload_carries_derived_type_and_no_template_overrides`: payload question has
    `questionType == "L"` and `toolOverrides == {}` for an item with an old `LimeSurvey` block.
  - `test_override_wins`: `generate_lss_from_customization` with `toolOverrides: {"questionType": "!"}` writes type `!`.
  - Parity: CLI `survey export-lss-customized` vs the Studio customizer export route, same input → identical `.lss`.
  - vitest (`app/static/js/survey-customizer` has no module split; if `detectQuestionType` is not importable, extract it
    to `app/static/js/survey-customizer/question-type.js` with a test): returns `toolOverrides.questionType` if set,
    else `question.questionType`.
- [ ] **Step 2: Run** → fail.
- [ ] **Step 3: Implement**: exporter and customizer apply `strip_export_settings` in memory on load and no longer read
  `LimeSurvey` for settings (keep `columnName` reads); `item_is_mandatory` reads only `Mandatory` (default True),
  `item_has_other` only `OtherOption.enabled`, `item_help` only `Help`; `_determine_ls_question_type` loses the
  explicit-type branch; JS `detectQuestionType` becomes the two-line lookup (its mirror of the Python logic is
  deleted); the Preview/Word renderers drop their `LimeSurvey` branch.
- [ ] **Step 4: Run** the new tests, the parity test, `npx vitest run`, `pytest -q -x` → pass.
- [ ] **Step 5: Commit** `feat(export): LimeSurvey export derives question settings from the template; overrides only per export`

### Task 8: A template must be complete to be used

**Files:**
- Modify: `src/template_save.py` (add the gate next to `SavedTemplate`)
- Modify: `app/src/converters/survey.py:~1420-1430` (after `templates = loaded.templates`, gate the templates matched
  to the data), `app/src/limesurvey_exporter.py` (`generate_lss`, `generate_lss_from_customization`),
  `src/converters/pavlovia.py` (`export_to_pavlovia`), `app/src/questionnaire_renderer.py`
  (`render_questionnaire_docx`; confirm `src.questionnaire_renderer` resolves there first)
- Test: `tests/test_incomplete_template_is_not_used.py` (create)

**Interfaces:**
- Consumes: `missing_required_fields` (Task 5).
- Produces: `class TemplateIncomplete(TemplateInvalid)` and
  `require_complete_template(template: dict, *, source: str, app_root, schema_version: str = "stable") -> None` in
  `src/template_save.py`; raises `TemplateIncomplete` whose message is one line per field:
  `"<path> is missing in <source>"` (language-consistency findings are listed the same way), with `Technical/Respondent` additionally saying
  `"– set who answered the questionnaire (self, parent, clinician, …)"`. Validates against the full (unrelaxed)
  schema: a template used in a project is a project template.

- [ ] **Step 1: Failing tests:**
  - convert a one-column CSV with a project template whose `Respondent` is `""` → raises `TemplateIncomplete`, message
    contains `Technical/Respondent is missing in code/library/survey/survey-x.json`; nothing written to the dataset.
  - same with the template completed → converts.
  - `generate_lss`, `export_to_pavlovia`, `render_questionnaire_docx` each raise `TemplateIncomplete` for a template
    without `Metadata.Creator`.
  - CLI `survey convert` prints the message and exits 1 (no traceback); Studio's convert route returns it as the error
    message (assert the JSON `error` field).
- [ ] **Step 2: Run** → fail.
- [ ] **Step 3: Implement** the gate and the five calls.
- [ ] **Step 4: Run** the new tests and `pytest -q -x` → pass.
- [ ] **Step 5: Commit** `feat(survey): converting or exporting needs a complete template; the message names what is missing`

### Task 9: Editor field map and "missing" rule (JS module)

**Files:**
- Create: `app/static/js/template-editor/questionnaire-sections.js`, `.test.js` beside it

**Interfaces:**
- Produces (ES module, loaded like `technical-groups.js` at `template-editor.js:339-341`):
  - `QUESTIONNAIRE_SECTIONS`: ordered array of `{id, label, fields: string[]}` where each field is
    `"<Section>/<Field>"`. Ids, labels and fields exactly as the spec's section C list (`identity` "Identity",
    `edition` "Edition and forms" = `Study/Version`, `Study/Versions`, `Study/VariantDefinitions`, `authors`
    "Authors and citation", `license` "License and access", `administration` "Administration", `quality`
    "Quality and norms", `languages` "Languages" = all `I18n/*`, `record` "Record", `advanced` "Advanced" =
    `Study/TermURL`, `Study/License`).
  - `assignFields(schemaFields: string[]) -> Map<string, string[]>`: every schema field in exactly one section, in
    section order; unknown fields go to `advanced`; `Technical/StimulusType` and `Technical/FileFormat` go nowhere.
  - `isMissing(value) -> boolean`: `undefined`, `null`, whitespace string, empty array, or an object whose `en` is
    empty/absent.
  - `FIELD_LABELS`: `{"Study/TaskName": "File ID (e.g. phq9)", "Study/ShortName": "Abbreviation (e.g. PHQ-9)",
    "Study/Version": "Edition (e.g. 3.0)", "Study/Versions": "Forms (e.g. long, short)",
    "Study/VariantDefinitions": "Response formats", "ITEM/ApplicableVersions": "Used in forms"}` (the item form uses
    the `ITEM/` key).
  - `LICENSE_FIRST = ["CC-BY-4.0", "CC0-1.0", "Proprietary"]` (the rest of the schema enum follows under "Other…").

- [ ] **Step 1: Failing vitest tests**: every field of the real stable survey schema's `Technical`, `Study`,
  `Metadata`, `I18n` (read the JSON in the test) appears exactly once across `assignFields` except
  `StimulusType`/`FileFormat`; a made-up `Study/NewThing` lands in `advanced`; `isMissing` for `""`, `"  "`, `[]`,
  `{en: "", de: "x"}`, `{de: "x"}` is true and for `"x"`, `{en: "x"}`, `0`, `false` is false.
- [ ] **Step 2: Run** `npx vitest run app/static/js/template-editor/questionnaire-sections.test.js` → fail.
- [ ] **Step 3: Implement.**
- [ ] **Step 4: Run** → pass.
- [ ] **Step 5: Commit** `feat(editor): questionnaire info sections and the missing-value rule`

### Task 10: Editor layout — Questionnaire info and Items

**Files:**
- Modify: `app/templates/template_editor.html:176-306`
- Modify: `app/static/js/template-editor.js` (`renderTopLevel` 3599, `renderSection` 2658, `setItemsPanelVisible`
  203, `focusField` ~405, `renderBulkEdit` 3076 LimeSurvey part ~3160-3300, `renderToolProperties` 3303-3597,
  `renderCompletionBar` 534, `renderFieldInRow` missing check 2587, `RESERVED_TOPLEVEL`/`RESERVED_SECTIONS` drop
  `'LimeSurvey'`, `LS_QUESTION_TYPES` if unused)
- Test: vitest for `isMissing` use is in Task 9; this task is verified in the running app (Step 4)

**Interfaces:**
- Consumes: `questionnaire-sections.js` (Task 9); Studio save JSON `missing`/`removed` (Task 5).

- [ ] **Step 1: Failing test**: extend an existing editor e2e/smoke test if the repo has one for the template editor
  (search `tests/` for `template_editor`); assert the page has no `#toolPropertiesSection`, and the card
  `#topLevelPanel` header reads "Questionnaire info". If no such test exists, add a Flask test-client test that GETs
  the editor page and asserts both on the HTML.
- [ ] **Step 2: Run** → fail.
- [ ] **Step 3: Implement**:
  - HTML: delete the Tool Properties card; rename "Top-level" → "Questionnaire info"; the Selected item and Bulk edit
    cards are visible only in Items mode (`setItemsPanelVisible(true)`), Questionnaire info only in General info mode.
  - `renderTopLevel`: render one collapsible group per `assignFields` section via the existing `renderSectionGroup`;
    a section opens by default when it has a required field that `isMissing`; use `FIELD_LABELS` and the
    `LICENSE_FIRST` ordering for the `LicenseID` select.
  - `renderFieldInRow`: "Required" hint when `isMissing(value)` (replaces the `undefined/null` check at 2587).
  - Completion bar counts only Questionnaire info fields.
  - Delete `renderToolProperties`, the LimeSurvey part of Bulk edit, and every `toolProperties*` reference.
  - After save, show `removed` and `missing` from the response in the existing alert.
- [ ] **Step 4: Verify in the running app** (use the `run` skill): import the class's Excel template
  (`official/` or `docs/` example), confirm: General info shows only Questionnaire info in sections; empty Respondent
  shows "Required"; Items tab shows list + Selected item + Bulk edit; no LimeSurvey fields anywhere; save shows the
  missing list; Preview still renders. Then run the Task 10 test → pass, and `npx vitest run`.
- [ ] **Step 5: Commit** `feat(editor): General info is questionnaire info only; item work lives in Items; no tool properties`

### Task 10b: Remaining fixtures and the demo project (added after Task 2's failure inventory)

**Files:** the test groups the Task 2 report lists as unowned: `tests/test_save_gate_battery.py` (demo project sidecars
lack `Metadata.Creator`/`I18n.Languages`), `test_modality_contribution.py`, `test_validation_matrix.py`,
`test_validation_matrix_cli.py`, `test_cli_personal_library.py`, `test_template_editor_personal.py`,
`test_cli_library_template_save_delete.py`, plus whatever the full suite still fails after Tasks 3-10.

- [ ] **Step 1:** `PRISM_SKIP_VENV_CHECK=1 pytest -q --ignore=tests/e2e` and list every failure.
- [ ] **Step 2:** Fix each by giving the fixture/demo data the required values (`Creator`, `I18n.Languages`,
  `Respondent`, `Language`, current `SchemaVersion`), never by relaxing the schema or the tests' assertions.
  `test_studio_version_flag` fails only from the long worktree path; do not chase it.
- [ ] **Step 3:** Suite green (e2e excluded; run `tests/e2e` once on the finished branch if time allows).
- [ ] **Step 4: Commit** `test: fixtures and demo project meet the stricter specification`

### Task 11: Docs and finishing

**Files:**
- Modify: `CHANGELOG.md`, the template-editor user docs that mention Tool Properties or "Top-level" (search `docs/`)

- [ ] **Step 1:** `grep -rn "Tool Properties\|Top-level" docs/ README.md` → update each hit to the new names; add a
  CHANGELOG entry (templates no longer carry LimeSurvey export settings; required fields must be filled; convert/export
  need a complete template).
- [ ] **Step 2:** `pytest -q`, `npx vitest run`, `python tests/verify_repo.py --check dual-tree-drift --no-fix` → all pass.
- [ ] **Step 3:** Run `/ponytail:ponytail-audit` on the branch, apply what is worth it, re-run Step 2.
- [ ] **Step 4: Commit** `docs: template manager restructure`
