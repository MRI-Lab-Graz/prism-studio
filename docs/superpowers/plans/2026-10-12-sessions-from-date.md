# Sessions from Acquisition Date Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Repeated-measures LimeSurvey files (one row per participant per wave, no session column) get a `session` column numbered "1", "2", ... per participant by acquisition date, in participants import (CLI + GUI) and survey conversion.

**Architecture:** One backend function `number_sessions_by_date` in `src/participants_sessions.py`. One source loader `load_participant_source` in `src/participants_converter.py` that every participants entry point (converter, merge re-read, CLI, GUI) calls, so `.lsa` reading and session numbering live in one place. The derived `session` column then flows into the existing session pick / session map / merge session-resolution logic unchanged. Survey conversion's `duplicate_handling="sessions"` calls the same function.

**Tech Stack:** Python 3, pandas, argparse, Flask, vanilla JS, pytest.

**Spec:** `docs/superpowers/specs/2026-10-12-sessions-from-date-design.md`

## Global Constraints

- Session labels are free-form strings, compared exactly, never normalized or zero-padded (CLAUDE.md). Generated labels are `"1"`, `"2"`, ... as `str`.
- Order only: no time windows, rows are never dropped or merged.
- Missing/unparseable date after fallback -> `ValueError`, never a guess.
- Existing `session` column in the source -> `ValueError`, never overwritten.
- In a longitudinal project every generated label must still pass the session map (`src/session_map.py`); unmapped labels fail.
- One implementation: logic in `src/`, CLI and GUI only pass the option through (CLAUDE.md).
- Before editing anything under `app/src/`, run the dual-tree check from CLAUDE.md (`find src -name '<file>.py'`, `python3 -c "import src.<mod> as m; print(m.__file__)"`).
- TDD: every task writes the failing test first and watches it fail.

## Review Focus

1. Mixed date formats in one column (`2026-03-01` next to `2026-03-01 10:00:00`; pandas 3 infers one format and silently turns the rest into NaT unless `format="mixed"`), and empty `startdate` cells that must fall back to `datestamp`. -> Task 1 tests `test_mixed_date_formats_parse` and `test_startdate_empty_falls_back_to_datestamp`.
2. Two responses of one ID with identical timestamps: order must be deterministic (stable sort keeps file order). -> Task 1 test `test_identical_dates_keep_file_order`.
3. IDs read as numbers (`1.0`) vs strings (`"1"`): grouping must use the same string form for all rows of an ID. -> Task 1 test `test_float_ids_group_with_string_ids`.
4. Option set but no ID column chosen yet (GUI preview with auto-detect): clear error, not a crash. -> Task 2 test `test_sessions_from_date_requires_id_column`.
5. Longitudinal project with generated labels not in the session map: conversion fails with the session-map error. -> Task 5 test `test_sessions_mode_in_longitudinal_project_requires_mapping`.

---

### Task 1: `number_sessions_by_date`

**Files:**
- Modify: `src/participants_sessions.py` (append function)
- Test: `tests/test_number_sessions_by_date.py` (create)

**Interfaces:**
- Produces: `number_sessions_by_date(df: pd.DataFrame, id_column: str, date_column: str = "startdate", session_column: str = "session") -> tuple[pd.DataFrame, list[str]]`. Returns a copy sorted by ID then date, with `session_column` holding `"1"`, `"2"`, ... per ID, plus warning strings.

- [ ] **Step 1: Write the failing tests**

```python
"""number_sessions_by_date: session labels from acquisition-date order."""

import pandas as pd
import pytest

from src.participants_sessions import number_sessions_by_date


def _df(rows):
    return pd.DataFrame(rows, columns=["token", "startdate", "datestamp", "submitdate", "lastpage"])


def test_sessions_follow_date_not_file_order():
    df = _df([
        ["a", "2026-09-01 10:00:00", "", "2026-09-01 10:20:00", "5"],
        ["a", "2026-03-01 10:00:00", "", "2026-03-01 10:20:00", "5"],
        ["b", "2026-03-02 10:00:00", "", "2026-03-02 10:20:00", "5"],
    ])
    out, _ = number_sessions_by_date(df, "token")
    got = {(r.token, r.startdate[:7]): r.session for r in out.itertuples()}
    assert got == {("a", "2026-03"): "1", ("a", "2026-09"): "2", ("b", "2026-03"): "1"}


def test_identical_dates_keep_file_order():
    df = _df([
        ["a", "2026-03-01 10:00:00", "", "x", "first"],
        ["a", "2026-03-01 10:00:00", "", "x", "second"],
    ])
    out, _ = number_sessions_by_date(df, "token")
    assert list(zip(out["lastpage"], out["session"])) == [("first", "1"), ("second", "2")]


def test_float_ids_group_with_string_ids():
    df = pd.DataFrame({"id": [1.0, "1"], "startdate": ["2026-01-01", "2026-02-01"]})
    out, _ = number_sessions_by_date(df, "id")
    assert list(out["session"]) == ["1", "2"]


def test_startdate_empty_falls_back_to_datestamp():
    df = _df([
        ["a", "", "2026-09-01 10:00:00", "x", "5"],
        ["a", "2026-03-01 10:00:00", "", "x", "5"],
    ])
    out, _ = number_sessions_by_date(df, "token")
    assert list(out["datestamp"]) == ["", "2026-09-01 10:00:00"]
    assert list(out["session"]) == ["1", "2"]


def test_mixed_date_formats_parse():
    df = _df([
        ["a", "2026-09-01 10:00:00", "", "x", "1"],
        ["a", "2026-03-01", "", "x", "1"],
    ])
    out, _ = number_sessions_by_date(df, "token")
    assert list(out["session"]) == ["1", "2"]
    assert out["startdate"].iloc[0] == "2026-03-01"


def test_missing_date_is_an_error():
    df = _df([["a", "", "", "", "1"]])
    with pytest.raises(ValueError, match="a"):
        number_sessions_by_date(df, "token")


def test_existing_session_column_is_an_error():
    df = pd.DataFrame({"token": ["a"], "startdate": ["2026-01-01"], "session": ["pre"]})
    with pytest.raises(ValueError, match="session"):
        number_sessions_by_date(df, "token")


def test_incomplete_runs_are_flagged():
    df = _df([
        ["a", "2026-03-01", "", "", "3"],
        ["a", "2026-03-02", "", "2026-03-02", "9"],
    ])
    _, warnings = number_sessions_by_date(df, "token")
    text = "\n".join(warnings)
    assert "a" in text and "session 1" in text and "lastpage 3" in text


def test_uneven_session_counts_are_reported():
    df = _df([
        ["a", "2026-03-01", "", "x", "1"],
        ["a", "2026-09-01", "", "x", "1"],
        ["b", "2026-03-01", "", "x", "1"],
    ])
    _, warnings = number_sessions_by_date(df, "token")
    assert any("1 IDs x 2 sessions" in w and "1 x 1" in w for w in warnings)


def test_even_counts_complete_runs_give_no_warnings():
    df = _df([["a", "2026-03-01", "", "x", "1"], ["b", "2026-03-01", "", "x", "1"]])
    _, warnings = number_sessions_by_date(df, "token")
    assert warnings == []
```

- [ ] **Step 2: Run to verify they fail**

Run: `python3 -m pytest tests/test_number_sessions_by_date.py -q`
Expected: collection error `ImportError: cannot import name 'number_sessions_by_date'`.

- [ ] **Step 3: Implement** (append to `src/participants_sessions.py`)

```python
def number_sessions_by_date(
    df: pd.DataFrame,
    id_column: str,
    date_column: str = "startdate",
    session_column: str = "session",
) -> tuple[pd.DataFrame, list[str]]:
    """Number each ID's rows "1", "2", ... by acquisition date (earliest first).

    For repeated-measures exports without a session indicator (LimeSurvey).
    Order only: rows are never dropped or merged. An empty ``startdate`` falls
    back to the row's ``datestamp``; a row still without a date is an error.
    Warnings flag incomplete runs (empty ``submitdate``) and uneven session counts.
    """
    if session_column in df.columns:
        raise ValueError(
            f"The file already has a '{session_column}' column; use it as the session column instead."
        )
    for column in (id_column, date_column):
        if column not in df.columns:
            raise ValueError(f"Column '{column}' not found in the file")

    ids = df[id_column].map(session_label)  # same string form for 1.0 and "1"
    def _parse(column):
        # format="mixed": otherwise pandas infers one format from the first value
        # and silently turns "2026-03-01 10:00:00" after "2026-03-01" into NaT.
        return pd.to_datetime(df[column].replace("", None), errors="coerce", format="mixed")

    dates = _parse(date_column)
    if date_column == "startdate" and "datestamp" in df.columns:
        dates = dates.fillna(_parse("datestamp"))
    undated = sorted(set(ids[dates.isna()]))
    if undated:
        raise ValueError(
            f"No usable '{date_column}' for ID(s): {', '.join(undated[:10])}. "
            "Fix these responses in LimeSurvey before numbering sessions."
        )

    out = df.assign(_id=ids, _date=dates).sort_values(["_id", "_date"], kind="stable")
    out[session_column] = (out.groupby("_id").cumcount() + 1).astype(str)

    warnings: list[str] = []
    if "submitdate" in out.columns:
        incomplete = out[out["submitdate"].map(session_label) == ""]
        for _, row in incomplete.iterrows():  # not itertuples: it renames "_id"
            lastpage = session_label(row.get("lastpage", ""))
            warnings.append(
                f"Incomplete run: ID {row['_id']}, session {row[session_column]}"
                + (f", lastpage {lastpage}" if lastpage else "")
            )
    counts = out.groupby("_id").size().value_counts().sort_index(ascending=False)
    if len(counts) > 1:
        parts = [f"{n} IDs x {k} sessions" if i == 0 else f"{n} x {k}"
                 for i, (k, n) in enumerate(counts.items())]
        warnings.append("Uneven session counts: " + ", ".join(parts))

    return out.drop(columns=["_id", "_date"]).reset_index(drop=True), warnings
```

Note: `counts` is indexed by sessions-per-ID (k) with the number of IDs (n) as value; sorted descending so the largest session count comes first, matching `"1 IDs x 2 sessions, 1 x 1"`.

- [ ] **Step 4: Run to verify they pass**

Run: `python3 -m pytest tests/test_number_sessions_by_date.py -q`
Expected: 10 passed.

- [ ] **Step 5: Commit**

```bash
git add src/participants_sessions.py tests/test_number_sessions_by_date.py
git commit -m "feat(sessions): number repeated IDs into sessions by acquisition date"
```

---

### Task 2: One participants source loader (`load_participant_source`)

**Files:**
- Modify: `src/participants_converter.py` (new module-level function; `convert_participant_data` loading block ~lines 361-405 calls it; new kwarg `sessions_from_date`)
- Test: `tests/test_participants_sessions_from_date.py` (create)

**Interfaces:**
- Consumes: `number_sessions_by_date` (Task 1).
- Produces:
  - `load_participant_source(source_path: Path, *, separator: str | None = None, sheet: str | int = 0, sessions_from_date: str | None = None, id_column: str | None = None) -> tuple[pd.DataFrame, list[str]]` — reads `.lsa` via `src.converters.survey._read_lsa_as_dataframe`, everything else via `_read_tabular_file` (same `kind_map` as today, unknown extension -> `"csv"`); returns `(df, warnings)` where warnings = file-reader warnings + numbering warnings. `separator=None` means auto. If `sessions_from_date` is set and `id_column` is empty -> `ValueError("Select the ID column before numbering sessions by date.")`.
  - `ParticipantsConverter.convert_participant_data(..., sessions_from_date: str | None = None)` — passes `id_column=mapping["mappings"]["participant_id"]["source_column"]` (first mapping whose `standard_variable == "participant_id"`).

- [ ] **Step 1: Write the failing tests**

```python
"""Participants import: sessions numbered from the acquisition date."""

import pandas as pd
import pytest

from src.participants_converter import ParticipantsConverter, load_participant_source

ROWS = [
    {"token": "a", "startdate": "2026-09-01 10:00:00", "submitdate": "x", "age": 31},
    {"token": "a", "startdate": "2026-03-01 10:00:00", "submitdate": "x", "age": 30},
    {"token": "b", "startdate": "2026-03-02 10:00:00", "submitdate": "x", "age": 40},
]
MAPPING = {
    "version": "1.0",
    "mappings": {
        "participant_id": {"source_column": "token", "standard_variable": "participant_id", "type": "string"},
        "age": {"source_column": "age", "standard_variable": "age", "type": "string"},
    },
}


def _csv(tmp_path):
    path = tmp_path / "in.csv"
    pd.DataFrame(ROWS).to_csv(path, index=False)
    return path


def test_loader_adds_session_column(tmp_path):
    df, _ = load_participant_source(_csv(tmp_path), sessions_from_date="startdate", id_column="token")
    assert sorted(zip(df["token"], df["session"])) == [("a", "1"), ("a", "2"), ("b", "1")]


def test_sessions_from_date_requires_id_column(tmp_path):
    with pytest.raises(ValueError, match="ID column"):
        load_participant_source(_csv(tmp_path), sessions_from_date="startdate")


def test_convert_picks_one_dated_session(tmp_path):
    ok, df, messages = ParticipantsConverter(tmp_path).convert_participant_data(
        _csv(tmp_path), MAPPING, output_file=tmp_path / "participants.tsv",
        sessions_from_date="startdate", session_column="session", session_value="1",
        reject_conflicting_repeats=True,
    )
    assert ok, messages
    assert dict(zip(df["participant_id"], df["age"].astype(str))) == {"sub-a": "30", "sub-b": "40"}
```

- [ ] **Step 2: Run to verify they fail**

Run: `python3 -m pytest tests/test_participants_sessions_from_date.py -q`
Expected: `ImportError: cannot import name 'load_participant_source'`.

- [ ] **Step 3: Implement**

In `src/participants_converter.py`, add at module level (below the imports; import `number_sessions_by_date` next to the existing `filter_rows_to_session` import, keeping that import's try/except fallback style):

```python
_SOURCE_KINDS = {
    ".xlsx": "xlsx", ".xls": "xlsx", ".csv": "csv", ".tsv": "tsv", ".txt": "tsv",
    ".sav": "sav", ".rds": "rds", ".rdata": "rdata", ".rda": "rdata",
}


def load_participant_source(
    source_path: Path,
    *,
    separator: str | None = None,
    sheet: str | int = 0,
    sessions_from_date: str | None = None,
    id_column: str | None = None,
) -> tuple[pd.DataFrame, list[str]]:
    """Read a participants source table; optionally number sessions by date."""
    source_path = Path(source_path)
    if sessions_from_date and not id_column:
        raise ValueError("Select the ID column before numbering sessions by date.")
    suffix = source_path.suffix.lower()
    if suffix == ".lsa":
        from src.converters.survey import _read_lsa_as_dataframe

        df, warnings = _read_lsa_as_dataframe(source_path), []
    else:
        result = _read_tabular_file(
            source_path,
            kind=_SOURCE_KINDS.get(suffix, "csv"),  # unknown: file_reader sniffs
            separator=separator,
            sheet=sheet,
        )
        df, warnings = result.df, list(result.warnings)
    if sessions_from_date:
        df, numbering_warnings = number_sessions_by_date(df, id_column, sessions_from_date)
        warnings += numbering_warnings
    return df, warnings
```

Replace the loading `try:` block in `convert_participant_data` (the `kind_map` / `.lsa` branch / `_read_tabular_file` code, ~lines 361-400) with:

```python
        try:
            id_source = next(
                (spec.get("source_column") for spec in mapping.get("mappings", {}).values()
                 if isinstance(spec, dict) and spec.get("standard_variable") == "participant_id"),
                None,
            )
            df, load_warnings = load_participant_source(
                source_path,
                separator=None if separator == "auto" else separator,
                sheet=sheet,
                sessions_from_date=sessions_from_date,
                id_column=id_source,
            )
            for w in load_warnings:
                self._log("WARNING", w)
                messages.append(f"⚠ {w}")
            self._log("INFO", f"Loaded {len(df)} rows from {source_path.name}")
            messages.append(f"✓ Loaded {len(df)} rows from {source_path.name}")
        except Exception as e:
```

Add `sessions_from_date: Optional[str] = None,` to the signature and the docstring Args.

- [ ] **Step 4: Run the new tests and the existing participants suite**

Run: `python3 -m pytest tests/test_participants_sessions_from_date.py tests/test_participants_convert_lsa.py -q && python3 -m pytest tests -q -k participants`
Expected: all pass (411+ previously). If an existing test asserted on the `(encoding: ...)` log text, keep the encoding in the log by returning it from the loader instead of changing the test.

- [ ] **Step 5: Commit**

```bash
git add src/participants_converter.py tests/test_participants_sessions_from_date.py
git commit -m "feat(participants): one source loader with optional sessions-from-date numbering"
```

---

### Task 3: Merge path + CLI flag

**Files:**
- Modify: `src/participants_backend.py` — `_build_participants_merge_input` (~969), `_plan_participants_merge` (~1418), `preview_participants_merge` (~1946), `apply_participants_merge` (~1976), `export_participants_merge_conflicts_csv` (~2036): add kwarg `sessions_from_date: str | None = None` and pass it down. In `_build_participants_merge_input`, pass it to `convert_participant_data`, and replace the repeated-rows re-read (the local `kind_map` + `_read_tabular_file` block, ~1072-1095) with `source_df, _ = load_participant_source(source_path, separator=separator_value, sheet=sheet, sessions_from_date=sessions_from_date, id_column=_selected_source_id_column())`. This also fixes `.lsa` in that re-read (today it falls back to CSV parsing). The derived `session` column is then found by `_find_session_column_name` (it prefers `"session"`).
- Modify: `app/src/cli/parser.py` — participants `preview`, `convert`, `merge` subparsers: add

```python
    parser_participants_X.add_argument(
        "--sessions-from-date",
        nargs="?",
        const="startdate",
        default=None,
        metavar="COLUMN",
        help="Repeated IDs without a session column (LimeSurvey): number each ID's rows "
        "1, 2, ... by this date column (default: startdate)",
    )
```
- Modify: `app/src/cli/commands/participants.py` — `_load_participant_table` becomes a thin call to `load_participant_source` (keep its `ValueError` for unsupported suffixes), gaining `sessions_from_date` / `id_column` args; `cmd_participants_preview` and `cmd_participants_convert` pass `getattr(args, "sessions_from_date", None)` and `getattr(args, "id_column", None)`; print returned warnings; `cmd_participants_merge` passes `sessions_from_date=` to `preview_participants_merge` / `apply_participants_merge` / `export_participants_merge_conflicts_csv`.
- Test: `tests/test_participants_cli_sessions_from_date.py` (create)

**Interfaces:**
- Consumes: `load_participant_source`, `convert_participant_data(sessions_from_date=...)` (Task 2).
- Produces: `preview_participants_merge(..., sessions_from_date=None)`, `apply_participants_merge(..., sessions_from_date=None)` used by Task 4.

- [ ] **Step 1: Write the failing tests** — follow the setup in `tests/test_participants_cli_merge_sessions.py` (read it first; reuse its project fixture helper rather than writing a new one):

```python
"""CLI: participants merge with --sessions-from-date on a repeated-ID file."""

import pandas as pd

from src.participants_backend import preview_participants_merge

# ROWS / MAPPING as in tests/test_participants_sessions_from_date.py


def test_merge_preview_resolves_dated_sessions(tmp_path):
    project = _make_project(tmp_path)          # reuse helper from test_participants_cli_merge_sessions.py
    src = tmp_path / "in.csv"
    pd.DataFrame(ROWS).to_csv(src, index=False)
    payload = preview_participants_merge(project, src, MAPPING, sessions_from_date="startdate")
    assert payload["session_resolution_column"] == "session"


def test_cli_parser_accepts_flag_with_default_column():
    from src.cli.parser import build_parser   # use the real factory name from app/src/cli/parser.py
    args = build_parser().parse_args(
        ["participants", "convert", "--input", "x.csv", "--sessions-from-date"]
    )
    assert args.sessions_from_date == "startdate"
```

(Before writing: check the parser factory's real name with `grep -n "^def " app/src/cli/parser.py` and the CLI entry used by `tests/test_participants_cli.py`; use those exact names.)

- [ ] **Step 2: Run to verify they fail**

Run: `python3 -m pytest tests/test_participants_cli_sessions_from_date.py -q`
Expected: `TypeError: ... unexpected keyword argument 'sessions_from_date'` and argparse `unrecognized arguments`.

- [ ] **Step 3: Implement** the changes listed under **Files** above.

- [ ] **Step 4: Run**

Run: `python3 -m pytest tests -q -k "participants"`
Expected: all pass.

- [ ] **Step 5: Commit**

```bash
git add src/participants_backend.py app/src/cli/parser.py app/src/cli/commands/participants.py tests/test_participants_cli_sessions_from_date.py
git commit -m "feat(participants): --sessions-from-date for preview, convert and merge"
```

---

### Task 4: GUI checkbox (pass-through only)

**Files:**
- Modify: `app/templates/converter_participants.html` — directly above the `<!-- Longitudinal file: which ONE session goes into participants.tsv -->` comment (~line 185):

```html
            <div class="form-check mt-3">
                <input class="form-check-input" type="checkbox" id="participantsSessionsFromDate">
                <label class="form-check-label" for="participantsSessionsFromDate">
                    Number sessions by acquisition date (repeated IDs, no session column, e.g. LimeSurvey)
                </label>
                <div class="form-text">Each ID's responses become sessions 1, 2, … ordered by <code>startdate</code>. Incomplete runs are flagged, not removed.</div>
            </div>
```
- Modify: `app/static/js/modules/converter/participants.js` — in `appendParticipantsFileImportFields` (~2720) and in the preview request builder (~1333-1342, next to `formData.append('separator', separator)`):

```js
        if (document.getElementById('participantsSessionsFromDate')?.checked) {
            formData.append('sessions_from_date', 'startdate');
        }
```
  and re-run the preview when the checkbox changes (same handler the separator select uses).
- Modify: `app/src/web/blueprints/conversion_participants_io.py` — `_read_participants_input_table` gains `sessions_from_date=None, id_column=None` and delegates to `load_participant_source` (keep its unsupported-suffix error).
- Modify: `app/src/web/blueprints/conversion_participants_blueprint.py` — `api_participants_preview` (~313), `api_participants_convert_start` (~777/836): read `request.form.get("sessions_from_date", "").strip() or None` and pass it (plus the form's `id_column`) through.
- Modify: `app/src/web/blueprints/conversion_participants_merge.py` — add `"sessions_from_date": request.form.get("sessions_from_date", "").strip() or None` to the merge request dict (~182); `api_participants_merge` (~616, ~675) and `api_participants_merge_conflicts` (~741) pass `sessions_from_date=merge_request["sessions_from_date"]`.
- Test: `tests/test_participants_sessions_from_date_api.py` (create)

**Interfaces:**
- Consumes: Task 2/3 functions. Form field name: `sessions_from_date`.

- [ ] **Step 0:** Run the dual-tree check for each `app/src/` file above (CLAUDE.md).

- [ ] **Step 1: Write the failing test** — use the Flask test-client setup from `tests/test_participants_session_api.py` (read it; reuse its fixture):

```python
def test_preview_with_sessions_from_date_offers_session_column(client, tmp_path):
    # post ROWS as CSV to the preview endpoint used in test_participants_session_api.py,
    # with data={"id_column": "token", "sessions_from_date": "startdate"}
    resp = ...  # same call shape as that file
    candidates = resp.get_json()["session_candidates"]
    assert {"column": "session", "values": ["1", "2"]} in candidates
```

(Fill the call with the exact endpoint/fixture from `tests/test_participants_session_api.py`; the assertion stays as written. Check the payload key name for session candidates in that file.)

- [ ] **Step 2: Run to verify it fails** — `python3 -m pytest tests/test_participants_sessions_from_date_api.py -q`; expected: the candidate list lacks `session`.

- [ ] **Step 3: Implement** the changes listed under **Files**.

- [ ] **Step 4: Run** `python3 -m pytest tests -q -k "participants"` (all pass), then start the app and check by hand with `.venv/survey_archive_195589.lsa`: tick the box, ID column `token`, Preview Merge — the "non-unique values" error from the screenshot must be gone and the session resolution offered.

- [ ] **Step 5: Commit**

```bash
git add app/templates/converter_participants.html app/static/js/modules/converter/participants.js app/src/web/blueprints/conversion_participants_io.py app/src/web/blueprints/conversion_participants_blueprint.py app/src/web/blueprints/conversion_participants_merge.py tests/test_participants_sessions_from_date_api.py
git commit -m "feat(participants-gui): sessions-from-date checkbox"
```

---

### Task 5: Survey conversion — date-ordered `"sessions"` mode, block lifted

**Files:**
- Modify: `app/src/converters/survey_core.py` — `_handle_duplicate_ids`, the `elif duplicate_handling == "sessions":` branch (~756).
- Modify: `app/src/converters/survey.py` — delete the `SessionMapError` raise for `"sessions"` in longitudinal projects (~1421-1425).
- Test: `tests/test_survey_sessions_by_date.py` (create)

**Interfaces:**
- Consumes: `number_sessions_by_date` (Task 1), imported as `from src.participants_sessions import number_sessions_by_date`.

- [ ] **Step 0:** Dual-tree check for `survey_core.py` and `survey.py` (CLAUDE.md).

- [ ] **Step 1: Write the failing tests**

```python
"""Survey conversion: duplicate_handling='sessions' numbers by date."""

import pandas as pd

from src.converters.survey_core import _handle_duplicate_ids


def test_sessions_mode_orders_by_startdate():
    df = pd.DataFrame({
        "token": ["a", "a"],
        "startdate": ["2026-09-01 10:00:00", "2026-03-01 10:00:00"],
        "q1": ["late", "early"],
    })
    out, ses_col, _ = _handle_duplicate_ids(
        df=df, res_id_col="token", duplicate_handling="sessions",
        normalize_sub_fn=lambda v: v,
    )
    assert dict(zip(out["q1"], out[ses_col])) == {"early": "1", "late": "2"}


def test_sessions_mode_without_dates_keeps_file_order():
    df = pd.DataFrame({"token": ["a", "a"], "q1": ["first", "second"]})
    out, ses_col, _ = _handle_duplicate_ids(
        df=df, res_id_col="token", duplicate_handling="sessions",
        normalize_sub_fn=lambda v: v,
    )
    assert [str(v) for v in out[ses_col]] == ["1", "2"]
```

Plus `test_sessions_mode_in_longitudinal_project_requires_mapping`: copy the longitudinal-project setup from the test added in commit `48f45369` (`git show 48f45369 --stat` to find it), run the conversion with `duplicate_handling="sessions"` and a session map lacking `"2"`, and assert the `SessionMapError` names the unmapped label `"2"` (not the old "invents session names" message).

- [ ] **Step 2: Run to verify they fail** — `python3 -m pytest tests/test_survey_sessions_by_date.py -q`; expected: first test gets `{"late": 1, "early": 2}`; longitudinal test hits the old "invents session names" error.

- [ ] **Step 3: Implement** — replace the `"sessions"` branch with:

```python
        elif duplicate_handling == "sessions":
            date_column = next((c for c in ("startdate", "datestamp") if c in df.columns), None)
            if date_column:
                df, numbering_warnings = number_sessions_by_date(
                    df.assign(_dup_norm_id=normalized_ids),
                    "_dup_norm_id",
                    date_column,
                    session_column="_dup_session_num",
                )
                df = df.drop(columns=["_dup_norm_id"])
                warnings.extend(numbering_warnings)
            else:
                df = df.copy()
                df["_dup_session_num"] = df.groupby(composite_key.values).cumcount() + 1
            res_ses_col_override = "_dup_session_num"
            warnings.append(
                f"Duplicate entries found ({dup_count}). Created multiple sessions for: {dup_label}"
            )
```

and delete the `if session_map is not None and duplicate_handling == "sessions": raise SessionMapError(...)` block in `survey.py`.

- [ ] **Step 4: Run** `python3 -m pytest tests -q -k "survey or session"`; expected: all pass. A test asserting the old "invents session names" error must be updated to the new behaviour (it encodes the decision this spec reverses) — note it in the commit message.

- [ ] **Step 5: Commit**

```bash
git add app/src/converters/survey_core.py app/src/converters/survey.py tests/test_survey_sessions_by_date.py
git commit -m "feat(survey): date-ordered session numbering; allow it in longitudinal projects via the session map"
```

---

### Task 6: Finish

- [ ] Full suite: `python3 -m pytest tests -q` — report any failure by name.
- [ ] `python tests/verify_repo.py --check dual-tree-drift --no-fix`.
- [ ] `/ponytail:ponytail-audit` on the branch (CLAUDE.md, before merge); apply worthwhile findings, re-run tests.
- [ ] superpowers:finishing-a-development-branch.
