# Project Item Mapping Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** A one-time, per-project mapping from a survey file's column names to a template's item IDs, guessed by the backend, confirmed by the user, stored in `code/item_maps/<task>.json` and used by every later conversion.

**Architecture:** One backend module `src/item_map.py` (guess, load, save, alias map). A CLI command `survey item-map` and a thin Flask blueprint call the same functions. The converter merges the stored maps into the alias map it already applies (`_apply_alias_map_to_dataframe`), so there is no second matching path. Studio shows a dialog with one pull-down per template item. Existing model to copy: `src/session_map.py` + `app/src/web/blueprints/session_map_blueprint.py` + `app/static/js/modules/converter/session-map-panel.js`.

**Tech Stack:** Python stdlib (`re`, `json`, `pathlib`), argparse, Flask, vanilla JS modules with `node --test`, Bootstrap modal already on the page.

**Spec:** `docs/superpowers/specs/2026-11-13-item-mapping-design.md`

## Global Constraints

- THE RULE: all logic in `src/item_map.py`; the route and the JS only collect input, call it and show the result. Same options and defaults in CLI and Studio.
- The template, the project library and the global library are never written.
- Nothing is saved or applied until the user confirms (`--accept` / `--set` in the CLI, Save in the dialog).
- File: `code/item_maps/<task>.json`, content `{"<template item>": "<file column>", ...}`. Plain git, never annexed.
- `<task>` is validated with `re.fullmatch(r"[A-Za-z0-9]+", task)` before it becomes a file name.
- The files are untrusted project data: an invalid file is skipped and reported (`[PRISM] WARNING ...`), never a crash.
- (Superseded by Task 7: the `--alias` file is removed; the stored map is the only item-name mapping.)
- TDD for every task: write the test, watch it fail, then implement. Import the module as `src.item_map`, no copy under `app/src/`.
- Before merge: `/ponytail:ponytail-audit`, `/code-review`, `/security-review` (the feature reads project data), then re-run the tests.
- Work on branch `feat/item-map` in a worktree (`superpowers:using-git-worktrees`).

## Review Focus

1. Two stem groups in one file (`A01..A20` and `B01..B20`): the guess must pick one group for the template, never mix them. (Task 1)
2. A stored map names a column the current file does not have: conversion continues, the entry is ignored for that file. (Task 2)
3. Two tasks' maps claim the same file column: conversion stops with a message naming both tasks and the column. (Task 2)
4. The file already uses the template's own IDs for some items and other names for the rest: identical names are paired first and are not stored. (Task 1)
5. A hand-edited or corrupt `code/item_maps/x.json` (not a dict, non-string values, item not in the template): skipped and reported, conversion and the dialog still work. (Tasks 1, 2)

---

### Task 1: `src/item_map.py` (guess, load, save)

**Files:**
- Create: `src/item_map.py`
- Test: `tests/test_item_map.py`

**Interfaces:**
- Produces:
  - `MAP_DIR = Path("code") / "item_maps"`
  - `class ItemMapError(ValueError)`
  - `template_items(template: dict) -> list[str]`: top-level keys in template order that are not in `_NON_ITEM_TOPLEVEL_KEYS` (`src.converters.survey_core`), whose value is a dict without `AliasOf`.
  - `suggest(items: list[str], columns: list[str], saved: dict[str, str] | None = None) -> list[dict]`: one row per item, in item order: `{"item": str, "column": str | None, "why": "saved" | "same" | "number" | "order" | "none"}`.
  - `map_path(project_path, task: str) -> Path` (raises `ItemMapError` for an invalid task name)
  - `load_item_map(project_path, task: str) -> dict[str, str]` (`{}` when absent or invalid; invalid prints a warning)
  - `save_item_map(project_path, task: str, mapping: dict[str, str], items: list[str]) -> Path | None`
  - `item_alias_map(project_path) -> dict[str, str]`: `{column: item}` over all `code/item_maps/*.json`.

- [ ] **Step 1: Write the failing tests** in `tests/test_item_map.py`

```python
import pytest

from src.item_map import ItemMapError, item_alias_map, load_item_map, save_item_map, suggest, template_items

ITEMS = ["ADS01", "ADS02", "ADS03"]

def _pairs(rows):
    return {r["item"]: (r["column"], r["why"]) for r in rows}

def test_same_number_pairs_whatever_the_name():
    assert _pairs(suggest(ITEMS, ["id", "A01", "A02", "A03"])) == {
        "ADS01": ("A01", "number"), "ADS02": ("A02", "number"), "ADS03": ("A03", "number")}

def test_separators_and_zero_padding_are_ignored():
    assert _pairs(suggest(ITEMS, ["ADS_1", "ADS_2", "ADS_3"]))["ADS02"] == ("ADS_2", "number")

def test_a_missing_number_falls_back_to_ascending_order():
    got = _pairs(suggest(ITEMS, ["A01", "A02", "A05"]))
    assert got["ADS03"] == ("A05", "order")

def test_no_column_left_gives_none():
    assert _pairs(suggest(ITEMS, ["A01", "A02"]))["ADS03"] == (None, "none")

def test_two_groups_are_never_mixed():
    got = _pairs(suggest(ITEMS, ["B01", "B02", "A01", "A02", "A03"]))
    assert [c for c, _ in got.values()] == ["A01", "A02", "A03"]

def test_names_with_several_numbers_pair_on_all_of_them():
    got = _pairs(suggest(["ADS1_1", "ADS1_2"], ["Q1x1", "Q1x2"]))
    assert got == {"ADS1_1": ("Q1x1", "number"), "ADS1_2": ("Q1x2", "number")}

def test_a_column_with_the_items_own_name_is_same_and_not_reused():
    got = _pairs(suggest(ITEMS, ["ADS01", "A02", "A03"]))
    assert got["ADS01"] == ("ADS01", "same") and got["ADS02"] == ("A02", "number")

def test_a_saved_entry_wins_when_its_column_is_in_the_file():
    got = _pairs(suggest(ITEMS, ["A01", "A02", "A03"], saved={"ADS01": "A03"}))
    assert got["ADS01"] == ("A03", "saved") and got["ADS03"][0] != "A03"

def test_template_items_skips_sections_and_alias_entries():
    t = {"Study": {}, "Technical": {}, "ADS01": {"Description": "x"}, "old": {"AliasOf": "ADS01"}}
    assert template_items(t) == ["ADS01"]

def test_save_then_load_round_trips_and_drops_identical_names(tmp_path):
    path = save_item_map(tmp_path, "ads", {"ADS01": "A01", "ADS02": "ADS02", "ADS03": ""}, ITEMS)
    assert path == tmp_path / "code" / "item_maps" / "ads.json"
    assert load_item_map(tmp_path, "ads") == {"ADS01": "A01"}

@pytest.mark.parametrize("mapping", [{"NOPE": "A01"}, {"ADS01": "A01", "ADS02": "A01"}])
def test_save_refuses_unknown_items_and_a_column_used_twice(tmp_path, mapping):
    with pytest.raises(ItemMapError):
        save_item_map(tmp_path, "ads", mapping, ITEMS)

@pytest.mark.parametrize("task", ["../x", "a/b", "", "ads.json"])
def test_the_task_name_cannot_leave_the_folder(tmp_path, task):
    with pytest.raises(ItemMapError):
        save_item_map(tmp_path, task, {"ADS01": "A01"}, ITEMS)

def test_saving_an_empty_mapping_removes_the_file(tmp_path):
    save_item_map(tmp_path, "ads", {"ADS01": "A01"}, ITEMS)
    assert save_item_map(tmp_path, "ads", {}, ITEMS) is None
    assert not (tmp_path / "code" / "item_maps" / "ads.json").exists()

@pytest.mark.parametrize("content", ["[1]", "{not json", '{"ADS01": 3}'])
def test_an_invalid_file_is_skipped_and_reported(tmp_path, capsys, content):
    folder = tmp_path / "code" / "item_maps"; folder.mkdir(parents=True)
    (folder / "ads.json").write_text(content, encoding="utf-8")
    assert load_item_map(tmp_path, "ads") == {} and item_alias_map(tmp_path) == {}
    assert "WARNING" in capsys.readouterr().out

def test_alias_map_is_column_to_item_over_all_tasks(tmp_path):
    save_item_map(tmp_path, "ads", {"ADS01": "A01"}, ITEMS)
    save_item_map(tmp_path, "bdi", {"BDI01": "B01"}, ["BDI01"])
    assert item_alias_map(tmp_path) == {"A01": "ADS01", "B01": "BDI01"}

def test_two_tasks_claiming_one_column_is_an_error_naming_both(tmp_path):
    save_item_map(tmp_path, "ads", {"ADS01": "X1"}, ITEMS)
    save_item_map(tmp_path, "bdi", {"BDI01": "X1"}, ["BDI01"])
    with pytest.raises(ItemMapError, match="ads.*bdi|bdi.*ads"):
        item_alias_map(tmp_path)
```

- [ ] **Step 2: Run** `python -m pytest tests/test_item_map.py -q`. Expected: FAIL, `No module named 'src.item_map'`.

- [ ] **Step 3: Implement `src/item_map.py`.** The guess, in this order (each column is used at most once):
  1. `saved`: an entry whose column is in `columns` -> `"saved"`.
  2. A column whose name equals the item -> `"same"`.
  3. Numbers of a name = the tuple of its digit runs as ints (`ADS_01` -> `(1,)`, `ADS1_3` -> `(1, 3)`). Stem of a name = lowercased, digit runs replaced by `#`, everything that is not a letter or `#` removed (`ADS_01` -> `ads#`). Group the remaining columns that have numbers by stem. Choose the one group with the most remaining items whose number tuple occurs in it; tie -> the group whose first column comes first in the file. No group shares a number tuple with any item -> choose the largest group (tie: first in file).
  4. Inside the chosen group: equal number tuple -> `"number"`.
  5. Items and group columns still left, each sorted by number tuple, paired by rank -> `"order"`.
  6. Everything else -> `column: None`, `"none"`.

  `save_item_map`: validate task, keys in `items`, values unique; drop empty values and entries where column == item; write atomically (`.json.tmp` then `replace`, as `save_session_map` does), `indent=2`, `ensure_ascii=False`, trailing newline; empty result -> delete the file, return `None`.
  `load_item_map` / `item_alias_map`: accept only a dict of non-empty str -> non-empty str; otherwise print `[PRISM] WARNING item map <path> ignored: <reason>` and treat as empty.

- [ ] **Step 4: Run** `python -m pytest tests/test_item_map.py -q`. Expected: all pass.

- [ ] **Step 5: Commit** `feat(item-map): guess, load and save a project's item mapping`

---

### Task 2: The converter uses the stored maps

**Files:**
- Modify: `app/src/converters/survey.py` (in `_convert_survey_dataframe_to_prism_dataset`, right after `alias_map = loaded.alias_map`, about line 1436)
- Test: `tests/test_item_map_conversion.py`

**Interfaces:**
- Consumes: `item_alias_map(project_path) -> dict[str, str]`, `ItemMapError` from Task 1.

- [ ] **Step 1: Write the failing tests.** Build the project with the helpers of `tests/test_survey_convert_saves_into_the_project.py` (same project layout, same call into the converter). Template task `ads` with items `ADS01`, `ADS02`; survey file with columns `participant_id`, `A01`, `A02`.

```python
def test_without_a_map_the_columns_are_unknown(project): ...
    # result.unknown_columns contains "A01" and "A02"; no ads file written
def test_with_a_stored_map_the_survey_converts(project):
    save_item_map(project, "ads", {"ADS01": "A01", "ADS02": "A02"}, ["ADS01", "ADS02"])
    # result.tasks_included == ["ads"]; the written TSV has columns ADS01, ADS02; unknown_columns has neither A01 nor A02
def test_an_entry_for_a_column_the_file_lacks_is_ignored(project):
    save_item_map(project, "ads", {"ADS01": "A01", "ADS02": "GONE"}, ["ADS01", "ADS02"])
    # converts without error; ADS01 filled
def test_an_explicit_alias_file_wins(project, tmp_path):
    # stored map ADS01<-A01, alias file line "ADS02 A01": A01 ends up as ADS02
def test_two_tasks_claiming_one_column_stops_the_conversion(project):
    # pytest.raises(ValueError, match="X1")
```

- [ ] **Step 2: Run** `python -m pytest tests/test_item_map_conversion.py -q`. Expected: the four map tests fail (columns stay unknown).

- [ ] **Step 3: Implement.** After `alias_map = loaded.alias_map`: when `project_path` is given, `alias_map = {**item_alias_map(project_path), **(alias_map or {})}` and print `[PRISM] Item map: <n> column(s) renamed from code/item_maps` when `n > 0` columns of `df` are affected. Nothing else changes; `_apply_alias_map_to_dataframe` does the renaming.

- [ ] **Step 4: Run** `python -m pytest tests/test_item_map_conversion.py tests/test_survey_alias_template_loading.py tests/test_survey_convert_options_parity.py -q`. Expected: all pass.

- [ ] **Step 5: Verify the preview path uses it too.** Run the Studio preview on the same project (the route in `app/src/web/blueprints/conversion_survey_preview_handlers.py` passes `project_path`); add one test to `tests/test_item_map_conversion.py` that posts to the preview route and asserts `A01` is not reported unknown. If the route does not pass `project_path` on some branch, fix the route to pass it (no logic in the route).

- [ ] **Step 6: Commit** `feat(item-map): conversion applies the project's stored item maps`

---

### Task 3: CLI `survey item-map`

**Files:**
- Modify: `app/src/cli/parser.py` (next to `import-limesurvey`), `app/src/cli/commands/survey.py`, the dispatch table that maps `survey_import_limesurvey` (find with `grep -rn survey_import_limesurvey app/src/cli`)
- Modify: `src/item_map.py` (add `suggest_for_project`)
- Test: `tests/test_item_map_cli.py`; add the row `(dict(command="survey", action="item-map"), "survey_item_map")` to `tests/test_cli_dispatch_routing.py` and `"item-map"` to the survey list in `tests/test_prism_tools_cli_contract.py`

**Interfaces:**
- Produces (in `src/item_map.py`, used by CLI and route alike):
  - `tasks_needing_map(project_path, columns: list[str]) -> list[str]`: project-library survey tasks (`code/library/survey/survey-<task>.json`) with at least one item that is neither a column nor covered by the stored map; sorted.
  - `suggest_for_project(project_path, task: str, columns: list[str]) -> dict`: `{"task", "rows": suggest(...), "columns": columns, "saved": bool}`; `ItemMapError` when the project has no template for the task. Prints one line per row: `[PRISM]   ADS01 <- A01  (number)`.
  - `apply_choices(project_path, task, columns, choices: dict[str, str] | None, accept: bool) -> Path | None`: with `accept` the suggested rows are the base, `choices` override them (an empty value clears a row); a chosen column not in `columns` -> `ItemMapError`; saves with `save_item_map`.
  - `read_survey_columns(path) -> list[str]`: column names as the converter sees them; reuse the table reader in `app/src/converters/survey.py` (the function ending in `raise ValueError(f"Unsupported table kind: {kind}")`), so an `.lsa` gets the same renamed columns.
- CLI flags: `--input FILE` (required), `--project DIR` (required), `--task TASK` (without it: list `tasks_needing_map`), `--accept`, `--set ITEM=COLUMN [...]` (`ITEM=` clears). Without `--accept`/`--set` nothing is written.

- [ ] **Step 1: Write the failing tests** (`cmd_survey_item_map(SimpleNamespace(...))`, project fixture as in Task 2):

```python
def test_without_task_it_lists_the_tasks_that_need_a_map(project, capsys)      # "ads" in out; no file
def test_with_task_it_prints_the_guess_and_writes_nothing(project, capsys)     # "ADS01 <- A01" in out; no code/item_maps
def test_accept_saves_the_guess(project)                                       # ads.json == {"ADS01": "A01", "ADS02": "A02"}
def test_set_overrides_one_row_of_the_accepted_guess(project)                  # --accept --set ADS02=A01 ADS01=A02
def test_set_alone_saves_only_what_was_set(project)                            # --set ADS01=A01 -> {"ADS01": "A01"}
def test_a_column_not_in_the_file_is_refused(project)                          # SystemExit; no file
def test_an_unknown_task_is_refused(project)                                   # SystemExit
```

- [ ] **Step 2: Run** `python -m pytest tests/test_item_map_cli.py tests/test_cli_dispatch_routing.py -q`. Expected: FAIL (no such command).
- [ ] **Step 3: Implement** the four functions in `src/item_map.py`, the parser entry and `cmd_survey_item_map` (prints `Error: ...` and `sys.exit(1)` on `ItemMapError`/`OSError`, as `cmd_survey_import_limesurvey` does).
- [ ] **Step 4: Run** the same command plus `tests/test_prism_tools_cli_contract.py`. Expected: all pass.
- [ ] **Step 5: Document** the command in `docs/CLI_REFERENCE.md` (survey section) and a short "Different item names in a project" paragraph in `docs/TEMPLATES.md`.
- [ ] **Step 6: Commit** `feat(item-map): survey item-map command`

---

### Task 4: Studio route and parity test

**Files:**
- Create: `app/src/web/blueprints/item_map_blueprint.py` (model: `session_map_blueprint.py`)
- Modify: `app/prism-studio.py` (register `item_map_bp` where `session_map_bp` is registered, about line 737)
- Test: `tests/test_item_map_parity.py`

**Interfaces:**
- Consumes: `read_survey_columns`, `tasks_needing_map`, `suggest_for_project`, `apply_choices`, `ItemMapError`.
- Produces:
  - `POST /api/item-map/suggest` (multipart: `file`, `project_path`, optional `task`) -> without `task`: `{"tasks": [...]}`; with `task`: the `suggest_for_project` dict.
  - `POST /api/item-map` (multipart: `file`, `project_path`, `task`, `choices` = JSON object item -> column, `accept` = `1`|absent) -> `{"ok": true, "path": "code/item_maps/<task>.json" | null}`.
  - Errors: `ItemMapError` -> 400 `{"error": str}`. Each route prints `[PRISM] CLI equivalent: python prism_tools.py survey item-map ...`.
  - The route saves the upload to a temp dir, calls the functions, nothing else. Project root via `_resolve_requested_or_current_project_root`.

- [ ] **Step 1: Write the failing parity test.** Two identical copies of the Task 2 project. Copy A: `cmd_survey_item_map(... task="ads", accept=True, set=["ADS02=A01", "ADS01=A02"])`. Copy B: `POST /api/item-map` with `accept=1`, `choices={"ADS02": "A01", "ADS01": "A02"}`. Assert the two `code/item_maps/ads.json` have identical bytes and nothing else differs between the trees (reuse `_tree` from `tests/test_cli_studio_parity_survey.py`). Second test: `suggest` returns the same rows the CLI prints. Third: an invalid task gives 400 and writes nothing.
- [ ] **Step 2: Run** `python -m pytest tests/test_item_map_parity.py -q`. Expected: FAIL (404).
- [ ] **Step 3: Implement** the blueprint and register it.
- [ ] **Step 4: Run** `python -m pytest tests/test_item_map_parity.py tests/test_cli_no_web_layer_imports.py -q`. Expected: all pass.
- [ ] **Step 5: Commit** `feat(item-map): Studio route over the same functions, parity test`

---

### Task 5: The dialog

**Files:**
- Create: `app/static/js/modules/converter/item-map-dialog.js`, `app/static/js/modules/converter/item-map-dialog.test.js`
- Modify: `app/templates/converter_survey.html` (modal markup, built from the theme macros in `app/templates/includes/ui/macros.html`), `app/static/js/modules/converter/survey-convert.js` (open it; model: how `sessionMapPanel.show(...)` is wired at about line 1284)

**Interfaces:**
- Consumes: the two routes of Task 4.
- Produces (pure, exported for the test):
  - `columnsFor(item, rows, columns)`: the columns offered in that item's pull-down = its own column plus every column no other row uses.
  - `unusedColumns(rows, columns)`: columns no row uses.
  - `choicesToSend(rows)`: `{item: column || ''}` for every row.
  - `unmappedItems(rows)`: items whose column is empty.
  - `createItemMapDialog({root, post})` with `open(file, projectPath)`; resolves `true` after a save, `false` on cancel.

- [ ] **Step 1: Write the failing JS tests** (`node --test app/static/js/modules/converter/item-map-dialog.test.js`):

```js
const rows = [{item: 'ADS01', column: 'A01', why: 'number'}, {item: 'ADS02', column: null, why: 'none'}];
const columns = ['id', 'A01', 'A02'];
assert.deepEqual(columnsFor('ADS02', rows, columns), ['id', 'A02']);      // A01 is taken
assert.deepEqual(columnsFor('ADS01', rows, columns), ['id', 'A01', 'A02']); // its own column stays
assert.deepEqual(unusedColumns(rows, columns), ['id', 'A02']);
assert.deepEqual(choicesToSend(rows), {ADS01: 'A01', ADS02: ''});
assert.deepEqual(unmappedItems(rows), ['ADS02']);
```

- [ ] **Step 2: Run it.** Expected: FAIL, module not found.
- [ ] **Step 3: Implement the dialog.** Behaviour, all of it UI state:
  - Opened by `survey-convert.js` after a preview whose response lists unknown columns: call `POST /api/item-map/suggest` without `task`; if `tasks` is empty do nothing; otherwise open with the first task selected and a task pull-down when there are several. Also a "Map item names" button next to the preview result to reopen it.
  - One row per template item: item code, a native `<select>` (options from `columnsFor`, first option "- none -"), and the reason mark: `saved`/`same`/`number` plain, `order` and `none` highlighted with the theme's warning style. Changing a select re-renders the other selects and the unused-columns line.
  - Below: "Columns not used: ..." (`unusedColumns`) and, when `unmappedItems` is not empty, "Left unmapped: ...". Save is always enabled.
  - Texts (fixed): title `Match survey columns to template "<task>"`; intro `Your file has different item names than the template. Check the guess below. It is saved for this project only (the template is not changed) and used for every later import of this survey.`; buttons `Cancel`, `Save mapping and continue`.
  - Save posts `choices` (no `accept`: what is shown is what is sent), then re-runs the preview. Cancel closes and changes nothing.
  - All project/file text goes in with `textContent`, never `innerHTML`.
- [ ] **Step 4: Run** the JS test and the page's template tests: `node --test app/static/js/modules/converter/item-map-dialog.test.js && python -m pytest tests -q -k "converter and template"`. Expected: pass.
- [ ] **Step 5: See it work.** Start Studio (`python prism-studio.py`), open a project with a prepared template, preview a file with `A01`-style columns: the dialog opens with the guess, a changed row frees and takes columns, Save writes `code/item_maps/<task>.json` and the preview then shows the task matched. Record what was seen in the commit body.
- [ ] **Step 6: Commit** `feat(item-map): dialog on the survey converter page`

---

### Task 6: "Use library template" saves the project item map (instead of writing `Aliases`)

Decision (user, 2026-11-13): one item has exactly one file column (format stays `{item: column}`, no lists); the project item map replaces `Aliases` in the template and the `--alias` file.

**Files:**
- Modify: `src/converters/library_wording_match.py` (`apply_library_template`), `src/converters/template_import.py` (`finish_import`)
- Modify: texts that say "kept as Aliases": `app/src/cli/parser.py` (`--use-library` help), `finish_import`'s print line, `app/static/js/template-editor/library-match-card.js`, `docs/LIMESURVEY_INTEGRATION.md` (~line 289), `docs/TEMPLATES.md`
- Test: `tests/test_template_import_pipeline.py` (existing use-library tests: update), `tests/test_item_map_library.py`, parity test

**Interfaces:**
- Consumes: `save_item_map(project_path, task, mapping, items)`, `template_items(template)` from `src/item_map.py`; `match["id_map"]` = `{imported_code: library_code}`.
- Produces: `apply_library_template(match)` returns the library template UNCHANGED (a copy, no `Aliases` added); `finish_import(..., use_library=True, project_path=...)` additionally saves `code/item_maps/<task>.json` = `{library_code: imported_code}` for every pair where the codes differ, `<task>` = the library template's `Study.TaskName`; payload gets `"item_map": {"task": str, "path": str, "entries": int} | None` (None when no code differed; nothing written then).

- [ ] **Step 1: Write the failing tests.** (a) `apply_library_template` result has no `Aliases` key on any item; (b) `finish_import` with `use_library=True` and a project writes `code/item_maps/ads.json == {"ADS_01": "A01", ...}` (library code -> imported code) and reports it in `payload["item_map"]`; (c) identical codes write no file and `item_map` is None; (d) `use_library=True` without a `project_path` raises `ValueError` saying a project is needed to store the item names; (e) Studio route `POST /api/template-editor/import-limesurvey` with `use_library=1` and `project_path` and the CLI `survey import-limesurvey --select KEY --use-library --project P --output D` leave identical project trees and identical template files (parity); (f) converting a survey file that uses the imported codes into the project then succeeds (the map is applied by Task 2).
- [ ] **Step 2: Run** them; expected FAIL.
- [ ] **Step 3: Implement.** Remove the `Aliases` writing from `apply_library_template`; in `finish_import`, after adopting, build the map and call `save_item_map` (one place, so CLI and Studio share it). Template task name: `template["Study"]["TaskName"]`; if a library template has none, derive it with `task_name(...)` from the library file stem and say so in a code comment. Update the printed line to `Using library template '<key>' (<source>): <n> item code(s) saved to the project item map`, the match card text and the docs. Existing templates that already contain `Aliases` keep working: matching still reads them (do not touch the reading code, the schema is vendored).
- [ ] **Step 4: Run** `python -m pytest tests/test_template_import_pipeline.py tests/test_item_map_library.py tests/test_library_wording_match.py tests/test_cli_studio_parity.py -q` and the template-editor JS tests; expected PASS.
- [ ] **Step 5: Commit** `feat(item-map): using a library template saves the project item map, not Aliases`

---

### Task 7: Remove the `--alias` file (the project item map is the only way)

**Files:**
- Modify: `app/src/cli/parser.py` (`--alias`), `app/src/cli/commands/survey.py` (`alias_file=`), `src/survey_workflow_service.py` (`alias_file`), `app/src/converters/survey.py` and `app/src/converters/survey_core.py` (`alias_file` parameters, `_read_alias_rows`, `_build_alias_map`, `_build_canonical_aliases`, `_apply_alias_file_to_dataframe`, the `alias_file` branch of `_load_survey_aliases_and_templates`), `src/survey_input_checks.py` (`alias_file=None` arguments), the Flask handlers `conversion_survey_preview_handlers.py`, `conversion_survey_convert_handlers.py`, `conversion_survey_convert_validate_handlers.py` (the `alias` upload and `alias_file=alias_path`), `docs/CLI_REFERENCE.md`, `docs/RELEASE_*`/CHANGELOG
- Test: delete or rewrite `tests/test_survey_alias_template_loading.py`, `tests/test_survey_convert_options_parity.py` (remove the `alias_file`/`alias` pair), the "explicit alias wins" test in `tests/test_item_map_conversion.py`; add `tests/test_alias_file_removed.py`

**Interfaces:**
- Consumes: `item_alias_map(project_path)` (Task 1).
- Produces: the converter's alias map is exactly `item_alias_map(project_path)` (empty without a project). `survey convert --alias` no longer exists (argparse error `unrecognized arguments`); the Flask routes ignore no field silently: a request that still sends `alias` gets HTTP 400 `{"error": "The alias file is gone; use the project item map (survey item-map)"}` (same text from the CLI for the removed flag is not needed, argparse's error is enough).
- Reading `Aliases`/`AliasOf` that already sit inside a template (`_reverse_aliases`, `AliasOf`) stays: templates and the schema are vendored, 0 official templates use them, user templates may.

- [ ] **Step 1: Write the failing tests.** (a) `parse_args(["survey","convert",...,"--alias","x.tsv"])` exits with an argparse error; (b) `POST /api/survey-convert` (use the real route names found in the handlers) with an `alias` file returns 400 with the sentence above and writes nothing; (c) a conversion with a stored map still works and the converter has no `alias_file` parameter (`inspect.signature` of `convert_survey_xlsx_to_prism_dataset` and `SurveyWorkflowService` options has none); (d) a template that carries `Aliases` inside still matches its aliased columns (guard for the reading code that stays).
- [ ] **Step 2: Run** them; expected FAIL.
- [ ] **Step 3: Delete the alias-file code listed under Files**, trace every caller with `grep -rn "alias_file\|_apply_alias_file\|_read_alias_rows\|_build_alias_map\|_build_canonical_aliases" src app tests`, and keep `_apply_alias_map_to_dataframe` (the stored map still uses it). In `_convert_survey_dataframe_to_prism_dataset` the line becomes `alias_map = item_alias_map(project_path) if project_path else None`. Remove the now-dead tests; do not leave a deprecated stub.
- [ ] **Step 4: Run** `python -m pytest tests -q -k "survey or alias or item_map or cli or parity"` and `python tests/verify_repo.py --check dual-tree-drift --no-fix`; expected PASS; quote the result.
- [ ] **Step 5: Commit** `refactor(item-map)!: remove the --alias file, the project item map replaces it`

---

### Task 8: Finish the branch

- [ ] Run `python -m pytest tests -q -k "item_map or survey or cli or parity or repo or symlink or dual_tree or template"` and the converter/template-editor JS tests; quote the result. The e2e failures seen so far are environmental: every accessibility test fails on main too (`node_modules/axe-core` missing); `test_converter_participants_flows.py::test_merge_without_conflicts_adds_new_people_and_columns_but_keeps_existing_values` fails on main as well. State that in the merge notes; do not claim e2e green.
- [ ] `/ponytail:ponytail-audit`, `/code-review`, `/security-review` on the branch; apply what is worth it; re-run the tests.
- [ ] Browser check of the dialog and of "Use library template" by the user (not run by any agent); CHANGELOG entry (breaking: `--alias` removed); `superpowers:finishing-a-development-branch`. No merge or push without the user's go-ahead.
