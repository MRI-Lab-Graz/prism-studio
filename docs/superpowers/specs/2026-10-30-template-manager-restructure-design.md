# Template manager restructure — design

Date: 2026-10-30. Status: draft for approval.

## Why

In a PRISM Studio class, students built a survey template from scratch with the Excel template, imported it, and got
lost in the editor's **General info** tab. That tab mixes four unrelated things (template metadata, the selected item,
LimeSurvey tool properties, bulk item edits), and its metadata part is ~45 schema fields in four raw sections, Study
alone ~30 in one flat list. In the same session, a student left *Respondent* empty and nothing warned: required fields
are satisfied by empty strings, and importers silently fill in answers (`Respondent: "self"`) the user never gave.

## The principle

**A survey template describes the questionnaire, in as much detail as possible, and nothing else.** It can be built
from scratch, from the Excel template, or from a LimeSurvey `.lsa`/`.lss`, but it carries no settings for any export
target. The survey export (e.g. LimeSurvey) reads the template and derives a good questionnaire from it; the user can
override that derivation for one export. Export settings are never written back into a template or the project.

## Goals

1. General info contains only questionnaire-level information, grouped so a first-time user can fill it in.
2. All item work (list, selected item, bulk edit) happens in the Items tab.
3. Templates contain no export settings; existing ones lose them.
4. Required fields mean "has a value": empty does not count, and importers do not invent answers.
5. "Edition 3.0, long form" is obvious to a student.

## Non-goals

- `LimeSurvey.columnName` and `LimeSurvey.answerCodes` stay in templates for now. They map LimeSurvey *response data*
  to items (import side: `src/converters/limesurvey.py`, `src/survey_answer_codes.py`,
  `app/src/converters/survey_templates.py`) and are a separate decision.
- The Preview tab and the Word export are unchanged.
- The stored structure of `Study`, `Technical`, `Metadata`, `I18n` is unchanged; the regrouping is presentation.

## Anti-goals

- A template that only works well with LimeSurvey.
- An editor that still lets someone save a template whose required fields are empty strings without saying so.
- Any of this implemented only in Studio (THE RULE in `CLAUDE.md`): stripping, mapping and defaults live in `src/`,
  run by the CLI, and Studio calls the same functions.

## Decided

### A. Specification (prism-specification repo, first PR, then sync the tag here)

The schemas are vendored (`specification.lock.json`), so "required" changes there:

- Required `Technical` fields (`StimulusType`, `FileFormat`, `SoftwarePlatform`, `Language`, `Respondent`,
  `AdministrationMethod`) no longer accept `""` (drop `""` from their enums; `minLength: 1` for `Language`).
- Required `Study` string fields (`TaskName`, `Citation`, `LicenseID`, and `OriginalName` in every form it takes)
  must be non-empty.
- `Metadata.Creator` becomes required and non-empty.
- `Technical.Language` means **the language the instrument was originally published in**: one tag, required, never
  `""` (an empty value no longer stands for "multilingual, see I18n"; `I18n` lists the languages).
- **Questionnaire info is always in English** (Karl, 2026-10-30): the descriptive fields (`OriginalName`,
  `Description`, `Instructions`, `Citation`, `Construct`, and the other `Study` text fields that take a language object)
  require an `en` value when they are language objects; other languages are optional. Item texts and anything that
  ends up in an export (`Description`, `Levels` of items) stay in any language.
- `Help` and `OtherOption` are added to the item schema (see B.1).

**Official library vs project templates.** `Respondent` is required for project templates only, not for the official
library: add it to the library relaxation (`LIBRARY_RELAXED_TECHNICAL_REQUIRED` in `src/prism_template_validation.py`)
instead of filling it in for every instrument. Official templates get `Creator: "PRISM Studio"`. `Language` is not
relaxed: each official template gets its instrument's original language, looked up per instrument (citation/source),
never guessed. Before tagging, validate the official library against the new schema; the release must not make it
invalid.

### B. Backend (`src/`), the only place with logic

1. **Templates hold no export settings.** One function in `src/` (next to `src/template_save.py::save_template`) removes
   an item's export settings from its `LimeSurvey` block, keeping only `columnName` and `answerCodes` (the block is
   deleted when nothing is left). Where a generic item field exists and is not already set, the value moves there
   instead of being lost:

   | `LimeSurvey.*` | becomes |
   |---|---|
   | `mandatory` | `Mandatory` |
   | `validation.min` / `validation.max` | `MinValue` / `MaxValue` |
   | `relevance` (when not `"1"`) | `Relevance` |
   | `helpText` | `Help` |
   | `other` | `OtherOption.enabled` |
   | `questionType`, `inputWidth`, `displayRows`, `hidden`, `equation`, `validation.integerOnly`, design attributes (`LS_DESIGN_ATTRIBUTES`) | dropped |

   It returns what it dropped so callers can report it ("removed LimeSurvey display settings from 12 items").
   It runs in `save_template` (so every save path, CLI and Studio, strips), in every importer that builds a template
   (LimeSurvey `.lsa`/`.lss`/`.lsq`, Excel, Pavlovia, codebook), when conversions write dataset sidecars
   (`task-*_survey.json`, which today copy the template's block), and in memory in the exporter before it derives
   anything (so an old, never re-saved file exports exactly like its stripped form). Existing files are cleaned when
   next saved; no migration command. *(Builder-check call: sidecars and in-memory strip.)*

   `Help` and `OtherOption` are read by the exporter and customizer but not in the item schema; the specification PR
   (A) adds them, so the mapping targets are specified fields. *(Builder-check call.)*
2. **Importers stop inventing answers.** Remove the presets that look like user answers: `Respondent: "self"`
   (`excel_to_survey.py`, `survey_io.py`, `limesurvey.py`, `pavlovia_import.py`, `phenotype_import.py`),
   `OriginalName` copied from `TaskName`, `LicenseID: "Other"`, `Creator: "excel_to_library.py"`, and the fixer's
   `Respondent: "self"` / `Language: "en"` (`app/src/fixer.py:491`). Unknown stays empty
   and is reported as missing. Facts stay: `StimulusType: "Questionnaire"`, `FileFormat: "tsv"`, `CreationDate` (today),
   `SchemaVersion`, and values actually present in the source (an Excel `Respondent` cell, an `.lsa` language).
3. **The export derives, the user may override.** `app/src/limesurvey_exporter.py` (moving it into `src/` is not part
   of this work) stops reading the item `LimeSurvey`
   block for export settings (`_ls_settings`, the `questionType` branch, `item_is_mandatory`, `item_has_other`,
   `item_help`) and always derives question type, mandatory, width etc. from the generic fields (`Levels`, `DataType`,
   `Mandatory`, `MinValue`/`MaxValue`, ...), which it already does when `questionType` is absent. The survey
   customizer's existing per-question `tool_overrides` (`src/survey_customizer.py`, CLI
   `survey export-lss-customized`) are the override mechanism; they are seeded from the derivation instead of from the
   template. The derivation of a question type is one backend function; the editor's own copy in
   `template-editor.js` (~line 4127, used by Preview) calls it or is deleted.

4. **A valid template is the first step of working with surveys** (Karl, 2026-10-30). Saving always works, so a
   student can save half-done work: `save_template` writes a template whose only problems are missing required
   fields and returns them as warnings (other schema errors still refuse, as today). Everything that *uses* a template
   (survey convert into a project, the LimeSurvey/Pavlovia/Word exports) refuses an invalid one and lists what is
   missing, in the CLI and Studio alike. Project validation reports empty required fields as errors, so existing
   projects with `Respondent: ""` / `Language: ""` show errors until filled. *(Save-with-warnings is my reading of
   "first have a valid template"; the gate is on use, not on save.)*

### C. Template editor (Studio, presentation only)

Tabs stay **General info · Items · Preview**.

**General info** holds only the former "Top-level" card, renamed **Questionnaire info**, as collapsible sections, the
ones with required fields open first:

1. **Identity**: `TaskName` (labelled "File ID, e.g. phq9"), `OriginalName`, `ShortName` (labelled "Abbreviation, e.g.
   PHQ-9"), `Category`, `Construct`, `Keywords`, `Description`
2. **Edition and forms**: see below
3. **Authors and citation**: `Authors`, `Citation`, `DOI`
4. **License and access**: `LicenseID` (dropdown), `LicenseURL`, `CopyrightHolder`, `Access`, `PermissionsNote`,
   `PermissionsURL`
5. **Administration**: `Respondent`, `AdministrationMethod`, `Instructions`, `AdministrationTime`, `ScoringTime`,
   `AgeRange`, `ItemCount`, and the Technical fields `Language`, `SoftwarePlatform`, `SoftwareVersion`
   (`StimulusType`/`FileFormat` are single-value and shown read-only or not at all)
6. **Quality and norms**: `Reliability`, `Validity`, `Norming`, `Subscales`
7. **Languages**: the `I18n` fields
8. **Record**: `Creator`, `CreationDate`, `SchemaVersion`
9. **Advanced** (collapsed): `TermURL`, `License` (the registry's free text), anything in the schema not placed above

The field→section map is a static list in the editor; a schema field missing from it lands in Advanced, so a new
spec field is never hidden. A field is "missing" when it is `undefined`, `null`, `""`, or a language object whose
values are all empty; missing required fields show "Required". The completion bar counts only Questionnaire info.

**Edition and forms** replaces the word "version" in the UI (one template file holds all forms):

- **Edition** (`Study.Version`): free text, "e.g. 3.0".
- **Forms** (`Study.Versions`): which item sets exist, e.g. `long`, `short`. Items choose their forms in the Items tab
  (`ApplicableVersions`, "Used in forms").
- **Response formats** (`Study.VariantDefinitions`): only when the same items are answered in different ways (e.g.
  5-point Likert vs 0–100 VAS); a small table of ID, item count, scale type, description. Items' `VariantScales` refer
  to these.

**Items** tab: the item list (add, delete, select, check), **Selected item** (opens when a row is picked), and **Bulk
edit** (applies to checked items, or all if none). No LimeSurvey fields anywhere: the Tool Properties card, its tool
tabs, the LimeSurvey part of Bulk edit and of the item form are deleted.

### D. Tests

- Backend unit tests for the strip/map function (each row of the table, `columnName`/`answerCodes` kept, report).
- Each importer: no invented `Respondent`/`OriginalName`/`LicenseID`/`Creator`; no export settings in its output.
- Exporter: a template with and without the old `LimeSurvey` block exports the same `.lss`.
- Parity (`tests/test_cli_studio_parity.py`): CLI save vs Studio save of a template with a `LimeSurvey` block write the
  same file; CLI `export-lss-customized` vs Studio customizer export write the same `.lss`.
- Editor (vitest, alongside `app/static/js/template-editor/*.test.js`): the field→section map puts every schema field
  in exactly one section; empty string counts as missing.

## Left to the builder

- Exact labels and help texts, icons, which sections start open.
- Whether `StimulusType`/`FileFormat` show read-only or are hidden.
- How Studio shows the strip report (an alert after save is enough).
- Splitting the work into PRs (the specification PR must come first).

## Open (for Karl)

- License dropdown: which few options to show first (all 17 stay reachable under "Other…")? Until answered:
  `CC-BY-4.0`, `CC0-1.0`, `Proprietary`, `Other…` (my call).
