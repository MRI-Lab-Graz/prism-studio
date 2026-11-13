# Project item mapping (survey column -> template item)

## Why
The same survey has different item IDs in different projects (mostly LimeSurvey exports: template `ADS01`,
study `ADS_01` or `A01`). Today the only routes are `Aliases` in the template (shared by every project) and
`survey convert --alias file.tsv` (CLI only, nothing stored). The user wants a **one-time** mapping per
survey, guessed by Studio, checked by the user, **stored in the project and never in the template**.

## Goals
- A guessed mapping the user reviews and corrects once; later conversions of that survey use it unasked.
- Stored per survey in the project as JSON: `code/item_maps/<task>.json`, `{"ADS01": "A01", ...}`
  (template item -> file column).
- The CLI does everything; Studio only shows the suggestion and sends the user's choices back (THE RULE).

## Non-goals / anti-goals
- No change to the template, the library or the global library.
- No second matching path: the stored map feeds the existing alias handling in the converter
  (`alias_map`, `_apply_alias_map_to_dataframe`), so a mapped column behaves exactly like an aliased one.
- No silent application: nothing is saved or applied until the user confirms.
- No drag and drop, no typed numbers (see decision below).

## Approaches considered
1. **Stored JSON map read by the existing alias path (chosen).** Template stays clean; reuses matching.
2. Write the codes into the project's copy of the template as `Aliases`. Rejected: user said not in the
   template; it drifts from the shared template.
3. Extend `--alias` to a stored TSV. Rejected: not the format wanted; nothing for the pop-up to read back.

## Design
- **`src/item_map.py`** (backend, one implementation): `suggest(template, columns)`, `load(project, task)`,
  `save(project, task, mapping)`; validation: each column used once, each key a template item.
- **Guess**: literal number first (number in the name, zero-padding and separators ignored: `A01`,
  `ADS_01`, `ADS01` are 1), wherever the number sits. Fallback: ascending order of the numbers when a name has
  several numbers or two columns claim one item. Each row carries why: `number`, `order` or `none`.
- **CLI**: `survey item-map --input <survey file> --task <task> --project <p>` prints the suggestion
  (`--list`); `--set ADS01=A01 ...` / `--accept` saves it. Same options and defaults as Studio.
- **Converter**: if `code/item_maps/<task>.json` exists it is loaded as the alias map automatically
  (an explicit `--alias` still wins). CLI and Studio read it identically.
- **Studio**: when the chosen template's items do not fit the file's columns, the converter page opens the
  pop-up (sketch below), calls the suggest command, and on Save calls the save command.
  UI state only: which rows are open, whether Save is enabled.
- **Pop-up**: one row per template item (code + start of wording), a pull-down of the file's columns,
  a "why" mark (number / order / none), and a list of unused columns. A column picked in one row leaves
  the other pull-downs (project-page pattern, `chip-list.js` helpers). Typing in the open list filters it.
  Guessed (order) and empty rows are highlighted; number-matched rows need no click. An empty row may stay
  unmapped; the dialog lists the template items left out. Cancel changes nothing.
- **Decision**: pull-down per row, not drag and drop or typed numbers (same widget as everywhere else,
  keyboard friendly, shows real column names). It is a one-time job per survey.

## Constraints
- CLI/Studio parity test (`tests/test_cli_studio_parity.py` style): both save the same JSON from identical input.
- TDD; the guess has unit tests for `A01`, `ADS_01`, `ADS1_3`, a missing number, two columns claiming one item.
- Text-format policy: the JSON is plain git, never annexed (`.json` is already covered).
- The file is project data: reading skips and reports an invalid file, never crashes.

## Left to the builder
- Exact CLI flag names; where the converter page decides "columns do not fit"; wording of the dialog.
- Whether a "shift all by 1" button is worth adding (not in this change).
