# Session Map Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** In a longitudinal project every session label in an import must be explicitly mapped by the user (`code/session_map.json`); nothing is ever guessed or filled in.

**Architecture:** One backend module `src/session_map.py` owns the rule (load/save/validate/gate). The survey converter and the participants importer call it; the CLI and a thin Flask blueprint expose it; the GUI shows a panel with empty inputs. A new required project field `StudyDesign.Timepoints` (`single`/`multiple`) decides whether the gate applies.

**Tech Stack:** Python 3 (pytest), Flask, vanilla ES-module JS (vitest), Playwright (tests/e2e).

**Spec:** `docs/superpowers/specs/2026-09-30-session-map-design.md`

**Commits:** the project owner commits. Steps end at green tests; there are no `git commit` steps.

## Global Constraints

- Explicit only, never autofill: no suggested, pre-filled, ordered or numbered session names anywhere (API, CLI, GUI).
- Strict: in a `multiple` project *every* label being imported needs a map entry, even `1 -> 1`.
- Many-to-one is allowed: `T0 -> 1` and `pre -> 1` may coexist.
- Source labels compare by exact string via `session_label` (`src/participants_sessions.py`): only whitespace is trimmed and a whole-number float such as `1.0` becomes `1`. No case folding, no zero padding, no `ses-` prefix stripping. `1`, `01`, `pre` are three labels.
- Target must fullmatch `[A-Za-z0-9]+`. Integers are a convention, not enforced.
- The map lives in `code/session_map.json` (flat `{"source": "target"}`); the declaration lives in `project.json` as `StudyDesign.Timepoints`.
- `single` projects and runs without a project path behave exactly as before.
- Existing converted data is never rewritten.
- CLI parity: every GUI capability works from `prism_tools.py` with the same rule (one backend implementation; GUI/Flask are thin adapters).
- Text files stay out of git-annex (JSON is already covered by the project text policy; do not touch `.gitattributes` logic).
- `src/session_map.py` is a new file under top-level `src/` only. Check `find src app/src -name session_map.py` shows exactly one file (dual-tree rule).
- Every task is TDD: write the failing test, run it and watch it fail for the expected reason, then implement.

## Review Focus

Failure modes the spec implies but a straightforward implementation would miss. Each has a test in the task that owns the code.

1. **Blank or NaN session cell in a `multiple` project** must block (listed as `(empty)`), not silently become `ses-1` (today's `normalize_ses` default). Task 3.
2. **Numeric session column** (`1`, `2` read from CSV/Excel as int or `1.0` float) must match map keys `"1"`, `"2"`; never become `ses-10`. Task 1 and Task 3.
3. **`duplicate_handling="sessions"`** invents session names (`1`, `2`, ...) and must be refused in a `multiple` project with a clear message. Task 3.
4. **No session source at all** (no session column, no chosen session) in a `multiple` project must be refused, not default to `ses-1`. Task 3.
5. **Corrupt or invalid `code/session_map.json`** (bad JSON, non-object, invalid target) must raise an error naming the file, never be read as an empty map. Task 1.
6. **Declared `multiple` but no map file yet** means every label is unmapped (block), not "no map, pass through". Task 3.
7. **Existing project with `project.json` but no `Timepoints`** must be refused with the "declare it" message; a folder with no `project.json` is not a PRISM project and is left alone. Task 1 and Task 3.
8. **Key exactness**: data label `01` with only `1` in the map is unmapped; `ses-1` is its own label. Task 1 and Task 3.

## File Structure

| File | Responsibility |
|---|---|
| `src/session_map.py` (new) | The whole rule: errors, `project_timepoints`, load/save/validate map, `unmapped_labels`, `apply_session_map`, `session_map_for_conversion`, `require_sessions_mapped` |
| `tests/test_session_map.py` (new) | Unit tests for the module |
| `app/src/converters/survey_core.py` | `build_survey_id_normalizers(project_path, session_map=None)`: map applied inside `normalize_ses` |
| `app/src/converters/survey.py` | Load the map once, refuse unsupported duplicate handling, gate after row filtering |
| `tests/test_survey_session_map.py` (new) | Survey converter behaviour with the map |
| `app/src/web/blueprints/projects_metadata_helpers.py` | `CREATION_BLOCKING_FIELDS` gains `StudyDesign.Timepoints` |
| `app/templates/includes/projects/study_metadata.html`, `app/static/js/modules/projects/{metadata,create-project,validation}.js` | The required "Timepoints" select |
| `app/src/cli/commands/session_map.py` (new), `parser.py`, `dispatch.py`, `entrypoint.py` | `prism_tools.py session-map show/set` |
| `app/src/web/blueprints/session_map_blueprint.py` (new), `app/prism-studio.py` | `GET/POST /api/session-map` |
| `app/src/web/blueprints/conversion_survey_version_context_handlers.py`, `conversion_survey_handlers.py` | Detect endpoint answers 409 `sessions_not_mapped` with the labels |
| `app/static/js/modules/converter/session-map-panel.js` (+ `.test.js`) (new) | Pure panel rules + thin DOM |
| `app/templates/converter_survey.html`, `app/static/js/modules/converter/survey-convert.js` | Panel markup; block Preview/Convert while labels are unmapped |
| `src/participants_converter.py` | `convert_participant_data` gates the chosen file's session labels |
| `tests/e2e/test_session_map_flows.py` (new) | Browser flows |

---

### Task 1: Backend module `src/session_map.py`

**Files:**
- Create: `src/session_map.py`
- Test: `tests/test_session_map.py`

**Interfaces:**
- Consumes: `src.participants_sessions.session_label(value) -> str`
- Produces (all in `src/session_map.py`):
  - `MAP_FILE: Path` (`code/session_map.json`), `TIMEPOINT_VALUES = ("single", "multiple")`
  - `class SessionMapError(ValueError)`; `class TimepointsNotDeclaredError(SessionMapError)`; `class SessionsNotMappedError(SessionMapError)` with `.labels: list[str]`
  - `project_timepoints(project_path) -> str | None`: `"single"`, `"multiple"`, `"undeclared"` (project.json exists, field missing/invalid), or `None` (no project.json)
  - `load_session_map(project_path) -> dict[str, str]`
  - `save_session_map(project_path, mapping) -> None`
  - `set_session_entries(project_path, entries: Mapping[str, str]) -> dict[str, str]` (merge into the file, returns the saved map)
  - `unmapped_labels(labels, mapping) -> list[str]`
  - `apply_session_map(label, mapping) -> str` (target only, no `ses-`)
  - `session_map_for_conversion(project_path) -> dict[str, str] | None`
  - `require_sessions_mapped(mapping, labels) -> None`

- [ ] **Step 1: Write the failing tests**

Create `tests/test_session_map.py`:

```python
"""Session map rules: exact labels, explicit entries, no guessing."""

import json

import pytest

from src.session_map import (
    SessionMapError,
    SessionsNotMappedError,
    TimepointsNotDeclaredError,
    apply_session_map,
    load_session_map,
    project_timepoints,
    require_sessions_mapped,
    save_session_map,
    session_map_for_conversion,
    set_session_entries,
    unmapped_labels,
)


def make_project(tmp_path, timepoints="multiple", project_json=True):
    if project_json:
        study = {} if timepoints is None else {"StudyDesign": {"Timepoints": timepoints}}
        (tmp_path / "project.json").write_text(json.dumps(study))
    return tmp_path


def test_timepoints_states(tmp_path):
    assert project_timepoints(tmp_path) is None  # no project.json: not a PRISM project
    make_project(tmp_path, timepoints=None)
    assert project_timepoints(tmp_path) == "undeclared"
    make_project(tmp_path, "single")
    assert project_timepoints(tmp_path) == "single"
    make_project(tmp_path, "multiple")
    assert project_timepoints(tmp_path) == "multiple"
    make_project(tmp_path, "sometimes")  # unknown value is not a declaration
    assert project_timepoints(tmp_path) == "undeclared"


def test_timepoints_accepts_the_project_json_path(tmp_path):
    make_project(tmp_path, "multiple")
    assert project_timepoints(tmp_path / "project.json") == "multiple"


def test_missing_map_file_is_an_empty_map(tmp_path):
    assert load_session_map(make_project(tmp_path)) == {}


def test_save_then_load_round_trips_and_creates_code_folder(tmp_path):
    root = make_project(tmp_path)
    save_session_map(root, {"pre": "1", "T0": "1", "post": "2"})
    assert (root / "code" / "session_map.json").is_file()
    assert load_session_map(root) == {"pre": "1", "T0": "1", "post": "2"}  # many-to-one is fine


@pytest.mark.parametrize("target", ["", "ses-1", "a b", "é", "1_2"])
def test_invalid_targets_are_rejected(tmp_path, target):
    with pytest.raises(SessionMapError, match="pre"):
        save_session_map(make_project(tmp_path), {"pre": target})


def test_empty_source_label_is_rejected(tmp_path):
    with pytest.raises(SessionMapError):
        save_session_map(make_project(tmp_path), {"  ": "1"})


@pytest.mark.parametrize("content", ["{not json", "[]", '{"pre": 1}', '{"pre": "a b"}'])
def test_corrupt_map_file_raises_and_names_the_file(tmp_path, content):
    root = make_project(tmp_path)
    (root / "code").mkdir()
    (root / "code" / "session_map.json").write_text(content)
    with pytest.raises(SessionMapError, match="session_map.json"):
        load_session_map(root)


def test_set_session_entries_merges_without_dropping_existing_entries(tmp_path):
    root = make_project(tmp_path)
    save_session_map(root, {"pre": "1"})
    assert set_session_entries(root, {"post": "2"}) == {"pre": "1", "post": "2"}
    assert load_session_map(root) == {"pre": "1", "post": "2"}


def test_labels_compare_exactly(tmp_path):
    mapping = {"1": "a"}
    assert unmapped_labels(["1", "01", "ses-1", "Pre"], mapping) == ["01", "ses-1", "Pre"]
    assert apply_session_map(" 1 ", mapping) == "a"  # only whitespace is trimmed


def test_spreadsheet_float_artifact_matches_the_integer_label():
    assert apply_session_map(1.0, {"1": "a"}) == "a"
    assert unmapped_labels([1.0, 2.0], {"1": "a"}) == ["2"]


def test_blank_and_nan_are_unmapped_never_defaulted():
    assert unmapped_labels(["", None, float("nan"), "  "], {"1": "a"}) == [""]
    with pytest.raises(SessionsNotMappedError) as info:
        apply_session_map("", {"1": "a"})
    assert info.value.labels == [""]
    assert "(empty)" in str(info.value)


def test_unmapped_labels_are_deduplicated_in_order_of_appearance():
    assert unmapped_labels(["b", "a", "b", "c"], {}) == ["b", "a", "c"]


def test_error_lists_every_missing_label_and_names_the_ways_to_fix_it():
    with pytest.raises(SessionsNotMappedError) as info:
        require_sessions_mapped({"pre": "1"}, ["pre", "post", "T2"])
    assert info.value.labels == ["post", "T2"]
    message = str(info.value)
    assert "'post'" in message and "'T2'" in message
    assert "session_map.json" in message and "session-map set" in message


def test_require_sessions_mapped_with_no_map_is_a_no_op():
    require_sessions_mapped(None, ["anything", ""])


def test_conversion_map_by_project_state(tmp_path):
    assert session_map_for_conversion(None) is None
    assert session_map_for_conversion(tmp_path) is None  # no project.json
    make_project(tmp_path, "single")
    assert session_map_for_conversion(tmp_path) is None
    make_project(tmp_path, "multiple")
    assert session_map_for_conversion(tmp_path) == {}  # declared, nothing mapped yet
    save_session_map(tmp_path, {"pre": "1"})
    assert session_map_for_conversion(tmp_path) == {"pre": "1"}
    make_project(tmp_path, None)
    with pytest.raises(TimepointsNotDeclaredError, match="Timepoints"):
        session_map_for_conversion(tmp_path)
```

- [ ] **Step 2: Run the tests and watch them fail**

Run: `python3 -m pytest tests/test_session_map.py -q`
Expected: collection error `ModuleNotFoundError: No module named 'src.session_map'`.

- [ ] **Step 3: Implement the module**

Create `src/session_map.py`:

```python
"""Session map for longitudinal projects.

Spec: docs/superpowers/specs/2026-09-30-session-map-design.md

In a project that declares several timepoints, every session label being
imported must have an explicit entry in ``code/session_map.json``. Nothing is
guessed: labels compare by exact string (see ``session_label``), a blank label
is never defaulted, and PRISM never suggests a target.
"""

from __future__ import annotations

import json
import os
import re
from collections.abc import Iterable, Mapping
from pathlib import Path

from src.participants_sessions import session_label

MAP_FILE = Path("code") / "session_map.json"
TIMEPOINT_VALUES = ("single", "multiple")
_TARGET = re.compile(r"[A-Za-z0-9]+")


class SessionMapError(ValueError):
    """Anything wrong with the session map or the project's timepoint declaration."""


class TimepointsNotDeclaredError(SessionMapError):
    def __init__(self) -> None:
        super().__init__(
            "This project does not say whether it has one timepoint or several. "
            "Set 'Timepoints' (single or multiple) under Study Design on the "
            "Projects page, then run again."
        )


class SessionsNotMappedError(SessionMapError):
    def __init__(self, labels: Iterable[str]) -> None:
        self.labels = list(labels)
        shown = ", ".join(repr(label) if label else "(empty)" for label in self.labels)
        super().__init__(
            f"Session label(s) not in the session map: {shown}. This project has "
            "several timepoints, so every session label must be mapped by you. "
            f"Add them to {MAP_FILE.as_posix()} (Converter page, or "
            "`prism_tools.py session-map set`), then run again."
        )


def _root(project_path: str | Path) -> Path:
    path = Path(project_path).expanduser()
    return path.parent if path.is_file() else path


def map_path(project_path: str | Path) -> Path:
    return _root(project_path) / MAP_FILE


def project_timepoints(project_path: str | Path) -> str | None:
    """'single', 'multiple', 'undeclared' (project.json without a valid
    StudyDesign.Timepoints) or None (no project.json: not a PRISM project)."""
    pj = _root(project_path) / "project.json"
    if not pj.is_file():
        return None
    try:
        data = json.loads(pj.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        raise SessionMapError(f"{pj} could not be read: {exc}") from exc
    design = data.get("StudyDesign") if isinstance(data, dict) else None
    value = design.get("Timepoints") if isinstance(design, dict) else None
    return value if value in TIMEPOINT_VALUES else "undeclared"


def _clean(mapping: object, where: str) -> dict[str, str]:
    if not isinstance(mapping, dict):
        raise SessionMapError(f"{where} must be a JSON object of source label to session name")
    clean: dict[str, str] = {}
    for source, target in mapping.items():
        label = str(source).strip()
        if not label:
            raise SessionMapError(f"{where} has an entry with an empty source label")
        if not isinstance(target, str) or not _TARGET.fullmatch(target.strip()):
            raise SessionMapError(
                f"{where}: session name for {label!r} must be letters and digits only, got {target!r}"
            )
        clean[label] = target.strip()
    return clean


def load_session_map(project_path: str | Path) -> dict[str, str]:
    path = map_path(project_path)
    if not path.is_file():
        return {}
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        raise SessionMapError(f"{path} could not be read: {exc}") from exc
    return _clean(raw, str(path))


def save_session_map(project_path: str | Path, mapping: Mapping[str, str]) -> None:
    path = map_path(project_path)
    clean = _clean(dict(mapping), str(path))
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(".json.tmp")
    tmp.write_text(json.dumps(clean, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    os.replace(tmp, path)


def set_session_entries(project_path: str | Path, entries: Mapping[str, str]) -> dict[str, str]:
    merged = load_session_map(project_path)
    merged.update(_clean(dict(entries), "entries"))
    save_session_map(project_path, merged)
    return merged


def unmapped_labels(labels: Iterable[object], mapping: Mapping[str, str]) -> list[str]:
    """Labels without an entry, deduplicated, in order of first appearance.
    A blank label is reported as '' (it is never defaulted)."""
    missing: list[str] = []
    for raw in labels:
        label = session_label(raw)
        if label not in mapping and label not in missing:
            missing.append(label)
    return missing


def apply_session_map(label: object, mapping: Mapping[str, str]) -> str:
    key = session_label(label)
    if key in mapping:
        return mapping[key]
    raise SessionsNotMappedError([key])


def session_map_for_conversion(project_path: str | Path | None) -> dict[str, str] | None:
    """None when the gate does not apply (no project, single timepoint);
    the map (possibly empty) for a multiple-timepoint project."""
    if not project_path:
        return None
    state = project_timepoints(project_path)
    if state in (None, "single"):
        return None
    if state == "undeclared":
        raise TimepointsNotDeclaredError()
    return load_session_map(project_path)


def require_sessions_mapped(mapping: Mapping[str, str] | None, labels: Iterable[object]) -> None:
    if mapping is None:
        return
    missing = unmapped_labels(labels, mapping)
    if missing:
        raise SessionsNotMappedError(missing)
```

- [ ] **Step 4: Run the tests and watch them pass**

Run: `python3 -m pytest tests/test_session_map.py -q`
Expected: all pass. If `test_error_lists_every_missing_label...` fails on the `session-map set` wording, the message text above is the contract; fix the code, not the test.

- [ ] **Step 5: Dual-tree check**

Run: `find src app/src -name session_map.py` and `python3 -c "import src.session_map as m; print(m.__file__)"`
Expected: one file, under top-level `src/`.

---

### Task 2: Required study-metadata field `StudyDesign.Timepoints`

**Files:**
- Modify: `app/src/web/blueprints/projects_metadata_helpers.py:335-337` (`CREATION_BLOCKING_FIELDS`)
- Modify: `app/templates/includes/projects/study_metadata.html` (after the `smSDType` select block, ~line 281)
- Modify: `app/static/js/modules/projects/metadata.js` (lines ~141 load, ~417 save, ~2358 and ~2781 id lists, ~3194 hint map, ~3652 `creationBlockingFields`, ~3728 `addField`, ~2210 modal labels)
- Modify: `app/static/js/modules/projects/create-project.js:179`
- Modify: `app/static/js/modules/projects/validation.js:55`
- Test: `tests/test_projects_metadata_helpers.py`, `tests/e2e/test_projects_flows.py`

**Interfaces:**
- Consumes: none from Task 1 (the value strings `single`/`multiple` match `TIMEPOINT_VALUES`).
- Produces: `project.json` key `StudyDesign.Timepoints` in `{"single","multiple"}`; DOM id `smSDTimepoints`; `CREATION_BLOCKING_FIELDS["StudyDesign"] == {"Timepoints"}`.

- [ ] **Step 1: Write the failing backend test**

Append to `tests/test_projects_metadata_helpers.py`:

```python
def test_timepoints_blocks_project_creation_but_not_the_core_readiness_score():
    from src.web.blueprints.projects_metadata_helpers import (
        CREATION_BLOCKING_FIELDS,
        REQUIRED_FIELDS_SCHEMA,
    )

    assert "Timepoints" in CREATION_BLOCKING_FIELDS["StudyDesign"]
    assert "Timepoints" not in REQUIRED_FIELDS_SCHEMA["StudyDesign"]  # third tier, not CORE
```

- [ ] **Step 2: Run it and watch it fail**

Run: `python3 -m pytest tests/test_projects_metadata_helpers.py -q -k timepoints`
Expected: FAIL `KeyError: 'StudyDesign'`.

- [ ] **Step 3: Backend constant**

In `projects_metadata_helpers.py` change:

```python
CREATION_BLOCKING_FIELDS: dict[str, set[str]] = {
    "Basics": {"Name", "Authors", "Keywords"},
    "StudyDesign": {"Timepoints"},
}
```

Run the test from Step 2 again. Expected: PASS. Then run `python3 -m pytest tests/test_projects_metadata_helpers.py tests/test_api_config_route.py tests/test_project_manager.py -q` and fix any completeness-count test whose expected totals shift by one (update the expected number only if the test is asserting a count of creation-blocking fields).

- [ ] **Step 4: Write the failing browser test**

Append to `tests/e2e/test_projects_flows.py`:

```python
def test_timepoints_is_required_and_saved_with_the_project(bare_page, studio_url, tmp_path):
    bare_page.goto(f"{studio_url}/projects")
    bare_page.click("#card-create")
    bare_page.fill("#projectName", "long_study")
    bare_page.fill("#projectPath", str(tmp_path))

    bare_page.click("#createProjectSubmitBtnTop")
    expect(bare_page.get_by_role("heading", name="Required Fields Missing")).to_be_visible()
    expect(bare_page.locator(".modal.show")).to_contain_text("Timepoints")
    bare_page.get_by_role("button", name="Go back and fill fields").click()

    open_study_metadata(bare_page)
    bare_page.locator('[data-bs-target="#smStudyDesign"]').click()
    bare_page.select_option("#smSDTimepoints", "multiple")
    bare_page.click("#createProjectSubmitBtnTop")
    bare_page.get_by_role("button", name="Create anyway (incomplete)").click()

    expect(bare_page.locator("#createResult")).to_contain_text("long_study")
    saved = json.loads((tmp_path / "long_study" / "project.json").read_text())
    assert saved["StudyDesign"]["Timepoints"] == "multiple"
```

- [ ] **Step 5: Run it and watch it fail**

Run: `python3 -m pytest tests/e2e/test_projects_flows.py -q -k timepoints`
Expected: FAIL (`Timepoints` not in the modal text).

- [ ] **Step 6: Implement the form field**

In `study_metadata.html`, directly after the closing `</div>` of the column that holds `smSDType` (the `col-md-4` starting at line ~266), add:

```html
                                <div class="col-md-4">
                                    <label class="form-label fw-bold small text-muted text-uppercase mb-1" for="smSDTimepoints">
                                        <span class="badge bg-danger">REQUIRED</span> Timepoints
                                    </label>
                                    <select class="form-select form-select-sm" id="smSDTimepoints">
                                        <option value="">-- Select --</option>
                                        <option value="single">One timepoint (cross-sectional)</option>
                                        <option value="multiple">Several timepoints (longitudinal)</option>
                                    </select>
                                    <small class="text-muted">Several timepoints: every session label in an import must be mapped by you (Converter).</small>
                                </div>
```

In `metadata.js`:
- load (after line 141): `document.getElementById('smSDTimepoints').value = sd.Timepoints || '';`
- save (in the `StudyDesign:` object at ~417, after `Type`): `Timepoints: document.getElementById('smSDTimepoints').value || undefined,`
- add `'smSDTimepoints'` next to `'smSDType'` in both id lists (~2358 and ~2781)
- `_smHintFieldMap` (~3194): `'StudyDesign.Timepoints': { el: 'smSDTimepoints', type: 'select' },`
- `creationBlockingFields` (~3652): `StudyDesign: new Set(['Timepoints'])` alongside `Basics`
- `addField` block (~3728): `addField('StudyDesign', 'Timepoints', textFilled(document.getElementById('smSDTimepoints')?.value));`
- the `labels` object (~2210): add `StudyDesign: { Timepoints: 'Timepoints (one or several)' }` next to `Basics`.

In `create-project.js` (in the `StudyDesign:` object at line ~179) and `validation.js` (id list at ~55) add the same `Timepoints` / `'smSDTimepoints'` entries.

- [ ] **Step 7: Run browser and vitest suites**

Run: `python3 -m pytest tests/e2e/test_projects_flows.py -q` then `npx vitest run`
Expected: all pass, including the new test and the earlier Projects flows (the create flow now also lists Timepoints in the modal, which its assertions do not forbid).

---

### Task 3: Survey converter gate and mapping

**Files:**
- Modify: `app/src/converters/survey_core.py:174-223` (`build_survey_id_normalizers`)
- Modify: `app/src/converters/survey.py:1409` and after `:1528`
- Test: `tests/test_survey_session_map.py`

**Interfaces:**
- Consumes: `session_map_for_conversion`, `require_sessions_mapped`, `apply_session_map`, `SessionMapError` from `src.session_map` (Task 1).
- Produces: `build_survey_id_normalizers(project_path, session_map=None)`; when `session_map` is not `None`, `normalize_ses(val)` returns `f"ses-{target}"` or raises `SessionsNotMappedError`.

- [ ] **Step 1: Write the failing tests**

Create `tests/test_survey_session_map.py`:

```python
"""Survey conversion in a longitudinal project uses only the user's session map."""

import json
import shutil
from pathlib import Path

import pytest

from src.converters.survey import convert_survey_file_to_prism_dataset
from src.session_map import (
    SessionMapError,
    SessionsNotMappedError,
    TimepointsNotDeclaredError,
    save_session_map,
)

BRS = Path(__file__).resolve().parents[1] / "official" / "library" / "survey" / "survey-brs.json"


@pytest.fixture
def library(tmp_path):
    lib = tmp_path / "library" / "survey"
    lib.mkdir(parents=True)
    shutil.copy(BRS, lib / "survey-brs.json")
    return lib


def project(tmp_path, timepoints="multiple"):
    root = tmp_path / "proj"
    root.mkdir(exist_ok=True)
    study = {} if timepoints is None else {"StudyDesign": {"Timepoints": timepoints}}
    (root / "project.json").write_text(json.dumps(study))
    return root


def convert(tmp_path, library, csv_text, proj=None, **kwargs):
    src = tmp_path / "in.csv"
    src.write_text(csv_text)
    out = tmp_path / "out"
    convert_survey_file_to_prism_dataset(
        input_path=src,
        library_dir=library,
        output_root=out,
        name="t",
        session_column=kwargs.pop("session_column", "session"),
        project_path=proj,
        **kwargs,
    )
    return out


def sessions(out, participant):
    return sorted(p.name for p in (out / participant).glob("ses-*"))


LONG = "participant_id,session,BRS01,BRS02,BRS03\nP001,pre,3,4,2\nP001,post,4,4,3\nP002,pre,1,0,2\n"


def test_unmapped_labels_block_and_nothing_is_written(tmp_path, library):
    proj = project(tmp_path)
    save_session_map(proj, {"pre": "1"})
    with pytest.raises(SessionsNotMappedError) as info:
        convert(tmp_path, library, LONG, proj)
    assert info.value.labels == ["post"]
    assert not (tmp_path / "out" / "sub-P001").exists()


def test_declared_multiple_without_a_map_file_blocks_every_label(tmp_path, library):
    proj = project(tmp_path)
    with pytest.raises(SessionsNotMappedError) as info:
        convert(tmp_path, library, LONG, proj)
    assert info.value.labels == ["pre", "post"]


def test_mapped_labels_become_the_users_session_names(tmp_path, library):
    proj = project(tmp_path)
    save_session_map(proj, {"pre": "1", "post": "2"})
    out = convert(tmp_path, library, LONG, proj)
    assert sessions(out, "sub-P001") == ["ses-1", "ses-2"]
    assert sessions(out, "sub-P002") == ["ses-1"]


def test_two_source_labels_may_share_one_session(tmp_path, library):
    proj = project(tmp_path)
    save_session_map(proj, {"T0": "1", "pre": "1"})
    csv_text = "participant_id,session,BRS01,BRS02,BRS03\nP001,T0,3,4,2\nP002,pre,1,0,2\n"
    out = convert(tmp_path, library, csv_text, proj)
    assert sessions(out, "sub-P001") == ["ses-1"] and sessions(out, "sub-P002") == ["ses-1"]


def test_numeric_session_column_matches_integer_keys(tmp_path, library):
    proj = project(tmp_path)
    save_session_map(proj, {"1": "a", "2": "b"})
    csv_text = "participant_id,session,BRS01,BRS02,BRS03\nP001,1,3,4,2\nP001,2,4,4,3\n"
    out = convert(tmp_path, library, csv_text, proj)
    assert sessions(out, "sub-P001") == ["ses-a", "ses-b"]  # never ses-10


def test_zero_padded_label_is_not_the_unpadded_key(tmp_path, library):
    proj = project(tmp_path)
    save_session_map(proj, {"1": "a"})
    csv_text = "participant_id,session,BRS01,BRS02,BRS03\nP001,01,3,4,2\n"
    with pytest.raises(SessionsNotMappedError) as info:
        convert(tmp_path, library, csv_text, proj)
    assert info.value.labels == ["01"]


def test_blank_session_cell_blocks_instead_of_becoming_ses_1(tmp_path, library):
    proj = project(tmp_path)
    save_session_map(proj, {"pre": "1"})
    csv_text = "participant_id,session,BRS01,BRS02,BRS03\nP001,pre,3,4,2\nP002,,1,0,2\n"
    with pytest.raises(SessionsNotMappedError) as info:
        convert(tmp_path, library, csv_text, proj)
    assert info.value.labels == [""]


def test_no_session_source_is_refused_in_a_longitudinal_project(tmp_path, library):
    proj = project(tmp_path)
    csv_text = "participant_id,BRS01,BRS02,BRS03\nP001,3,4,2\n"
    with pytest.raises(SessionMapError, match="session"):
        convert(tmp_path, library, csv_text, proj, session_column=None)


def test_chosen_session_must_be_mapped_and_imports_only_its_rows(tmp_path, library):
    proj = project(tmp_path)
    save_session_map(proj, {"pre": "1"})
    out = convert(tmp_path, library, LONG, proj, session="pre")
    assert sessions(out, "sub-P001") == ["ses-1"]


def test_duplicate_handling_sessions_is_refused_because_it_invents_names(tmp_path, library):
    proj = project(tmp_path)
    save_session_map(proj, {"pre": "1"})
    with pytest.raises(SessionMapError, match="invents"):
        convert(tmp_path, library, LONG, proj, duplicate_handling="sessions")


def test_undeclared_project_is_refused_with_the_declare_message(tmp_path, library):
    with pytest.raises(TimepointsNotDeclaredError):
        convert(tmp_path, library, LONG, project(tmp_path, timepoints=None))


def test_single_timepoint_project_keeps_todays_behaviour(tmp_path, library):
    out = convert(tmp_path, library, LONG, project(tmp_path, "single"))
    assert sessions(out, "sub-P001") == ["ses-post", "ses-pre"]


def test_without_a_project_nothing_changes(tmp_path, library):
    out = convert(tmp_path, library, LONG, proj=None)
    assert sessions(out, "sub-P001") == ["ses-post", "ses-pre"]
```

- [ ] **Step 2: Run and watch them fail**

Run: `python3 -m pytest tests/test_survey_session_map.py -q`
Expected: the gate tests FAIL (no error raised; sessions written as `ses-pre`/`ses-post`); the `single` and no-project tests already pass (they pin today's behaviour).

- [ ] **Step 3: Implement the normalizer change**

In `survey_core.py` add at the top with the other imports: `from src.session_map import apply_session_map`. Change the signature and `normalize_ses`:

```python
def build_survey_id_normalizers(
    project_path: str | Path | None, session_map: dict[str, str] | None = None
) -> SurveyIdNormalizers:
```

and at the top of `normalize_ses`:

```python
    def normalize_ses(val) -> str:
        if session_map is not None:
            # Longitudinal project: the user's map is the only source of session names.
            return f"ses-{apply_session_map(val, session_map)}"
        s = sanitize_id(str(val).strip())
        ...  # rest unchanged
```

Update the docstring of `build_survey_id_normalizers` with one line: "When `session_map` is given (longitudinal project), `normalize_ses` uses only that map."

- [ ] **Step 4: Implement the converter gate**

In `survey.py` add to the imports of that module: `from src.session_map import SessionMapError, require_sessions_mapped, session_map_for_conversion`.

Replace line 1409 (`id_normalizers = _survey_core.build_survey_id_normalizers(project_path)`) with:

```python
    session_map = session_map_for_conversion(project_path)
    if session_map is not None and duplicate_handling == "sessions":
        raise SessionMapError(
            "Duplicate handling 'sessions' invents session names (1, 2, ...), which "
            "longitudinal projects do not allow. Add a real session column instead."
        )
    id_normalizers = _survey_core.build_survey_id_normalizers(
        project_path, session_map=session_map
    )
```

Directly after the `df = _survey_core._filter_rows_by_selected_session(...)` call (after line 1528) add:

```python
    # Longitudinal project: every session label being imported needs a map entry.
    if session_map is not None:
        if res_ses_col and res_ses_col in df.columns:
            session_labels = df[res_ses_col].tolist()
        elif session and session != "all":
            session_labels = [session]
        else:
            raise SessionMapError(
                "This project has several timepoints: the file needs a session "
                "column, or a session must be chosen."
            )
        require_sessions_mapped(session_map, session_labels)
```

- [ ] **Step 5: Run and watch them pass**

Run: `python3 -m pytest tests/test_survey_session_map.py -q`
Expected: all pass. If `test_chosen_session_must_be_mapped_and_imports_only_its_rows` fails because the converter filters by exact column text, check `_filter_rows_by_selected_session` (it compares `.astype(str).str.strip()`); the map keys are the same stripped strings, so no change is needed unless the failure shows otherwise.

- [ ] **Step 6: Whole-suite regression**

Run: `python3 -m pytest tests -q --ignore=tests/e2e -p no:cacheprovider`
Expected: all pass. A failure in an older survey test that passes a `project_path` whose `project.json` exists but has no `Timepoints` means that test needs the `single` declaration added to its fixture project (that is the intended new rule); a failure anywhere else is a real regression, so stop and diagnose it.

---

### Task 4: CLI `prism_tools.py session-map show|set`

**Files:**
- Create: `app/src/cli/commands/session_map.py`
- Modify: `app/src/cli/parser.py` (new subparser), `app/src/cli/dispatch.py` (new branch), `app/src/cli/entrypoint.py` (import at ~line 60, handlers dict at ~line 140)
- Test: `tests/test_cli_session_map.py`

**Interfaces:**
- Consumes: `project_timepoints`, `load_session_map`, `set_session_entries`, `SessionMapError` (Task 1); `cmd_survey_convert` (existing, prints `Error: <message>` and exits 1 on any exception).
- Produces: `cmd_session_map_show(args)`, `cmd_session_map_set(args)`; args fields `project`, `json` (show) and `project`, `label`, `target` (set).

- [ ] **Step 1: Write the failing tests**

Create `tests/test_cli_session_map.py`:

```python
"""prism_tools.py session-map show / set, and conversion failing with the label list."""

import json
import shutil
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

APP_ROOT = Path(__file__).resolve().parents[1] / "app"
if str(APP_ROOT) not in sys.path:
    sys.path.insert(0, str(APP_ROOT))

from src.cli.commands.session_map import cmd_session_map_set, cmd_session_map_show  # noqa: E402
from src.cli.commands.survey import cmd_survey_convert  # noqa: E402
from src.session_map import load_session_map  # noqa: E402

BRS = Path(__file__).resolve().parents[1] / "official" / "library" / "survey" / "survey-brs.json"


@pytest.fixture
def proj(tmp_path):
    root = tmp_path / "proj"
    root.mkdir()
    (root / "project.json").write_text(json.dumps({"StudyDesign": {"Timepoints": "multiple"}}))
    return root


def test_set_then_show_lists_only_what_the_user_entered(proj, capsys):
    cmd_session_map_set(SimpleNamespace(project=str(proj), label="pre", target="1"))
    cmd_session_map_set(SimpleNamespace(project=str(proj), label="T0", target="1"))
    assert load_session_map(proj) == {"pre": "1", "T0": "1"}

    cmd_session_map_show(SimpleNamespace(project=str(proj), json=True))
    payload = json.loads(capsys.readouterr().out)
    assert payload == {"timepoints": "multiple", "map": {"pre": "1", "T0": "1"}}


def test_set_rejects_an_invalid_target_with_exit_code_2(proj, capsys):
    with pytest.raises(SystemExit) as info:
        cmd_session_map_set(SimpleNamespace(project=str(proj), label="pre", target="ses-1"))
    assert info.value.code == 2
    assert "letters and digits" in capsys.readouterr().out
    assert load_session_map(proj) == {}


def test_survey_convert_fails_naming_the_unmapped_labels(tmp_path, proj, capsys):
    lib = tmp_path / "lib"
    lib.mkdir()
    shutil.copy(BRS, lib / "survey-brs.json")
    data = tmp_path / "in.csv"
    data.write_text("participant_id,session,BRS01,BRS02,BRS03\nP001,pre,3,4,2\nP001,post,4,4,3\n")
    args = SimpleNamespace(
        input=str(data), output=str(tmp_path / "out"), library=str(lib), project=str(proj),
        survey=None, id_column="participant_id", session_column="session", sheet=0,
        unknown="warn", dry_run=False, force=False, name="t", authors=None, lang="en",
    )
    with pytest.raises(SystemExit) as info:
        cmd_survey_convert(args)
    assert info.value.code == 1
    out = capsys.readouterr().out
    assert "'pre'" in out and "'post'" in out and "session-map set" in out
```

- [ ] **Step 2: Run and watch them fail**

Run: `python3 -m pytest tests/test_cli_session_map.py -q`
Expected: collection error (`No module named 'src.cli.commands.session_map'`).

- [ ] **Step 3: Implement the commands**

Create `app/src/cli/commands/session_map.py`:

```python
"""Session-map prism_tools command handlers (thin adapters over src.session_map)."""

from __future__ import annotations

import json
import sys

from src.session_map import (
    SessionMapError,
    load_session_map,
    project_timepoints,
    set_session_entries,
)


def cmd_session_map_show(args) -> None:
    try:
        payload = {
            "timepoints": project_timepoints(args.project),
            "map": load_session_map(args.project),
        }
    except SessionMapError as exc:
        print(f"Error: {exc}")
        sys.exit(2)
    if getattr(args, "json", False):
        print(json.dumps(payload, indent=2, ensure_ascii=False))
        return
    print(f"Timepoints: {payload['timepoints'] or '(no project.json)'}")
    for label, target in payload["map"].items():
        print(f"  {label!r} -> {target}")
    if not payload["map"]:
        print("  (no entries; add them with `session-map set`)")


def cmd_session_map_set(args) -> None:
    try:
        set_session_entries(args.project, {args.label: args.target})
    except SessionMapError as exc:
        print(f"Error: {exc}")
        sys.exit(2)
    print(f"Mapped {args.label!r} -> {args.target}")
```

- [ ] **Step 4: Register parser, dispatch and handlers**

In `parser.py`, after the `participants` subparsers block (before `parser_environment`, ~line 426), add:

```python
    parser_session_map = subparsers.add_parser(
        "session-map",
        help="Session map for longitudinal projects (code/session_map.json)",
    )
    session_map_subparsers = parser_session_map.add_subparsers(dest="action", help="Action")

    parser_session_map_show = session_map_subparsers.add_parser(
        "show", help="Show the project's timepoint declaration and session map"
    )
    parser_session_map_show.add_argument("--project", required=True, help="Project root or project.json path")
    parser_session_map_show.add_argument("--json", action="store_true", help="Emit machine-readable JSON")

    parser_session_map_set = session_map_subparsers.add_parser(
        "set", help="Map one source session label to a session name"
    )
    parser_session_map_set.add_argument("--project", required=True, help="Project root or project.json path")
    parser_session_map_set.add_argument("--label", required=True, help="Source label exactly as it appears in the data")
    parser_session_map_set.add_argument("--target", required=True, help="Session name to write (letters and digits)")
```

Also add `"session-map": parser_session_map,` to the dict returned at the end of `build_prism_tools_parsers` (`parser.py:2082`, right after the `"participants": parser_participants,` entry at line 2085).

In `dispatch.py` add before the final `else`:

```python
    elif args.command == "session-map":
        if args.action == "show":
            handlers["session_map_show"](args)
        elif args.action == "set":
            handlers["session_map_set"](args)
        else:
            parsers["session-map"].print_help()
```

In `entrypoint.py`: import `from src.cli.commands.session_map import cmd_session_map_set, cmd_session_map_show` next to the other command imports, and add `"session_map_show": cmd_session_map_show, "session_map_set": cmd_session_map_set,` to the handlers dict.

- [ ] **Step 5: Run and watch them pass**

Run: `python3 -m pytest tests/test_cli_session_map.py tests/test_cli_command_import_boundaries.py -q`
Expected: pass. Then `python3 prism_tools.py session-map --help` must list `show` and `set`.

- [ ] **Step 6: Document**

Add a "Session map" section to `docs/CLI_REFERENCE.md` (the two commands, one example with `pre`/`post`, and the sentence "PRISM never suggests or fills in session names") and a CHANGELOG entry.

---

### Task 5: API and the survey GUI panel

**Files:**
- Create: `app/src/web/blueprints/session_map_blueprint.py`
- Modify: `app/prism-studio.py` (~line 557, `modular_blueprints`)
- Modify: `app/src/web/blueprints/conversion_survey_version_context_handlers.py` (new `except` and parameter), `conversion_survey_handlers.py` (~line 803 wrapper passes the class)
- Create: `app/static/js/modules/converter/session-map-panel.js`, `session-map-panel.test.js`
- Modify: `app/templates/converter_survey.html` (panel markup, before the `<hr class="my-4">` at ~line 158), `app/static/js/modules/converter/survey-convert.js` (`syncVersionWizardContext` at ~1278 and `updateConvertBtn` at ~1718)
- Test: `tests/test_session_map_api.py`, `app/static/js/modules/converter/session-map-panel.test.js`, `tests/e2e/test_session_map_flows.py`

**Interfaces:**
- Consumes: Task 1 functions; `_resolve_requested_or_current_project_root(path) -> Path | None` from `tools_helpers`.
- Produces:
  - `GET /api/session-map?project_path=` -> `{"ok": true, "timepoints": ..., "map": {...}}`
  - `POST /api/session-map` body `{"project_path": "...", "entries": {"pre": "1"}}` -> `{"ok": true, "map": {...}}`; 400 `{"error": "..."}` on `SessionMapError` or empty entries
  - detect endpoint: `409 {"error": "sessions_not_mapped", "message": "...", "unmapped_labels": ["post"]}`
  - JS: `validSessionName(text) -> boolean`, `canSaveSessionMap(labels, typed) -> boolean`, `createSessionMapPanel({...}) -> { show(labels), hide(), isPending() }`

- [ ] **Step 1: Write the failing API tests**

Create `tests/test_session_map_api.py`:

```python
import json
import sys
from pathlib import Path

import pytest
from flask import Flask

APP_ROOT = Path(__file__).resolve().parents[1] / "app"
if str(APP_ROOT) not in sys.path:
    sys.path.insert(0, str(APP_ROOT))

from src.web.blueprints.session_map_blueprint import session_map_bp  # noqa: E402


@pytest.fixture
def client(tmp_path):
    app = Flask(__name__)
    app.register_blueprint(session_map_bp)
    root = tmp_path / "proj"
    root.mkdir()
    (root / "project.json").write_text(json.dumps({"StudyDesign": {"Timepoints": "multiple"}}))
    return app.test_client(), root


def test_get_returns_declaration_and_map(client):
    http, root = client
    body = http.get("/api/session-map", query_string={"project_path": str(root)}).get_json()
    assert body == {"ok": True, "timepoints": "multiple", "map": {}}


def test_post_adds_entries_and_keeps_existing_ones(client):
    http, root = client
    http.post("/api/session-map", json={"project_path": str(root), "entries": {"pre": "1"}})
    resp = http.post("/api/session-map", json={"project_path": str(root), "entries": {"post": "2"}})
    assert resp.get_json() == {"ok": True, "map": {"pre": "1", "post": "2"}}


def test_post_rejects_an_invalid_target_and_writes_nothing(client):
    http, root = client
    resp = http.post("/api/session-map", json={"project_path": str(root), "entries": {"pre": "ses-1"}})
    assert resp.status_code == 400 and "letters and digits" in resp.get_json()["error"]
    assert not (root / "code" / "session_map.json").exists()


def test_post_without_entries_is_a_400(client):
    http, root = client
    assert http.post("/api/session-map", json={"project_path": str(root)}).status_code == 400
```

Run: `python3 -m pytest tests/test_session_map_api.py -q`. Expected: collection error (`No module named ...session_map_blueprint`).

- [ ] **Step 2: Implement the blueprint and register it**

Create `app/src/web/blueprints/session_map_blueprint.py`:

```python
"""Thin Flask adapter over src.session_map (the rule lives there)."""

from flask import Blueprint, jsonify, request

from src.session_map import (
    SessionMapError,
    load_session_map,
    project_timepoints,
    set_session_entries,
)

from .tools_helpers import _resolve_requested_or_current_project_root

session_map_bp = Blueprint("session_map", __name__)


@session_map_bp.route("/api/session-map", methods=["GET"])
def api_get_session_map():
    root = _resolve_requested_or_current_project_root(request.args.get("project_path"))
    if root is None:
        return jsonify({"error": "No project selected"}), 400
    try:
        return jsonify({"ok": True, "timepoints": project_timepoints(root), "map": load_session_map(root)})
    except SessionMapError as exc:
        return jsonify({"error": str(exc)}), 400


@session_map_bp.route("/api/session-map", methods=["POST"])
def api_set_session_map():
    payload = request.get_json(silent=True) or {}
    root = _resolve_requested_or_current_project_root(payload.get("project_path"))
    if root is None:
        return jsonify({"error": "No project selected"}), 400
    entries = payload.get("entries")
    if not isinstance(entries, dict) or not entries:
        return jsonify({"error": "entries must be a non-empty object of label to session name"}), 400
    try:
        return jsonify({"ok": True, "map": set_session_entries(root, entries)})
    except SessionMapError as exc:
        return jsonify({"error": str(exc)}), 400
```

In `app/prism-studio.py` add to `modular_blueprints` after the `conversion_participants` tuple:

```python
    (
        "src.web.blueprints.session_map_blueprint",
        "session_map_bp",
        "session_map",
    ),
```

Run `python3 -m pytest tests/test_session_map_api.py tests/test_backend_monitoring.py -q`. Expected: pass; if a monitoring test requires every `/api/*` route to be listed in `backend_monitoring.py`, add `"/api/session-map": "session_map.api_get_session_map"` in the same style as its neighbours.

- [ ] **Step 3: Failing test for the detect endpoint's 409**

Append to `tests/test_web_blueprints_conversion.py` inside `TestSurveyVersionContextEndpoint`, modelled on `test_detect_version_context_forwards_retry_resolution_hints` (same Flask/`patch.object` setup):

```python
    def test_detect_version_context_reports_unmapped_sessions_as_409(self):
        import importlib

        from src.session_map import SessionsNotMappedError

        handlers = importlib.import_module("src.web.blueprints.conversion_survey_handlers")
        app = Flask(__name__)
        app.secret_key = "test-secret"  # pragma: allowlist secret
        app.add_url_rule(
            "/api/survey-detect-version-contexts",
            view_func=handlers.api_survey_detect_version_context,
            methods=["POST"],
        )
        with patch.object(handlers, "_resolve_effective_library_path", return_value=Path("/tmp/library")):
            with patch.object(
                handlers, "_detect_survey_version_contexts",
                side_effect=SessionsNotMappedError(["post"]),
            ):
                with app.test_client() as client:
                    response = client.post(
                        "/api/survey-detect-version-contexts",
                        data={"excel": (io.BytesIO(b"Code,WB01\n1,5\n"), "input.csv"), "id_column": "Code"},
                        content_type="multipart/form-data",
                    )
        self.assertEqual(response.status_code, 409)
        payload = response.get_json()
        self.assertEqual(payload["error"], "sessions_not_mapped")
        self.assertEqual(payload["unmapped_labels"], ["post"])
```

Run it: expected FAIL (status 400, generic handler).

- [ ] **Step 4: Implement the 409**

In `conversion_survey_version_context_handlers.py` add the parameter `sessions_not_mapped_error_cls,` after `missing_id_mapping_error_cls,` in the signature and, before `except unmatched_groups_error_cls`, add:

```python
    except sessions_not_mapped_error_cls as error:
        return (
            jsonify(
                {
                    "error": "sessions_not_mapped",
                    "message": str(error),
                    "unmapped_labels": error.labels,
                }
            ),
            409,
        )
```

In `conversion_survey_handlers.py` (`api_survey_detect_version_context`, ~line 803) add `from src.session_map import SessionsNotMappedError` to the module imports and pass `sessions_not_mapped_error_cls=SessionsNotMappedError,` next to `missing_id_mapping_error_cls=MissingIdMappingError,`. Run the new test: PASS.

- [ ] **Step 5: Write the failing vitest for the panel rules**

Create `app/static/js/modules/converter/session-map-panel.test.js`:

```js
import { describe, expect, it } from 'vitest';

import { canSaveSessionMap, entriesToSave, validSessionName } from './session-map-panel.js';

describe('session map panel rules', () => {
    it('accepts letters and digits only', () => {
        for (const ok of ['1', '01', 'pre', 'T0', 'a1B2']) expect(validSessionName(ok)).toBe(true);
        for (const bad of ['', ' ', 'ses-1', 'a b', '1_2', 'é']) expect(validSessionName(bad)).toBe(false);
    });

    it('cannot save until every label has a valid name typed by the user', () => {
        expect(canSaveSessionMap(['pre', 'post'], {})).toBe(false);
        expect(canSaveSessionMap(['pre', 'post'], { pre: '1' })).toBe(false);
        expect(canSaveSessionMap(['pre', 'post'], { pre: '1', post: 'ses-2' })).toBe(false);
        expect(canSaveSessionMap(['pre', 'post'], { pre: '1', post: '2' })).toBe(true);
    });

    it('never invents a value: nothing typed means nothing to save', () => {
        expect(entriesToSave(['pre', 'post'], {})).toEqual({});
        expect(entriesToSave(['pre', 'post'], { pre: ' 1 ', post: '' })).toEqual({ pre: '1' });
    });

    it('shows a blank source label as (empty) but still requires a name for it', () => {
        expect(canSaveSessionMap([''], {})).toBe(false);
        expect(canSaveSessionMap([''], { '': '1' })).toBe(true);
    });
});
```

Run `npx vitest run app/static/js/modules/converter/session-map-panel.test.js`. Expected: FAIL (module missing).

- [ ] **Step 6: Implement the panel module**

Create `app/static/js/modules/converter/session-map-panel.js`:

```js
/**
 * Session mapping panel: lists source session labels next to EMPTY inputs.
 * Nothing is suggested or pre-filled; the user types every session name.
 */

export function validSessionName(text) {
    return /^[A-Za-z0-9]+$/.test(String(text ?? '').trim());
}

export function canSaveSessionMap(labels, typed) {
    return labels.length > 0 && labels.every((label) => validSessionName(typed[label]));
}

/** Only what the user actually typed (trimmed, non-empty). */
export function entriesToSave(labels, typed) {
    const entries = {};
    for (const label of labels) {
        const value = String(typed[label] ?? '').trim();
        if (value) entries[label] = value;
    }
    return entries;
}

/**
 * Thin DOM wrapper. `root` holds #sessionMapRows, #sessionMapSaveBtn, #sessionMapStatus.
 * `save(entries)` POSTs to /api/session-map and resolves on success; `onSaved()` re-runs detection.
 */
export function createSessionMapPanel({ root, save, onSaved, onChange }) {
    const rows = root.querySelector('#sessionMapRows');
    const saveBtn = root.querySelector('#sessionMapSaveBtn');
    const status = root.querySelector('#sessionMapStatus');
    let labels = [];
    const typed = {};

    function refresh() {
        saveBtn.disabled = !canSaveSessionMap(labels, typed);
        if (onChange) onChange();
    }

    function show(unmapped) {
        labels = unmapped.slice();
        rows.replaceChildren(
            ...labels.map((label) => {
                const group = document.createElement('div');
                group.className = 'input-group input-group-sm mb-1';
                const name = document.createElement('span');
                name.className = 'input-group-text';
                name.textContent = label === '' ? '(empty)' : label;
                const input = document.createElement('input');
                input.className = 'form-control';
                input.placeholder = 'session name (letters and digits)';
                input.setAttribute('aria-label', `Session name for ${label === '' ? 'empty label' : label}`);
                input.addEventListener('input', () => {
                    typed[label] = input.value;
                    refresh();
                });
                group.append(name, input);
                return group;
            })
        );
        status.textContent = '';
        root.classList.remove('d-none');
        refresh();
    }

    function hide() {
        labels = [];
        root.classList.add('d-none');
        if (onChange) onChange();
    }

    saveBtn.addEventListener('click', async () => {
        saveBtn.disabled = true;
        try {
            await save(entriesToSave(labels, typed));
            status.textContent = 'Saved.';
            if (onSaved) await onSaved();
        } catch (error) {
            status.textContent = error.message || 'Could not save the session map.';
            refresh();
        }
    });

    return { show, hide, isPending: () => labels.length > 0 };
}
```

Run the vitest file. Expected: PASS.

- [ ] **Step 7: Markup and wiring**

In `converter_survey.html`, directly before the `<hr class="my-4">` that precedes "Step 3 (Optional) - Advanced Adjustments", add:

```html
                            <div id="sessionMapPanel" class="alert alert-warning d-none mb-3" role="region" aria-labelledby="sessionMapPanelTitle">
                                <strong id="sessionMapPanelTitle">Session mapping required</strong>
                                <p class="small mb-2">This project has several timepoints. Say which session name each label in your file stands for. Nothing is filled in for you.</p>
                                <div id="sessionMapRows"></div>
                                <button type="button" class="btn btn-sm btn-warning mt-2" id="sessionMapSaveBtn" disabled>Save session map</button>
                                <span class="small ms-2" id="sessionMapStatus" aria-live="polite"></span>
                            </div>
```

In `survey-convert.js`:
- import: `import { createSessionMapPanel } from './session-map-panel.js';`
- near the other element lookups create the controller once:

```js
    const sessionMapPanelEl = document.getElementById('sessionMapPanel');
    const sessionMapPanel = sessionMapPanelEl
        ? createSessionMapPanel({
            root: sessionMapPanelEl,
            save: async (entries) => {
                const response = await fetchWithApiFallback('/api/session-map', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ project_path: window.currentProjectPath || '', entries }),
                });
                const data = await response.json().catch(() => ({}));
                if (!response.ok) throw new Error(data.error || 'Could not save the session map.');
            },
            onSaved: () => syncVersionWizardContext(),
            onChange: () => updateConvertBtn(),
        })
        : null;
```

- in `syncVersionWizardContext`, in the `if (!response.ok)` branch (line ~1278) before `hideVersionWizard()` add:

```js
                if (data?.error === 'sessions_not_mapped' && sessionMapPanel) {
                    sessionMapPanel.show(data.unmapped_labels || []);
                } else if (sessionMapPanel) {
                    sessionMapPanel.hide();
                }
```

  and after the `!response.ok` block (success path) add `if (sessionMapPanel) sessionMapPanel.hide();`
- in `updateConvertBtn` (line ~1718) add `const sessionMapPending = Boolean(sessionMapPanel && sessionMapPanel.isPending());`, OR it into `convertBtn.disabled` and `previewBtn.disabled`, and add title branches: `else if (sessionMapPending) { previewBtn.title = 'Map the session labels first.'; }` and the same for `convertBtn.title`.

- [ ] **Step 8: Write and run the browser flow**

Create `tests/e2e/test_session_map_flows.py`:

```python
"""Longitudinal projects: the user maps every session label; nothing is filled in."""

import json

from playwright.sync_api import expect

from tests.e2e.test_converter_flows import open_survey_tab

LONG = "participant_id,session,BRS01,BRS02,BRS03\nP001,pre,3,4,2\nP001,post,4,4,3\nP002,pre,1,0,2\n"


def make_longitudinal(project):
    (project / "project.json").write_text(json.dumps({"StudyDesign": {"Timepoints": "multiple"}}))


def select_file(page, tmp_path):
    data = tmp_path / "brs.csv"
    data.write_text(LONG)
    page.set_input_files("#convertSurveyFile", str(data))


def test_unmapped_labels_show_empty_inputs_and_block_preview(app_page, studio_url, tmp_path, project):
    make_longitudinal(project)
    open_survey_tab(app_page, studio_url)

    select_file(app_page, tmp_path)

    expect(app_page.locator("#sessionMapPanel")).to_be_visible(timeout=30000)
    inputs = app_page.locator("#sessionMapRows input")
    expect(inputs).to_have_count(2)
    for index in range(2):
        expect(inputs.nth(index)).to_have_value("")  # never pre-filled
    expect(app_page.locator("#previewBtn")).to_be_disabled()
    expect(app_page.locator("#sessionMapSaveBtn")).to_be_disabled()


def test_mapping_the_labels_unlocks_preview_and_convert_uses_the_names(app_page, studio_url, tmp_path, project):
    make_longitudinal(project)
    open_survey_tab(app_page, studio_url)
    select_file(app_page, tmp_path)
    expect(app_page.locator("#sessionMapPanel")).to_be_visible(timeout=30000)

    inputs = app_page.locator("#sessionMapRows input")
    inputs.nth(0).fill("1")
    inputs.nth(1).fill("2")
    app_page.click("#sessionMapSaveBtn")

    expect(app_page.locator("#sessionMapPanel")).to_be_hidden(timeout=30000)
    saved = json.loads((project / "code" / "session_map.json").read_text())
    assert saved == {"pre": "1", "post": "2"}
    expect(app_page.locator("#previewBtn")).to_be_enabled()
    app_page.click("#previewBtn")
    expect(app_page.locator("#convertBtn")).to_be_enabled(timeout=30000)
    app_page.click("#convertBtn")
    app_page.wait_for_function(
        "() => !document.getElementById('surveyRunProgressContainer') "
        "|| getComputedStyle(document.getElementById('surveyRunProgressContainer')).display === 'none'",
        timeout=60000,
    )
    names = sorted(p.name for p in (project / "sub-P001").glob("ses-*"))
    assert names == ["ses-1", "ses-2"]
```

Verified against the real page: with a session column, the Session ID control (`#convertSessionSelect`) offers `all` ("All sessions") plus each detected label, so a user imports every session of a longitudinal file by choosing `all`. In the second test, add this line right after the panel has hidden (before clicking Preview):

```python
    app_page.select_option("#convertSessionSelect", "all")
```

With `all`, the converter's gate takes the labels from the session column (`res_ses_col` branch), so every label in the file must be mapped.

Run: `python3 -m pytest tests/e2e/test_session_map_flows.py -q`. Expected before Step 7: FAIL (no panel). After Step 7: PASS.

- [ ] **Step 9: Whole-suite regression**

Run: `python3 -m pytest tests -q -p no:cacheprovider`, `npx vitest run`.
Expected: all pass.

---

### Task 6: Participants importer

**Files:**
- Modify: `src/participants_converter.py:400-411` (`convert_participant_data`)
- Modify: `app/templates/converter_participants.html`, `app/static/js/modules/converter/participants.js` (reuse the panel)
- Test: `tests/test_participants_session_map.py`, extend `tests/e2e/test_session_map_flows.py`

**Interfaces:**
- Consumes: `session_map_for_conversion`, `require_sessions_mapped` (Task 1); `ParticipantsConverter.dataset_path` (project root); `createSessionMapPanel` (Task 5).
- Produces: `convert_participant_data` returns `(False, None, ["✗ <message>"])` when the chosen file's session column holds unmapped labels in a `multiple` project. `participants.tsv` stays one row per participant with no session column, so the map only **gates** here; it does not rename anything.

- [ ] **Step 1: Write the failing test**

Create `tests/test_participants_session_map.py`:

```python
import json

from src.participants_converter import ParticipantsConverter
from src.session_map import save_session_map

MAPPING = {
    "version": "1.0",
    "description": "t",
    "mappings": {"participant_id": {"source_column": "participant_id", "standard_variable": "participant_id", "type": "string"}},
}
LONG = "participant_id,session,age\nP001,pre,21\nP001,post,22\nP002,pre,34\n"


def run(tmp_path, timepoints, mapped=None, **kwargs):
    (tmp_path / "project.json").write_text(json.dumps({"StudyDesign": {"Timepoints": timepoints}}))
    if mapped is not None:
        save_session_map(tmp_path, mapped)
    src = tmp_path / "people.csv"
    src.write_text(LONG)
    return ParticipantsConverter(tmp_path).convert_participant_data(
        source_file=src, mapping=MAPPING, output_file=tmp_path / "participants.tsv",
        session_column="session", session_value="pre", **kwargs,
    )


def test_unmapped_labels_in_the_session_column_block_the_import(tmp_path):
    ok, df, messages = run(tmp_path, "multiple", mapped={"pre": "1"})
    assert not ok and df is None
    assert "'post'" in " ".join(messages)


def test_fully_mapped_file_imports_the_chosen_session(tmp_path):
    ok, df, _ = run(tmp_path, "multiple", mapped={"pre": "1", "post": "2"})
    assert ok and len(df) == 2


def test_single_timepoint_project_is_unchanged(tmp_path):
    ok, df, _ = run(tmp_path, "single")
    assert ok and len(df) == 2
```

Run it. Expected: the first test FAILS (import succeeds), the other two pass.

- [ ] **Step 2: Implement the gate**

In `src/participants_converter.py` add `from src.session_map import SessionMapError, require_sessions_mapped, session_map_for_conversion` with the other imports, and replace the block at line 400 with:

```python
        if session_column and session_value:
            try:
                session_map = session_map_for_conversion(self.dataset_path)
                if session_map is not None and session_column in df.columns:
                    # Longitudinal project: every label in the file must be mapped,
                    # even though participants.tsv itself carries no session column.
                    require_sessions_mapped(session_map, df[session_column].tolist())
                total_rows = len(df)
                df = filter_rows_to_session(df, session_column, session_value)
            except (ValueError, SessionMapError) as e:
                self._log("ERROR", str(e))
                messages.append(f"✗ {e}")
                return False, None, messages
```

(`SessionMapError` subclasses `ValueError`, so the tuple could be just `ValueError`; keep it explicit for the reader.) Run the Step 1 tests: PASS. Also run `python3 -m pytest tests/test_cli_participants_neurobagel_schema.py tests/test_converter_participants_workflow_wiring.py -q` and the whole Python suite.

- [ ] **Step 3: GUI wiring (failing browser test first)**

Append to `tests/e2e/test_session_map_flows.py`:

```python
def test_participants_convert_names_the_unmapped_session_labels(app_page, studio_url, tmp_path, project):
    make_longitudinal(project)
    app_page.on("dialog", lambda dialog: dialog.accept())
    app_page.goto(f"{studio_url}/converter")
    app_page.click("#participants-tab")
    data = tmp_path / "people.csv"
    data.write_text("participant_id,session,age\nP001,pre,21\nP001,post,22\nP002,pre,34\n")
    app_page.set_input_files("#participantsDataFile", str(data))
    app_page.click("#participantsPreviewBtn")
    expect(app_page.locator("#participantsSessionChoiceCard")).to_be_visible(timeout=30000)
    app_page.click("#participantsSessionLongitudinalYes")
    app_page.select_option("#participantsSessionColumn", "session")
    app_page.select_option("#participantsSessionValue", "pre")
    expect(app_page.locator("#participantsConvertBtn")).to_be_enabled(timeout=30000)

    app_page.click("#participantsConvertBtn")

    expect(app_page.locator("#participantsError")).to_contain_text("'post'", timeout=30000)
    assert not (project / "participants.tsv").exists()
```

Run: expect FAIL until Step 2 is in place (it then passes, because the backend message is surfaced by the existing error div). The participants page shows the error text; a dedicated mapping panel there is intentionally **not** added (participants.tsv has no session names to choose), so the user maps labels on the survey page or with `session-map set`. If you want the panel on the participants page too, that is a follow-up requiring a spec decision, not part of this plan.

- [ ] **Step 4: Final verification**

Run in this order and expect all green:
1. `python3 -m pytest tests -q -p no:cacheprovider`
2. `npx vitest run`
3. `python3 tests/verify_repo.py --check dual-tree-drift --no-fix`
4. Manual: `python3 prism_tools.py session-map --help`

Update the memory note `gui-e2e-tests-page-by-page.md` with the new flows and the interpretation that on the participants page the map only gates.
