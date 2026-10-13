# Session Assignment Review Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Repeated LimeSurvey responses get sessions only from *completed* responses (numbered by date), with a per-response review table whose overrides are saved in the project and honoured by every importer (CLI and GUI).

**Architecture:** `number_sessions_by_date` (`src/participants_sessions.py`) gains the completed-only rule and a `decisions` argument; a new `session_assignment_table` shares its per-response logic. Decisions live in `code/session_assignments.json` (`src/session_assignments.py`, keyed by LimeSurvey response `id`). The participants importer and survey conversion load that file themselves from the project they already know. A new `sessions` CLI group (`review|set|unset`) and a thin Flask blueprint expose the same functions; the GUI only shows the table and writes decisions through the blueprint.

**Tech Stack:** Python 3, pandas, argparse, Flask, vanilla JS (ES modules), pytest, Playwright (tests/e2e).

**Spec:** `docs/superpowers/specs/2026-10-12-session-assignment-review-design.md`

## Global Constraints

- Session labels are free-form strings, compared exactly, never normalized or zero-padded (CLAUDE.md). Generated labels are `"1"`, `"2"`, ... as `str`; overrides are stored as given (only surrounding whitespace is stripped, as `session_label` does).
- One implementation: logic in `src/`; CLI and GUI only pass options through and render results (CLAUDE.md golden rule). Every new GUI action has a CLI command.
- Rows are never merged. A *completed* response is one whose `submitdate` is non-empty; a file without a `submitdate` column treats every response as completed.
- Decisions file: `code/session_assignments.json` = `{"version": 1, "responses": {"<response id>": {"skip": true} | {"session": "<label>"}}}`; written atomically (tmp + `os.replace`), like `src/session_map.py`.
- A participant that ends up with the same session label on two responses is a blocker (`ValueError`), never silently resolved.
- Before editing a file under `app/src/`, run the dual-tree check from CLAUDE.md (`find src -name '<file>.py'`, `python3 -c "import src.<mod> as m; print(m.__file__)"`). At the time of writing every `app/src/` file below is `app/`-only.
- TDD: every task writes the failing test first and watches it fail for the right reason.
- Text-format files (`.json`) are never git-annexed (CLAUDE.md DataLad policy); `code/session_assignments.json` is a normal JSON file in the project, nothing to do.

**Deviations from the spec (flag in the final report):** (1) `session_assignment_table` returns `(rows, warnings)` rather than just the rows, so the CLI and GUI show the same warnings without recomputing them. (2) the spec lists `--session-assignments FILE` on every importer. This plan drops it: the importers already know the project, and `--project` selects the file. It would add one more parameter threaded through five merge functions for no current need. Add later if asked. (3) The review table's GUI supports files chosen from the computer only (the upload endpoint); a file picked from the project's sourcedata list shows a "choose the file from your computer" message. Add a server-path variant if that turns out to be the common route.

## Review Focus

1. A participant with **only incomplete responses** (real archive: 8 responses, none completed) must be left out *and named* in a warning, not crash and not silently vanish. -> Task 2 `test_participant_without_a_completed_response_is_named`.
2. A **single incomplete response** (no repeats) in `sessions` mode must also be left out; today the survey path only numbers when duplicates exist. -> Task 4 `test_single_incomplete_response_is_left_out_in_sessions_mode`.
3. **Two completed responses** with identical timestamps keep file order (deterministic). -> Task 2 `test_identical_dates_keep_file_order`.
4. An override label that **collides** with an automatic one (`"1"` typed on a second response) must be a blocker, not a silent duplicate. -> Task 2 `test_duplicate_label_is_a_blocker`.
5. A decision for a response id that is **no longer in the export** (re-export dropped it) is ignored with one warning. -> Task 2 `test_stale_decision_is_ignored_with_a_warning`.

---

### Task 1: Decisions file (`src/session_assignments.py`)

**Files:**
- Create: `src/session_assignments.py`
- Test: `tests/test_session_assignments.py` (create)

**Interfaces:**
- Produces:
  - `class SessionAssignmentError(ValueError)`
  - `FILE = Path("code") / "session_assignments.json"`
  - `load_session_assignments(project_path: str | Path) -> dict[str, dict]` — `{}` when the file is absent; returns the `responses` mapping (`{"501": {"skip": True}, "502": {"session": "pre"}}`); raises `SessionAssignmentError` for a malformed file.
  - `set_assignment(project_path, response_id: str, *, skip: bool = False, session: str | None = None) -> dict[str, dict]` — exactly one of `skip=True` / `session=<non-empty label>`; returns the new mapping.
  - `unset_assignment(project_path, response_id: str) -> dict[str, dict]` — unknown id raises `SessionAssignmentError`.

- [ ] **Step 1: Write the failing tests**

```python
"""Decisions file: code/session_assignments.json, keyed by LimeSurvey response id."""

import json

import pytest

from src.session_assignments import (
    SessionAssignmentError,
    load_session_assignments,
    set_assignment,
    unset_assignment,
)


def test_missing_file_means_no_decisions(tmp_path):
    assert load_session_assignments(tmp_path) == {}


def test_set_skip_and_session_round_trip(tmp_path):
    set_assignment(tmp_path, "501", skip=True)
    set_assignment(tmp_path, "502", session="pre")

    assert load_session_assignments(tmp_path) == {
        "501": {"skip": True},
        "502": {"session": "pre"},
    }
    raw = json.loads((tmp_path / "code" / "session_assignments.json").read_text())
    assert raw["version"] == 1


def test_labels_are_kept_exactly_as_given(tmp_path):
    set_assignment(tmp_path, "1", session="01")
    set_assignment(tmp_path, "2", session="1")

    assert load_session_assignments(tmp_path) == {
        "1": {"session": "01"},
        "2": {"session": "1"},
    }


def test_a_project_json_path_resolves_to_its_folder(tmp_path):
    (tmp_path / "project.json").write_text("{}")
    set_assignment(tmp_path / "project.json", "7", skip=True)

    assert load_session_assignments(tmp_path) == {"7": {"skip": True}}


def test_exactly_one_of_skip_or_session(tmp_path):
    with pytest.raises(SessionAssignmentError):
        set_assignment(tmp_path, "1")
    with pytest.raises(SessionAssignmentError):
        set_assignment(tmp_path, "1", skip=True, session="pre")
    with pytest.raises(SessionAssignmentError):
        set_assignment(tmp_path, "1", session="  ")
    assert not (tmp_path / "code" / "session_assignments.json").exists()


def test_unset_removes_one_and_rejects_unknown(tmp_path):
    set_assignment(tmp_path, "1", skip=True)
    set_assignment(tmp_path, "2", skip=True)

    assert unset_assignment(tmp_path, "1") == {"2": {"skip": True}}
    with pytest.raises(SessionAssignmentError, match="999"):
        unset_assignment(tmp_path, "999")


def test_malformed_file_is_reported(tmp_path):
    path = tmp_path / "code" / "session_assignments.json"
    path.parent.mkdir()
    path.write_text('{"version": 1, "responses": {"1": {"skip": "yes"}}}')

    with pytest.raises(SessionAssignmentError, match="session_assignments.json"):
        load_session_assignments(tmp_path)
```

- [ ] **Step 2: Run to verify they fail**

Run: `python3 -m pytest tests/test_session_assignments.py -q`
Expected: collection error `ModuleNotFoundError: No module named 'src.session_assignments'`.

- [ ] **Step 3: Implement**

```python
"""Per-response session decisions for repeated LimeSurvey exports.

Spec: docs/superpowers/specs/2026-10-12-session-assignment-review-design.md

``code/session_assignments.json`` maps a LimeSurvey response ``id`` to
``{"skip": true}`` or ``{"session": "<label>"}``. Keyed by response id so the
decisions survive re-exports. Labels are free-form strings: only surrounding
whitespace is stripped, nothing is padded or coerced.
"""

from __future__ import annotations

import json
import os
from pathlib import Path

FILE = Path("code") / "session_assignments.json"


class SessionAssignmentError(ValueError):
    """Anything wrong with the decisions file or a requested change."""


def _path(project_path: str | Path) -> Path:
    root = Path(project_path).expanduser()
    return (root.parent if root.is_file() else root) / FILE


def _clean(raw: object, where: str) -> dict[str, dict]:
    responses = raw.get("responses") if isinstance(raw, dict) else None
    if not isinstance(responses, dict):
        raise SessionAssignmentError(f"{where} must hold an object under 'responses'")
    clean: dict[str, dict] = {}
    for response_id, decision in responses.items():
        key = str(response_id).strip()
        if not key or not isinstance(decision, dict):
            raise SessionAssignmentError(f"{where}: bad entry for {response_id!r}")
        if decision == {"skip": True}:
            clean[key] = {"skip": True}
        elif set(decision) == {"session"} and isinstance(decision["session"], str) and decision["session"].strip():
            clean[key] = {"session": decision["session"].strip()}
        else:
            raise SessionAssignmentError(
                f"{where}: entry for {key!r} must be {{'skip': true}} or {{'session': '<label>'}}"
            )
    return clean


def load_session_assignments(project_path: str | Path) -> dict[str, dict]:
    path = _path(project_path)
    if not path.is_file():
        return {}
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        raise SessionAssignmentError(f"{path} could not be read: {exc}") from exc
    return _clean(raw, str(path))


def _save(project_path: str | Path, responses: dict[str, dict]) -> None:
    path = _path(project_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(".json.tmp")
    payload = {"version": 1, "responses": responses}
    tmp.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    os.replace(tmp, path)


def set_assignment(
    project_path: str | Path,
    response_id: str,
    *,
    skip: bool = False,
    session: str | None = None,
) -> dict[str, dict]:
    label = (session or "").strip()
    if skip == bool(label):  # neither, or both
        raise SessionAssignmentError("Give exactly one of --skip or a non-empty --session label")
    key = str(response_id).strip()
    if not key:
        raise SessionAssignmentError("The response id must not be empty")
    responses = load_session_assignments(project_path)
    responses[key] = {"skip": True} if skip else {"session": label}
    _save(project_path, responses)
    return responses


def unset_assignment(project_path: str | Path, response_id: str) -> dict[str, dict]:
    responses = load_session_assignments(project_path)
    key = str(response_id).strip()
    if key not in responses:
        raise SessionAssignmentError(f"No decision stored for response {key!r}")
    del responses[key]
    _save(project_path, responses)
    return responses
```

- [ ] **Step 4: Run to verify they pass**

Run: `python3 -m pytest tests/test_session_assignments.py -q`
Expected: 7 passed.

- [ ] **Step 5: Commit**

```bash
git add src/session_assignments.py tests/test_session_assignments.py
git commit -m "feat(sessions): per-response decisions file (code/session_assignments.json)"
```

---

### Task 2: Completed-only numbering, overrides, review table (`src/participants_sessions.py`)

**Files:**
- Modify: `src/participants_sessions.py` (replace the body of `number_sessions_by_date`; add `session_assignment_table`)
- Modify: `tests/test_number_sessions_by_date.py` (update the one test that encodes the old "number every response" rule)
- Test: `tests/test_session_assignment_rule.py` (create)

**Interfaces:**
- Consumes: `session_label` (same module).
- Produces:
  - `number_sessions_by_date(df, id_column, date_column="startdate", session_column="session", decisions=None, response_id_column="id") -> tuple[pd.DataFrame, list[str]]` — returned frame holds **only responses that get a session**, ordered by participant then date; `decisions` is the mapping from `load_session_assignments` (or `None`).
  - `session_assignment_table(df, id_column, date_column="startdate", decisions=None, response_id_column="id") -> tuple[list[dict], list[str]]` — one dict per response: `{"participant": str, "response_id": str, "date": str ("" if none), "completed": bool, "lastpage": str, "session": str | None, "reason": "auto" | "override" | "incomplete" | "skipped"}`, ordered by participant then date; plus the same warnings.
- Warning texts relied on by later tasks/tests (substrings): `"left out"`, `"No completed response for: <ids>"`, `"Uneven session counts"`, `"Ignored decisions for responses not in this file: <ids>"`, and a first line beginning `"Sessions numbered by <date_column>"`.

- [ ] **Step 1: Write the failing tests** (`tests/test_session_assignment_rule.py`)

```python
"""Sessions come from completed responses only; overrides and the review table."""

import pandas as pd
import pytest

from src.participants_sessions import number_sessions_by_date, session_assignment_table

COLS = ["id", "token", "startdate", "submitdate", "lastpage"]
# Mirrors the real archive: a (1 abandoned + 2 completed), b (only abandoned), c (1 completed).
ROWS = [
    ["1", "a", "2026-03-01 09:00:00", "", "2"],
    ["2", "a", "2026-03-01 11:00:00", "2026-03-01 11:20:00", "5"],
    ["3", "a", "2026-09-01 10:00:00", "2026-09-01 10:20:00", "5"],
    ["4", "b", "2026-03-02 10:00:00", "", "4"],
    ["5", "b", "2026-03-02 10:05:00", "", ""],
    ["6", "c", "2026-03-03 10:00:00", "2026-03-03 10:10:00", "5"],
]


def _df(rows=ROWS):
    return pd.DataFrame(rows, columns=COLS)


def _by_id(out):
    return dict(zip(out["id"], out["session"]))


def test_only_completed_responses_get_a_session():
    out, _ = number_sessions_by_date(_df(), "token")

    assert _by_id(out) == {"2": "1", "3": "2", "6": "1"}


def test_incomplete_responses_are_left_out_and_counted():
    _, warnings = number_sessions_by_date(_df(), "token")

    text = "\n".join(warnings)
    assert warnings[0].startswith("Sessions numbered by startdate")
    assert "3 incomplete response(s) left out" in text


def test_participant_without_a_completed_response_is_named():
    _, warnings = number_sessions_by_date(_df(), "token")

    assert any(w.startswith("No completed response for: b") for w in warnings)


def test_identical_dates_keep_file_order():
    rows = [
        ["1", "a", "2026-03-01 10:00:00", "x", "5"],
        ["2", "a", "2026-03-01 10:00:00", "x", "5"],
    ]
    out, _ = number_sessions_by_date(_df(rows), "token")

    assert _by_id(out) == {"1": "1", "2": "2"}


def test_a_file_without_submitdate_treats_every_response_as_completed():
    df = pd.DataFrame({"token": ["a", "a"], "startdate": ["2026-03-01", "2026-09-01"]})
    out, _ = number_sessions_by_date(df, "token")

    assert list(out["session"]) == ["1", "2"]


def test_skip_decision_removes_a_completed_response():
    out, _ = number_sessions_by_date(_df(), "token", decisions={"2": {"skip": True}})

    assert _by_id(out) == {"3": "1", "6": "1"}


def test_session_decision_sets_an_exact_label_and_can_include_an_incomplete_response():
    decisions = {"4": {"session": "pre"}, "3": {"session": "post"}}
    out, _ = number_sessions_by_date(_df(), "token", decisions=decisions)

    assert _by_id(out) == {"2": "1", "3": "post", "4": "pre", "6": "1"}


def test_duplicate_label_is_a_blocker():
    with pytest.raises(ValueError, match=r"a.*'1'.*2.*3|a.*'1'.*3.*2"):
        number_sessions_by_date(_df(), "token", decisions={"3": {"session": "1"}})


def test_stale_decision_is_ignored_with_a_warning():
    out, warnings = number_sessions_by_date(_df(), "token", decisions={"999": {"skip": True}})

    assert _by_id(out) == {"2": "1", "3": "2", "6": "1"}
    assert "Ignored decisions for responses not in this file: 999" in warnings


def test_undated_completed_response_is_an_error_but_undated_incomplete_is_not():
    rows = [["1", "a", "", "", "2"], ["2", "a", "2026-03-01", "x", "5"]]
    out, _ = number_sessions_by_date(_df(rows), "token")
    assert _by_id(out) == {"2": "1"}

    rows = [["1", "a", "", "x", "5"]]
    with pytest.raises(ValueError, match="a"):
        number_sessions_by_date(_df(rows), "token")


def test_existing_session_column_is_still_an_error():
    df = _df().assign(session="pre")
    with pytest.raises(ValueError, match="session"):
        number_sessions_by_date(df, "token")


def test_table_lists_every_response_with_reason_and_session():
    rows, _ = session_assignment_table(_df(), "token", decisions={"3": {"skip": True}})

    by_id = {r["response_id"]: r for r in rows}
    assert [r["response_id"] for r in rows] == ["1", "2", "3", "4", "5", "6"]
    assert by_id["1"] | {"date": ""} == {
        "participant": "a", "response_id": "1", "date": "", "completed": False,
        "lastpage": "2", "session": None, "reason": "incomplete",
    }
    assert (by_id["2"]["session"], by_id["2"]["reason"]) == ("1", "auto")
    assert (by_id["3"]["session"], by_id["3"]["reason"]) == (None, "skipped")
    assert by_id["2"]["date"].startswith("2026-03-01")
```

- [ ] **Step 2: Run to verify they fail**

Run: `python3 -m pytest tests/test_session_assignment_rule.py -q`
Expected: `ImportError: cannot import name 'session_assignment_table'` (collection error).

- [ ] **Step 3: Implement.** Replace `number_sessions_by_date` in `src/participants_sessions.py` with the three functions below (keep the module's imports; `pd` is already imported with the pandas-less fallback).

```python
def _outcomes(
    df: pd.DataFrame,
    id_column: str,
    date_column: str,
    response_id_column: str,
    decisions: dict | None,
) -> tuple[pd.DataFrame, list[str], str]:
    """Per-response outcome shared by numbering and the review table.

    Returns (res, warnings, date_column_used). ``res`` is indexed like ``df`` with
    participant, response_id, when, completed, lastpage, session (str | None), reason.
    """
    if (
        date_column == "startdate"
        and date_column not in df.columns
        and "datestamp" in df.columns
    ):
        date_column = "datestamp"  # LimeSurvey exports without "Save start time"
    for column in (id_column, date_column):
        if column not in df.columns:
            raise ValueError(f"Column '{column}' not found in the file")
    decisions = decisions or {}

    def _parse(column: str) -> pd.Series:
        # format="mixed": otherwise pandas infers one format from the first value
        # and silently turns "2026-03-01 10:00:00" after "2026-03-01" into NaT.
        return pd.to_datetime(
            df[column].replace("", None), errors="coerce", format="mixed"
        )

    when = _parse(date_column)
    if date_column == "startdate" and "datestamp" in df.columns:
        when = when.fillna(_parse("datestamp"))

    blank = pd.Series("", index=df.index)
    res = pd.DataFrame(
        {
            "participant": df[id_column].map(session_label),  # same form for 1.0 and "1"
            "response_id": df[response_id_column].map(session_label)
            if response_id_column in df.columns
            else blank,
            "when": when,
            "completed": df["submitdate"].map(session_label) != ""
            if "submitdate" in df.columns
            else pd.Series(True, index=df.index),
            "lastpage": df["lastpage"].map(session_label)
            if "lastpage" in df.columns
            else blank,
        },
        index=df.index,
    )
    res["session"] = None
    res["reason"] = ""

    for i, row in res.iterrows():
        decision = decisions.get(row["response_id"]) if row["response_id"] else None
        if decision and decision.get("skip"):
            res.at[i, "reason"] = "skipped"
        elif decision and decision.get("session"):
            res.at[i, "session"] = session_label(decision["session"])
            res.at[i, "reason"] = "override"
        elif row["completed"]:
            res.at[i, "reason"] = "auto"
        else:
            res.at[i, "reason"] = "incomplete"

    auto = res[res["reason"] == "auto"]
    undated = sorted(set(auto.loc[auto["when"].isna(), "participant"]))
    if undated:
        raise ValueError(
            f"No usable '{date_column}' for ID(s): {', '.join(undated[:10])}. "
            "Fix these responses in LimeSurvey before numbering sessions."
        )
    ordered = auto.sort_values(["participant", "when"], kind="stable")
    res.loc[ordered.index, "session"] = (
        ordered.groupby("participant").cumcount() + 1
    ).astype(str)

    assigned = res[res["session"].notna()]
    clash = assigned[assigned.duplicated(["participant", "session"], keep=False)]
    if not clash.empty:
        lines = [
            f"ID {pid}: session {label!r} on responses {', '.join(group['response_id'])}"
            for (pid, label), group in clash.groupby(["participant", "session"])
        ]
        raise ValueError(
            "One participant would get the same session label twice; fix it with "
            "`sessions set`/`sessions unset`: " + "; ".join(lines)
        )

    warnings = [
        f"Sessions numbered by {date_column} (completed responses only): "
        f"{len(assigned)} of {len(res)} responses kept."
    ]
    left_out = res[res["session"].isna()]
    incomplete = left_out[left_out["reason"] == "incomplete"]
    if len(incomplete):
        warnings.append(f"{len(incomplete)} incomplete response(s) left out (no submitdate).")
    without = sorted(set(res["participant"]) - set(assigned["participant"]))
    if without:
        warnings.append("No completed response for: " + ", ".join(without[:10]))
    known = set(res["response_id"])
    stale = sorted(str(k) for k in decisions if str(k) not in known)
    if stale:
        warnings.append(
            "Ignored decisions for responses not in this file: " + ", ".join(stale)
        )
    counts = assigned.groupby("participant").size().value_counts().sort_index(ascending=False)
    if len(counts) > 1:
        parts = [
            f"{n} IDs x {k} sessions" if i == 0 else f"{n} x {k}"
            for i, (k, n) in enumerate(counts.items())
        ]
        warnings.append("Uneven session counts: " + ", ".join(parts))
    return res, warnings, date_column


def number_sessions_by_date(
    df: pd.DataFrame,
    id_column: str,
    date_column: str = "startdate",
    session_column: str = "session",
    decisions: dict | None = None,
    response_id_column: str = "id",
) -> tuple[pd.DataFrame, list[str]]:
    """Give each participant's *completed* responses sessions "1", "2", ... by date.

    For repeated-measures exports without a session indicator (LimeSurvey).
    Incomplete responses (empty ``submitdate``) are left out, and listed in the
    warnings; ``decisions`` (``{response_id: {"skip": True} | {"session": label}}``)
    override the automatic rule. Rows are never merged. The returned frame holds
    only the responses that got a session.
    """
    if session_column in df.columns:
        raise ValueError(
            f"The file already has a '{session_column}' column; use it as the session column instead."
        )
    res, warnings, _ = _outcomes(df, id_column, date_column, response_id_column, decisions)
    kept = res[res["session"].notna()].sort_values(["participant", "when"], kind="stable")
    out = df.loc[kept.index].copy()
    out[session_column] = kept["session"]
    return out.reset_index(drop=True), warnings


def session_assignment_table(
    df: pd.DataFrame,
    id_column: str,
    date_column: str = "startdate",
    decisions: dict | None = None,
    response_id_column: str = "id",
) -> tuple[list[dict], list[str]]:
    """One row per response for review: what session it gets and why."""
    res, warnings, _ = _outcomes(df, id_column, date_column, response_id_column, decisions)
    rows = [
        {
            "participant": r["participant"],
            "response_id": r["response_id"],
            "date": "" if pd.isna(r["when"]) else str(r["when"]),
            "completed": bool(r["completed"]),
            "lastpage": r["lastpage"],
            "session": r["session"],
            "reason": r["reason"],
        }
        for _, r in res.sort_values(["participant", "when"], kind="stable").iterrows()
    ]
    return rows, warnings
```

Then update the one old test that encodes "number every response" in `tests/test_number_sessions_by_date.py`: replace `test_incomplete_runs_are_flagged` with

```python
def test_incomplete_runs_are_left_out_and_flagged():
    df = _df([
        ["a", "2026-03-01", "", "", "3"],
        ["a", "2026-03-02", "", "2026-03-02", "9"],
    ])
    out, warnings = number_sessions_by_date(df, "token")
    assert list(out["session"]) == ["1"]  # only the completed response
    assert any("incomplete response(s) left out" in w for w in warnings)
```

(The `_df` helper there has no `id` column, so responses have no response id; decisions simply never match. `test_even_counts_complete_runs_give_no_warnings` asserts `warnings == []` and now fails because the summary line is always present: change it to `assert warnings == [w for w in warnings if w.startswith("Sessions numbered by")]`. `test_uneven_session_counts_are_reported` keeps passing.)

- [ ] **Step 4: Run**

Run: `python3 -m pytest tests/test_session_assignment_rule.py tests/test_number_sessions_by_date.py -q`
Expected: all pass. If `test_missing_date_is_an_error` (old file) fails: its row has `submitdate=""`, i.e. incomplete, so it no longer raises; change that row's `submitdate` to `"x"` (it is testing the undated *completed* case).

- [ ] **Step 5: Commit**

```bash
git add src/participants_sessions.py tests/test_session_assignment_rule.py tests/test_number_sessions_by_date.py
git commit -m "feat(sessions): completed-only numbering with overrides and a review table

Replaces the old 'number every response' rule (test_incomplete_runs_are_flagged
encoded it): a real archive turned six abandoned starts into ses-1..6."
```

---

### Task 3: Participants importer honours decisions

**Files:**
- Modify: `src/participants_converter.py` (`load_participant_source`, `convert_participant_data`)
- Modify: `src/participants_backend.py` (`_build_participants_merge_input` re-read)
- Modify: `app/src/cli/commands/participants.py` (`cmd_participants_preview`)
- Test: `tests/test_participants_session_assignments.py` (create)

**Interfaces:**
- Consumes: `number_sessions_by_date(..., decisions=...)` (Task 2), `load_session_assignments` (Task 1).
- Produces: `load_participant_source(..., sessions_from_date=None, id_column=None, decisions: dict | None = None)`; `convert_participant_data` loads `code/session_assignments.json` from `self.dataset_path` itself when `sessions_from_date` is set.

- [ ] **Step 1: Write the failing test**

```python
"""Participants import: the project's session decisions are applied automatically."""

import pandas as pd

from src.participants_converter import ParticipantsConverter, load_participant_source
from src.session_assignments import set_assignment

ROWS = [
    {"id": "1", "token": "a", "startdate": "2026-03-01 09:00:00", "submitdate": "", "age": 29},
    {"id": "2", "token": "a", "startdate": "2026-03-01 11:00:00", "submitdate": "x", "age": 30},
    {"id": "3", "token": "a", "startdate": "2026-09-01 10:00:00", "submitdate": "x", "age": 31},
    {"id": "4", "token": "b", "startdate": "2026-03-02 10:00:00", "submitdate": "x", "age": 40},
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


def test_loader_leaves_out_the_incomplete_response(tmp_path):
    df, _ = load_participant_source(_csv(tmp_path), sessions_from_date="startdate", id_column="token")

    assert sorted(zip(df["id"].astype(str), df["session"])) == [("2", "1"), ("3", "2"), ("4", "1")]


def test_loader_applies_decisions(tmp_path):
    df, _ = load_participant_source(
        _csv(tmp_path), sessions_from_date="startdate", id_column="token",
        decisions={"2": {"skip": True}},
    )

    assert sorted(zip(df["id"].astype(str), df["session"])) == [("3", "1"), ("4", "1")]


def test_convert_reads_the_project_decisions_file(tmp_path):
    project = tmp_path / "proj"
    project.mkdir()
    set_assignment(project, "2", skip=True)  # drop a's first completed response

    ok, df, messages = ParticipantsConverter(project).convert_participant_data(
        _csv(tmp_path), MAPPING, output_file=project / "participants.tsv",
        sessions_from_date="startdate", session_column="session", session_value="1",
        reject_conflicting_repeats=True,
    )

    assert ok, messages
    assert dict(zip(df["participant_id"], df["age"].astype(str))) == {"sub-a": "31", "sub-b": "40"}
```

- [ ] **Step 2: Run to verify they fail**

Run: `python3 -m pytest tests/test_participants_session_assignments.py -q`
Expected: `TypeError: load_participant_source() got an unexpected keyword argument 'decisions'`; the convert test fails with `sub-a` age `30` (decision ignored).

- [ ] **Step 3: Implement**

In `src/participants_converter.py`:

1. `load_participant_source`: add the parameter and pass it on.

```python
def load_participant_source(
    source_path: Path,
    *,
    separator: str | None = None,
    sheet: str | int = 0,
    sessions_from_date: str | None = None,
    id_column: str | None = None,
    decisions: dict | None = None,
) -> Tuple[pd.DataFrame, List[str]]:
```
and replace the numbering call with
`df, numbering_warnings = number_sessions_by_date(df, id_column, sessions_from_date, decisions=decisions)`.

2. `convert_participant_data`: just before the `df, load_warnings = load_participant_source(` call add
```python
            decisions = None
            if sessions_from_date:
                from src.session_assignments import load_session_assignments

                decisions = load_session_assignments(self.dataset_path)
```
and pass `decisions=decisions` into the call. (A `SessionAssignmentError` is a `ValueError`; the surrounding `except Exception` already turns it into the "✗ Failed to load source file" message.)

In `src/participants_backend.py`, `_build_participants_merge_input`: in the repeated-rows re-read, pass the same decisions:

```python
            from src.session_assignments import load_session_assignments

            source_df, _ = load_participant_source(
                source_path,
                separator=separator_value,
                sheet=sheet,
                sessions_from_date=sessions_from_date,
                id_column=source_id_column,
                decisions=load_session_assignments(project_root) if sessions_from_date else None,
            )
```

In `app/src/cli/commands/participants.py`, `cmd_participants_preview`: it calls `_load_participant_table(..., sessions_from_date=..., id_column=...)`. Add a `decisions` pass-through: extend `_load_participant_table` with `decisions: dict | None = None` (forward to `load_participant_source`), and in the preview call pass
```python
            decisions=(
                load_session_assignments(project_root) if sessions_from_date else None
            ),
```
with `from src.session_assignments import load_session_assignments` at the top. (`project_root` is already resolved above that call.)

- [ ] **Step 4: Run**

Run: `python3 -m pytest tests/test_participants_session_assignments.py tests/test_participants_sessions_from_date.py tests/test_participants_cli_sessions_from_date.py tests/test_participants_sessions_from_date_api.py -q`
Expected: all pass. The older tests used rows with a `submitdate` column of `"x"`, so they keep their meaning; if one has rows without `submitdate` it treats them as completed.

- [ ] **Step 5: Commit**

```bash
git add src/participants_converter.py src/participants_backend.py app/src/cli/commands/participants.py tests/test_participants_session_assignments.py
git commit -m "feat(participants): sessions-from-date honours the project's session decisions"
```

---

### Task 4: Survey conversion honours decisions and the completed-only rule

**Files:**
- Create: `tests/lsa_fixtures.py` (shared synthetic archive builder, reused by Tasks 5-8)
- Modify: `app/src/converters/survey_core.py` (`_handle_duplicate_ids`)
- Modify: `app/src/converters/survey.py` (the `_handle_duplicate_ids` call, ~line 1595)
- Test: `tests/test_survey_session_assignments.py` (create)

**Interfaces:**
- Consumes: `number_sessions_by_date(..., decisions=...)`, `load_session_assignments`.
- Produces:
  - `tests/lsa_fixtures.py::make_lsa(tmp_path: Path, rows: list[list[str]]) -> Path` — writes `<tmp_path>/repeated.lsa` with the columns `id, token, startdate, submitdate, lastpage, MTESTSQ001, MTESTSQ002, MTESTSQ003`; `make_library(tmp_path) -> Path` — alias of `tests.test_survey_cli_lsa._library`; constant `REAL_PATTERN` = rows mirroring the real archive (below).
  - `_handle_duplicate_ids(..., decisions: dict | None = None)`; in `"sessions"` mode **without a real session column** it numbers the whole file (not only when duplicates exist).

- [ ] **Step 1: Create the fixtures** (`tests/lsa_fixtures.py`)

```python
"""Synthetic LimeSurvey archive with response ids, completion and last page."""

import zipfile
from pathlib import Path

from tests.test_limesurvey_e2e import LSS_XML
from tests.test_survey_cli_lsa import _library as make_library  # noqa: F401

FIELDS = ["id", "token", "startdate", "submitdate", "lastpage", "MTESTSQ001", "MTESTSQ002", "MTESTSQ003"]

# a: one abandoned start + two completed; b: only abandoned starts; c: one completed.
REAL_PATTERN = [
    ["1", "a", "2026-03-01 09:00:00", "", "2", "4", "3", "5"],
    ["2", "a", "2026-03-01 11:00:00", "2026-03-01 11:20:00", "5", "2", "4", "3"],
    ["3", "a", "2026-09-01 10:00:00", "2026-09-01 10:20:00", "5", "3", "3", "3"],
    ["4", "b", "2026-03-02 10:00:00", "", "4", "1", "2", "3"],
    ["5", "b", "2026-03-02 10:05:00", "", "", "1", "2", "3"],
    ["6", "c", "2026-03-03 10:00:00", "2026-03-03 10:10:00", "5", "5", "5", "5"],
]


def make_lsa(tmp_path: Path, rows: list[list[str]] = REAL_PATTERN) -> Path:
    body = "".join(
        "<row>" + "".join(f"<{f}><![CDATA[{v}]]></{f}>" for f, v in zip(FIELDS, row)) + "</row>"
        for row in rows
    )
    lsr = (
        '<?xml version="1.0" encoding="UTF-8"?><document>'
        "<LimeSurveyDocType>Responses</LimeSurveyDocType><DBVersion>636</DBVersion>"
        "<languages><language>en</language></languages><responses><fields>"
        + "".join(f"<fieldname>{f}</fieldname>" for f in FIELDS)
        + f"</fields><rows>{body}</rows></responses></document>"
    )
    path = tmp_path / "repeated.lsa"
    with zipfile.ZipFile(path, "w") as z:
        z.writestr("survey_999999.lss", LSS_XML)
        z.writestr("survey_999999_responses.lsr", lsr)
    return path
```

- [ ] **Step 2: Write the failing tests**

```python
"""Survey conversion: sessions mode uses completed responses and the project's decisions."""

from src.converters.survey import convert_survey_lsa_to_prism_dataset
from src.session_assignments import set_assignment
from tests.lsa_fixtures import make_library, make_lsa


def _convert(tmp_path, project=None, **kwargs):
    return convert_survey_lsa_to_prism_dataset(
        input_path=make_lsa(tmp_path),
        library_dir=make_library(tmp_path),
        output_root=tmp_path / "out",
        id_column="token",
        duplicate_handling="sessions",
        project_path=project,
        **kwargs,
    )


def _sessions(tmp_path, participant):
    return sorted(p.name for p in (tmp_path / "out" / participant).glob("ses-*"))


def test_only_completed_responses_become_sessions(tmp_path):
    _convert(tmp_path)

    assert _sessions(tmp_path, "sub-a") == ["ses-1", "ses-2"]
    assert _sessions(tmp_path, "sub-c") == ["ses-1"]
    assert _sessions(tmp_path, "sub-b") == []  # only abandoned starts


def test_single_incomplete_response_is_left_out_in_sessions_mode(tmp_path):
    rows = [["1", "a", "2026-03-01 09:00:00", "", "2", "4", "3", "5"],
            ["2", "c", "2026-03-03 10:00:00", "2026-03-03 10:10:00", "5", "5", "5", "5"]]
    convert_survey_lsa_to_prism_dataset(
        input_path=make_lsa(tmp_path, rows), library_dir=make_library(tmp_path),
        output_root=tmp_path / "out", id_column="token", duplicate_handling="sessions",
    )

    assert _sessions(tmp_path, "sub-a") == []
    assert _sessions(tmp_path, "sub-c") == ["ses-1"]


def test_project_decisions_are_applied(tmp_path):
    project = tmp_path / "proj"
    project.mkdir()
    (project / "project.json").write_text('{"StudyDesign": {"Timepoints": "single"}}')
    set_assignment(project, "2", skip=True)

    _convert(tmp_path, project=project)

    assert _sessions(tmp_path, "sub-a") == ["ses-1"]  # response 3 is now its first completed one
```

- [ ] **Step 3: Run to verify they fail**

Run: `python3 -m pytest tests/test_survey_session_assignments.py -q`
Expected: `test_only_completed...` fails (`sub-a` has `ses-1..ses-3`, `sub-b` is written), the single-incomplete test fails (`sub-a` still converted), the decisions test fails.

- [ ] **Step 4: Implement**

`app/src/converters/survey_core.py`, `_handle_duplicate_ids`: add `decisions: dict | None = None` to the signature. Leave the existing `elif duplicate_handling == "sessions":` branch inside the `if composite_key.duplicated().any():` block untouched (it is the fallback for files with a real session column or no date column), and add this block **before** that `if`, right after `composite_key` is built:

```python
    if duplicate_handling == "sessions" and not (res_ses_col and res_ses_col in df.columns):
        # Numbered for the whole file, not only when IDs repeat: a single
        # abandoned start must be left out too.
        date_column = next(
            (c for c in ("startdate", "datestamp") if c in df.columns), None
        )
        if date_column:
            df, numbering_warnings = number_sessions_by_date(
                df.assign(_dup_norm_id=normalized_ids),
                "_dup_norm_id",
                date_column,
                session_column="_dup_session_num",
                decisions=decisions,
            )
            df = df.drop(columns=["_dup_norm_id"])
            return df, "_dup_session_num", numbering_warnings
        # No date column: keep the old file-order numbering below.
```

The new block returns early, so the old file-order `cumcount` branch only runs for files with a real session column or without any date column; the two paths never both run.

`app/src/converters/survey.py`, the `_handle_duplicate_ids` call: pass the project's decisions.

```python
    decisions = None
    if duplicate_handling == "sessions" and project_path:
        from src.session_assignments import load_session_assignments

        decisions = load_session_assignments(project_path)
    df, _res_ses_override, duplicate_warnings = _survey_core._handle_duplicate_ids(
        df=df,
        res_id_col=res_id_col,
        duplicate_handling=duplicate_handling,
        normalize_sub_fn=_normalize_sub_id,
        res_ses_col=res_ses_col,
        res_run_col=res_run_col,
        decisions=decisions,
    )
```

Note: the numbering now returns `"_dup_session_num"` even when nobody repeats, so the later `if _res_ses_override:` block in `survey.py` (sets `session = "all"` and map-checks the generated labels) runs for the whole file; its `elif ... duplicate_handling == "sessions"` fallback branch (raising `_NEEDS_SESSION_MESSAGE` when nothing was numbered) stays for the no-date-column case.

- [ ] **Step 5: Run**

Run: `python3 -m pytest tests/test_survey_session_assignments.py tests/test_survey_sessions_by_date.py tests/test_survey_cli_lsa.py tests/test_survey_lsa_unmatched_groups.py -q`
Expected: all pass. The older `test_survey_sessions_by_date.py` tests use frames without `submitdate` (all completed) and keep passing. If `test_sessions_mode_without_repeats_still_needs_a_session_source` now fails because a single-wave file is numbered `"1"`: that test asserts the *old* "needs a session source" refusal for a longitudinal project with no repeats; with whole-file numbering a single-wave file legitimately gets session `"1"` which must be in the map. Update that test to expect `SessionsNotMappedError` with `labels == ["1"]` when the map has no `"1"`, and note it in the commit message.

- [ ] **Step 6: Commit**

```bash
git add tests/lsa_fixtures.py tests/test_survey_session_assignments.py app/src/converters/survey_core.py app/src/converters/survey.py tests/test_survey_sessions_by_date.py
git commit -m "feat(survey): sessions mode uses completed responses and the project's decisions"
```

---

### Task 5: `sessions` CLI (`review`, `set`, `unset`)

**Files:**
- Create: `app/src/cli/commands/sessions.py`
- Modify: `app/src/cli/parser.py` (new `sessions` group, next to `session-map`, ~line 453)
- Modify: `app/src/cli/entrypoint.py` (import + two dispatch entries, next to `session_map_*`, lines ~73 and ~167)
- Modify: `docs/CLI_REFERENCE.md`
- Test: `tests/test_cli_sessions.py` (create)

**Interfaces:**
- Consumes: `load_participant_source`, `session_assignment_table`, `load_session_assignments`, `set_assignment`, `unset_assignment`; fixtures from Task 4.
- Produces CLI: `sessions review --input X --id-column COL [--date-column startdate] [--project P] [--json]`; `sessions set --project P --response ID (--skip | --session LABEL)`; `sessions unset --project P --response ID`.

- [ ] **Step 1: Write the failing tests**

```python
"""CLI: sessions review / set / unset."""

import json
import subprocess
import sys
from pathlib import Path

from tests.lsa_fixtures import make_lsa

PROJECT_ROOT = Path(__file__).resolve().parent.parent
PRISM_TOOLS_APP = PROJECT_ROOT / "app" / "prism_tools.py"


def _run(*args):
    return subprocess.run(
        [sys.executable, str(PRISM_TOOLS_APP), "sessions", *args],
        capture_output=True, text=True, encoding="utf-8", cwd=str(PROJECT_ROOT), timeout=60,
    )


def _project(tmp_path):
    project = tmp_path / "proj"
    project.mkdir()
    return project


def test_review_lists_every_response_with_its_session(tmp_path):
    result = _run("review", "--input", str(make_lsa(tmp_path)), "--id-column", "token", "--json")

    payload = json.loads(result.stdout)
    by_id = {r["response_id"]: r for r in payload["rows"]}
    assert (by_id["2"]["session"], by_id["2"]["reason"]) == ("1", "auto")
    assert (by_id["1"]["session"], by_id["1"]["reason"]) == (None, "incomplete")
    assert any("No completed response for: b" in w for w in payload["warnings"])


def test_set_then_review_shows_the_override_and_unset_removes_it(tmp_path):
    project = _project(tmp_path)
    source = str(make_lsa(tmp_path))

    assert _run("set", "--project", str(project), "--response", "4", "--session", "pre").returncode == 0
    payload = json.loads(_run("review", "--input", source, "--id-column", "token",
                              "--project", str(project), "--json").stdout)
    row = {r["response_id"]: r for r in payload["rows"]}["4"]
    assert (row["session"], row["reason"]) == ("pre", "override")

    assert _run("unset", "--project", str(project), "--response", "4").returncode == 0
    payload = json.loads(_run("review", "--input", source, "--id-column", "token",
                              "--project", str(project), "--json").stdout)
    assert {r["response_id"]: r for r in payload["rows"]}["4"]["session"] is None


def test_set_needs_skip_or_a_session(tmp_path):
    result = _run("set", "--project", str(_project(tmp_path)), "--response", "4")

    assert result.returncode == 2
    assert "exactly one" in (result.stdout + result.stderr).lower()


def test_review_prints_a_readable_table_without_json(tmp_path):
    result = _run("review", "--input", str(make_lsa(tmp_path)), "--id-column", "token")

    assert result.returncode == 0
    assert "response" in result.stdout and "left out" in result.stdout
```

- [ ] **Step 2: Run to verify they fail**

Run: `python3 -m pytest tests/test_cli_sessions.py -q`
Expected: argparse `invalid choice: 'sessions'` (exit 2), so the JSON parsing assertions fail.

- [ ] **Step 3: Implement**

`app/src/cli/commands/sessions.py`:

```python
"""`sessions` prism_tools commands: review how repeated responses map to sessions."""

from __future__ import annotations

import json
import sys
from pathlib import Path

from src.participants_converter import load_participant_source
from src.participants_sessions import session_assignment_table
from src.session_assignments import (
    SessionAssignmentError,
    load_session_assignments,
    set_assignment,
    unset_assignment,
)


def cmd_sessions_review(args) -> None:
    try:
        df, _ = load_participant_source(Path(args.input).expanduser().resolve())
        decisions = load_session_assignments(args.project) if args.project else {}
        rows, warnings = session_assignment_table(
            df, args.id_column, args.date_column, decisions=decisions
        )
    except ValueError as exc:  # SessionAssignmentError is a ValueError
        print(f"Error: {exc}")
        sys.exit(2)
    if getattr(args, "json", False):
        print(json.dumps({"rows": rows, "warnings": warnings}, indent=2, ensure_ascii=False))
        return
    print(f"{'participant':<14}{'response':<10}{'date':<21}{'done':<6}{'lastpage':<9}session")
    for r in rows:
        shown = r["session"] if r["session"] is not None else f"left out ({r['reason']})"
        print(
            f"{r['participant']:<14}{r['response_id']:<10}{r['date'][:19]:<21}"
            f"{'yes' if r['completed'] else 'no':<6}{r['lastpage']:<9}{shown}"
        )
    for warning in warnings:
        print(f"WARNING: {warning}")


def cmd_sessions_set(args) -> None:
    try:
        set_assignment(
            args.project, args.response, skip=bool(args.skip), session=args.session
        )
    except SessionAssignmentError as exc:
        print(f"Error: {exc}")
        sys.exit(2)
    what = "skipped" if args.skip else f"session {args.session!r}"
    print(f"Response {args.response}: {what}")


def cmd_sessions_unset(args) -> None:
    try:
        unset_assignment(args.project, args.response)
    except SessionAssignmentError as exc:
        print(f"Error: {exc}")
        sys.exit(2)
    print(f"Response {args.response}: decision removed (automatic rule applies)")
```

`app/src/cli/parser.py` (after the `session-map` block):

```python
    parser_sessions = subparsers.add_parser(
        "sessions",
        help="Review how repeated survey responses map to sessions (code/session_assignments.json)",
    )
    sessions_subparsers = parser_sessions.add_subparsers(dest="action", help="Action")

    parser_sessions_review = sessions_subparsers.add_parser(
        "review", help="List every response with the session it gets (completed responses only)"
    )
    parser_sessions_review.add_argument("--input", required=True, help="Survey data file (.lsa/.csv/.tsv/.xlsx)")
    parser_sessions_review.add_argument("--id-column", required=True, help="Participant ID column (e.g. token)")
    parser_sessions_review.add_argument("--date-column", default="startdate", help="Date column (default: startdate, falls back to datestamp)")
    parser_sessions_review.add_argument("--project", help="Project root or project.json path (applies its saved decisions)")
    parser_sessions_review.add_argument("--json", action="store_true", help="Emit machine-readable JSON")

    parser_sessions_set = sessions_subparsers.add_parser(
        "set", help="Skip a response, or give it an exact session label"
    )
    parser_sessions_set.add_argument("--project", required=True, help="Project root or project.json path")
    parser_sessions_set.add_argument("--response", required=True, help="LimeSurvey response id (the 'id' column)")
    parser_sessions_set.add_argument("--skip", action="store_true", help="Leave this response out")
    parser_sessions_set.add_argument("--session", help="Session label to use for this response (exact string)")

    parser_sessions_unset = sessions_subparsers.add_parser(
        "unset", help="Remove the saved decision for one response"
    )
    parser_sessions_unset.add_argument("--project", required=True, help="Project root or project.json path")
    parser_sessions_unset.add_argument("--response", required=True, help="LimeSurvey response id")
```

`app/src/cli/entrypoint.py`: add `from src.cli.commands.sessions import (cmd_sessions_review, cmd_sessions_set, cmd_sessions_unset,)` next to the `session_map` import, and in the dispatch dict
`"sessions_review": cmd_sessions_review, "sessions_set": cmd_sessions_set, "sessions_unset": cmd_sessions_unset,`.

`docs/CLI_REFERENCE.md`: under the session-map section add:

```markdown
**`sessions review|set|unset`** — repeated LimeSurvey responses (one row per start, no
session column). Sessions come from *completed* responses (`submitdate` filled), numbered
by `startdate`/`datestamp`; incomplete ones are left out. Review, then override:

```bash
python prism_tools.py sessions review --input survey_archive.lsa --id-column token --project /abs/path/my-project
python prism_tools.py sessions set --project /abs/path/my-project --response 502 --session pre
python prism_tools.py sessions set --project /abs/path/my-project --response 501 --skip
python prism_tools.py sessions unset --project /abs/path/my-project --response 502
```

Decisions are saved in `code/session_assignments.json` keyed by response id, so they survive
re-exports; `survey convert --duplicate-handling sessions` and
`participants … --sessions-from-date` apply them automatically.
```

- [ ] **Step 4: Run**

Run: `python3 -m pytest tests/test_cli_sessions.py -q`
Expected: 4 passed.

- [ ] **Step 5: Commit**

```bash
git add app/src/cli/commands/sessions.py app/src/cli/parser.py app/src/cli/entrypoint.py docs/CLI_REFERENCE.md tests/test_cli_sessions.py
git commit -m "feat(cli): sessions review/set/unset for repeated survey responses"
```

---

### Task 6: GUI endpoints (thin adapter over the same functions)

**Files:**
- Create: `app/src/web/blueprints/session_assignments_blueprint.py`
- Modify: `app/prism-studio.py` (blueprint list, next to `session_map_blueprint`, ~line 557)
- Test: `tests/test_session_assignments_api.py` (create)

**Interfaces:**
- Consumes: `session_assignment_table`, `load_participant_source`, `set_assignment`, `unset_assignment`, `load_session_assignments`; from `conversion_participants_io`: `_save_participants_upload_to_temp`, `_resolve_participants_sheet_arg`, `_normalize_separator_option`, `_expected_delimiter_for_suffix`; `_resolve_requested_or_current_project_root` from `tools_helpers`.
- Produces:
  - `POST /api/session-assignments/review` (multipart: `file`, `id_column`, optional `date_column`, `separator`, `sheet`; project from the Flask session) → `{"rows": [...], "warnings": [...]}`
  - `POST /api/session-assignments` (JSON `{project_path?, response_id, skip?: bool, session?: str, clear?: bool}`) → `{"ok": true, "responses": {...}}`; `400` with `{"error": ...}` on invalid input.

- [ ] **Step 1: Write the failing tests**

```python
"""GUI endpoints for the session review table."""

import io

import pytest
from flask import Flask

from src.web.blueprints.session_assignments_blueprint import session_assignments_bp
from src.session_assignments import load_session_assignments
from tests.lsa_fixtures import make_lsa


@pytest.fixture
def client(tmp_path):
    app = Flask(__name__)
    app.secret_key = "test"  # pragma: allowlist secret
    app.register_blueprint(session_assignments_bp)
    project = tmp_path / "proj"
    project.mkdir()
    (project / "project.json").write_text('{"StudyDesign": {"Timepoints": "single"}}')
    http = app.test_client()
    with http.session_transaction() as s:
        s["current_project_path"] = str(project)
    http.project = project
    return http


def _upload(tmp_path):
    return {
        "file": (io.BytesIO(make_lsa(tmp_path).read_bytes()), "repeated.lsa"),
        "id_column": "token",
    }


def test_review_returns_the_rows_and_warnings(client, tmp_path):
    body = client.post(
        "/api/session-assignments/review", data=_upload(tmp_path),
        content_type="multipart/form-data",
    ).get_json()

    by_id = {r["response_id"]: r for r in body["rows"]}
    assert (by_id["2"]["session"], by_id["1"]["reason"]) == ("1", "incomplete")
    assert any("No completed response for: b" in w for w in body["warnings"])


def test_review_applies_the_projects_saved_decisions(client, tmp_path):
    client.post("/api/session-assignments", json={"response_id": "4", "session": "pre"})

    body = client.post(
        "/api/session-assignments/review", data=_upload(tmp_path),
        content_type="multipart/form-data",
    ).get_json()

    assert {r["response_id"]: r for r in body["rows"]}["4"]["session"] == "pre"


def test_post_saves_and_clears_a_decision(client):
    saved = client.post("/api/session-assignments", json={"response_id": "7", "skip": True})
    assert saved.get_json() == {"ok": True, "responses": {"7": {"skip": True}}}
    assert load_session_assignments(client.project) == {"7": {"skip": True}}

    cleared = client.post("/api/session-assignments", json={"response_id": "7", "clear": True})
    assert cleared.get_json() == {"ok": True, "responses": {}}


def test_post_rejects_an_empty_decision(client):
    resp = client.post("/api/session-assignments", json={"response_id": "7"})

    assert resp.status_code == 400
    assert "exactly one" in resp.get_json()["error"].lower()
    assert load_session_assignments(client.project) == {}
```

- [ ] **Step 2: Run to verify they fail**

Run: `python3 -m pytest tests/test_session_assignments_api.py -q`
Expected: `ModuleNotFoundError: ... session_assignments_blueprint`.

- [ ] **Step 3: Implement** (`app/src/web/blueprints/session_assignments_blueprint.py`)

```python
"""Thin Flask adapter over src.session_assignments / src.participants_sessions."""

import shutil
from pathlib import Path

from flask import Blueprint, jsonify, request

from src.participants_converter import load_participant_source
from src.participants_sessions import session_assignment_table
from src.session_assignments import (
    SessionAssignmentError,
    load_session_assignments,
    set_assignment,
    unset_assignment,
)

from .conversion_participants_io import (
    _expected_delimiter_for_suffix,
    _normalize_separator_option,
    _resolve_participants_sheet_arg,
    _save_participants_upload_to_temp,
)
from .tools_helpers import _resolve_requested_or_current_project_root

session_assignments_bp = Blueprint("session_assignments", __name__)


@session_assignments_bp.route("/api/session-assignments/review", methods=["POST"])
def api_review_session_assignments():
    root = _resolve_requested_or_current_project_root(request.form.get("project_path"))
    id_column = request.form.get("id_column", "").strip()
    if not id_column:
        return jsonify({"error": "Select the participant ID column first."}), 400
    try:
        upload = _save_participants_upload_to_temp(
            uploaded_file=request.files.get("file"),
            temp_prefix="prism_session_review_",
        )
    except ValueError as exc:
        return jsonify({"error": str(exc)}), 400
    try:
        input_path = Path(str(upload["input_path"]))
        suffix = str(upload["suffix"])
        df, _ = load_participant_source(
            input_path,
            separator=_expected_delimiter_for_suffix(
                suffix, _normalize_separator_option(request.form.get("separator"))
            ),
            sheet=_resolve_participants_sheet_arg(
                input_path=input_path, suffix=suffix, sheet_value=request.form.get("sheet")
            ),
        )
        decisions = load_session_assignments(root) if root else {}
        rows, warnings = session_assignment_table(
            df,
            id_column,
            request.form.get("date_column", "").strip() or "startdate",
            decisions=decisions,
        )
        return jsonify({"rows": rows, "warnings": warnings})
    except ValueError as exc:
        return jsonify({"error": str(exc)}), 400
    finally:
        shutil.rmtree(str(upload["tmp_dir"]), ignore_errors=True)


@session_assignments_bp.route("/api/session-assignments", methods=["POST"])
def api_set_session_assignment():
    payload = request.get_json(silent=True) or {}
    root = _resolve_requested_or_current_project_root(payload.get("project_path"))
    if root is None:
        return jsonify({"error": "No project selected"}), 400
    response_id = str(payload.get("response_id") or "").strip()
    try:
        if payload.get("clear"):
            responses = unset_assignment(root, response_id)
        else:
            responses = set_assignment(
                root,
                response_id,
                skip=bool(payload.get("skip")),
                session=payload.get("session"),
            )
    except SessionAssignmentError as exc:
        return jsonify({"error": str(exc)}), 400
    return jsonify({"ok": True, "responses": responses})
```

`app/prism-studio.py`: add
```python
    (
        "src.web.blueprints.session_assignments_blueprint",
        "session_assignments_bp",
        "session_assignments",
    ),
```
right after the `session_map_blueprint` tuple.

- [ ] **Step 4: Run**

Run: `python3 -m pytest tests/test_session_assignments_api.py tests/test_session_map_api.py -q`
Expected: all pass. (The `session` payload value may be `None`/`str`; `set_assignment` validates.)

- [ ] **Step 5: Commit**

```bash
git add app/src/web/blueprints/session_assignments_blueprint.py app/prism-studio.py tests/test_session_assignments_api.py
git commit -m "feat(gui-api): session review and decision endpoints"
```

---

### Task 7: GUI — dates-derived mode of the Session ID box, and the notes section

**Files:**
- Modify: `app/static/js/modules/converter/survey-session-assignments.js` (create; used again in Task 8)
- Modify: `app/static/js/modules/converter/survey-convert.js` (import + create + `initialize()`, next to `surveyUnmatchedTemplatesController`, ~line 2344 and ~2413)
- Modify: `app/static/js/modules/converter/survey-workflow-convert.js` (skip the "enter a session ID" check in dates mode, ~line 143)
- Modify: `app/static/js/modules/converter/survey-convert.js` (re-run the session check when the dropdown changes, so the session-map panel lists the real labels)
- Modify: `app/static/js/modules/converter/survey-conversion-summary.js` (`displayConversionSummary`: Notes section)
- Modify: `app/templates/converter_survey.html` (ids on the badge/hint)
- Modify: `app/static/css/converter.css`
- Test: `tests/e2e/test_converter_flows.py` (append)

**Interfaces:**
- Produces: `createSurveySessionAssignmentsController({ ... })` with `initialize()`; DOM ids `convertSessionBadge`, `convertSessionHint` (the hint already has `convertSessionHint`; add `convertSessionBadge` to the badge `<span>`); CSS class `session-derived` on `#convertSessionGroup`.
- Dates mode = `#convertDuplicateHandling` value `"sessions"`.

- [ ] **Step 1: Write the failing e2e tests** (append to `tests/e2e/test_converter_flows.py`)

```python
def test_dates_mode_disables_the_session_id_box_and_explains_why(app_page, studio_url):
    open_survey_tab(app_page, studio_url)
    app_page.select_option("#convertDuplicateHandling", "sessions")

    expect(app_page.locator("#convertSessionSelect")).to_be_disabled()
    expect(app_page.locator("#convertSessionCustom")).to_be_disabled()
    expect(app_page.locator("#convertSessionHint")).to_contain_text("completed responses only")
    expect(app_page.locator("#convertSessionBadge")).to_have_text("FROM DATES")

    app_page.select_option("#convertDuplicateHandling", "error")
    expect(app_page.locator("#convertSessionCustom")).to_be_enabled()
    expect(app_page.locator("#convertSessionBadge")).to_have_text("REQUIRED")


def test_dates_mode_converts_without_a_typed_session_id(app_page, studio_url, tmp_path, project):
    from tests.lsa_fixtures import make_library, make_lsa
    import shutil

    shutil.copy(make_library(tmp_path) / "survey-wellbeing.json", project / "code" / "library" / "survey")
    open_survey_tab(app_page, studio_url)
    app_page.set_input_files("#convertSurveyFile", str(make_lsa(tmp_path)))
    app_page.select_option("#convertIdColumn", "token")
    app_page.select_option("#convertDuplicateHandling", "sessions")

    app_page.click("#previewBtn")
    expect(app_page.locator("#convertBtn")).to_be_enabled(timeout=30000)
    expect(app_page.locator("#conversionSummaryBody")).to_contain_text("incomplete response(s) left out")
    app_page.click("#convertBtn")
    app_page.wait_for_function(
        "() => !document.getElementById('surveyRunProgressContainer') "
        "|| getComputedStyle(document.getElementById('surveyRunProgressContainer')).display === 'none'",
        timeout=60000,
    )

    assert sorted(p.name for p in (project / "sub-a").glob("ses-*")) == ["ses-1", "ses-2"]


def test_dates_mode_refreshes_the_session_map_panel_with_the_real_labels(app_page, studio_url, tmp_path, project):
    import json

    from tests.lsa_fixtures import make_library, make_lsa
    import shutil

    app_page.allowed_http[409] = "/api/survey-detect-version-contexts"  # unmapped labels are the point
    (project / "project.json").write_text(json.dumps({"StudyDesign": {"Timepoints": "multiple"}}))
    shutil.copy(make_library(tmp_path) / "survey-wellbeing.json", project / "code" / "library" / "survey")
    open_survey_tab(app_page, studio_url)
    app_page.set_input_files("#convertSurveyFile", str(make_lsa(tmp_path)))
    app_page.select_option("#convertIdColumn", "token")

    app_page.select_option("#convertDuplicateHandling", "sessions")

    # a has two completed responses, c one: the generated labels are 1 and 2 (not a typed one).
    expect(app_page.locator("#sessionMapRows input")).to_have_count(2, timeout=30000)
```

- [ ] **Step 2: Run to verify they fail**

Run: `python3 -m pytest tests/e2e/test_converter_flows.py -q -p no:cacheprovider -k "dates_mode"`
Expected: first test: `#convertSessionBadge` not found / select not disabled; second: "Please enter a session ID" blocks the preview/convert (no `convertBtn`); third: the session-map panel is not refreshed (0 inputs).

- [ ] **Step 3: Implement**

`app/templates/converter_survey.html`: give the badge an id: `<span class="badge ms-1 session-required-badge" id="convertSessionBadge">REQUIRED</span>`.

`app/static/css/converter.css`: append

```css
/* Dates mode: the Session ID box is not used, so it is neutral instead of red/green. */
#convertSessionGroup.session-derived { --session-required: var(--bs-secondary); }
#convertSessionGroup.session-derived:has(#convertSessionSelect:valid, #convertSessionCustom:not(:placeholder-shown)) { --session-required: var(--bs-secondary); }
```

`app/static/js/modules/converter/survey-session-assignments.js` (the review table is added in Task 8; here only the mode switch):

```js
export function createSurveySessionAssignmentsController() {
    const DERIVED_HINT = 'Sessions are numbered 1, 2, … by startdate (completed responses only).';

    function applyMode() {
        const derived = document.getElementById('convertDuplicateHandling')?.value === 'sessions';
        const group = document.getElementById('convertSessionGroup');
        const select = document.getElementById('convertSessionSelect');
        const custom = document.getElementById('convertSessionCustom');
        const hint = document.getElementById('convertSessionHint');
        const badge = document.getElementById('convertSessionBadge');
        if (!group) return;
        group.classList.toggle('session-derived', derived);
        [select, custom].forEach((el) => {
            if (!el) return;
            el.disabled = derived;
            if (derived) el.value = '';
        });
        if (hint) {
            if (hint.dataset.original === undefined) hint.dataset.original = hint.firstChild?.textContent || '';
            if (hint.firstChild) hint.firstChild.textContent = derived ? DERIVED_HINT : hint.dataset.original;
        }
        if (badge) badge.textContent = derived ? 'FROM DATES' : 'REQUIRED';
    }

    function initialize() {
        document.getElementById('convertDuplicateHandling')?.addEventListener('change', applyMode);
        applyMode();
    }

    return { initialize, applyMode };
}
```

`survey-convert.js`: also, next to the other listeners that call `syncVersionWizardContext()`, add `document.getElementById('convertDuplicateHandling')?.addEventListener('change', () => syncVersionWizardContext());` (that call already sends `duplicate_handling`, so the unmapped-label list is built from the generated labels). And `import { createSurveySessionAssignmentsController } from './survey-session-assignments.js';` next to the other controller imports; after `surveyUnmatchedTemplatesController` is created add `const surveySessionAssignmentsController = createSurveySessionAssignmentsController();` and, next to `surveyUnmatchedTemplatesController.initialize();`, `surveySessionAssignmentsController.initialize();`.

`survey-workflow-convert.js` (~line 143): change the check to

```js
        const sessionsFromDates = document.getElementById('convertDuplicateHandling')?.value === 'sessions';
        const sessionVal = getSurveySessionValue();
        if (!sessionVal && !sessionsFromDates) {
```
and guard the later `formData.append('session', sessionVal); appendLog('Forcing session ID: ...')` with `if (sessionVal) { ... }`.

`survey-conversion-summary.js`, in `displayConversionSummary` right after `let html = '';` add:

```js
        const notes = Array.isArray(summary.conversion_warnings) ? summary.conversion_warnings : [];
        if (notes.length > 0) {
            html += `<h6 class="mb-2"><i class="fas fa-circle-info me-1"></i>Notes</h6><ul class="small mb-3">`
                + notes.map((note) => `<li>${escapeHtml(String(note))}</li>`).join('')
                + `</ul>`;
        }
```
(`escapeHtml` is already a dependency of this controller.)

- [ ] **Step 4: Run**

Run: `python3 -m pytest tests/e2e/test_converter_flows.py tests/test_converter_workflow_wiring.py -q -p no:cacheprovider`
Expected: all pass. If a wiring test asserts the exact old text of `survey-workflow-convert.js` around the session check, update that expected string to the new two-line form (it encodes the old behaviour).

- [ ] **Step 5: Commit**

```bash
git add app/static app/templates/converter_survey.html tests/e2e/test_converter_flows.py tests/test_converter_workflow_wiring.py
git commit -m "feat(survey-gui): dates mode disables the Session ID box; preview shows the notes"
```

---

### Task 8: GUI — review table

**Files:**
- Modify: `app/static/js/modules/converter/survey-session-assignments.js` (add the table)
- Modify: `app/templates/converter_survey.html` (card with a button and a container, below the "Repeated participant IDs" column's row)
- Test: `tests/e2e/test_converter_flows.py` (append)

**Interfaces:**
- Consumes: `POST /api/session-assignments/review` and `POST /api/session-assignments` (Task 6); `fetchWithApiFallback` from `../../shared/api.js`.
- Produces DOM ids: `sessionAssignmentsCard` (hidden unless dates mode), `sessionAssignmentsBtn`, `sessionAssignmentsBody`.

- [ ] **Step 1: Write the failing e2e test**

```python
def test_review_table_shows_the_responses_and_a_skip_changes_the_preview(app_page, studio_url, tmp_path, project):
    from tests.lsa_fixtures import make_library, make_lsa
    import shutil

    shutil.copy(make_library(tmp_path) / "survey-wellbeing.json", project / "code" / "library" / "survey")
    open_survey_tab(app_page, studio_url)
    app_page.set_input_files("#convertSurveyFile", str(make_lsa(tmp_path)))
    app_page.select_option("#convertIdColumn", "token")
    app_page.select_option("#convertDuplicateHandling", "sessions")

    app_page.click("#sessionAssignmentsBtn")

    rows = app_page.locator("#sessionAssignmentsBody tbody tr")
    expect(rows).to_have_count(6, timeout=15000)
    expect(app_page.locator("#sessionAssignmentsBody")).to_contain_text("left out")
    row2 = app_page.locator("#sessionAssignmentsBody tr[data-response-id='2']")
    expect(row2.locator(".session-cell")).to_have_text("1")

    row2.locator("input[type=checkbox][data-role=skip]").check()   # skip a's first completed response
    expect(app_page.locator("#sessionAssignmentsBody tr[data-response-id='3'] .session-cell")).to_have_text("1")
    import json
    saved = json.loads((project / "code" / "session_assignments.json").read_text())
    assert saved["responses"] == {"2": {"skip": True}}
```

- [ ] **Step 2: Run to verify it fails**

Run: `python3 -m pytest tests/e2e/test_converter_flows.py -q -p no:cacheprovider -k review_table`
Expected: `#sessionAssignmentsBtn` not found.

- [ ] **Step 3: Implement**

`app/templates/converter_survey.html`: directly after the row that contains `convertDuplicateHandling` (before `<div id="sessionMapPanel"`), add

```html
                            <div id="sessionAssignmentsCard" class="mb-3 d-none">
                                <button type="button" class="btn btn-sm btn-outline-secondary" id="sessionAssignmentsBtn">
                                    <i class="fas fa-table-list me-1"></i>Review session assignment
                                </button>
                                <div id="sessionAssignmentsBody" class="mt-2 small"></div>
                            </div>
```

`survey-session-assignments.js`: replace the file with the version below (the mode switch stays; the table is added). The card's visibility follows the mode.

```js
import { fetchWithApiFallback } from '../../shared/api.js';

export function createSurveySessionAssignmentsController() {
    const DERIVED_HINT = 'Sessions are numbered 1, 2, … by startdate (completed responses only).';
    const esc = (value) => String(value ?? '').replace(/[&<>"']/g, (c) => ({
        '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;',
    }[c]));

    function applyMode() {
        const derived = document.getElementById('convertDuplicateHandling')?.value === 'sessions';
        const group = document.getElementById('convertSessionGroup');
        const select = document.getElementById('convertSessionSelect');
        const custom = document.getElementById('convertSessionCustom');
        const hint = document.getElementById('convertSessionHint');
        const badge = document.getElementById('convertSessionBadge');
        if (!group) return;
        group.classList.toggle('session-derived', derived);
        [select, custom].forEach((el) => {
            if (!el) return;
            el.disabled = derived;
            if (derived) el.value = '';
        });
        if (hint) {
            if (hint.dataset.original === undefined) hint.dataset.original = hint.firstChild?.textContent || '';
            if (hint.firstChild) hint.firstChild.textContent = derived ? DERIVED_HINT : hint.dataset.original;
        }
        if (badge) badge.textContent = derived ? 'FROM DATES' : 'REQUIRED';
        document.getElementById('sessionAssignmentsCard')?.classList.toggle('d-none', !derived);
    }

    function render(body, data) {
        const rows = Array.isArray(data.rows) ? data.rows : [];
        let html = '<table class="table table-sm table-bordered mb-2"><thead><tr>'
            + '<th>Participant</th><th>Response</th><th>Date</th><th>Done</th><th>Last page</th>'
            + '<th>Session</th><th>Skip</th><th>Set label</th></tr></thead><tbody>';
        rows.forEach((r) => {
            const left = r.session === null;
            html += `<tr data-response-id="${esc(r.response_id)}" class="${left ? 'text-muted' : ''}">`
                + `<td>${esc(r.participant)}</td><td>${esc(r.response_id)}</td>`
                + `<td>${esc(String(r.date).slice(0, 16))}</td><td>${r.completed ? 'yes' : 'no'}</td>`
                + `<td>${esc(r.lastpage)}</td>`
                + `<td class="session-cell">${left ? `left out (${esc(r.reason)})` : esc(r.session)}</td>`
                + `<td><input type="checkbox" data-role="skip" ${r.reason === 'skipped' ? 'checked' : ''}></td>`
                + `<td><input type="text" data-role="label" class="form-control form-control-sm" size="8"`
                + ` value="${r.reason === 'override' ? esc(r.session) : ''}" placeholder="auto"></td></tr>`;
        });
        html += '</tbody></table>';
        (data.warnings || []).forEach((w) => { html += `<div class="text-muted">${esc(w)}</div>`; });
        body.innerHTML = html;
    }

    async function save(body, responseId, payload) {
        const response = await fetchWithApiFallback('/api/session-assignments', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ response_id: responseId, ...payload }),
        });
        const data = await response.json();
        if (!response.ok) {
            body.insertAdjacentHTML('afterbegin', `<div class="text-danger">${esc(data.error || 'Save failed')}</div>`);
            return false;
        }
        return true;
    }

    async function load() {
        const body = document.getElementById('sessionAssignmentsBody');
        const file = document.getElementById('convertSurveyFile')?.files?.[0];
        const idColumn = document.getElementById('convertIdColumn')?.value || '';
        if (!file || !idColumn) {
            body.textContent = 'Choose the survey file (from your computer) and the participant ID column first.';
            return;
        }
        const formData = new FormData();
        formData.append('file', file);
        formData.append('id_column', idColumn);
        const response = await fetchWithApiFallback('/api/session-assignments/review', { method: 'POST', body: formData });
        const data = await response.json();
        if (!response.ok) {
            body.textContent = data.error || 'Could not build the review table.';
            return;
        }
        render(body, data);
    }

    function initialize() {
        document.getElementById('convertDuplicateHandling')?.addEventListener('change', applyMode);
        document.getElementById('sessionAssignmentsBtn')?.addEventListener('click', load);
        const body = document.getElementById('sessionAssignmentsBody');
        body?.addEventListener('change', async (event) => {
            const row = event.target.closest('tr[data-response-id]');
            if (!row) return;
            const responseId = row.dataset.responseId;
            const role = event.target.dataset.role;
            let payload = null;
            if (role === 'skip') {
                payload = event.target.checked ? { skip: true } : { clear: true };
            } else if (role === 'label') {
                const label = event.target.value.trim();
                payload = label ? { session: label } : { clear: true };
            }
            // clearing a response that has no saved decision is a no-op, not an error
            if (payload && (await save(body, responseId, payload) || payload.clear)) await load();
        });
        applyMode();
    }

    return { initialize, applyMode };
}
```

(`clear` on a response with no decision returns 400 from the endpoint; the `|| payload.clear` makes the table reload anyway so it reflects the real state.)

- [ ] **Step 4: Run**

Run: `python3 -m pytest tests/e2e/test_converter_flows.py tests/test_converter_workflow_wiring.py -q -p no:cacheprovider`
Expected: all pass.

- [ ] **Step 5: Commit**

```bash
git add app/static/js/modules/converter/survey-session-assignments.js app/templates/converter_survey.html tests/e2e/test_converter_flows.py
git commit -m "feat(survey-gui): review table for session assignment, saved through the same backend"
```

---

### Task 9: Finish

- [ ] Run the whole suite: `python3 -m pytest tests -q -p no:cacheprovider --deselect tests/test_validator_no_fake_environment.py::test_fake_environment_package_is_gone` (that one fails only because of a leftover empty `app/src/environment/providers/` folder on the author's machine); report any other failure by name.
- [ ] `python3 tests/verify_repo.py --check dual-tree-drift --no-fix`.
- [ ] Manual check against the real archive (not in git): `python3 app/prism_tools.py sessions review --input .venv/survey_archive_939812.lsa --id-column token` — expect 144070 and 144112 each with at most the completed responses numbered, the rest "left out (incomplete)", and `No completed response for: 144112 ...`; then in the Studio: Survey tab, tick "Number as sessions by date", open the review table, skip one row, Preview.
- [ ] `.gitleaks.toml` has an uncommitted allowlist for `res_id_col="token"` (a secret scanner flagged the `token` column name in `tests/test_survey_sessions_by_date.py`); review and commit it with this branch if it is still needed.
- [ ] `/ponytail:ponytail-audit` on the branch (CLAUDE.md, before merge); apply worthwhile findings, re-run tests.
- [ ] superpowers:finishing-a-development-branch.
