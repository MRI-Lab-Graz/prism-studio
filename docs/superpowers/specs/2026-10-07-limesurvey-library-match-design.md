# LimeSurvey import: match imported questionnaires against the template library

Date: 2026-10-07 · Branch: `limesurvey-import-questionnaires` (follow-up to
`2026-10-07-limesurvey-import-questionnaires-design.md`, before the merge)

## Problem

The Template Editor import now turns a LimeSurvey file into one clean PRISM
template per questionnaire, but it never asks whether the same (or nearly the
same) instrument already exists as a prepared template in the **global** or
**project** library. Users re-create templates that already exist, and the item
IDs they end up with differ from the library's.

What exists today (`app/src/converters/survey_templates.py`,
`match_against_library`) is used only by the Survey Generator's group mode and
the response conversion, not by the editor import or the CLI. It compares item
**IDs** (loosely: lowercase, non-alphanumerics stripped, run suffixes ignored),
names and abbreviations, and answer-option **keys**. It ignores **question
wording**, so a survey whose IDs differ from the library's (numeric row codes
like `ADS1_1` vs `ads_01`) is never recognised.

## Goal

When a questionnaire is chosen in the editor (or listed on the CLI), compare it
with every template in the global and project libraries by **wording**, report
the best match with a confidence and an exact **item-ID mapping**, and let the
user take the prepared template, only when every imported item maps 1:1.
GUI is the main entry point; the logic lives once in the backend and the CLI
offers the same.

## Out of scope

- Matching on questionnaire title/instructions text.
- Guessing when the wording differs a lot (below the `medium` threshold there
  is simply no match).
- Changing the Survey Generator's existing code-based matching.
- Automatic adoption: nothing is ever swapped silently.
- Writing to the global library. **This feature never writes to the global
  template folder** (a PR-based workflow for new global templates is a later,
  separate piece of work). Matching only reads it; adopting a global template
  yields an alias-annotated copy that is saved to the project library.

## Matching (new module `src/converters/library_wording_match.py`)

Standard library only (`difflib`, `re`, `html`, `unicodedata`). It reuses
`_load_global_templates`, `_load_project_templates` and
`_localize_survey_template` from `survey_templates.py` (physical file lives in
`app/src/converters/`; import it as `src.converters.survey_templates`; no
copy under top-level `src/`).

### Wording normalisation
Strip HTML tags and entities, NFKC, lowercase, drop a leading ellipsis
(`…`/`...`), keep letters/digits only (unicode aware) separated by single
spaces. Similarity = `difflib.SequenceMatcher(None, a, b).ratio()`.
Library templates are localized to the imported questionnaire's default
language before comparing (`_localize_survey_template`).

### Pairing
For one library template with `m` items and an imported questionnaire with `n`
items, compute all `n x m` similarities, sort candidate pairs by
`(-similarity, |relative position difference|)` and accept greedily while both
items are free and `similarity >= 0.85`. Templates whose item count differs by
more than a factor of two from `n` are skipped. Pairing is therefore strictly
one-to-one; position breaks ties between identical wordings.

### Levels
For each pair where both items have `Levels`: keys must be equal
(`_compare_levels`) and the label wording of each key must reach similarity
`>= 0.9`. `levels_ok` is true when all comparable pairs pass.

### Confidence
| confidence | condition |
|---|---|
| `exact` | `paired == n == m`, every similarity `>= 0.97`, `levels_ok` |
| `high` | `paired == n` (every imported item paired, library may have extra items or small wording differences), `levels_ok` |
| `medium` | `paired >= 0.7 * n`, or all paired but `levels_ok` is false, or an ID conflict (below) |
| none | anything else — no match is returned |

### ID conflict
If an imported item code equals the key of any library item but is paired to a
*different* library item (including crossed pairings), writing it as an alias
would be ambiguous, so the match is capped at `medium` (`ids_conflict = true`).

### Result
`best_library_match(template, project_path=None) -> dict | None`, the template
with the best `(confidence rank, mean similarity, project before global)`:

```
{
  "template_key", "source": "global"|"project", "template_path",
  "confidence", "paired", "imported_items", "library_items",
  "ids_identical",      # every paired imported code == library code
  "adoptable",          # confidence in (exact, high) and not ids_conflict
  "id_map": {imported_code: library_code, ...},
  "reworded": [{"imported", "library", "similarity"}],   # pairs below 0.97
  "unpaired_imported": [...], "unpaired_library": [...],
  "levels_ok": bool
}
```

`apply_library_template(match) -> dict` loads the library
template (deep copy) and, for every paired item whose codes are not
string-identical, appends the imported code to that item's existing `Aliases`
list (deduplicated). The library IDs stay authoritative; response conversion
already reads `Aliases`. Raises `ValueError` when `adoptable` is false.

## Item-ID safety rules

- A library template is only offered for adoption at `exact` or `high` with no
  ID conflict, i.e. every imported item maps 1:1.
- Existing `Aliases` lists and alias-only (`AliasOf`) entries of the library
  template count as owners of a code for the conflict check: an imported code
  owned by a different item than the one it was paired with is a conflict.
- `medium` shows the differences and offers nothing but "Import as new".
- A global template is read-only: the alias-annotated copy is saved to the
  project, as the editor already does for global templates.
- The imported codes are never lost: they end up in `Aliases`.

## Components

1. **Backend**: the module above; `list_limesurvey_questionnaires` and
   `limesurvey_questionnaire_template` stay as they are, a thin function
   `limesurvey_questionnaire_match(xml, key, split, project_path)` in
   `src/converters/limesurvey.py` builds the template (already available) and
   calls `best_library_match`. Every comparison is logged with the `[PRISM]`
   prefix, e.g.
   `[PRISM] Library match for 'ADS': ads (global) exact — 20/20 items paired, levels equal, IDs differ (ADS1_1->ads_01, ...)`
   and `[PRISM] Library match for 'Händigkeit': none`.
2. **API** (`POST /api/template-editor/import-limesurvey`, same route): new
   optional form field `project_path` (as other editor routes send it).
   - list call: each questionnaire gains `library_match`: `null` or the full
     result (the editor card shows the ID table before the user loads
     anything). The local file path is never sent to the browser.
   - key call: the response gains the same `library_match`.
   - key call with `use_library=1`: returns the library template with aliases
     (`template`, `suggested_filename`, `item_count`, `languages`,
     `library_match`); 400 `{"error"}` when not adoptable.
3. **Editor** (`app/static/js/template-editor/source-workflow.js`,
   `template_editor.html`): the picker entry shows the match, e.g.
   "ADS (20 items) · match: ads (global, exact)". Selecting an entry shows a
   small card: "Library match: ads (global) — 20/20 items, wording identical,
   levels identical, IDs differ" with an expandable ID table and two buttons,
   **Use library template** (only when `adoptable`) and **Import as new**.
   The card and buttons carry readable contrast (the validation-box rule from
   the previous change). The JS only displays what the backend returns.
4. **CLI** (`survey import-limesurvey`): `--project PATH` (optional) adds that
   project's library; `--list` prints a match line per questionnaire;
   `--select KEY --use-library` writes the library template with aliases and
   exits 1 with a clear message unless the match is adoptable. Without
   `--use-library`, `--select` writes the imported template as before.

## Error handling

- Library folders missing or unreadable: no match (logged), import unaffected.
- A broken library template file is skipped (as the existing loaders do).
- `use_library=1` without a match, or with a non-adoptable match: 400 with a
  readable message; the editor restores its previous state.
- Matching failure never blocks a plain import: wrap in a clear
  `[PRISM] Library match skipped: <reason>` line.

## Testing (TDD, tests first)

Synthetic library folders in `tmp_path` (global path via monkeypatching the
loader, project via `code/library/survey/`); no real library or survey data.

- Backend: identical wording with different IDs → `exact` + `id_map`;
  slightly reworded → `high`/`medium` by threshold; unrelated → none;
  partial coverage → `medium`; duplicate wording items stay 1:1 by position;
  differing levels cap at `medium`; crossed-ID conflict → `adoptable` false;
  German import against a bilingual library template; project beats global at
  equal score; template with item count off by more than 2x skipped.
- `apply_library_template`: aliases appended and deduplicated, identical codes
  untouched, library IDs unchanged, non-adoptable raises.
- Round trip: PRISM template → `generate_lss` → import → matches its own
  library entry `exact` with identical IDs.
- Route: list contains `library_match`; key call full details; `use_library`
  success and 400; `project_path` honoured.
- CLI: `--list` shows the match line; `--use-library` writes aliased template;
  refuses non-adoptable; `--project` honoured.
- Editor: vitest for the card rendering helpers; Playwright flow: import →
  select entry with a match → card visible and readable (contrast) → Use
  library template loads the library items with the alias; Import as new
  loads the imported ones.

## Risks

- Cost: `n x m` ratio computations per template; fine for real libraries
  (dozens to hundreds of templates, questionnaires of tens of items). The
  item-count prefilter and `quick_ratio` short-circuit keep it linear in the
  library size.
- A wording language mismatch (German import vs English-only library
  template) yields no match; this is deliberate.
- Library templates with `Aliases` already set keep them; imported codes are
  appended.
