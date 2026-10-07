# LimeSurvey import: one template per questionnaire

Date: 2026-10-07 · Branch: `limesurvey-import-questionnaires`

## Problem

Importing a `.lsa`/`.lss` in the template editor ("Import Template Source")
calls `/api/survey-generate-templates` with `mode=combined`, which runs
`parse_lss_xml`. That function turns every LimeSurvey *question* into one
PRISM item and nests array rows in a hidden `Items` dict. Result for a real
multi-questionnaire survey (WHO-5, PSS, ADS, ...):

- every questionnaire shows up as a single "item" (`WHO5`, `PSS`, `ADS1`);
- the array stem (instructions + scale legend) lands in that item's
  `Description`;
- all questionnaires are mixed into one template; there is no way to pick one;
- the terminal shows only the item-registry line, nothing about what was found.

`parse_lss_xml_by_groups` / `parse_lss_xml_by_questions` (Survey Generator)
shared the nesting bug (the per-question mode was removed on 2026-10-07: no
templates of a single question). `_build_prism_template_from_parsed` (used by the
`.lsq`/`.lsg` import) already flattens rows correctly.

## Goal

The import is the exact inverse of the exporter
(`app/src/limesurvey_exporter.generate_lss`), so PRISM → LimeSurvey → PRISM
round-trips, and foreign surveys import as one clean template per
questionnaire. The GUI is the main entry point; the logic lives once in the
backend and the CLI offers the same options.

## Mapping (inverse of the exporter)

| PRISM | LimeSurvey |
|---|---|
| one template | one question group (default split) |
| `Study.OriginalName` / `Study.Description` | group name / group description |
| `Study.Instructions` | array question text (stem) |
| one item per row | array subquestions |
| standalone item | non-array question |
| `Levels` | answer options |
| metadata + original item codes | hidden `PRISMMETAg<n>` question (parsed with the existing `_extract_prismmeta` / `parse_prismmeta_codemap`) |

Defaults: `Technical.SoftwarePlatform = "LimeSurvey"`,
`Technical.AdministrationMethod = "online"`. `SoftwareVersion`, `Citation`,
`Category` are left for the user unless PRISMMETA supplies them (the `.lss`
carries only `DBVersion`, not the LimeSurvey version).

Task name: sanitized group name (e.g. `WHO-5` → `who5`), editable before save.

### Split modes

| `split` | one template per | for |
|---|---|---|
| `group` (default) | question group | exporter output; most hand-built surveys |
| `question` | top-level question (arrays keep their rows) | several questionnaires inside one group |
| `survey` | whole survey | small ad-hoc surveys |

### Item IDs

- Row code kept as-is when it is a valid identifier and unique within the
  template (`WHO1`, `PSS1`).
- Otherwise (e.g. ADS rows coded `1`..`20`) prefixed with the parent question
  code: `ADS1_1` .. `ADS1_20`. No zero-padding, no other normalization.
- If PRISMMETA has a CodeMap, the original PRISM code wins.
- Each item keeps its LimeSurvey column name (`ADS1[1]`) in its `LimeSurvey`
  block so data conversion can match response columns.

### Helper groups

A questionnaire whose only content is free text / equation / display
questions without levels (e.g. `catchsubmittedID`) is flagged
`helper: true`: still listed and loadable, marked "(helper)" in the picker.
PRISMMETA questions are never items.

## Components

1. **Backend** (`src/converters/limesurvey.py`):
   - `list_limesurvey_questionnaires(path, split="group")` →
     `[{"key", "name", "item_count", "helper"}]`
   - `limesurvey_questionnaire_template(path, key, split="group")` → template
   - both log to the terminal with the `[PRISM]` prefix: file, DBVersion,
     languages, split mode, every questionnaire with item count / array code /
     helper reason, and on load: item count, where the stem went, whether
     PRISMMETA was found and what it restored.
   - `parse_lss_xml_by_groups` reuses the same builder (fixes the Survey
     Generator). The Survey Generator's per-question mode (and
     `parse_lss_xml_by_questions`) is removed, not fixed. `parse_lss_xml` (combined) stays as
     is: data conversion depends on it.
2. **API**: `POST /api/template-editor/import-limesurvey` — thin route.
   `file` + `split` → list; `file` + `split` + `key` → template.
3. **Editor** (`app/static/js/template-editor/source-workflow.js`):
   `.lss`/`.lsa` go to the new endpoint. One questionnaire → load directly.
   More → reuse the existing group picker row ("Name (n items)", helpers
   marked) plus a "Split by: group / question / whole survey" select that
   re-fetches the list. The picker stays visible after loading so the user can
   save, then load the next one.
4. **CLI**: `prism_tools.py survey import-limesurvey` gains
   `--split group|question|survey`, `--list`, `--select KEY` (repeatable) or
   `--select all`, and `--output DIR` (one JSON per questionnaire).

Not included: a GUI "import all" button (each template should be reviewed;
the CLI's `--select all` covers bulk).

## Error handling

- No `.lss` inside the archive / invalid XML / unsupported extension → 400
  with a clear message, same text in the terminal.
- Unknown `key` → 400 listing the valid keys.
- Survey with no questions → empty list, editor says "no questionnaires found".
- Editor restores its previous state on any failure (existing
  `restoreEditorState` path).

## Testing (TDD, tests first)

Test fixtures are **synthetic** `.lss` XML built in the tests. The real
`.lsa` under `.venv/` contains participant responses and must never be
committed or copied into `tests/`.

- Backend: a group with an array (numeric row codes) + a standalone question +
  a helper group → listing (names, counts, helper flag) for each split mode;
  template has flattened items, stem in `Study.Instructions`, prefixed IDs,
  levels, Technical defaults; LS 6.x l10n tables handled.
- Round-trip: PRISM template → `generate_lss` → import → same item codes,
  levels, OriginalName, Instructions, PRISMMETA metadata.
- Survey Generator: `parse_lss_xml_by_groups` no longer returns nested `Items`.
- Terminal: `capsys` asserts the listing lines are printed.
- Route: list call and key call through the Flask test client.
- CLI: `--list` and `--select all --output DIR`.
- Editor: extend the Playwright suite in `tests/e2e` with a multi-questionnaire
  `.lss` import → picker → load.
