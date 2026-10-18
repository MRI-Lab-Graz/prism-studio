# Project Required-Fields Gate and Timepoints Policy Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Block every project-working tool until the project's required fields are set (telling the user at save time), and make `StudyDesign.Timepoints` drive session naming in every importer (single = always `ses-1`, multiple = mapped, defaults 1, 2, 3).

**Architecture:** One backend module (`src/project_ready.py`) decides readiness; two choke points enforce it (CLI `dispatch_prism_tools`, Flask `before_request`). The existing `src/session_map.py` gains one function, `session_target()`, that all importers call instead of their own heuristics. GUI and CLI stay thin adapters over those functions.

**Tech Stack:** Python 3 (argparse CLI, Flask), pytest, vanilla JS modules with node tests (`*.test.js`).

**Spec:** `docs/superpowers/specs/2026-10-15-project-required-fields-gate-design.md`

## Global Constraints

- One implementation: logic in `src/`, CLI + Flask are thin adapters (CLAUDE.md "One implementation").
- Required fields (one constant): `Basics.Name`, `Basics.Authors`, `Basics.Keywords`, `StudyDesign.Timepoints`.
- No `project.json` in the addressed folder means **no gate** (not a PRISM project).
- `single` timepoint: every file is `ses-1`, whatever label the data carries; the report warns that the label was replaced.
- `multiple` timepoints: session label mapped via `code/session_map.json`; defaults offered as 1, 2, 3 in order of first appearance, never written until the user confirms.
- Session labels are exact strings, never zero-padded or coerced, **except** the declared-single rule above.
- Save on the Projects page stays allowed for incomplete projects.
- New code under `src/` only; do not add a same-named file under `app/src/` (dual-tree drift; check with `python3 -c "import src.<mod> as m; print(m.__file__)"`).
- TDD: failing test first in every task; run `python tests/verify_repo.py --check dual-tree-drift --no-fix` before the final task's commit.
- Text-format files are never git-annexed (not touched by this plan).

## Review Focus

- Project folder has `project.json` that is invalid JSON: gate reports a readable error, not a traceback (Task 1).
- Field present but whitespace-only (`"Name": "  "`) or empty list for Authors/Keywords counts as missing (Task 1).
- `--help` / argparse errors must not be blocked by the gate (Task 2).
- CLI command given `--output` pointing at a not-yet-existing folder: not gated, no crash (Task 2).
- `single` project whose data has labels `1` and `01` or `pre` and `post` in one file: all become `ses-1` and the report warns (Task 6).
- Re-running an import after the user fixes the Projects page works with no restart (gate reads `project.json` per request, no caching) (Tasks 3, 4).

---

### Task 1: Readiness rule in the backend

**Files:**
- Create: `src/project_ready.py`
- Test: `tests/test_project_ready.py`

**Interfaces:**
- Produces: `REQUIRED_FIELDS: tuple[tuple[str, str], ...]` = `(("Basics","Name"),("Basics","Authors"),("Basics","Keywords"),("StudyDesign","Timepoints"))`; `missing_required_fields(project_path: str | Path) -> list[str]` (labels like `"Authors"`, `"Timepoints"`; `[]` when no `project.json` or all set); `class ProjectNotReadyError(ValueError)` with `.missing: list[str]` and a message from `not_ready_message(missing)`; `not_ready_message(missing: list[str]) -> str`; `require_project_ready(project_path) -> None` (raises `ProjectNotReadyError`).

- [ ] **Step 1: Write the failing tests**

```python
# tests/test_project_ready.py
import json
import pytest
from src.project_ready import (
    ProjectNotReadyError, missing_required_fields, not_ready_message, require_project_ready,
)

FULL = {
    "Basics": {"Name": "N", "Authors": ["A"], "Keywords": ["k"]},
    "StudyDesign": {"Timepoints": "single"},
}

def _proj(tmp_path, data):
    (tmp_path / "project.json").write_text(json.dumps(data), encoding="utf-8")
    return tmp_path

def test_no_project_json_is_not_gated(tmp_path):
    assert missing_required_fields(tmp_path) == []

def test_complete_project_is_ready(tmp_path):
    assert missing_required_fields(_proj(tmp_path, FULL)) == []

@pytest.mark.parametrize("section,field,label", [
    ("Basics", "Name", "Name"), ("Basics", "Authors", "Authors"),
    ("Basics", "Keywords", "Keywords"), ("StudyDesign", "Timepoints", "Timepoints"),
])
def test_each_missing_field_is_reported(tmp_path, section, field, label):
    data = json.loads(json.dumps(FULL))
    del data[section][field]
    assert missing_required_fields(_proj(tmp_path, data)) == [label]

def test_blank_and_empty_values_count_as_missing(tmp_path):
    data = {"Basics": {"Name": "  ", "Authors": [], "Keywords": [""]},
            "StudyDesign": {"Timepoints": "weekly"}}
    assert missing_required_fields(_proj(tmp_path, data)) == ["Name", "Authors", "Keywords", "Timepoints"]

def test_invalid_json_gives_readable_error(tmp_path):
    (tmp_path / "project.json").write_text("{nope", encoding="utf-8")
    with pytest.raises(ProjectNotReadyError) as exc:
        require_project_ready(tmp_path)
    assert "project.json" in str(exc.value)

def test_require_raises_with_message(tmp_path):
    _proj(tmp_path, {})
    with pytest.raises(ProjectNotReadyError) as exc:
        require_project_ready(tmp_path)
    assert exc.value.missing == ["Name", "Authors", "Keywords", "Timepoints"]
    assert "Projects page" in str(exc.value) and "Authors" in str(exc.value)

def test_accepts_project_json_path(tmp_path):
    _proj(tmp_path, FULL)
    assert missing_required_fields(tmp_path / "project.json") == []
```

- [ ] **Step 2: Run to verify failure**

Run: `python -m pytest tests/test_project_ready.py -v`
Expected: FAIL (`ModuleNotFoundError: src.project_ready`).

- [ ] **Step 3: Implement**

```python
# src/project_ready.py
"""Is a PRISM project complete enough to work with? (one rule for CLI and GUI)

A folder without project.json is not a PRISM project and is never gated.
Spec: docs/superpowers/specs/2026-10-15-project-required-fields-gate-design.md
"""

from __future__ import annotations

import json
from pathlib import Path

REQUIRED_FIELDS = (
    ("Basics", "Name"),
    ("Basics", "Authors"),
    ("Basics", "Keywords"),
    ("StudyDesign", "Timepoints"),
)
_TIMEPOINT_VALUES = ("single", "multiple")


class ProjectNotReadyError(ValueError):
    def __init__(self, missing: list[str], message: str | None = None) -> None:
        self.missing = missing
        super().__init__(message or not_ready_message(missing))


def not_ready_message(missing: list[str]) -> str:
    return (
        "This project is not finished: " + ", ".join(missing) + " "
        "still need(s) to be set on the Projects page. PRISM tools are blocked "
        "until then (saving the page is always allowed)."
    )


def _root(project_path) -> Path:
    path = Path(project_path).expanduser()
    return path.parent if path.is_file() else path


def _filled(value) -> bool:
    if isinstance(value, str):
        return bool(value.strip())
    if isinstance(value, list):
        return any(_filled(v) for v in value)
    return value is not None


def missing_required_fields(project_path) -> list[str]:
    pj = _root(project_path) / "project.json"
    if not pj.is_file():
        return []
    try:
        data = json.loads(pj.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        raise ProjectNotReadyError([], f"{pj} could not be read: {exc}") from exc
    data = data if isinstance(data, dict) else {}
    missing = []
    for section, field in REQUIRED_FIELDS:
        value = (data.get(section) or {}).get(field) if isinstance(data.get(section), dict) else None
        ok = value in _TIMEPOINT_VALUES if field == "Timepoints" else _filled(value)
        if not ok:
            missing.append(field)
    return missing


def require_project_ready(project_path) -> None:
    missing = missing_required_fields(project_path)
    if missing:
        raise ProjectNotReadyError(missing)
```

- [ ] **Step 4: Run to verify pass**

Run: `python -m pytest tests/test_project_ready.py -v`
Expected: PASS (8 tests).

- [ ] **Step 5: Commit**

```bash
git add src/project_ready.py tests/test_project_ready.py
git commit -m "feat(project): one readiness rule for required project fields"
```

---

### Task 2: CLI gate in dispatch

**Files:**
- Modify: `app/src/cli/dispatch.py` (top of `dispatch_prism_tools`, before the `if args.command == "anonymize"` chain)
- Test: `tests/test_cli_project_ready_gate.py`

**Interfaces:**
- Consumes: `require_project_ready`, `ProjectNotReadyError` (Task 1).
- Produces: `project_path_from_args(args) -> str | None` in `dispatch.py` (first of `args.project`, `args.dataset`, `args.output` that has a `project.json`, else `None`); `GATE_EXEMPT_COMMANDS = {"session-map", "environment", "demo"}`.

Existing CLI tests in `tests/test_cli_dispatch_routing.py` show how to build `args`/handlers; reuse that style.

- [ ] **Step 1: Write the failing tests**

```python
# tests/test_cli_project_ready_gate.py
import json
from argparse import Namespace
from unittest.mock import MagicMock
import pytest
from src.cli.dispatch import dispatch_prism_tools

def _incomplete(tmp_path):
    (tmp_path / "project.json").write_text(json.dumps({"Basics": {"Name": "x"}}), encoding="utf-8")
    return str(tmp_path)

def _run(args, handlers):
    parsers = {"root": MagicMock(), "survey": MagicMock()}
    dispatch_prism_tools(args, parsers=parsers, handlers=handlers)

def test_tool_command_blocked_on_incomplete_project(tmp_path, capsys):
    h = {"survey_convert": MagicMock()}
    args = Namespace(command="survey", action="convert", project=_incomplete(tmp_path))
    with pytest.raises(SystemExit) as exc:
        _run(args, h)
    assert exc.value.code == 2
    assert "Timepoints" in capsys.readouterr().out
    h["survey_convert"].assert_not_called()

def test_session_map_is_exempt(tmp_path):
    h = {"session_map_show": MagicMock()}
    args = Namespace(command="session-map", action="show", project=_incomplete(tmp_path))
    _run(args, h)
    h["session_map_show"].assert_called_once()

def test_non_project_output_is_not_gated(tmp_path):
    h = {"survey_convert": MagicMock()}
    args = Namespace(command="survey", action="convert", project=None, output=str(tmp_path / "new"))
    _run(args, h)
    h["survey_convert"].assert_called_once()

def test_complete_project_runs(tmp_path):
    (tmp_path / "project.json").write_text(json.dumps({
        "Basics": {"Name": "N", "Authors": ["A"], "Keywords": ["k"]},
        "StudyDesign": {"Timepoints": "single"}}), encoding="utf-8")
    h = {"survey_convert": MagicMock()}
    _run(Namespace(command="survey", action="convert", project=str(tmp_path)), h)
    h["survey_convert"].assert_called_once()
```

- [ ] **Step 2: Run to verify failure**

Run: `python -m pytest tests/test_cli_project_ready_gate.py -v`
Expected: FAIL (first test: handler was called / no SystemExit).

- [ ] **Step 3: Implement** — add to `dispatch.py` above `dispatch_prism_tools`, and call it first inside:

```python
import sys
from pathlib import Path

from src.project_ready import ProjectNotReadyError, require_project_ready

# Commands that must keep working on an unfinished project (they fix or inspect it).
GATE_EXEMPT_COMMANDS = {"session-map", "environment", "demo"}


def project_path_from_args(args: Namespace) -> str | None:
    for name in ("project", "dataset", "output"):
        value = getattr(args, name, None)
        if value and (Path(str(value)).expanduser() / "project.json").is_file():
            return str(value)
    return None
```

Inside `dispatch_prism_tools`, directly after `root_parser = parsers["root"]`:

```python
    if args.command not in GATE_EXEMPT_COMMANDS:
        project = project_path_from_args(args)
        if project:
            try:
                require_project_ready(project)
            except ProjectNotReadyError as exc:
                print(f"Error: {exc}")
                sys.exit(2)
```

(`--help` and argparse errors exit inside `parser.parse_args()` before dispatch, so they are never gated.)

- [ ] **Step 4: Run to verify pass**

Run: `python -m pytest tests/test_cli_project_ready_gate.py tests/test_cli_dispatch_routing.py -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add app/src/cli/dispatch.py tests/test_cli_project_ready_gate.py
git commit -m "feat(cli): block project commands until required fields are set"
```

---

### Task 3: Flask gate

**Files:**
- Create: `app/src/web/project_ready_guard.py`
- Modify: `app/prism-studio.py` (call `install_project_ready_guard(app)` right after `install_cross_site_guard(app)` at ~line 1025; do not add logic to the monolith)
- Test: `tests/test_project_ready_guard.py`

**Interfaces:**
- Consumes: `missing_required_fields`, `not_ready_message` (Task 1); Flask `session["current_project_path"]` (set by `ensure_project_selected_first`).
- Produces: `install_project_ready_guard(app: Flask) -> None`; `is_gate_exempt(path: str, method: str) -> bool`; blocked response: HTTP 409 JSON `{"error": <message>, "code": "project_not_ready", "missing": [...]}`.

Rule: only requests that act (any non-GET, or any `/api/` path) are gated; page GETs stay open so the user can see the banner. Exempt: `/static/`, `/favicon.ico`, `/health`, `/shutdown`, `/specifications`, `/projects`, `/api/projects`, `/api/settings`, `/api/browse-folder`, `/api/browse-file`, `/api/fs`, `/api/v1/`, `/editor`, `/api/template-editor/`, `/api/runtime-capabilities`, `/api/list-library-files`, `/api/session-map`, `/api/survey-customizer/` .

- [ ] **Step 1: Write the failing tests**

```python
# tests/test_project_ready_guard.py
import json
import pytest
from flask import Flask, jsonify
from app.src.web.project_ready_guard import install_project_ready_guard, is_gate_exempt
```

Use the import style of `tests/test_cross_site_guard.py` for the module path (check its first lines and copy the exact import form). Test body:

```python
@pytest.fixture
def client(tmp_path):
    app = Flask(__name__)
    app.secret_key = "t"
    install_project_ready_guard(app)
    @app.route("/api/tool", methods=["POST"])
    def tool(): return jsonify(ok=True)
    @app.route("/api/projects/save", methods=["POST"])
    def save(): return jsonify(ok=True)
    @app.route("/converter")
    def page(): return "page"
    return app.test_client(), tmp_path

def _set_project(client, path):
    with client.session_transaction() as s:
        s["current_project_path"] = str(path)

def test_tool_blocked_with_409(client):
    c, root = client
    (root / "project.json").write_text(json.dumps({}), encoding="utf-8")
    _set_project(c, root)
    r = c.post("/api/tool")
    assert r.status_code == 409
    body = r.get_json()
    assert body["code"] == "project_not_ready" and "Timepoints" in body["missing"]

def test_projects_api_and_pages_stay_open(client):
    c, root = client
    (root / "project.json").write_text(json.dumps({}), encoding="utf-8")
    _set_project(c, root)
    assert c.post("/api/projects/save").status_code == 200
    assert c.get("/converter").status_code == 200

def test_no_project_selected_not_gated(client):
    c, _ = client
    assert c.post("/api/tool").status_code == 200

def test_fixing_project_unblocks_without_restart(client):
    c, root = client
    pj = root / "project.json"
    pj.write_text("{}", encoding="utf-8")
    _set_project(c, root)
    assert c.post("/api/tool").status_code == 409
    pj.write_text(json.dumps({"Basics": {"Name": "N", "Authors": ["A"], "Keywords": ["k"]},
                              "StudyDesign": {"Timepoints": "single"}}), encoding="utf-8")
    assert c.post("/api/tool").status_code == 200

def test_exempt_list():
    assert is_gate_exempt("/api/session-map", "POST")
    assert not is_gate_exempt("/api/participants-convert-start", "POST")
```

- [ ] **Step 2: Run to verify failure**

Run: `python -m pytest tests/test_project_ready_guard.py -v`
Expected: FAIL (`ModuleNotFoundError`).

- [ ] **Step 3: Implement**

```python
# app/src/web/project_ready_guard.py
"""Block tool requests while the open project is missing required fields."""

from __future__ import annotations

from flask import Flask, jsonify, request, session

from src.project_ready import ProjectNotReadyError, missing_required_fields, not_ready_message

_EXEMPT_PREFIXES = (
    "/static/", "/projects", "/api/projects", "/api/settings", "/api/fs",
    "/api/v1/", "/editor", "/api/template-editor/", "/api/session-map",
    "/api/survey-customizer/",
)
_EXEMPT_PATHS = {
    "/favicon.ico", "/health", "/shutdown", "/specifications", "/api/browse-folder",
    "/api/browse-file", "/api/runtime-capabilities", "/api/list-library-files",
}


def is_gate_exempt(path: str, method: str) -> bool:
    if path in _EXEMPT_PATHS or path.startswith(_EXEMPT_PREFIXES):
        return True
    # Page views stay open so the user can read why tools are blocked.
    return method in ("GET", "HEAD") and not path.startswith("/api/")


def install_project_ready_guard(app: Flask) -> None:
    @app.before_request
    def _require_project_ready():
        project = session.get("current_project_path")
        if not project or is_gate_exempt(request.path, request.method):
            return None
        try:
            missing = missing_required_fields(project)
        except ProjectNotReadyError as exc:
            return jsonify({"error": str(exc), "code": "project_not_ready", "missing": []}), 409
        if missing:
            return (
                jsonify({"error": not_ready_message(missing), "code": "project_not_ready", "missing": missing}),
                409,
            )
        return None
```

Wire-up in `app/prism-studio.py` after `install_cross_site_guard(app)`:

```python
install_project_ready_guard(app)
```
(plus the import beside the other `request_guard` imports).

- [ ] **Step 4: Run to verify pass**

Run: `python -m pytest tests/test_project_ready_guard.py tests/test_cross_site_guard.py -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add app/src/web/project_ready_guard.py app/prism-studio.py tests/test_project_ready_guard.py
git commit -m "feat(web): 409 on tool requests while the project is unfinished"
```

---

### Task 4: Tell the user at save time

**Files:**
- Modify: `app/src/web/blueprints/projects.py` (`save_study_metadata` response — find `handle_save_study_metadata` with `grep -rn "def handle_save_study_metadata" app/src/web/blueprints`) and the file defining it
- Modify: `app/static/js/modules/projects/metadata.js` (save-success handler), `app/templates/includes/projects/study_metadata.html` (banner element)
- Test: `tests/test_study_metadata_save_not_ready.py`, `app/static/js/modules/projects/not-ready-banner.test.js`

**Interfaces:**
- Consumes: `missing_required_fields`, `not_ready_message` (Task 1).
- Produces: save response gains `"missing_required": list[str]` and `"not_ready_message": str | None`; JS export `notReadyText(missing) -> string` in a new `app/static/js/modules/projects/not-ready-banner.js` returning `""` for `[]`.

- [ ] **Step 1: Write failing tests**

Python (copy the Flask client setup from the nearest existing study-metadata save test: `grep -ln "study-metadata" tests/*.py`):

```python
def test_save_incomplete_returns_missing_required(client_with_project):
    r = client_with_project.post("/api/projects/study-metadata", json={"Basics": {"Name": "N"}})
    assert r.status_code == 200
    body = r.get_json()
    assert set(body["missing_required"]) >= {"Authors", "Keywords", "Timepoints"}
    assert "blocked" in body["not_ready_message"]

def test_save_complete_returns_no_missing(client_with_project):
    r = client_with_project.post("/api/projects/study-metadata", json={
        "Basics": {"Name": "N", "Authors": ["A"], "Keywords": ["k"]},
        "StudyDesign": {"Timepoints": "single"}})
    assert r.get_json()["missing_required"] == []
```

JS:

```js
import { notReadyText } from './not-ready-banner.js';
import assert from 'node:assert';
import test from 'node:test';
test('empty list gives empty text', () => assert.strictEqual(notReadyText([]), ''));
test('lists the missing fields and says tools are blocked', () => {
    const t = notReadyText(['Authors', 'Timepoints']);
    assert.match(t, /Saved/); assert.match(t, /Authors, Timepoints/); assert.match(t, /blocked/);
});
```
Match the runner/import style of `global-tier-totals.test.js`.

- [ ] **Step 2: Run to verify failure** — `python -m pytest tests/test_study_metadata_save_not_ready.py -v` and the node test (command: see `package.json` scripts / `tests/` README; typically `node --test app/static/js/modules/projects/not-ready-banner.test.js`). Expected: FAIL.

- [ ] **Step 3: Implement**
  - In the save handler, after writing `project.json`, add `missing = missing_required_fields(project_root)` and put `missing_required=missing`, `not_ready_message=(not_ready_message(missing) if missing else None)` into the JSON response.
  - `not-ready-banner.js`:

```js
export function notReadyText(missing) {
    if (!missing || !missing.length) return '';
    return `Saved. Tools are blocked until these are filled: ${missing.join(', ')}.`;
}
```
  - In `metadata.js` save-success path: render `notReadyText(response.missing_required)` into a new persistent `<div id="smNotReadyBanner" class="alert alert-warning">` in `study_metadata.html` (hidden when text is empty). Also fill the banner on page load from the `GET /api/projects/study-metadata` response, which gets the same `missing_required` field (add it in `handle_get_study_metadata` alongside).
  - Tool pages: in the shared fetch error path that displays `error` JSON, a 409 with `code == "project_not_ready"` appends a link to `/projects`. Find the shared helper with `grep -rn "response.ok" app/static/js/shared | head`.

- [ ] **Step 4: Run to verify pass** — both test commands. Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add -A app tests
git commit -m "feat(projects): banner and response field say tools are blocked until required fields are set"
```

---

### Task 5: Required-field list from the backend (no JS copy)

**Files:**
- Modify: `app/src/web/blueprints/projects_metadata_helpers.py:331-335` (`CREATION_BLOCKING_FIELDS` derived from `REQUIRED_FIELDS`), `app/static/js/modules/projects/metadata.js:3588` (`creationBlockingFields` read from the study-metadata GET response)
- Test: `tests/test_required_fields_parity.py`

**Interfaces:**
- Consumes: `REQUIRED_FIELDS` (Task 1).
- Produces: GET study-metadata response key `creation_blocking_fields: {section: [field,...]}`.

- [ ] **Step 1: Write the failing test**

```python
import re
from pathlib import Path
from src.project_ready import REQUIRED_FIELDS
from app.src.web.blueprints.projects_metadata_helpers import CREATION_BLOCKING_FIELDS  # use the repo's import form

def test_backend_constant_derives_from_required_fields():
    derived = {}
    for section, field in REQUIRED_FIELDS:
        derived.setdefault(section, set()).add(field)
    assert CREATION_BLOCKING_FIELDS == derived

def test_js_has_no_private_copy():
    js = Path("app/static/js/modules/projects/metadata.js").read_text(encoding="utf-8")
    assert not re.search(r"creationBlockingFields\s*=\s*\{\s*Basics", js)
```

- [ ] **Step 2:** `python -m pytest tests/test_required_fields_parity.py -v` → FAIL (JS copy present; constant is hand-written, may match but the JS check fails).

- [ ] **Step 3: Implement**
  - `projects_metadata_helpers.py`: replace the dict literal with

```python
from src.project_ready import REQUIRED_FIELDS

CREATION_BLOCKING_FIELDS: dict[str, set[str]] = {}
for _section, _field in REQUIRED_FIELDS:
    CREATION_BLOCKING_FIELDS.setdefault(_section, set()).add(_field)
```
  - GET study-metadata handler adds `creation_blocking_fields={k: sorted(v) for k, v in CREATION_BLOCKING_FIELDS.items()}`.
  - `metadata.js`: replace the literal at `creationBlockingFields = {...}` with a module variable populated from that response key (`window`-free: store in the module's existing state object), defaulting to the same literal only until the response arrives is **not** allowed; use `{}` and recompute after load.

- [ ] **Step 4:** run the parity test plus `python -m pytest tests -k "metadata and completeness" -v` and the projects JS tests. Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add -A app src tests
git commit -m "refactor(projects): required-field list comes from one backend constant"
```

---

### Task 6: `session_target()` — Timepoints policy in one place

**Files:**
- Modify: `src/session_map.py`
- Test: `tests/test_session_target.py`

**Interfaces:**
- Consumes: existing `project_timepoints`, `load_session_map`, `apply_session_map`, `SessionsNotMappedError`.
- Produces: `SINGLE_SESSION = "1"`; `session_target(project_path, label) -> str | None` — `None` when no `project.json` (caller keeps legacy behavior), `"1"` when `single` (any label), the mapped target when `multiple` (raises `SessionsNotMappedError` if unmapped); `SINGLE_SESSION_WARNING = "Project has one timepoint: session label {label!r} was written as ses-1."`; `single_session_warning(label) -> str | None` (None when the label is already blank or `"1"`).
- Removes: the `undeclared` state — `project_timepoints` returns `None` or a valid value; an invalid/missing value now raises `TimepointsNotDeclaredError` (the gate in Tasks 2–3 already blocks earlier, so this is a safety net).

- [ ] **Step 1: Write the failing tests**

```python
import json, pytest
from src.session_map import (
    SINGLE_SESSION, SessionsNotMappedError, TimepointsNotDeclaredError,
    save_session_map, session_target, single_session_warning,
)

def _p(tmp_path, tp):
    d = {"StudyDesign": {"Timepoints": tp}} if tp else {}
    (tmp_path / "project.json").write_text(json.dumps(d), encoding="utf-8")
    return tmp_path

def test_no_project_json_returns_none(tmp_path):
    assert session_target(tmp_path, "pre") is None

@pytest.mark.parametrize("label", ["pre", "1", "01", "", "ses-3"])
def test_single_is_always_one(tmp_path, label):
    assert session_target(_p(tmp_path, "single"), label) == SINGLE_SESSION == "1"

def test_multiple_uses_map_and_raises_when_unmapped(tmp_path):
    p = _p(tmp_path, "multiple")
    save_session_map(p, {"pre": "1"})
    assert session_target(p, "pre") == "1"
    with pytest.raises(SessionsNotMappedError):
        session_target(p, "post")

def test_undeclared_raises(tmp_path):
    with pytest.raises(TimepointsNotDeclaredError):
        session_target(_p(tmp_path, None), "pre")

def test_single_warning_only_when_label_replaced():
    assert single_session_warning("pre") and "ses-1" in single_session_warning("pre")
    assert single_session_warning("1") is None and single_session_warning("") is None
```

- [ ] **Step 2:** `python -m pytest tests/test_session_target.py -v` → FAIL (ImportError).

- [ ] **Step 3: Implement** in `src/session_map.py`:

```python
SINGLE_SESSION = "1"


def session_target(project_path, label: object) -> str | None:
    """The session name a source label becomes in this project, or None when the
    folder is not a PRISM project (callers keep their legacy behaviour)."""
    state = project_timepoints(project_path)
    if state is None:
        return None
    if state == "undeclared":
        raise TimepointsNotDeclaredError()
    if state == "single":
        return SINGLE_SESSION
    return apply_session_map(label, load_session_map(project_path))


def single_session_warning(label: object) -> str | None:
    shown = session_label(label)
    if shown in ("", SINGLE_SESSION):
        return None
    return f"Project has one timepoint: session label {shown!r} was written as ses-{SINGLE_SESSION}."
```
Also update the module docstring: "single timepoint writes `ses-1` for every label (declared project rule); PRISM only *pre-fills* defaults for multiple (Task 7), never applies them unconfirmed."

- [ ] **Step 4:** run `tests/test_session_target.py tests/test_cli_session_map.py -v` → PASS.

- [ ] **Step 5: Commit**

```bash
git add src/session_map.py tests/test_session_target.py
git commit -m "feat(sessions): session_target() decides ses-1 (single) or mapped (multiple)"
```

---

### Task 7: Survey and participants import use `single` = `ses-1`

**Files:**
- Modify: `app/src/converters/survey.py` (~1416-1614: when `timepoints == "single"`, force `session_label` to `"1"`, ignore `res_ses_col` values for naming, add `single_session_warning` to `conversion_warnings`; delete the `undeclared` branch at ~1550), `app/src/converters/survey_core.py` (`build_survey_id_normalizers`: `normalize_ses` returns `"ses-1"` when project is single), `src/participants_converter.py:447` (same rule)
- Test: `tests/test_survey_single_timepoint_ses1.py`, extend `tests/test_participants_*` equivalent

**Interfaces:**
- Consumes: `session_target`, `single_session_warning`, `SINGLE_SESSION` (Task 6).

Existing longitudinal fixtures: `tests/lsa_fixtures.py` and the survey session-map tests (`grep -ln "session_map" tests/test_*survey*.py`). Reuse their fixture builders.

- [ ] **Step 1: Write the failing test** — build a single-timepoint project (project.json with `Timepoints: single`) and a long-format survey CSV with a session column holding `pre`, `post` for the same participants.

```python
def test_single_project_writes_ses_1_for_any_label(tmp_path, ...):  # use the survey test helper that runs convert_survey_xlsx_to_prism_dataset
    result = run_survey_convert(project_single, data_with_sessions=["pre", "post"])
    files = sorted(p.name for p in output.rglob("*_survey-*.tsv"))
    assert files and all("_ses-1_" in f for f in files)
    assert not any("ses-pre" in f or "ses-post" in f for f in files)
    assert any("ses-1" in w and "pre" in w for w in result.warnings)
```
Note: two labels in one file for the same subject collapse into the same `ses-1` target. The converter's existing duplicate handling then applies; assert that the duplicate is surfaced as the existing duplicate-ID warning/error and not silently overwritten (read how `_handle_duplicate_ids` reports and assert that exact behavior).

- [ ] **Step 2:** run → FAIL (files are `ses-pre`).

- [ ] **Step 3: Implement**
  - `survey.py`: right after `timepoints` is determined (line ~1416-1422): `single = timepoints == "single"`; `if single: session_map = None`, and after `_filter_rows_by_selected_session` (~1527) when `single` and `res_ses_col` in `df.columns`: record `single_labels = set(map(session_label, df[res_ses_col]))`, append `single_session_warning(lbl)` for each non-trivial label, and force `res_ses_col = None` and `session = None` so downstream naming uses the default. Remove the `timepoints == "undeclared"` block (its work is now done by the gate).
  - `survey_core.build_survey_id_normalizers`: `normalize_ses` is only reached when a project is not single; no change needed except that its `if not s: return "ses-1"` stays the legacy no-project default.
  - `participants_converter.py:447`: when `_session_map.project_timepoints(...) == "single"`, set the session value to `"1"` before use.

- [ ] **Step 4:** `python -m pytest tests/test_survey_single_timepoint_ses1.py -k survey -v` then the full survey/participants suites: `python -m pytest tests -k "survey or participants or session" -q` → PASS.

- [ ] **Step 5: Commit**

```bash
git add -A app src tests
git commit -m "feat(import): single-timepoint projects always write ses-1 (survey, participants)"
```

---

### Task 8: Default 1, 2, 3 for multiple timepoints (backend, CLI, panel)

**Files:**
- Modify: `src/session_map.py` (add `suggest_session_map`), `app/src/cli/commands/session_map.py` + `app/src/cli/parser.py` (new `session-map suggest`), `app/src/web/blueprints/session_map_blueprint.py` (`GET /api/session-map?labels=` returns `suggested`), `app/static/js/modules/converter/session-map-panel.js` (pre-fill + header comment)
- Test: `tests/test_session_map_suggest.py`, extend `tests/test_cli_session_map.py`, extend `app/static/js/modules/converter/session-map-panel.test.js`

**Interfaces:**
- Produces: `suggest_session_map(labels: Iterable[object], mapping: Mapping[str, str]) -> dict[str, str]` — for each unmapped, non-blank label in order of first appearance, the lowest positive integer (as string) not already used as a target in `mapping` or in this suggestion. Never writes. CLI: `session-map suggest --project P --labels "pre,post,follow-up" [--apply]`; without `--apply` it prints the proposal; with `--apply` it calls `set_session_entries`.

- [ ] **Step 1: Write the failing tests**

```python
from src.session_map import suggest_session_map

def test_ascending_from_one_in_order_of_appearance():
    assert suggest_session_map(["pre", "post", "follow-up", "pre"], {}) == {"pre": "1", "post": "2", "follow-up": "3"}

def test_skips_numbers_already_used_and_mapped_labels():
    assert suggest_session_map(["pre", "post"], {"pre": "1"}) == {"post": "2"}
    assert suggest_session_map(["x"], {"a": "1", "b": "3"}) == {"x": "2"}

def test_blank_label_gets_no_suggestion_and_labels_are_exact():
    assert suggest_session_map(["", "1", "01"], {}) == {"1": "1", "01": "2"}
```
CLI test: `session-map suggest` prints the proposal and does **not** change `code/session_map.json`; `--apply` does. JS test: `show(['pre','post'])` followed by `typedDefaults()` equals `{pre:'1', post:'2'}`, and `canSaveSessionMap` is true only after the user presses Confirm (the panel keeps a `confirmed` flag, false after every `show`).

- [ ] **Step 2:** run all three → FAIL.

- [ ] **Step 3: Implement**

```python
def suggest_session_map(labels: Iterable[object], mapping: Mapping[str, str]) -> dict[str, str]:
    """Editable defaults for unmapped labels: 1, 2, 3 ... in order of first appearance.
    Only a proposal: nothing is written until the user confirms."""
    used = set(mapping.values())
    out: dict[str, str] = {}
    n = 1
    for label in unmapped_labels(labels, mapping):
        if label == "":
            continue
        while str(n) in used:
            n += 1
        out[label] = str(n)
        used.add(str(n))
    return out
```
Blueprint: `GET /api/session-map?labels=a,b` adds `"suggested": suggest_session_map(labels, load_session_map(root))` (labels split on the JSON array passed as repeated `label` params to avoid comma ambiguity: use `request.args.getlist("label")`). Panel: update the header comment to "Defaults 1, 2, 3 are pre-filled and editable; saving requires the user's Confirm"; inputs are filled with the suggestion; Save stays disabled until Confirm is pressed.

- [ ] **Step 4:** run the three test files plus `tests/test_cli_session_map.py` → PASS.

- [ ] **Step 5: Commit**

```bash
git add -A app src tests
git commit -m "feat(sessions): pre-filled 1, 2, 3 defaults for multiple-timepoint session maps"
```

---

### Task 9: Physio / eyetracking batch import uses the policy

**Files:**
- Modify: `src/batch_convert.py` (in `batch_convert_folder` after `parse_bids_filename`, ~1353-1367; the converted `parsed["ses"]` feeds `convert_physio_file`/eyetracking/generic converters)
- Test: `tests/test_batch_convert_timepoints.py`

**Interfaces:**
- Consumes: `session_target`, `single_session_warning` (Task 6). `batch_convert_folder` already knows its output dataset folder (`output_folder`); the project root is that folder when it holds `project.json`.

- [ ] **Step 1: Write the failing tests** (use the existing tiny-fixture helpers in `tests/test_batch_convert_utils.py`):
  - single project: input `sub-001_ses-pre_task-rest.raw` → output path contains `ses-1`, none contain `ses-pre`; result warnings mention `ses-1`.
  - single project: input without any `ses-` → output goes under `ses-1` (there is always a session level).
  - multiple project with session map `{"pre": "1"}`: input `sub-001_ses-pre_task-rest.raw` → output `ses-1`; an unmapped `post` is skipped, with the `SessionsNotMappedError` message in `result.skipped`.
  - no `project.json` in output folder: behavior identical to today (existing tests stay green).

- [ ] **Step 2:** run → FAIL.

- [ ] **Step 3: Implement** — a small helper in `batch_convert.py`:

```python
def _project_session(output_folder, parsed, result, file_path):
    """Apply the project's Timepoints policy to the session parsed from the filename.
    Returns (parsed, skip_message)."""
    raw = (parsed.get("ses") or "")
    label = raw[4:] if raw.startswith("ses-") else raw
    try:
        target = session_target(output_folder, label)
    except SessionMapError as exc:
        return parsed, str(exc)
    if target is None:
        return parsed, None
    warning = single_session_warning(label)
    if warning:
        result.warnings.append(f"{file_path.name}: {warning}")
    return {**parsed, "ses": f"ses-{target}"}, None
```
Call it right after `parse_bids_filename`; on a skip message append to `result.skipped` and `continue`. (If `result` has no `warnings` list, add one to its dataclass and report it with the other result fields — check the `BatchConvertResult` definition near line 76.)

- [ ] **Step 4:** `python -m pytest tests/test_batch_convert_timepoints.py tests/test_batch_convert_utils.py tests/test_convert_physio_cli.py -v` → PASS.

- [ ] **Step 5: Commit**

```bash
git add src/batch_convert.py tests/test_batch_convert_timepoints.py
git commit -m "feat(import): physio/eyetracking batch import follows the project's Timepoints"
```

---

### Task 10: Biometrics and environment importers use the policy

**Files:**
- Modify: `src/converters/biometrics.py` (where `session_column` / `session` are turned into `ses-*`), `src/environment_conversion.py` (~841-884 `session_col` / `session_override` resolution)
- Test: `tests/test_biometrics_timepoints.py`, `tests/test_environment_timepoints.py`

**Interfaces:**
- Consumes: `session_target`, `single_session_warning` (Task 6).

- [ ] **Step 1: Write failing tests** per importer, same four cases as Task 9 (single → `ses-1` for any/no label with warning; multiple → mapped / unmapped raises with the session-map message; no project → unchanged). Use the existing fixtures: `tests/test_biometrics_utils.py` and `tests/test_conversion_environment_mri_scan.py` / the environment preview tests for table builders.

- [ ] **Step 2:** run → FAIL.

- [ ] **Step 3: Implement** — at the single point in each module where the session name is finalized (find with `grep -n "ses-" src/converters/biometrics.py src/environment_conversion.py`), wrap it:

```python
target = session_target(project_root, raw_label)
if target is not None:
    session_name = f"ses-{target}"
    warning = single_session_warning(raw_label)
    if warning:
        warnings.append(warning)
```
using each module's existing warnings list. For `environment`, remove the `--session-override` effect when the project is `single` (the project rule wins; print the warning) — session options become unnecessary in a single project, not an error.

- [ ] **Step 4:** run both new test files plus `tests/test_biometrics_cli.py tests/test_cli_environment_scan_mri.py` → PASS.

- [ ] **Step 5: Commit**

```bash
git add -A src tests
git commit -m "feat(import): biometrics and environment importers follow the project's Timepoints"
```

---

### Task 11: Audit remaining importers, GUI hides session UI for single, docs

**Files:**
- Modify: `src/converters/wide_to_long.py`, `src/converters/phenotype_import.py` (only if the audit shows they write `ses-*`), `app/static/js/modules/converter/*` (hide session picker / map panel / assignment review when `timepoints === 'single'`; the value comes from `GET /api/session-map` → `timepoints`), `CLAUDE.md` (session-ID note), `docs/` page for the converter (find with `grep -rln "session_map" docs | head`)
- Test: `tests/test_importers_use_session_policy.py`

- [ ] **Step 1: Write the failing test** — a source scan that fails whenever a module writes `ses-` filenames without consulting the policy:

```python
import re
from pathlib import Path

WRITERS = [  # every module that creates ses-<label> output names
    "src/batch_convert.py", "src/converters/biometrics.py", "src/environment_conversion.py",
    "app/src/converters/survey.py", "src/participants_converter.py",
]

def test_every_session_writing_importer_uses_the_policy():
    for rel in WRITERS:
        text = Path(rel).read_text(encoding="utf-8")
        assert re.search(r"session_target|project_timepoints|session_map_for_conversion", text), rel

def test_writer_list_is_complete():
    found = []
    for root in ("src", "app/src"):
        for p in Path(root).rglob("*.py"):
            t = p.read_text(encoding="utf-8")
            if re.search(r'f"ses-\{|"ses-" \+|f\'ses-\{', t) and re.search(r"def .*convert|def .*import", t):
                found.append(str(p))
    unknown = [f for f in found if f not in WRITERS and "test" not in f]
    assert not unknown, f"audit these importers and add them to WRITERS or exempt them: {unknown}"
```

- [ ] **Step 2:** run → FAIL for `wide_to_long.py` / `phenotype_import.py` (if they match) or PASS-by-accident; for any hit, read the module, and either apply the Task 9/10 pattern (+ a test) or add a one-line reason to an `EXEMPT` dict in the test (e.g., wide-to-long reshapes tables and never names output files by session).

- [ ] **Step 3: Implement** the audit results, the JS hiding (small: in `survey-convert.js` and the participants panel, `if (timepoints === 'single') panel.hidden = true`; add a JS test beside `session-map-panel.test.js`), the CLAUDE.md amendment:

> Exception (2026-10-15): in a project that declares `StudyDesign.Timepoints = single`, the one session is always `ses-1` whatever label the data carries (a reported, deliberate project-level rule, not label normalization). In `multiple` projects, labels stay exact strings and are mapped by the user; defaults 1, 2, 3 are only pre-filled.

and the docs paragraph describing: required fields block tools; single = `ses-1`; multiple = mapping with 1, 2, 3 defaults.

- [ ] **Step 4: Full verification**

Run:
```bash
python -m pytest tests -q
python tests/verify_repo.py --check dual-tree-drift --no-fix
python3 -c "import src.project_ready as m; print(m.__file__)"
```
Expected: all pass; `project_ready` resolves under top-level `src/`. Then run `/ponytail:ponytail-audit` on the branch (standing rule before merge), apply worthwhile findings, re-run tests.

- [ ] **Step 5: Commit**

```bash
git add -A
git commit -m "feat(import): audit remaining importers, hide session UI for single, document Timepoints policy"
```
