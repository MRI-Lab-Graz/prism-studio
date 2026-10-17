# Per-Modality Schema Versions Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Each community modality schema has its own version; the validator uses the latest by default, a project pins versions in `project.json` when a modality is first imported, the command line can override one modality per run, and a user is told once when a newer version exists and can update or freeze.

**Architecture:** One new backend module `src/modality_versions.py` (resolution, archive loading, pins, update/freeze state machine) is the single implementation. `schema_manager.load_all_schemas` and `runner.validate_dataset` consume it; `prism.py` and a new `prism_tools modality-version` command are thin adapters; converters pin on import; a CI script guards frozen versions. Studio notice buttons are a separate follow-up plan (the routes will be thin wrappers over this module).

**Tech Stack:** Python 3, pytest, jsonschema (already used), GitHub Actions YAML, Sphinx/MyST docs.

**Spec:** `docs/superpowers/specs/2026-10-16-modality-versioning-design.md`. This plan clarifies the spec in four places (Task 7 writes them into it): (a) project pins apply only when the base is `stable` (an explicit legacy `--schema-version v0.x` ignores them; `--modality-version` applies on any base); (b) a `prism_tools modality-version pin` command pins modalities of existing projects; (c) validation is read-only and never writes pins; (d) the Studio notice is a follow-up plan.

## Global Constraints

- TDD: every task starts with a failing test, run it and see it fail first (repo rule).
- One implementation: logic lives in `src/modality_versions.py`; `prism.py`, `prism_tools` and later Studio only call it. The module exists only under `src/` (no `app/src/` copy; dual-tree-drift check).
- `stable/` stays the latest version; archived versions (`app/schemas/archive/<name>/<x.y.z>.schema.json`) are frozen. Versions must match `^\d+\.\d+\.\d+$`.
- An unknown or unavailable version is an error that lists the available versions; never a silent fallback to another version.
- Validation never writes to `project.json`. Only converters (on import) and the `modality-version` commands write pins.
- Do NOT bump `project.schema.json`'s own `version` (1.0.0): sidecar compatibility warnings compare it (same major, minor not lower). The new keys are optional and additive.
- Text-format policy: `project.json` stays plain git; no `.gitattributes` change.
- Run tests with `PRISM_SKIP_VENV_CHECK=1 python3 -m pytest ...`. Known failing on main: 3 tests in `tests/test_lsa_import_integration.py`; `tests/e2e` is out of scope. `tests/verify_repo.py` writes a `*_report_*.txt` into the cwd: delete it before committing.
- Commit messages end with `Co-Authored-By: Claude Sonnet 5.5 <noreply@anthropic.com>`.
- Before merging: run `/ponytail:ponytail-audit` on the branch (CLAUDE.md rule).

## Review Focus

- A project with no pins, no `project.json`, or a broken `project.json` must validate against the latest, never crash.
- A pin naming a version that is not available (archive entry removed, typo) must produce one clear validation ERROR, not a traceback and not a silent switch to the latest.
- `--modality-version survey=1.0` (malformed) and `--modality-version nope=1.0.0` (unknown modality) must exit with a clear message, not a traceback.
- Pin-on-import must never overwrite an existing pin and must never make a conversion fail (a pinning problem is a warning on stderr).
- A pinned modality whose latest version is newer and not yet acknowledged yields exactly one notice; after `freeze` or `update` no repeat; a still-newer version notifies again.
- The CI guard must pass a brand-new modality (no archive) and a correctly released new version, and must fail on an edited archive file, an unchanged `version` with changed content, and a bumped `version` without the previous version archived.

---

## File Structure

- Create `src/modality_versions.py`: names, versions, archive loading, resolution, pins, pending/update/freeze, `pin_after_import`, hint formatting.
- Modify `app/src/schema_manager.py`: `_read_schema_file` helper, `load_all_schemas(..., modality_versions=None)`.
- Modify `app/src/runner.py`: `_default_schema_dir`, `_load_schemas`, `validate_dataset` / `validate_subject_only` parameters, `prism_schema_sources`.
- Modify `app/prism.py`: `--modality-version`, extended `--list-versions`, error handling, pending-update hint.
- Modify `app/schemas/stable/project.schema.json`: two optional objects.
- Create `app/src/cli/commands/modality_version.py`; modify `app/src/cli/parser.py`, `app/src/cli/entrypoint.py`.
- Modify converters: `app/src/converters/survey.py`, `src/converters/biometrics.py`, `src/batch_convert.py`, `app/src/cli/commands/environment.py` (pin on import).
- Create `scripts/ci/check_schema_versions.py`; modify `.github/workflows/ci.yml`.
- Docs: `docs/SCHEMA_VERSIONING.md`, `docs/CLI_REFERENCE.md`, `docs/MODALITY_WORKFLOW.md`, the spec.
- New tests: `tests/test_modality_versions.py`, `tests/test_modality_version_pins.py`, `tests/test_schema_manager_modality_versions.py`, `tests/test_runner_modality_versions.py`, `tests/test_cli_modality_version.py`, `tests/test_pin_on_import.py`, `tests/test_check_schema_versions.py`.

---

### Task 1: `src/modality_versions.py` core: versions, archive loading, resolution

**Files:**
- Create: `src/modality_versions.py`
- Modify: `app/src/schema_manager.py` (extract `_read_schema_file` out of `load_schema`, ~lines 63-97)
- Test: `tests/test_modality_versions.py`

**Interfaces:**
- Produces:
  - `ModalityVersionError(ValueError)`
  - `modality_names(schema_dir=None) -> list[str]`: modalities in `stable/entities.schema.json` that have a `stable/<name>.schema.json`
  - `current_version(name, schema_dir=None) -> str`; `current_versions(schema_dir=None) -> dict[str, str]`
  - `available_versions(name, schema_dir=None) -> list[str]` (archive plus current, ascending semver)
  - `load_modality_schema(name, version, schema_dir=None) -> dict` (has `_validator_info` like `load_schema`)
  - `parse_overrides(items: list[str]) -> dict[str, str]` (`["survey=1.0.3"]`)
  - `resolve_modality_versions(pins=None, overrides=None, schema_dir=None) -> tuple[dict[str, str], dict[str, str]]`: (versions, sources) with sources in `{"cli", "project.json", "latest"}`
  - `schema_manager._read_schema_file(schema_path: str, name: str, version_tag: str) -> dict | None`
  - `VERSION_RE`

- [ ] **Step 1: Write the failing tests** `tests/test_modality_versions.py`

```python
import json
from pathlib import Path

import pytest

from src.modality_versions import (
    ModalityVersionError,
    available_versions,
    current_version,
    current_versions,
    load_modality_schema,
    modality_names,
    parse_overrides,
    resolve_modality_versions,
)


def _schema(name: str, version: str) -> dict:
    return {"$id": f"https://prism.org/schemas/{name}/v{version}", "version": version,
            "title": name, "type": "object", "properties": {"Metadata": {"type": "object"}}}


@pytest.fixture
def schema_dir(tmp_path: Path) -> str:
    stable = tmp_path / "stable"
    stable.mkdir()
    (stable / "entities.schema.json").write_text(json.dumps({"modalities": {
        "survey": {"kind": "prism"}, "physio": {"kind": "prism"}, "anat": {"kind": "bidsPassthrough"}}}))
    (stable / "survey.schema.json").write_text(json.dumps(_schema("survey", "1.2.0")))
    (stable / "physio.schema.json").write_text(json.dumps(_schema("physio", "1.0.0")))
    archive = tmp_path / "archive" / "survey"
    archive.mkdir(parents=True)
    for v in ("1.0.0", "1.1.0", "1.10.0"):
        (archive / f"{v}.schema.json").write_text(json.dumps(_schema("survey", v)))
    return str(tmp_path)


def test_names_are_modalities_that_have_a_stable_schema(schema_dir):
    assert modality_names(schema_dir) == ["survey", "physio"]  # anat has no schema file


def test_current_versions(schema_dir):
    assert current_version("survey", schema_dir) == "1.2.0"
    assert current_versions(schema_dir) == {"survey": "1.2.0", "physio": "1.0.0"}


def test_unknown_modality_lists_the_known_ones(schema_dir):
    with pytest.raises(ModalityVersionError, match="survey, physio"):
        current_version("nope", schema_dir)


def test_available_versions_are_sorted_by_semver_not_text(schema_dir):
    assert available_versions("survey", schema_dir) == ["1.0.0", "1.1.0", "1.2.0", "1.10.0"]
    assert available_versions("physio", schema_dir) == ["1.0.0"]


def test_load_current_and_archived_versions(schema_dir):
    assert load_modality_schema("survey", "1.2.0", schema_dir)["_validator_info"]["schema_version"] == "1.2.0"
    old = load_modality_schema("survey", "1.1.0", schema_dir)
    assert old["version"] == "1.1.0"
    assert old["_validator_info"]["schema_version"] == "1.1.0"
    assert old["_validator_info"]["modality"] == "survey"


def test_unknown_version_is_an_error_listing_what_exists(schema_dir):
    with pytest.raises(ModalityVersionError) as exc:
        load_modality_schema("survey", "9.9.9", schema_dir)
    assert "1.0.0" in str(exc.value) and "1.2.0" in str(exc.value)


def test_parse_overrides():
    assert parse_overrides(["survey=1.0.3", "physio=2.0.0"]) == {"survey": "1.0.3", "physio": "2.0.0"}


@pytest.mark.parametrize("bad", ["survey", "survey=1.0", "=1.0.0", "survey=v1.0.0", "survey=1.0.0=2"])
def test_malformed_overrides_are_errors(bad):
    with pytest.raises(ModalityVersionError, match="NAME=X.Y.Z"):
        parse_overrides([bad])


def test_resolution_precedence_and_sources(schema_dir):
    versions, sources = resolve_modality_versions(
        pins={"survey": "1.1.0", "physio": "1.0.0"}, overrides={"survey": "1.0.0"}, schema_dir=schema_dir)
    assert versions == {"survey": "1.0.0", "physio": "1.0.0"}
    assert sources == {"survey": "cli", "physio": "project.json"}
    versions, sources = resolve_modality_versions(schema_dir=schema_dir)
    assert versions == {"survey": "1.2.0", "physio": "1.0.0"}
    assert set(sources.values()) == {"latest"}


def test_pin_for_a_modality_that_no_longer_exists_is_ignored(schema_dir):
    versions, _ = resolve_modality_versions(pins={"gone": "1.0.0"}, schema_dir=schema_dir)
    assert "gone" not in versions


def test_override_for_an_unknown_modality_is_an_error(schema_dir):
    with pytest.raises(ModalityVersionError, match="survey, physio"):
        resolve_modality_versions(overrides={"nope": "1.0.0"}, schema_dir=schema_dir)
```
- [ ] **Step 2: Run to verify failure**

Run: `PRISM_SKIP_VENV_CHECK=1 python3 -m pytest -q tests/test_modality_versions.py`
Expected: FAIL (ImportError: `src.modality_versions`).

- [ ] **Step 3: Implement**

In `app/src/schema_manager.py` replace the body of `load_schema` after the path is built with a call to a new helper (behaviour identical):

```python
def _read_schema_file(schema_path, name, version_tag):
    """Load one schema file and attach the _validator_info block (None on failure)."""
    if not os.path.exists(schema_path):
        return None
    try:
        with open(schema_path) as f:
            schema = json.load(f)
        schema["_validator_info"] = {
            "schema_version": schema.get("version", "1.0.0"),
            "modality": name,
            "version_tag": version_tag,
            "loaded_at": json.dumps({"timestamp": "runtime"}),
        }
        return schema
    except (json.JSONDecodeError, IOError) as e:
        print(f"Warning: Could not load schema {schema_path}: {e}")
    return None
```
and in `load_schema`: `return _read_schema_file(schema_path, name, version)` (delete the old inline try/except).

Create `src/modality_versions.py`:

```python
"""Per-modality schema versions: which exist, which one applies, pins in project.json."""

from __future__ import annotations

import json
import re
from pathlib import Path

from src.schema_manager import DEFAULT_SCHEMA_DIR, _read_schema_file, load_schema, parse_version

VERSION_RE = re.compile(r"^\d+\.\d+\.\d+$")


class ModalityVersionError(ValueError):
    """A modality name or version that does not exist (the message lists what does)."""


def _dir(schema_dir) -> Path:
    return Path(schema_dir or DEFAULT_SCHEMA_DIR)


def modality_names(schema_dir=None) -> list[str]:
    stable = _dir(schema_dir) / "stable"
    entities = json.loads((stable / "entities.schema.json").read_text(encoding="utf-8"))
    return [n for n in entities.get("modalities", {}) if (stable / f"{n}.schema.json").is_file()]


def current_version(name: str, schema_dir=None) -> str:
    path = _dir(schema_dir) / "stable" / f"{name}.schema.json"
    if not path.is_file():
        raise ModalityVersionError(
            f"unknown modality '{name}'; known: {', '.join(modality_names(schema_dir))}"
        )
    return json.loads(path.read_text(encoding="utf-8")).get("version", "1.0.0")


def current_versions(schema_dir=None) -> dict[str, str]:
    return {n: current_version(n, schema_dir) for n in modality_names(schema_dir)}


def available_versions(name: str, schema_dir=None) -> list[str]:
    current = current_version(name, schema_dir)
    archived = {
        p.name[: -len(".schema.json")]
        for p in (_dir(schema_dir) / "archive" / name).glob("*.schema.json")
    }
    return sorted({current, *archived}, key=parse_version)


def load_modality_schema(name: str, version: str, schema_dir=None) -> dict:
    base = _dir(schema_dir)
    if version == current_version(name, schema_dir):
        return load_schema(name, str(base), "stable")
    path = base / "archive" / name / f"{version}.schema.json"
    schema = _read_schema_file(str(path), name, f"{name}@{version}")
    if schema is None:
        raise ModalityVersionError(
            f"{name} has no version {version}; available: {', '.join(available_versions(name, schema_dir))}"
        )
    return schema


def parse_overrides(items: list[str]) -> dict[str, str]:
    """['survey=1.0.3'] -> {'survey': '1.0.3'}; anything else is an error."""
    out: dict[str, str] = {}
    for item in items or []:
        name, sep, version = item.partition("=")
        if not (sep and name and VERSION_RE.match(version)):
            raise ModalityVersionError(f"'{item}': use NAME=X.Y.Z (for example survey=1.0.3)")
        out[name] = version
    return out


def resolve_modality_versions(pins=None, overrides=None, schema_dir=None):
    """(versions, sources): per modality override > project pin > latest."""
    names = modality_names(schema_dir)
    overrides, pins = dict(overrides or {}), dict(pins or {})
    unknown = sorted(set(overrides) - set(names))
    if unknown:
        raise ModalityVersionError(f"unknown modality {unknown}; known: {', '.join(names)}")
    versions: dict[str, str] = {}
    sources: dict[str, str] = {}
    for name in names:
        if name in overrides:
            versions[name], sources[name] = overrides[name], "cli"
        elif name in pins:
            versions[name], sources[name] = pins[name], "project.json"
        else:
            versions[name], sources[name] = current_version(name, schema_dir), "latest"
    return versions, sources
```

- [ ] **Step 4: Run to verify pass**

Run: `PRISM_SKIP_VENV_CHECK=1 python3 -m pytest -q tests/test_modality_versions.py tests/test_unit.py`
Expected: PASS (`test_unit.py` proves `load_schema` behaves as before).

- [ ] **Step 5: Commit**

```bash
git add src/modality_versions.py app/src/schema_manager.py tests/test_modality_versions.py
git commit -m "feat(schemas): per-modality versions: archive loading and resolution

Co-Authored-By: Claude Sonnet 5.5 <noreply@anthropic.com>"
```

---

### Task 2: Use versions when validating (`load_all_schemas`, runner, `prism.py`)

**Files:**
- Modify: `app/src/schema_manager.py` (`load_all_schemas`)
- Modify: `app/src/runner.py` (`validate_dataset` ~line 104, `validate_subject_only` ~line 790, new helpers)
- Modify: `app/prism.py` (arguments ~line 183, `--list-versions` ~line 321, validate call ~line 485)
- Test: `tests/test_schema_manager_modality_versions.py`, `tests/test_runner_modality_versions.py`

**Interfaces:**
- Consumes: Task 1 functions; `read_pins` from Task 3 is needed here, so Task 2 defines a **minimal** `read_pins` first (see Step 3) and Task 3 extends the module around it without changing its signature: `read_pins(project_root) -> tuple[dict[str, str], dict[str, str]]` (pins, acknowledged).
- Produces: `load_all_schemas(schema_dir, version=None, modality_versions=None)`; `runner._default_schema_dir() -> str`; `runner._load_schemas(root_dir, schema_version, modality_versions, schema_dir=None) -> tuple[dict, dict[str, str]]`; `validate_dataset(..., modality_versions=None)` and `validate_subject_only(..., modality_versions=None)`; `stats.validator_info["prism_schema_sources"]`; CLI flag `--modality-version NAME=X.Y.Z` (repeatable).

- [ ] **Step 1: Write the failing tests**

`tests/test_schema_manager_modality_versions.py`:

```python
import json
import shutil
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "app" / "src"))

from schema_manager import load_all_schemas  # noqa: E402


def _copy_schemas(tmp_path: Path) -> str:
    dest = tmp_path / "schemas"
    shutil.copytree(REPO / "app" / "schemas", dest)
    return str(dest)


def _archive_survey(schema_dir: str, version: str) -> None:
    stable = json.loads((Path(schema_dir) / "stable" / "survey.schema.json").read_text())
    stable["version"] = version
    target = Path(schema_dir) / "archive" / "survey"
    target.mkdir(parents=True, exist_ok=True)
    (target / f"{version}.schema.json").write_text(json.dumps(stable))


def test_default_load_is_unchanged(tmp_path):
    schemas = load_all_schemas(_copy_schemas(tmp_path))
    assert schemas["survey"]["_validator_info"]["version_tag"] == "stable"


def test_one_modality_can_be_loaded_at_an_archived_version(tmp_path):
    schema_dir = _copy_schemas(tmp_path)
    _archive_survey(schema_dir, "1.0.0")
    schemas = load_all_schemas(schema_dir, modality_versions={"survey": "1.0.0"})
    assert schemas["survey"]["_validator_info"]["schema_version"] == "1.0.0"
    assert schemas["biometrics"]["_validator_info"]["version_tag"] == "stable"


def test_aliases_follow_the_overridden_schema(tmp_path):
    schema_dir = _copy_schemas(tmp_path)
    archive = Path(schema_dir) / "archive" / "physio"
    archive.mkdir(parents=True)
    phys = json.loads((Path(schema_dir) / "stable" / "physio.schema.json").read_text())
    phys["version"] = "1.0.0"
    (archive / "1.0.0.schema.json").write_text(json.dumps(phys))
    schemas = load_all_schemas(schema_dir, modality_versions={"physio": "1.0.0"})
    assert schemas["physiological"] is schemas["physio"]
    assert schemas["physio"]["version"] == "1.0.0"
```

`tests/test_runner_modality_versions.py`:

```python
import json
import shutil
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "app" / "src"))

import runner  # noqa: E402
from src.modality_versions import ModalityVersionError  # noqa: E402


@pytest.fixture
def schema_dir(tmp_path):
    dest = tmp_path / "schemas"
    shutil.copytree(REPO / "app" / "schemas", dest)
    stable = json.loads((dest / "stable" / "survey.schema.json").read_text())
    current = stable["version"]
    old = dict(stable, version="0.9.0")
    (dest / "archive" / "survey").mkdir(parents=True)
    (dest / "archive" / "survey" / "0.9.0.schema.json").write_text(json.dumps(old))
    return str(dest), current


def _project(tmp_path: Path, pins=None) -> Path:
    root = tmp_path / "proj"
    root.mkdir()
    payload = {"Metadata": {"SchemaVersion": "1.0.0"}}
    if pins is not None:
        payload["SchemaVersions"] = pins
    (root / "project.json").write_text(json.dumps(payload))
    return root


def test_no_pins_means_latest(tmp_path, schema_dir):
    sdir, current = schema_dir
    schemas, sources = runner._load_schemas(_project(tmp_path), None, None, sdir)
    assert schemas["survey"]["_validator_info"]["schema_version"] == current
    assert set(sources.values()) == {"latest"}


def test_project_pin_selects_the_archived_version(tmp_path, schema_dir):
    sdir, _ = schema_dir
    schemas, sources = runner._load_schemas(_project(tmp_path, {"survey": "0.9.0"}), None, None, sdir)
    assert schemas["survey"]["_validator_info"]["schema_version"] == "0.9.0"
    assert sources["survey"] == "project.json"


def test_cli_override_beats_the_pin(tmp_path, schema_dir):
    sdir, current = schema_dir
    schemas, sources = runner._load_schemas(
        _project(tmp_path, {"survey": "0.9.0"}), None, {"survey": current}, sdir)
    assert schemas["survey"]["_validator_info"]["schema_version"] == current
    assert sources["survey"] == "cli"


def test_pins_are_ignored_on_a_legacy_base_but_overrides_apply(tmp_path, schema_dir):
    sdir, _ = schema_dir
    root = _project(tmp_path, {"survey": "0.9.0"})
    _, sources = runner._load_schemas(root, "v0.2", None, sdir)
    assert sources["survey"] == "latest"
    _, sources = runner._load_schemas(root, "v0.2", {"survey": "0.9.0"}, sdir)
    assert sources["survey"] == "cli"


def test_broken_or_missing_project_json_means_latest(tmp_path, schema_dir):
    sdir, current = schema_dir
    root = tmp_path / "p2"
    root.mkdir()
    (root / "project.json").write_text("{not json")
    schemas, _ = runner._load_schemas(root, None, None, sdir)
    assert schemas["survey"]["_validator_info"]["schema_version"] == current


def test_unavailable_pinned_version_is_an_error(tmp_path, schema_dir):
    sdir, _ = schema_dir
    with pytest.raises(ModalityVersionError, match="0.9.0"):
        runner._load_schemas(_project(tmp_path, {"survey": "7.7.7"}), None, None, sdir)


def test_validate_dataset_reports_an_unavailable_pin_as_one_error(tmp_path, monkeypatch, schema_dir):
    sdir, _ = schema_dir
    monkeypatch.setattr(runner, "_default_schema_dir", lambda: sdir)
    root = _project(tmp_path, {"survey": "7.7.7"})
    issues, _ = runner.validate_dataset(str(root), run_bids=False)
    assert [i for i in issues if i[0] == "ERROR" and "7.7.7" in i[1]]


def test_validator_info_records_where_each_version_came_from(tmp_path, monkeypatch, schema_dir):
    sdir, _ = schema_dir
    monkeypatch.setattr(runner, "_default_schema_dir", lambda: sdir)
    root = _project(tmp_path, {"survey": "0.9.0"})
    _, stats = runner.validate_dataset(str(root), run_bids=False)
    assert stats.validator_info["prism_schema_sources"]["survey"] == "project.json"
    assert stats.validator_info["prism_schema_versions"]["survey"] == "0.9.0"
```

- [ ] **Step 2: Run to verify failure**

Run: `PRISM_SKIP_VENV_CHECK=1 python3 -m pytest -q tests/test_schema_manager_modality_versions.py tests/test_runner_modality_versions.py`
Expected: FAIL (`modality_versions` keyword, `_load_schemas` missing).

- [ ] **Step 3: Implement**

`app/src/schema_manager.py` `load_all_schemas(schema_dir=DEFAULT_SCHEMA_DIR, version=None, modality_versions=None)`: insert, directly after the `for modality in [*entities.get("modalities", {}), "dataset_description"]:` loop and before the aliases loop:

```python
    if modality_versions:
        from src.modality_versions import load_modality_schema

        for modality, modality_version in modality_versions.items():
            schemas[modality] = load_modality_schema(modality, modality_version, schema_dir)
```
(the existing aliases loop that follows then points aliases at the overridden schema). Update the docstring (Args).

Add to `src/modality_versions.py` the minimal reader (Task 3 extends this module, keep the signature):

```python
def _read_project(project_root) -> dict | None:
    path = Path(project_root) / "project.json"
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    return data if isinstance(data, dict) else None


def _clean_map(value) -> dict[str, str]:
    if not isinstance(value, dict):
        return {}
    return {k: v for k, v in value.items() if isinstance(k, str) and isinstance(v, str) and VERSION_RE.match(v)}


def read_pins(project_root) -> tuple[dict[str, str], dict[str, str]]:
    """(SchemaVersions, SchemaVersionsAcknowledged) of a project; empty when absent or unreadable."""
    data = _read_project(project_root) or {}
    return _clean_map(data.get("SchemaVersions")), _clean_map(data.get("SchemaVersionsAcknowledged"))
```

`app/src/runner.py`: add near the top-level helpers

```python
def _default_schema_dir() -> str:
    return os.path.join(os.path.dirname(os.path.dirname(__file__)), "schemas")


def _load_schemas(root_dir, schema_version, modality_versions, schema_dir=None):
    """Schemas for one run plus where each modality's version came from.

    Project pins apply on the stable base only; an explicit legacy
    --schema-version ignores them, --modality-version applies on any base.
    """
    from src.modality_versions import read_pins, resolve_modality_versions

    schema_dir = schema_dir or _default_schema_dir()
    pins = read_pins(root_dir)[0] if schema_version in (None, "stable") else {}
    versions, sources = resolve_modality_versions(pins, modality_versions, schema_dir)
    explicit = {n: v for n, v in versions.items() if sources[n] != "latest"}
    schemas = load_all_schemas(schema_dir, version=schema_version, modality_versions=explicit or None)
    return schemas, sources
```
`validate_dataset`: add parameter `modality_versions: Optional[dict] = None` (docstring line), replace the two lines `schema_dir = ...; schemas = load_all_schemas(...)` by:

```python
    try:
        schemas, schema_sources = _load_schemas(root_dir, schema_version, modality_versions)
    except ModalityVersionError as exc:
        return [("ERROR", f"Schema version problem: {exc}")], stats
```
(import `from src.modality_versions import ModalityVersionError` at the top of runner next to its other `src.` imports), and add `"prism_schema_sources": schema_sources,` to the `stats.validator_info` dict. `validate_subject_only`: add keyword `modality_versions=None` and use `schemas, _ = _load_schemas(root_dir, schema_version, modality_versions)` (a `ModalityVersionError` propagates: its callers are commit hooks that already treat exceptions as failure; do not swallow).

`app/prism.py`: add after `--schema-version`:

```python
    parser.add_argument(
        "--modality-version",
        action="append",
        default=[],
        metavar="NAME=X.Y.Z",
        help="Validate one modality against a specific version (repeatable), "
        "e.g. --modality-version survey=1.0.3. Overrides the project.json pin.",
    )
```
Before the validate call: 

```python
    from src.modality_versions import ModalityVersionError, parse_overrides

    try:
        modality_versions = parse_overrides(args.modality_version)
    except ModalityVersionError as exc:
        print(f"❌ {exc}", file=sys.stderr)
        sys.exit(2)
```
and pass `modality_versions=modality_versions` to `validate_dataset(...)`. Extend `--list-versions` (after the global list):

```python
        from src.modality_versions import available_versions, modality_names

        print("\nModality versions (latest last):")
        for name in modality_names(schema_dir):
            print(f"  • {name}: {', '.join(available_versions(name, schema_dir))}")
```

- [ ] **Step 4: Run to verify pass**

Run: `PRISM_SKIP_VENV_CHECK=1 python3 -m pytest -q tests/test_schema_manager_modality_versions.py tests/test_runner_modality_versions.py tests/test_modality_versions.py tests/test_unit.py tests/test_cli_dispatch_routing.py`
Then: `python3 app/prism.py --list-versions` (expected: global versions plus a per-modality list) and `python3 app/prism.py /tmp --modality-version survey=1.0` (expected: exit 2, "use NAME=X.Y.Z").

- [ ] **Step 5: Commit**

```bash
git add app/src/schema_manager.py app/src/runner.py app/prism.py src/modality_versions.py tests
git commit -m "feat(validator): validate against per-modality versions; --modality-version

Co-Authored-By: Claude Sonnet 5.5 <noreply@anthropic.com>"
```

---

### Task 3: Pins in `project.json`: pin, pending notice, update, freeze

**Files:**
- Modify: `src/modality_versions.py`
- Modify: `app/schemas/stable/project.schema.json`
- Test: `tests/test_modality_version_pins.py`

**Interfaces:**
- Consumes: `read_pins`, `_read_project`, `current_version`, `modality_names`, `ModalityVersionError`.
- Produces:
  - `present_modalities(project_root, schema_dir=None) -> list[str]`
  - `pin_modalities(project_root, names, schema_dir=None) -> dict[str, str]` (newly pinned only)
  - `pin_present_modalities(project_root, schema_dir=None) -> dict[str, str]`
  - `pending_updates(project_root, schema_dir=None) -> list[tuple[str, str, str]]` (name, pinned, latest)
  - `update_modality(project_root, name, schema_dir=None) -> str` (new pin); `freeze_modality(project_root, name, schema_dir=None) -> str` (kept pin)
  - `pin_after_import(output_root) -> None` (never raises; warns on stderr)
  - `format_pending_hint(pending) -> list[str]`

- [ ] **Step 1: Write the failing tests** `tests/test_modality_version_pins.py`

```python
import json
from pathlib import Path

import jsonschema
import pytest

from src.modality_versions import (
    ModalityVersionError,
    format_pending_hint,
    freeze_modality,
    pending_updates,
    pin_after_import,
    pin_modalities,
    pin_present_modalities,
    present_modalities,
    read_pins,
    update_modality,
)

REPO = Path(__file__).resolve().parents[1]


def _schema(name, version):
    return {"version": version, "title": name, "type": "object"}


@pytest.fixture
def schema_dir(tmp_path):
    root = tmp_path / "schemas"
    stable = root / "stable"
    stable.mkdir(parents=True)
    (stable / "entities.schema.json").write_text(json.dumps({"modalities": {
        "survey": {"kind": "prism"}, "biometrics": {"kind": "prism"}, "events": {"kind": "prism"}}}))
    for n in ("survey", "biometrics", "events"):
        (stable / f"{n}.schema.json").write_text(json.dumps(_schema(n, "1.1.0")))
    return str(root)


def _project(tmp_path, **extra):
    root = tmp_path / "proj"
    root.mkdir(exist_ok=True)
    (root / "project.json").write_text(json.dumps({"Metadata": {"SchemaVersion": "1.0.0"}, **extra}))
    return root


def _touch(root: Path, rel: str):
    p = root / rel
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text("x")


def test_present_modalities_by_folder_and_events_by_file(tmp_path, schema_dir):
    root = _project(tmp_path)
    _touch(root, "sub-01/survey/sub-01_task-a_survey.tsv")
    _touch(root, "sub-02/ses-1/biometrics/sub-02_ses-1_task-b_biometrics.tsv")
    _touch(root, "sub-01/func/sub-01_task-a_events.tsv")
    (root / "sub-03" / "biometrics").mkdir(parents=True)  # empty folder does not count
    assert present_modalities(root, schema_dir) == ["survey", "biometrics", "events"]


def test_pin_present_pins_current_versions_and_never_overwrites(tmp_path, schema_dir):
    root = _project(tmp_path, SchemaVersions={"survey": "1.0.0"})
    _touch(root, "sub-01/survey/sub-01_task-a_survey.tsv")
    _touch(root, "sub-01/biometrics/sub-01_task-b_biometrics.tsv")
    new = pin_present_modalities(root, schema_dir)
    assert new == {"biometrics": "1.1.0"}
    assert read_pins(root)[0] == {"biometrics": "1.1.0", "survey": "1.0.0"}
    assert pin_present_modalities(root, schema_dir) == {}


def test_pinning_keeps_the_rest_of_project_json(tmp_path, schema_dir):
    root = _project(tmp_path, Sessions=[{"id": "ses-1"}])
    _touch(root, "sub-01/survey/sub-01_task-a_survey.tsv")
    pin_present_modalities(root, schema_dir)
    data = json.loads((root / "project.json").read_text())
    assert data["Sessions"] == [{"id": "ses-1"}] and data["SchemaVersions"] == {"survey": "1.1.0"}


def test_no_project_json_means_nothing_is_written(tmp_path, schema_dir):
    root = tmp_path / "bare"
    _touch(root, "sub-01/survey/sub-01_task-a_survey.tsv")
    assert pin_present_modalities(root, schema_dir) == {}
    assert not (root / "project.json").exists()


def test_pin_modalities_by_name_and_unknown_name_error(tmp_path, schema_dir):
    root = _project(tmp_path)
    assert pin_modalities(root, ["survey"], schema_dir) == {"survey": "1.1.0"}
    with pytest.raises(ModalityVersionError):
        pin_modalities(root, ["nope"], schema_dir)


def _bump(schema_dir, name, version):
    (Path(schema_dir) / "stable" / f"{name}.schema.json").write_text(json.dumps(_schema(name, version)))


def test_pending_update_is_told_once_per_new_version(tmp_path, schema_dir):
    root = _project(tmp_path, SchemaVersions={"survey": "1.1.0"})
    assert pending_updates(root, schema_dir) == []
    _bump(schema_dir, "survey", "1.2.0")
    assert pending_updates(root, schema_dir) == [("survey", "1.1.0", "1.2.0")]
    assert freeze_modality(root, "survey", schema_dir) == "1.1.0"
    assert pending_updates(root, schema_dir) == []
    assert read_pins(root)[0]["survey"] == "1.1.0"
    _bump(schema_dir, "survey", "1.3.0")
    assert pending_updates(root, schema_dir) == [("survey", "1.1.0", "1.3.0")]


def test_update_moves_the_pin_and_clears_the_notice(tmp_path, schema_dir):
    root = _project(tmp_path, SchemaVersions={"survey": "1.1.0"})
    _bump(schema_dir, "survey", "1.2.0")
    assert update_modality(root, "survey", schema_dir) == "1.2.0"
    assert read_pins(root)[0]["survey"] == "1.2.0"
    assert pending_updates(root, schema_dir) == []


def test_update_and_freeze_need_a_pin(tmp_path, schema_dir):
    root = _project(tmp_path)
    for fn in (update_modality, freeze_modality):
        with pytest.raises(ModalityVersionError, match="pin"):
            fn(root, "survey", schema_dir)


def test_malformed_pin_values_are_ignored(tmp_path):
    root = _project(tmp_path, SchemaVersions={"survey": "latest", "biometrics": "1.0.0", "x": 3})
    assert read_pins(root)[0] == {"biometrics": "1.0.0"}


def test_pin_after_import_never_raises(tmp_path, capsys, monkeypatch):
    import src.modality_versions as mv

    monkeypatch.setattr(mv, "pin_present_modalities", lambda root: (_ for _ in ()).throw(RuntimeError("boom")))
    pin_after_import(tmp_path)
    assert "boom" in capsys.readouterr().err


def test_hint_lines():
    lines = format_pending_hint([("survey", "1.1.0", "1.2.0")])
    assert "survey" in lines[0] and "1.2.0" in lines[0]
    assert any("modality-version update" in line and "freeze" in line for line in lines)
    assert format_pending_hint([]) == []


def test_project_schema_accepts_the_new_keys_and_rejects_bad_values():
    schema = json.loads((REPO / "app" / "schemas" / "stable" / "project.schema.json").read_text())
    base = {"Metadata": {"SchemaVersion": "1.0.0", "CreationDate": "2026-10-16"},
            "Sessions": [], "TaskDefinitions": {}}
    jsonschema.Draft7Validator(schema).validate({**base, "SchemaVersions": {"survey": "1.1.1"},
                                                  "SchemaVersionsAcknowledged": {"survey": "1.1.1"}})
    assert list(jsonschema.Draft7Validator(schema).iter_errors({**base, "SchemaVersions": {"survey": "latest"}}))
    assert schema["version"] == "1.0.0"
```

- [ ] **Step 2: Run to verify failure**

Run: `PRISM_SKIP_VENV_CHECK=1 python3 -m pytest -q tests/test_modality_version_pins.py`
Expected: FAIL (ImportError: new names).

- [ ] **Step 3: Implement**

Append to `src/modality_versions.py` (add `import os, sys, tempfile` at the top):

```python
def _write_pins(project_root, pins: dict[str, str], acknowledged: dict[str, str]) -> None:
    data = _read_project(project_root)
    if data is None:
        raise ModalityVersionError(f"no readable project.json in {project_root}")
    data["SchemaVersions"] = dict(sorted(pins.items()))
    if acknowledged:
        data["SchemaVersionsAcknowledged"] = dict(sorted(acknowledged.items()))
    else:
        data.pop("SchemaVersionsAcknowledged", None)
    path = Path(project_root) / "project.json"
    fd, tmp = tempfile.mkstemp(dir=path.parent, prefix=".project.json.")
    with os.fdopen(fd, "w", encoding="utf-8") as fh:
        fh.write(json.dumps(data, indent=2, ensure_ascii=False) + "\n")
    os.replace(tmp, path)


def present_modalities(project_root, schema_dir=None) -> list[str]:
    root = Path(project_root)
    found = []
    for name in modality_names(schema_dir):
        folders = [*root.glob(f"sub-*/{name}"), *root.glob(f"sub-*/ses-*/{name}")]
        has_files = any(f.is_dir() and any(f.iterdir()) for f in folders)
        if name == "events":  # events live next to other data, not in their own folder
            has_files = has_files or any(root.glob("sub-*/*/*_events.*")) or any(
                root.glob("sub-*/ses-*/*/*_events.*")
            )
        if has_files:
            found.append(name)
    return found


def pin_modalities(project_root, names, schema_dir=None) -> dict[str, str]:
    """Pin the current version of each named, not yet pinned modality; returns the new pins."""
    pins, acknowledged = read_pins(project_root)
    new = {n: current_version(n, schema_dir) for n in names if n not in pins}
    if new:
        _write_pins(project_root, {**pins, **new}, acknowledged)
    return new


def pin_present_modalities(project_root, schema_dir=None) -> dict[str, str]:
    if _read_project(project_root) is None:
        return {}
    return pin_modalities(project_root, present_modalities(project_root, schema_dir), schema_dir)


def pending_updates(project_root, schema_dir=None) -> list[tuple[str, str, str]]:
    pins, acknowledged = read_pins(project_root)
    out = []
    for name, pinned in sorted(pins.items()):
        try:
            latest = current_version(name, schema_dir)
        except ModalityVersionError:
            continue
        if parse_version(latest) > parse_version(pinned) and acknowledged.get(name) != latest:
            out.append((name, pinned, latest))
    return out


def _require_pinned(name: str, pins: dict[str, str]) -> None:
    if name not in pins:
        raise ModalityVersionError(
            f"'{name}' is not pinned in this project; pin it first: modality-version pin <project> {name}"
        )


def update_modality(project_root, name: str, schema_dir=None) -> str:
    pins, acknowledged = read_pins(project_root)
    _require_pinned(name, pins)
    latest = current_version(name, schema_dir)
    pins[name] = acknowledged[name] = latest
    _write_pins(project_root, pins, acknowledged)
    return latest


def freeze_modality(project_root, name: str, schema_dir=None) -> str:
    pins, acknowledged = read_pins(project_root)
    _require_pinned(name, pins)
    acknowledged[name] = current_version(name, schema_dir)
    _write_pins(project_root, pins, acknowledged)
    return pins[name]


def pin_after_import(output_root) -> None:
    """Pin modalities a conversion just wrote; a problem here must never fail the conversion."""
    try:
        new = pin_present_modalities(output_root)
    except Exception as exc:  # noqa: BLE001 - pinning is best effort
        print(f"Warning: could not record modality versions in project.json: {exc}", file=sys.stderr)
        return
    for name, version in new.items():
        print(f"Pinned {name} schema version {version} in project.json", file=sys.stderr)


def format_pending_hint(pending) -> list[str]:
    lines = [
        f"A newer {name} schema is available: {latest} (this project uses {pinned})."
        for name, pinned, latest in pending
    ]
    if lines:
        lines.append(
            "Decide with: prism_tools modality-version update <project> <name> | freeze <project> <name>"
        )
    return lines
```
Add to `app/schemas/stable/project.schema.json` `properties` (keep `additionalProperties: false`, do not touch `version`):

```json
"SchemaVersions": {
  "type": "object",
  "description": "Schema version each modality is validated against in this project (written when the modality is first imported).",
  "patternProperties": {"^[a-z][a-z0-9]*$": {"type": "string", "pattern": "^\\d+\\.\\d+\\.\\d+$"}},
  "additionalProperties": false
},
"SchemaVersionsAcknowledged": {
  "type": "object",
  "description": "Latest schema version per modality the user has already been told about (so a newer version is announced once).",
  "patternProperties": {"^[a-z][a-z0-9]*$": {"type": "string", "pattern": "^\\d+\\.\\d+\\.\\d+$"}},
  "additionalProperties": false
}
```

- [ ] **Step 4: Run to verify pass**

Run: `PRISM_SKIP_VENV_CHECK=1 python3 -m pytest -q tests/test_modality_version_pins.py tests/test_modality_versions.py tests/test_runner_modality_versions.py` and the project-schema tests `PRISM_SKIP_VENV_CHECK=1 python3 -m pytest -q -k "project_schema or project_json"`.
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add src/modality_versions.py app/schemas/stable/project.schema.json tests/test_modality_version_pins.py
git commit -m "feat(schemas): pins in project.json with a told-once update/freeze decision

Co-Authored-By: Claude Sonnet 5.5 <noreply@anthropic.com>"
```

---

### Task 4: `prism_tools modality-version` command

**Files:**
- Create: `app/src/cli/commands/modality_version.py`
- Modify: `app/src/cli/parser.py` (after the `modality` parser, ~line 1693), `app/src/cli/entrypoint.py` (import ~line 108, dispatch table ~line 145)
- Modify: `tests/test_cli_dispatch_routing.py` (rows)
- Test: `tests/test_cli_modality_version.py`

**Interfaces:**
- Consumes: Task 1 and 3 functions.
- Produces: commands `modality-version status <project>`, `list [name]`, `pin <project> [names...]`, `update <project> <name>`, `freeze <project> <name>`, each with `--json`; handlers `cmd_modality_version_status|list|pin|update|freeze(args)`. JSON contract: `{"success": true, ...}` or `{"success": false, "error": "..."}` with exit 1.

- [ ] **Step 1: Write the failing tests** `tests/test_cli_modality_version.py` (mirror the style of `tests/test_cli_modality.py`: `APP_ROOT` on `sys.path`, `SimpleNamespace` args, `build_prism_tools_parsers(APP_ROOT)`):

```python
import json
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

APP_ROOT = Path(__file__).resolve().parents[1] / "app"
if str(APP_ROOT) not in sys.path:
    sys.path.insert(0, str(APP_ROOT))

import src.cli.commands.modality_version as cmds  # noqa: E402
from src.cli.parser import build_prism_tools_parsers  # noqa: E402


@pytest.fixture
def project(tmp_path: Path) -> Path:
    (tmp_path / "project.json").write_text(json.dumps({"Metadata": {"SchemaVersion": "1.0.0"}}))
    survey = tmp_path / "sub-01" / "survey"
    survey.mkdir(parents=True)
    (survey / "sub-01_task-a_survey.tsv").write_text("x")
    return tmp_path


def _args(project, **over):
    values = dict(project=str(project), names=[], name=None, json=False)
    values.update(over)
    return SimpleNamespace(**values)


def test_parser_accepts_the_commands():
    parser, parsers = build_prism_tools_parsers(APP_ROOT)
    a = parser.parse_args(["modality-version", "update", "/p", "survey"])
    assert (a.command, a.action, a.project, a.name) == ("modality-version", "update", "/p", "survey")
    a = parser.parse_args(["modality-version", "pin", "/p", "survey", "physio"])
    assert a.names == ["survey", "physio"]
    assert "modality-version" in parsers


def test_pin_with_no_names_pins_what_is_present(project, capsys):
    cmds.cmd_modality_version_pin(_args(project, json=True))
    out = json.loads(capsys.readouterr().out)
    assert out["success"] and "survey" in out["pinned"]
    assert "survey" in json.loads((project / "project.json").read_text())["SchemaVersions"]


def test_status_lists_pins_and_pending(project, capsys):
    cmds.cmd_modality_version_pin(_args(project))
    capsys.readouterr()
    cmds.cmd_modality_version_status(_args(project, json=True))
    out = json.loads(capsys.readouterr().out)
    assert out["success"] and "survey" in out["pins"] and out["pending"] == []


def test_update_unpinned_modality_exits_1_with_json_error(project, capsys):
    with pytest.raises(SystemExit) as exc:
        cmds.cmd_modality_version_update(_args(project, name="survey", json=True))
    assert exc.value.code == 1
    assert json.loads(capsys.readouterr().out)["success"] is False


def test_list_shows_versions_of_a_modality(capsys):
    cmds.cmd_modality_version_list(SimpleNamespace(name="survey", json=False))
    assert "survey" in capsys.readouterr().out


def test_unknown_modality_in_list_exits_1(capsys):
    with pytest.raises(SystemExit) as exc:
        cmds.cmd_modality_version_list(SimpleNamespace(name="nope", json=True))
    assert exc.value.code == 1
```
In `tests/test_cli_dispatch_routing.py` add rows for the five actions following the existing tuple format; read `app/src/cli/entrypoint.py` lines ~100-180 first to see how the dispatch key is derived from `command`/`action` (hyphens become underscores in the existing keys such as the `modality_propose` one) and write the expected keys accordingly (e.g. `modality_version_update`).

- [ ] **Step 2: Run to verify failure**

Run: `PRISM_SKIP_VENV_CHECK=1 python3 -m pytest -q tests/test_cli_modality_version.py tests/test_cli_dispatch_routing.py`
Expected: FAIL (module missing).

- [ ] **Step 3: Implement**

`app/src/cli/commands/modality_version.py`:

```python
"""Per-modality schema version commands for prism_tools."""

from __future__ import annotations

import json
import sys

from src.modality_versions import (
    ModalityVersionError,
    available_versions,
    current_version,
    freeze_modality,
    modality_names,
    pending_updates,
    pin_modalities,
    pin_present_modalities,
    read_pins,
    update_modality,
)


def _emit(args, payload: dict, text: str) -> None:
    print(json.dumps(payload, ensure_ascii=False) if getattr(args, "json", False) else text)


def _fail(args, message: str) -> None:
    _emit(args, {"success": False, "error": message}, f"Error: {message}")
    sys.exit(1)


def cmd_modality_version_status(args) -> None:
    pins, _ = read_pins(args.project)
    pending = pending_updates(args.project)
    lines = [f"{n}: pinned {v}" for n, v in sorted(pins.items())] or ["No modality versions pinned."]
    lines += [f"{n}: {latest} is available (pinned {pinned})" for n, pinned, latest in pending]
    _emit(
        args,
        {"success": True, "pins": pins, "pending": [
            {"modality": n, "pinned": p, "latest": latest} for n, p, latest in pending]},
        "\n".join(lines),
    )


def cmd_modality_version_list(args) -> None:
    try:
        names = [args.name] if args.name else modality_names()
        versions = {n: available_versions(n) for n in names}
    except ModalityVersionError as exc:
        _fail(args, str(exc))
        return
    _emit(args, {"success": True, "versions": versions},
          "\n".join(f"{n}: {', '.join(v)} (latest {current_version(n)})" for n, v in versions.items()))


def cmd_modality_version_pin(args) -> None:
    try:
        new = pin_modalities(args.project, args.names) if args.names else pin_present_modalities(args.project)
    except ModalityVersionError as exc:
        _fail(args, str(exc))
        return
    _emit(args, {"success": True, "pinned": new},
          "\n".join(f"Pinned {n} {v}" for n, v in new.items()) or "Nothing to pin.")


def _change(args, fn, verb: str) -> None:
    try:
        version = fn(args.project, args.name)
    except ModalityVersionError as exc:
        _fail(args, str(exc))
        return
    _emit(args, {"success": True, "modality": args.name, "version": version},
          f"{verb} {args.name}: now {version}")


def cmd_modality_version_update(args) -> None:
    _change(args, update_modality, "Updated")


def cmd_modality_version_freeze(args) -> None:
    _change(args, freeze_modality, "Kept")
```
`parser.py` (after the `modality` parser): a `modality-version` subparser with `dest="action"`; actions `status` (positional `project`), `list` (optional positional `name`, `nargs="?"`), `pin` (`project`, `names` `nargs="*"`), `update` and `freeze` (`project`, `name`); every action gets `--json` (`action="store_true"`). `entrypoint.py`: import the five handlers and add them to the dispatch table using the key convention you confirmed above.

- [ ] **Step 4: Run to verify pass**

Run: `PRISM_SKIP_VENV_CHECK=1 python3 -m pytest -q tests/test_cli_modality_version.py tests/test_cli_dispatch_routing.py tests/test_cli_modality.py` and `python3 prism_tools.py modality-version list`.
Expected: PASS; the list command prints every modality with its versions.

- [ ] **Step 5: Commit**

```bash
git add app/src/cli tests/test_cli_modality_version.py tests/test_cli_dispatch_routing.py
git commit -m "feat(cli): prism_tools modality-version (status, list, pin, update, freeze)

Co-Authored-By: Claude Sonnet 5.5 <noreply@anthropic.com>"
```

---

### Task 5: Pin on import, and the one-line update hint

**Files:**
- Modify: `app/src/converters/survey.py` (`convert_survey_file_to_prism_dataset` ~line 790, `convert_survey_lsa_to_prism_dataset` ~line 851)
- Modify: `src/converters/biometrics.py` (`convert_biometrics_table_to_prism_dataset` ~line 163)
- Modify: `src/batch_convert.py` (`batch_convert_folder` ~line 1261)
- Modify: `app/src/cli/commands/environment.py` (`cmd_environment_convert` ~line 178)
- Modify: `app/prism.py` (after validation, print the hint)
- Test: `tests/test_pin_on_import.py`

**Interfaces:**
- Consumes: `pin_after_import(output_root)`, `pending_updates`, `format_pending_hint`.
- Produces: after a successful, non-dry-run conversion into `output_root`, `project.json` there has pins for the modalities present; `prism.py` prints the hint lines to stderr after a run when updates are pending.

- [ ] **Step 1: Write the failing tests** `tests/test_pin_on_import.py`. For each call site mirror the nearest existing test that already runs that function with a tiny fixture (find it with `grep -ln "convert_survey_file_to_prism_dataset" tests/*.py | head -3`, the same for `convert_survey_lsa_to_prism_dataset`, `convert_biometrics_table_to_prism_dataset`, `batch_convert_folder`, `cmd_environment_convert`) and assert via a recorder:

```python
import pytest

import src.modality_versions as mv


@pytest.fixture
def pinned_roots(monkeypatch):
    calls = []
    monkeypatch.setattr(mv, "pin_after_import", lambda root: calls.append(str(root)))
    return calls
```
One test per call site: run the existing fixture conversion with `output_root` (or `output_folder`) = tmp dir, then `assert pinned_roots == [str(output_root)]`; one `dry_run=True` test for survey asserting `pinned_roots == []`; one failing-conversion test per site is NOT required (the call sits after the success path). Add one end-to-end test with the real function: a tmp project with `project.json` and a `sub-01/survey/...tsv` file, then `mv.pin_after_import(root)` → `read_pins(root)[0]["survey"]` equals `current_version("survey")`.
Add `tests/test_prism_pending_hint.py`: build a tmp project pinned at a version lower than current (write `SchemaVersions: {"survey": "0.0.1"}`) and run `python app/prism.py <project> --no-bids` as a subprocess (`sys.executable`, `PRISM_SKIP_VENV_CHECK=1`); assert stderr contains "A newer survey schema is available" and the exit code is unaffected by the hint (same as a run without the pin ignoring pins: just assert the hint is present, and that a project pinned at the current version prints no hint).

- [ ] **Step 2: Run to verify failure**

Run: `PRISM_SKIP_VENV_CHECK=1 python3 -m pytest -q tests/test_pin_on_import.py tests/test_prism_pending_hint.py`
Expected: FAIL (recorders stay empty; no hint).

- [ ] **Step 3: Implement**

At each call site import lazily and call after the work succeeded and not in a dry run:

```python
        from src.modality_versions import pin_after_import

        pin_after_import(output_root)
```
Placement: in `convert_survey_file_to_prism_dataset` and `convert_survey_lsa_to_prism_dataset` after the `*_impl` call returns its result and only `if not dry_run` (store the result in a variable, pin, return it); in `convert_biometrics_table_to_prism_dataset` right before its final return (read the function end first); in `batch_convert_folder` after the loop, `if not dry_run`, with `output_folder`; in `cmd_environment_convert` when `exit_code == 0`, with the resolved output project path (read `_resolve_environment_convert_payload` to find the argument that names the project/output root, usually `args.project` or `args.output`; if the conversion writes into a project folder, pin that folder, otherwise skip with a code comment saying why).
In `app/prism.py`, after the validation block and before the process exits (find where the summary is printed; the hint goes to stderr so `--json` stdout stays clean):

```python
        from src.modality_versions import format_pending_hint, pending_updates

        for line in format_pending_hint(pending_updates(args.dataset)):
            print(line, file=sys.stderr)
```

- [ ] **Step 4: Run to verify pass**

Run: `PRISM_SKIP_VENV_CHECK=1 python3 -m pytest -q tests/test_pin_on_import.py tests/test_prism_pending_hint.py` and the existing tests of the touched converters: `PRISM_SKIP_VENV_CHECK=1 python3 -m pytest -q -k "survey_convert or biometrics_convert or batch_convert or environment_convert"`.
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add app/src src app/prism.py tests/test_pin_on_import.py tests/test_prism_pending_hint.py
git commit -m "feat(schemas): pin modality versions on import; one-line update hint

Co-Authored-By: Claude Sonnet 5.5 <noreply@anthropic.com>"
```

---

### Task 6: CI guard for frozen versions

**Files:**
- Create: `scripts/ci/check_schema_versions.py`
- Modify: `.github/workflows/ci.yml` (new job)
- Test: `tests/test_check_schema_versions.py`

**Interfaces:**
- Produces: `check(changes, read_base, read_head, exists_head, modalities) -> list[str]` (pure, error messages) where `changes` is a list of `(status, path)` from `git diff --name-status`, `read_base(path)` / `read_head(path)` return file text or `None`, `exists_head(path)` returns bool, `modalities` is the set of modality names; `main(argv)` runs it on `<base> <head>` refs and exits 1 with the messages on errors.

- [ ] **Step 1: Write the failing tests** `tests/test_check_schema_versions.py` (load the script with `importlib.util` like `tests/test_flag_restricted_schema_changes.py` does):

```python
import importlib.util
import json
from pathlib import Path

SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "ci" / "check_schema_versions.py"
spec = importlib.util.spec_from_file_location("check_schema_versions", SCRIPT)
mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mod)

STABLE = "app/schemas/stable/survey.schema.json"
ARCH = "app/schemas/archive/survey/1.0.0.schema.json"


def _doc(version, extra=0):
    return json.dumps({"version": version, "x": extra})


def _run(changes, base=None, head=None):
    base, head = base or {}, head or {}
    return mod.check(changes, base.get, head.get, lambda p: p in head, {"survey"})


def test_new_modality_without_archive_passes():
    assert _run([("A", STABLE)], head={STABLE: _doc("1.0.0")}) == []


def test_correct_release_passes():
    errors = _run(
        [("M", STABLE), ("A", ARCH)],
        base={STABLE: _doc("1.0.0")},
        head={STABLE: _doc("1.1.0", 1), ARCH: _doc("1.0.0")},
    )
    assert errors == []


def test_changed_content_without_a_version_bump_fails():
    errors = _run([("M", STABLE)], base={STABLE: _doc("1.0.0")}, head={STABLE: _doc("1.0.0", 1)})
    assert any("version" in e for e in errors)


def test_bump_without_archiving_the_previous_version_fails():
    errors = _run([("M", STABLE)], base={STABLE: _doc("1.0.0")}, head={STABLE: _doc("1.1.0")})
    assert any("1.0.0" in e and "archive" in e for e in errors)


def test_archived_copy_must_equal_the_previous_stable_file():
    errors = _run(
        [("M", STABLE), ("A", ARCH)],
        base={STABLE: _doc("1.0.0")},
        head={STABLE: _doc("1.1.0"), ARCH: _doc("1.0.0", 99)},
    )
    assert any("differs" in e for e in errors)


def test_editing_or_deleting_an_archive_file_fails():
    for status in ("M", "D"):
        assert _run([(status, ARCH)], base={ARCH: _doc("1.0.0")}, head={ARCH: _doc("1.0.0", 1)})


def test_unrelated_changes_pass():
    assert _run([("M", "docs/index.rst"), ("M", "app/schemas/stable/project.schema.json")]) == []
```

- [ ] **Step 2: Run to verify failure**

Run: `PRISM_SKIP_VENV_CHECK=1 python3 -m pytest -q tests/test_check_schema_versions.py`
Expected: FAIL (script missing).

- [ ] **Step 3: Implement** `scripts/ci/check_schema_versions.py`

```python
"""Fail when a frozen modality schema version is edited or a version is released wrongly.

Usage: check_schema_versions.py <base_ref> <head_ref>
Rules (modality schemas only; project/entities/dataset_description are not versioned this way):
- files under app/schemas/archive/ are frozen: never modified or deleted;
- a changed stable schema must carry a bumped `version`;
- a bumped version needs the previous version archived, equal to the previous stable file.
"""

from __future__ import annotations

import json
import subprocess
import sys

STABLE = "app/schemas/stable/"
ARCHIVE = "app/schemas/archive/"
SUFFIX = ".schema.json"


def _version(text: str | None) -> str | None:
    try:
        return json.loads(text)["version"] if text else None
    except (ValueError, KeyError, TypeError):
        return None


def _same(a: str | None, b: str | None) -> bool:
    try:
        return json.loads(a) == json.loads(b)
    except (ValueError, TypeError):
        return False


def check(changes, read_base, read_head, exists_head, modalities) -> list[str]:
    errors: list[str] = []
    for status, path in changes:
        if path.startswith(ARCHIVE) and status in ("M", "D"):
            errors.append(f"{path}: archived versions are frozen and must not be edited or deleted")
            continue
        if not (path.startswith(STABLE) and path.endswith(SUFFIX) and status == "M"):
            continue
        name = path[len(STABLE) : -len(SUFFIX)]
        if name not in modalities:
            continue
        old, new = _version(read_base(path)), _version(read_head(path))
        if old is not None and old == new:
            errors.append(f"{path}: content changed but `version` is still {old}; bump it")
        elif old is not None and new is not None:
            archived = f"{ARCHIVE}{name}/{old}{SUFFIX}"
            if not exists_head(archived):
                errors.append(f"{path}: version {old} must be copied to {archived} before it changes (archive)")
            elif not _same(read_head(archived), read_base(path)):
                errors.append(f"{archived}: differs from the previous {path}; archive an exact copy")
    return errors


def _git_show(ref: str, path: str) -> str | None:
    result = subprocess.run(["git", "show", f"{ref}:{path}"], capture_output=True, text=True)
    return result.stdout if result.returncode == 0 else None


def main(argv: list[str]) -> int:
    base, head = argv[1], argv[2]
    diff = subprocess.run(
        ["git", "diff", "--name-status", f"{base}...{head}"], capture_output=True, text=True, check=True
    ).stdout
    changes = [tuple(line.split("\t", 1)) for line in diff.splitlines() if "\t" in line]
    entities = _git_show(head, "app/schemas/stable/entities.schema.json")
    modalities = set(json.loads(entities)["modalities"]) if entities else set()
    errors = check(
        changes,
        lambda p: _git_show(base, p),
        lambda p: _git_show(head, p),
        lambda p: _git_show(head, p) is not None,
        modalities,
    )
    for message in errors:
        print(f"ERROR: {message}")
    return 1 if errors else 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
```
CI: add to `.github/workflows/ci.yml`, as a new job (same checkout pin and conventions as the `scope` job already there):

```yaml
  schema-versions:
    name: Modality schema versions
    if: github.event_name == 'pull_request'
    runs-on: ubuntu-latest
    steps:
      - name: Checkout
        uses: actions/checkout@3d3c42e5aac5ba805825da76410c181273ba90b1 # v7.0.1
        with:
          fetch-depth: 0

      - name: Check frozen modality schema versions
        env:
          BASE_BRANCH: ${{ github.base_ref }}
        run: python3 scripts/ci/check_schema_versions.py "origin/$BASE_BRANCH" HEAD
```
Run the script once against the real repo to prove it passes on a no-op range: `python3 scripts/ci/check_schema_versions.py HEAD HEAD` (exit 0).

- [ ] **Step 4: Run to verify pass**

Run: `PRISM_SKIP_VENV_CHECK=1 python3 -m pytest -q tests/test_check_schema_versions.py` and `python3 tests/verify_repo.py --check github-actions --no-fix`.
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add scripts/ci/check_schema_versions.py tests/test_check_schema_versions.py .github/workflows/ci.yml
git commit -m "ci: guard frozen modality schema versions

Co-Authored-By: Claude Sonnet 5.5 <noreply@anthropic.com>"
```

---

### Task 7: Documentation and spec clarifications

**Files:**
- Modify: `docs/SCHEMA_VERSIONING.md`, `docs/CLI_REFERENCE.md`, `docs/MODALITY_WORKFLOW.md`, `docs/superpowers/specs/2026-10-16-modality-versioning-design.md`
- Test: `tests/test_docs_modality_versions.py`

- [ ] **Step 1: Write the failing test** `tests/test_docs_modality_versions.py`

```python
from pathlib import Path

DOCS = Path(__file__).resolve().parents[1] / "docs"


def test_schema_versioning_documents_per_modality_versions():
    text = (DOCS / "SCHEMA_VERSIONING.md").read_text(encoding="utf-8")
    for needle in ("--modality-version", "SchemaVersions", "modality-version update",
                   "modality-version freeze", "archive/", "1.0.0"):
        assert needle in text, needle


def test_cli_reference_lists_the_commands():
    text = (DOCS / "CLI_REFERENCE.md").read_text(encoding="utf-8")
    assert "modality-version" in text and "--modality-version" in text


def test_workflow_tells_maintainers_how_to_release_a_modality_version():
    text = (DOCS / "MODALITY_WORKFLOW.md").read_text(encoding="utf-8")
    assert "archive" in text and "bump" in text
```

- [ ] **Step 2: Run to verify failure**

Run: `PRISM_SKIP_VENV_CHECK=1 python3 -m pytest -q tests/test_docs_modality_versions.py`
Expected: FAIL.

- [ ] **Step 3: Write the docs** (accurate to what Tasks 1-6 implemented; do not describe the Studio notice, say it is "coming")

- `docs/SCHEMA_VERSIONING.md`: new top section "Per-modality versions" before the legacy table: each modality has its own `major.minor.patch` version (a proposal starts at `1.0.0`); defaults to the latest; the pin in `project.json` (`SchemaVersions`, written when a modality is first imported; `SchemaVersionsAcknowledged`; the told-once decision: `prism_tools modality-version update <project> <name>` or `freeze <project> <name>`; `status`, `list`, `pin` for older projects); the override `prism.py <dataset> --modality-version survey=1.0.3` (repeatable) and precedence (flag, then pin, then latest); pins apply to the `stable` base, not to an explicit legacy `--schema-version`; an unknown version is an error listing the available ones; validation never writes to `project.json`; the report records the version used per modality and its source; maintainers: how to release a new modality version (bump `version` and the `$id` suffix in `app/schemas/stable/<name>.schema.json`, first copy the previous file unchanged to `app/schemas/archive/<name>/<old version>.schema.json`; CI check `Modality schema versions` enforces it); versions older than the first archive entry cannot be pinned; legacy `v0.1`/`v0.2` bundles stay as described below.
- `docs/CLI_REFERENCE.md`: a `modality-version` section (five actions with their arguments and `--json`) and the `--modality-version` flag under the validator options.
- `docs/MODALITY_WORKFLOW.md`: in the maintainer steps add: a new modality is registered at version `1.0.0`; later changes release a new version (bump, archive the previous file) as described in `SCHEMA_VERSIONING.md`.
- Spec: add a "Clarifications from the plan" section with the four points listed at the top of this plan.
- Build: `python3 -m sphinx -q -W -b html docs "$TMPDIR/html"` prints nothing.

- [ ] **Step 4: Run to verify pass**

Run: `PRISM_SKIP_VENV_CHECK=1 python3 -m pytest -q tests/test_docs_modality_versions.py tests/test_docs_example_paths.py tests/test_docs_landing_modality.py` and the Sphinx build above.
Expected: PASS, no Sphinx output.

- [ ] **Step 5: Commit**

```bash
git add docs tests/test_docs_modality_versions.py
git commit -m "docs: per-modality schema versions, pins and the release process

Co-Authored-By: Claude Sonnet 5.5 <noreply@anthropic.com>"
```

---

### Task 8: Full verification, audit, hand-over

**Files:** none new.

- [ ] **Step 1: Whole suite and repo checks**

Run (background, about 3 minutes): `PRISM_SKIP_VENV_CHECK=1 python3 -m pytest -q -p no:cacheprovider --ignore=tests/e2e`
Expected: PASS apart from the three known `test_lsa_import_integration.py` failures if they reappear (report exact counts).
Run: `python3 tests/verify_repo.py --no-fix` — Expected: all checks passed (includes `dual-tree-drift`: `src/modality_versions.py` exists only under `src/`). Delete the report file it writes.

- [ ] **Step 2: Try it by hand**

In a scratch copy of a small project (a folder with `project.json` and one survey file under `sub-01/survey/`):

```bash
python3 prism_tools.py modality-version pin <project>
python3 prism_tools.py modality-version status <project>
python3 app/prism.py <project> --no-bids --modality-version survey=<current version>
python3 app/prism.py <project> --no-bids --modality-version survey=9.9.9   # one clear error
```
Then simulate a release on a scratch copy of `app/schemas` (copy the current survey schema to `archive/survey/<old>.schema.json`, bump `stable` by a minor version) and confirm: the hint appears once on stderr, `freeze` silences it, `update` moves the pin, and a run with the old pin validates against the archived schema (the report shows the version and the source `project.json`). Never edit the real `app/schemas` for this.

- [ ] **Step 3: Audit and merge**

Invoke `/ponytail:ponytail-audit` on the branch, apply what is worth it, re-run Step 1, then ask the user before merging into `main` and pushing.

- [ ] **Step 4: Hand over**

Report: test counts, anything skipped, the follow-up plan still to write (Studio: a notice with "Update" / "Keep current version" buttons on the project page that call `update_modality` / `freeze_modality`, plus an optional per-modality version field in the validator's advanced options), and that the CI job `Modality schema versions` is new and not yet a required check in branch protection.
