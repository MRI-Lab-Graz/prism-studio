# Content Sessions Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** In a project declaring `StudyDesign.SessionLabels = "content"`, date-numbered LimeSurvey responses are named per participant from `code/session_order.tsv` (`P02: 1 -> rested` gives `ses-rested`).

**Architecture:** One new backend module `src/session_order.py` (file I/O + lookup). The date numbering in `src/participants_sessions._outcomes` gets an optional `order` and replaces numbers with names there, so survey conversion, participants import, the CLI review and the Studio review all inherit it. Downstream, the resolved names pass the existing session-map gate because `session_map_for_conversion` adds identity entries (`sleepdep -> sleepdep`) for every name in the order map of a content project.

**Tech Stack:** Python 3, pandas, Flask blueprints, vanilla JS modules, pytest.

**Spec:** `docs/superpowers/specs/2026-11-02-content-sessions-design.md`

## Global Constraints

- THE RULE (CLAUDE.md): logic in `src/`; CLI commands and Studio routes are thin adapters calling the same functions.
- Session labels are exact strings: `1` != `01`; never pad/coerce. Only `strip()` and stripping one leading `sub-` from `participant_id`.
- Session names: letters and digits only (`session_map._TARGET`, `[A-Za-z0-9]+`).
- An absent `SessionLabels` in a `multiple` project means `time`; present-but-invalid is an error; with `single` the field is ignored.
- Never guess: missing participant, missing number, count mismatch, or duplicate name stop the run before writing, listing every case.
- `code/session_order.tsv` is plain text (TSV, UTF-8, header `participant_id\tsession_number\tsession`); never annexed.
- TDD: each test is written and seen failing before the code.
- Info text (verbatim in the Projects page, schema description, CLI reference):
  "Time: sessions are waves in the same order for everyone (ses-1, ses-2 or pre/post). Content: sessions are conditions whose order differs per participant (e.g. sleepdep / rested in counterbalanced order); you then provide each participant's order, and the folders are named after the condition (ses-rested, not ses-2)."

## Review Focus

- Survey path numbers by the normalized ID (`_dup_norm_id`) but the order file uses the raw LimeSurvey ID: lookup must use the raw `res_id_col` value (test in Task 3).
- Token stored as float (`1.0`) or with whitespace: `session_label` already normalizes `1.0` -> `1`; order keys must go through the same `session_label` (test in Task 1).
- Excel-prepared file where `session_number` reads as `1.0` or the ID as int: `import_session_order` reads every column as `str` (`dtype=str`) then `session_label` (test in Task 1).
- Re-import after more waves arrive: a participant with entries 1,2 and now a third response must stop with the count message, not silently get `None` (test in Task 2).
- A `time` project with a stale `session_order.tsv` lying around: ignored completely (test in Task 2).

---

### Task 1: `src/session_order.py` + `SessionLabels` declaration

**Files:**
- Create: `src/session_order.py`
- Modify: `src/session_map.py` (add `project_session_labels`, `SESSION_LABEL_VALUES`)
- Test: `tests/test_session_order.py`

**Interfaces:**
- Produces:
  - `session_map.SESSION_LABEL_VALUES = ("time", "content")`
  - `session_map.project_session_labels(project_path) -> str` — `"time" | "content"`; raises `SessionMapError` for a present, invalid value. Only meaningful when `project_timepoints == "multiple"`; returns `"time"` otherwise.
  - `session_order.ORDER_FILE = Path("code") / "session_order.tsv"`
  - `class SessionOrderError(SessionMapError)`
  - `load_session_order(project_path) -> dict[str, dict[str, str]]` — `{raw_participant: {number: name}}`; `{}` if file absent.
  - `save_session_order(project_path, order) -> None` — atomic (tmp + `os.replace`), rows sorted by participant (natural), number (natural).
  - `set_order_entries(project_path, participant, entries: dict[str, str]) -> dict` (merge, validate, save, return full order)
  - `remove_order_entries(project_path, participant, numbers: list[str] | None = None) -> dict` (unknown participant/number raises)
  - `import_session_order(project_path, file, replace=False) -> dict` — `.tsv/.csv/.xlsx` via `pandas` with `dtype=str`; validates whole file before saving.
  - `content_session_order(project_path) -> dict | None` — the order when the project is `multiple` + `content`, else `None`.

- [ ] **Step 1: Write failing tests** in `tests/test_session_order.py` (fixture: `tmp_path` project with `project.json` `{"StudyDesign": {"Timepoints": "multiple", "SessionLabels": "content"}}`):
  - `test_round_trip`: `set_order_entries(p, "P01", {"1": "sleepdep", "2": "rested"})`; `load_session_order(p) == {"P01": {"1": "sleepdep", "2": "rested"}}`; file text starts with `"participant_id\tsession_number\tsession\n"`.
  - `test_sub_prefix_is_stripped_once`: entry for `"sub-P01"` loads as key `"P01"`; `"sub-sub-X"` loads as `"sub-X"`.
  - `test_numbers_compare_exactly`: entries `"1"` and `"01"` for one participant are two entries.
  - `test_load_errors_name_lines`: hand-written TSV with (a) missing `session` column, (b) duplicate (`P01`,`1`), (c) `P01` with `sleepdep` twice, (d) session `"sleep dep"` → each raises `SessionOrderError` whose message contains the line number (`"line 3"`).
  - `test_import_xlsx_reads_text`: xlsx with ID `1` (int) and `session_number` `1` → key `"1"`, number `"1"`.
  - `test_import_merge_and_replace`: existing `P01`; importing `P02` merges (both present); `replace=True` leaves only `P02`; an invalid file leaves the existing file unchanged.
  - `test_remove_entries`: remove one number, then whole participant; unknown participant raises.
  - `test_project_session_labels`: absent → `"time"`; `"content"` → `"content"`; `"weird"` raises `SessionMapError`; `Timepoints: "single"` + `"content"` → `"time"`.
  - `test_content_session_order_none_for_time`: `time` project with a TSV on disk → `None`.

- [ ] **Step 2: Run** `pytest tests/test_session_order.py -v` → FAIL (`ModuleNotFoundError: src.session_order`).

- [ ] **Step 3: Implement.** Reuse `session_map.session_label`, `session_map._TARGET`, `session_map._root`. Parse TSV with `csv` (stdlib) for load (line numbers are line index + 1 including header); use pandas only in `import_session_order` for xlsx/csv. Import file name: run `find src app/src -name session_order.py` first (dual-tree check) — must not exist.

- [ ] **Step 4: Run** `pytest tests/test_session_order.py -v` → PASS.

- [ ] **Step 5: Commit** `feat(sessions): per-participant session order file and SessionLabels declaration`.

### Task 2: Names in date numbering (`_outcomes`)

**Files:**
- Modify: `src/participants_sessions.py` (`_outcomes`, `number_sessions_by_date`, `session_assignment_table`)
- Test: `tests/test_participants_sessions_order.py`

**Interfaces:**
- Consumes: order dict shape from Task 1.
- Produces: new keyword args on all three functions: `order: dict | None = None, order_id_column: str | None = None` (raw ID column for the lookup; defaults to `id_column`). `class SessionsNotOrderedError(ValueError)` in `src/session_order.py` with `.problems: list[str]`. Review rows for affected participants get `reason="not in session order"`, `session=None`.

Rule (in `_outcomes`, after the cumcount numbering, before the clash check): when `order is not None`, for each participant group of rows with reason `auto`/`included`, key = `session_label` of the raw ID of the group's first row:
- key not in `order` → problem `"<key>: not in the session order"`
- `len(group) != len(order[key])` → problem `"<key>: N responses in this file, M in the session order"`
- a number not in `order[key]` → problem `"<key>: number <n> not in the session order"`
- else replace each `session` by `order[key][number]`, reason stays.
`number_sessions_by_date` raises `SessionsNotOrderedError` with all problems (message ends with: "Name these responses in the review table (`sessions set --session <name>`) or fix code/session_order.tsv."). `session_assignment_table` appends problems to warnings and marks rows instead of raising. The existing clash check then runs on resolved names (override `sleepdep` + order `sleepdep` → existing clash error).

- [ ] **Step 1: Write failing tests** (DataFrame fixture: columns `id, token, startdate, submitdate`; `P01` two completed responses Jan/Feb, `P02` two completed Jan/Feb):
  - `test_opposite_orders`: order `{"P01": {"1":"sleepdep","2":"rested"}, "P02": {"1":"rested","2":"sleepdep"}}` → P01 Jan = `sleepdep`, P02 Jan = `rested`.
  - `test_missing_participant_lists_all`: order only for P01 → `SessionsNotOrderedError`, `problems == ["P02: not in the session order"]`.
  - `test_count_mismatch`: P01 gets a third completed response → problem `"P01: 3 responses in this file, 2 in the session order"`.
  - `test_override_is_final_and_passes_count`: decisions override all P01 responses with `{"session": ...}` while P01 has no order → no error for P01.
  - `test_override_clash_after_resolution`: P01 response Feb override `sleepdep`, order maps P01 `1 -> sleepdep` and P01 has only one numbered response left with 1 entry → `ValueError` "same session label twice".
  - `test_raw_id_lookup`: grouping column `_norm` = `sub-P01`, `order_id_column="token"` → lookup by `P01` works.
  - `test_review_table_reports_instead_of_raising`: missing participant → rows for P02 have `reason == "not in session order"`, warning contains `"P02: not in the session order"`.
  - `test_no_order_unchanged`: `order=None` → labels `"1"`, `"2"` as before.

- [ ] **Step 2: Run** `pytest tests/test_participants_sessions_order.py -v` → FAIL.
- [ ] **Step 3: Implement** as described above.
- [ ] **Step 4: Run** the new file plus `pytest tests/test_participants_sessions*.py tests/test_session_assignment*.py -v` → PASS.
- [ ] **Step 5: Commit** `feat(sessions): date numbering names sessions from the session order`.

### Task 3: Wire conversions, gate, and registration

**Files:**
- Modify: `src/session_map.py` (`session_map_for_conversion`: in a content project, return `{**load_session_map(p), **{n: n for n in names in order}}`)
- Modify: `app/src/converters/survey.py:1405-1412` (use the same augmented map: call `session_map_for_conversion` semantics for `multiple`, keep the `undeclared` handling there as it is) and the `_handle_duplicate_ids` call (pass `order=content_session_order(project_path)`, `order_id_column=res_id_col`)
- Modify: `app/src/converters/survey_core.py` `_handle_duplicate_ids` (accept and pass `order`, `order_id_column` to both `number_sessions_by_date` calls)
- Modify: `src/participants_converter.py` `load_participant_source` (new kwarg `order=None`, passed through) and its caller near line 384; `app/src/cli/commands/participants.py:~290` (`_load_participant_table`) — both pass `order=content_session_order(project)` when `sessions_from_date`.
- Test: `tests/test_survey_content_sessions.py`, `tests/test_participants_content_sessions.py`

**Interfaces:**
- Consumes: `content_session_order`, `SessionsNotOrderedError` (Task 1/2).
- Produces: nothing new; behaviour only.

- [ ] **Step 1: Write failing tests** (reuse the `.lsa` fixture builder from `tests/test_survey_session_assignments.py`; project content as in Task 1):
  - survey: `test_content_project_writes_condition_folders`: P01/P02 opposite orders → files under `sub-P01/ses-sleepdep/`, `sub-P01/ses-rested/`, and P02's Jan response under `ses-rested`; no `ses-1` folder exists.
  - survey: `test_project_json_records_condition_sessions`: project.json sessions list contains `ses-sleepdep`, `ses-rested`, not `ses-1`.
  - survey: `test_missing_participant_stops_before_writing`: no `sub-*` folder written, error lists P02.
  - survey: `test_time_project_ignores_order_file`: same data, `SessionLabels` absent, global map `1->pre, 2->post`, order file present → `ses-pre`/`ses-post`.
  - participants: `test_split_columns_use_condition_names` (`--sessions-from-date`, split) → columns `age@ses-sleepdep`, `age@ses-rested`.
  - participants: `test_session_value_picks_condition`: `session_value="sleepdep"` → P01's Jan row and P02's Feb row kept.
- [ ] **Step 2: Run** both files → FAIL.
- [ ] **Step 3: Implement** the wiring listed under Files. Template-version overrides work because the augmented map's targets include the names (`_MappedSessionNormalizer._targets`); add one assertion to the survey test that a template-version selection for `ses-sleepdep` is accepted.
- [ ] **Step 4: Run** new files plus `pytest tests/test_survey_session_map.py tests/test_survey_session_assignments.py tests/test_participants_session_map.py tests/test_participants_sessions_from_date.py tests/test_importers_use_session_policy.py -v` → PASS.
- [ ] **Step 5: Commit** `feat(sessions): content projects name date-numbered sessions per participant`.

### Task 4: CLI `session-order` and review output

**Files:**
- Create: `app/src/cli/commands/session_order.py` (handlers, like `session_map.py`)
- Modify: `app/src/cli/parser.py` (subparser next to `session-map`, ~line 618; register in the dict ~line 3200), `app/src/cli/dispatch.py` (command name list line 21 and dispatch next to `session-map` line 136)
- Modify: `app/src/cli/commands/sessions.py` `cmd_sessions_review` (pass `order=content_session_order(args.project)` when `args.project`)
- Modify: `docs/CLI_REFERENCE.md` (new `session-order` section with the info text)
- Test: `tests/test_cli_session_order.py`

**Interfaces:**
- Commands: `session-order show --project P [--json]` (JSON `{"session_labels": ..., "order": {...}}`), `session-order set --project P --participant ID --number N --session NAME`, `session-order unset --project P --participant ID [--number N]`, `session-order import --project P --file F [--replace]`. Errors: print `Error: <msg>`, exit 2.

- [ ] **Step 1: Write failing tests** running the CLI entry the way `tests/test_cli_session_map.py` does: set → show `--json` round trip; import tsv; unset; invalid session name exits 2; `sessions review --json` in a content project shows `session == "sleepdep"` rows and the mismatch warning.
- [ ] **Step 2: Run** → FAIL.
- [ ] **Step 3: Implement** handlers as thin adapters.
- [ ] **Step 4: Run** `pytest tests/test_cli_session_order.py tests/test_cli_session_map.py -v` → PASS.
- [ ] **Step 5: Commit** `feat(cli): session-order commands`.

### Task 5: Studio — declaration, order panel, parity

**Files:**
- Modify: `app/schemas/stable/project.schema.json`, `app/schemas/v0.2/project.schema.json` (`StudyDesign.SessionLabels`, enum, description = info text)
- Modify: `app/templates/includes/projects/study_metadata.html` (select `smSDSessionLabels` next to `smSDTimepoints`, options "Time (waves, same order for everyone)" / "Content (conditions, order per participant)", visible info text below it, shown only when Timepoints is `multiple`, REQUIRED badge)
- Modify: `app/static/js/modules/projects/metadata.js` (load/save the field lines ~161/455; show/hide; required-field check alongside Timepoints ~2032 only when `multiple`)
- Create: `app/src/web/blueprints/session_order_blueprint.py` — `GET /api/session-order` (→ `{"session_labels", "order"}`), `POST /api/session-order` (`{participant, number, session}` → `set_order_entries`; `{participant, number, clear: true}` → `remove_order_entries`), `POST /api/session-order/import` (file upload → `import_session_order`, `replace` form flag). Register like `session_map_bp`.
- Modify: `app/src/web/blueprints/session_assignments_blueprint.py` review route: pass `order=content_session_order(root)` when `root`.
- Create: `app/static/js/modules/converter/session-order-panel.js` (+ `.test.js` like `session-map-panel.test.js`); hook into where `session-map-panel.js` is mounted: in a content project show this panel instead. Panel: upload input, table participant × number from the review rows with a text input per cell (datalist of names already in the order), highlights rows whose reason is `not in session order`, writes via the endpoints, DOM via `textContent` only.
- Test: `tests/test_session_order_api.py`, `app/static/js/modules/converter/session-order-panel.test.js`, add a case to `tests/test_cli_studio_parity.py`.

- [ ] **Step 1: Write failing tests:** API set/unset/import/show; parity: same prepared TSV via `session-order import` and via `POST /api/session-order/import` on identical project copies → byte-identical `code/session_order.tsv`; same for one `set`; JS test: panel renders rows from a review payload and a cell change POSTs `{participant, number, session}`; metadata JS test (if `metadata.js` has tests) that the select is required only for `multiple`.
- [ ] **Step 2: Run** `pytest tests/test_session_order_api.py tests/test_cli_studio_parity.py -v` and the JS test runner used for `session-map-panel.test.js` → FAIL.
- [ ] **Step 3: Implement.**
- [ ] **Step 4: Run** the same commands → PASS; then the full suite `pytest -q` and `python tests/verify_repo.py --check dual-tree-drift --no-fix`.
- [ ] **Step 5: Commit** `feat(studio): declare time/content sessions and edit the session order`.
