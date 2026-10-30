# Handoff: template manager restructure (resume on another machine)

Written 2026-10-30 at the end of a session. Everything needed to continue is in this branch
(`feat/template-manager-restructure`) and this folder; nothing depends on the machine it was built on.

## What this is

Karl asked to restructure the Template Manager GUI (5 points). It grew into a larger change because of decisions made
on the way. Authority, in order: the design `docs/superpowers/specs/2026-10-30-template-manager-restructure-design.md`
(approved by Karl), then the plan `docs/superpowers/plans/2026-10-30-template-manager-restructure.md`.

The five GUI points (the original ask):
1. General info is confusing -> sections, renamed ("Questionnaire info").
2. Bulk edit -> Items tab.
3. Tool Properties (LimeSurvey) -> out of the template editor and out of the template data; belongs to the survey export.
4. Selected item -> Items tab.
5. Only the former "Top-level" stays in General info.

## State at hand-off

Method: subagent-driven development (one implementer subagent per task, then a reviewer, fix rounds as needed).

| Task | What | State |
|---|---|---|
| 1, 1b | Spec repo: stricter survey schema (2.0.0), `Creator`, English rule, `Help`/`OtherOption`, `I18n.Languages` required | done, reviewed. **Lives only as patches in `spec-patches/`; not pushed upstream** |
| 2, 2b | Studio: sync the vendored spec; `Respondent` optional for the official library | done, reviewed |
| 3 | 103 official survey templates meet the new schema (`Technical.Language` = item-text language, provisional) | done, reviewed |
| 4 | `src/survey_export_settings.py::strip_export_settings` | done, reviewed |
| 5 | `save_template` strips export settings, returns `SavedTemplate(path, missing, removed)`, language-consistency checks, severity constants | done, reviewed (2 fix rounds) |
| 6 | Importers/fixer stop inventing answers; one function gives the schema's current version | done, reviewed (63c7bbbe, 3398511e, 6e0eee5d) |
| 2c | Rename the pinned spec tag v1.6.0 -> v1.5.1 (see below) | **not started** |
| 7 | LimeSurvey export derives question settings itself; per-export overrides only | not started |
| 8 | Converting/exporting needs a complete template (`require_complete_template`, `TemplateIncomplete`) | not started |
| 9 | Editor: `questionnaire-sections.js` (field->section map, `isMissing`, labels) | not started |
| 10 | Editor layout: Questionnaire info sections, Items tab owns Selected item + Bulk edit, no Tool Properties | not started |
| 10b | Remaining old fixtures / demo project fail the stricter schema | not started |
| 11 | Docs, CHANGELOG, `/ponytail:ponytail-audit`, final review | not started |

**Recommended order from here (Karl asked for the GUI first):** review Task 6 -> 2c -> 9 -> 10 -> 7 -> 8 -> 10b -> 11.
Task 10 only needs Task 9 for its data; the Tool Properties removal needs Task 7 so the export keeps working.

## Resume steps

1. Get the branch: `git fetch && git switch feat/template-manager-restructure` (or a worktree). Tests need
   `PRISM_SKIP_VENV_CHECK=1` where there is no `.venv`. `tests/e2e` takes 30+ minutes; skip it during development.
2. Rebuild the specification clone (the tag is not upstream):
   ```bash
   git clone https://github.com/MRI-Lab-Graz/prism-specification.git /some/dir/spec-repo
   cd /some/dir/spec-repo
   git checkout -b feat/stricter-survey-required 498173138d0a56a41d2eaf951742775f30845a25   # main at the time (v1.4.1 + later commits)
   git am <this-repo>/docs/superpowers/handoff/spec-patches/*.patch
   git tag -a v1.5.1 -m "survey 2.0.0"                # annotated; only needed locally
   ```
   If main in that repo has moved on, `git am` may need `--3way`; the three patches only touch
   `schemas/stable/survey.schema.json`, `schemas/archive/survey/1.1.1.schema.json` (new), `specs/survey.md`,
   `tests/test_survey_schema.py`. After applying: `python scripts/generate_schema_reference.py --check` and the
   repo's tests must pass (370+ at the time).
   If Karl has pushed the tag meanwhile, skip all this and sync without `--source`.
3. Task 2c (first thing): in Studio run
   `python scripts/sync_specification.py --tag v1.5.1 --source /some/dir/spec-repo`, change the pinned tag in
   `tests/test_vendored_specification.py` to `v1.5.1`, `grep -rn "v1.5.1" .` and fix the plan/spec/handoff text, run
   `python scripts/ci/check_specification_lock.py`. The schema content is byte-identical; only the tag name in
   `specification.lock.json` changes.
4. Recreate the SDD ledger (it was gitignored): first line
   `# SDD ledger — plan: docs/superpowers/plans/2026-10-30-template-manager-restructure.md`, then a line
   `Task N: complete` for tasks 1, 1b, 2, 2b, 3, 4, 5 and `Task 6: implemented (63c7bbbe, 3398511e), review pending`.
   Use `superpowers:subagent-driven-development`; its scripts `task-brief` and `review-package` work from the plan.

## Rulings made on Karl's behalf (all can be undone)

- **Tag naming (Karl):** finer-graded tags; the spec release is `v1.5.1`, not a minor bump. Schema file version is 2.0.0.
- **Nothing is pushed.** Spec patches live here; the spec repo must get a branch + tag pushed by Karl (outward-facing).
- **Official library `Technical.Language` = language of the item texts** (Karl, provisional): `en` for all 103.
  Karl reviews each questionnaire individually later. Notes of instruments possibly not English in origin:
  dass, dass21, rosenberg, cirens, gse, gsqs, zkpq, ccms, piuq, tsis, uplas. Some `Citation`/`Authors` strings
  contain garbled characters already in the library.
- **`Respondent` is required for project templates only**, optional in the official library. Official `Creator` is
  "PRISM Studio".
- **Saving always works; using needs a complete template.** `save_template` writes templates with missing required
  fields/sections and returns them as `missing` (severity `error`/`warning`, constants in
  `src/prism_template_validation.py`); other schema errors still refuse. Task 8 makes convert/export refuse
  incomplete templates and list what is missing. Cost if wrong: students can save half-done work but hit the gate at
  first conversion. Existing projects with empty `Respondent`/`Language` show validation errors after the schema sync.
- **English rule:** every Study text field that is a language object needs a non-empty `en` (nested notes included).
- **Declared languages:** `I18n.Languages` required; items/levels checked against it in
  `app/src/template_validator.py::validate_language_consistency_from_data` (`supersede_declared=True` from save).
  The editor's validate route still uses the old default (`False`): switch it in Task 10.
- **Export settings:** `strip_export_settings` maps `mandatory`, `validation.min/max`, `relevance`, `helpText`, `other`
  into generic fields and drops the rest; `LimeSurvey.columnName`/`answerCodes` stay (import side; separate decision).
- **`SchemaVersion` writers** read the schema's current version via the helper from commit 63c7bbbe, not a literal.
- Unowned old-fixture failures: Task 10b. `test_studio_version_flag` (2 failures) fails only from a long worktree path.

## Must-do notes for Task 7 (from the Task 6 review)

- `app/src/questionnaire_renderer.py:61` (`_detect_question_type`) reads `LimeSurvey.questionType`; imported templates no longer carry it, so numeric/long-text/date/hidden items would render as short-text. Give it a derivation from `DataType`/`InputType`/`Levels` (the plan lists the file; this is the reason).
- Three LimeSurvey tests (`test_limesurvey_attributes`, `test_limesurvey_fixed_answer_levels`, `test_limesurvey_row_types`) monkeypatch `strip_export_settings` so the exporter still sees an explicit `questionType`. When Task 7 removes the exporter's `questionType` branch, rewrite them to assert the derivation.

## Decided by Karl (2026-10-30), implemented as Task 6 fix round 2

Excel import writes no invented entries (no `AdministrationMethod` "paper", `SoftwarePlatform` "Paper and Pencil",
`ResponseType`, `Version` "1.0", `OriginalName` fallback). `AdministrationMethod`, `Respondent` and `SoftwarePlatform`
are set in the PROJECT copy of the survey, not globally. Still to check (Task 8/10): how the project copy gets them set
(`technical_defaults` from the project in `src/survey_template_sources.py`?) and that the gate message points there.

## OPEN DECISION (blocks Tasks 8, 9, 10): global vs project-level fields

Karl: some fields are mandatory for the template (global), others are project-specific: optional in the template,
mandatory in the project copy. Today this is only a patch: the schema has ONE required list (the project copy) and
`relax_schema_for_library_template` (src/prism_template_validation.py) removes TaskName, LicenseID, Citation,
SoftwarePlatform, AdministrationMethod, Respondent for library templates. Proposal sent to Karl, not yet answered:
- Global (mandatory in the template): OriginalName, Citation, LicenseID, Language, I18n.Languages, Creator,
  CreationDate, SchemaVersion, StimulusType, FileFormat; Category for the official library only.
- Project (optional in the template, mandatory in the project copy): Respondent, AdministrationMethod,
  SoftwarePlatform, SoftwareVersion.
- Grey zone: TaskName (file ID, derived), Version/Versions (template describes all forms, project picks one),
  ItemCount/AdministrationTime (follow from the form).
If agreed: spec patch release v1.5.2 states both lists in the schema (e.g. `x-prism.projectOnlyRequired` next to
`officialOnlyRequired`), Studio drops its own relaxation lists, Task 8 gates "template complete" (global) vs "project
copy complete" (global + project), the editor shows project fields in a separate "For this project" section only when
editing a project copy. Also check how the project copy gets these values today (`technical_defaults` in
src/survey_template_sources.py?).

## Deferred minors (from reviews)

Task 4: empty `LimeSurvey: {}` left in place; `other is True` stricter than the exporter; `relevance` compared as the
string "1" only; no tests for `min = 0`, falsy `mandatory` vs existing `True`, non-dict `validation`.
Task 5: inconsistent `path` formats in `missing` ("(template)" fallback); plain-string `Description`/`Levels`
labels are skipped by the language check when two or more languages are declared; the editor validate endpoint now
gets severity `error` for undeclared languages, check whether the JS reads `severity`.
Task 6: `I18n.Languages` of LimeSurvey imports is alphabetical, not primary-first; importers discard the strip report; the fixer's "still to fill in" note names only Language and Respondent.
Task 3: test does not assert `I18n.Languages` equals the detected languages.
Spec Task 1: `OtherOption` has no `required: ["enabled"]`; `I18n.TranslationMethod` still allows `""`.

## Before merging into main

Karl's standing rule (CLAUDE.md): run `/ponytail:ponytail-audit` on the branch, apply what is worth it, re-run tests,
then merge. Also: spec repo branch + `v1.5.1` pushed and merged first, so `specification.lock.json` names a real tag.
