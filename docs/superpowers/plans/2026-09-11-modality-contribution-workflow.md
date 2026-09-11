# Modality Contribution Workflow Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Let an outside contributor propose a brand-new PRISM modality (e.g. skin temperature) or a new survey instrument template, get it automatically checked for structural validity, and land it as a reviewable PR — without repository extraction, and without hand-authoring JSON Schema for the common case.

**Architecture:** Everything lands in the existing `prism-studio` repo (repository extraction is phase 2, deferred). A shared library module (`src/modality_contribution.py`) knows how to build and validate a minimal PRISM dataset fixture for a modality; two new `tests/verify_repo.py` checks gate PRs on schema conventions and on `index.json` freshness; a GitHub Issue Form plus a triggered Action reuse that same library module to turn a structured proposal into a draft PR automatically.

**Tech Stack:** Python 3.10, pytest, `jsonschema` (already a dependency), GitHub Actions, GitHub CLI (`gh`, preinstalled on `ubuntu-latest` runners — no new third-party PR-creation action).

**Spec:** `docs/superpowers/specs/2026-09-11-modality-contribution-workflow-design.md`

## Global Constraints

- Phase 1 only. No repository extraction, no git submodule, no new hosted GUI (per spec's "Phase 2 (deferred)" section).
- `entities.schema.json`, `project.schema.json`, `dataset_description.schema.json`, `instrument-registry.schema.json`, `recipe.survey.schema.json`, `tool-limesurvey.schema.json` are **not** community-editable; PRs touching them get flagged for core-maintainer review, never auto-rejected (spec §1.1).
- CI reuses the existing validator (`validate_dataset` in `app/src/runner.py`) rather than reimplementing validation logic (spec §1.3).
- Any GitHub Actions step handling issue-submitted text must pass it via `env:`, never interpolate `${{ github.event.issue.body }}` (or any issue field) directly into a `run:` shell block — this repo's nightly `actions-security` check (zizmor) gates on exactly this pattern (spec §1.5 "Security").
- New workflow steps follow this repo's existing action-pinning convention: version tags (`@v7`, `@v5`), matching `ci.yml`/`build.yml` — not blanket SHA-pinning (that's a separate, not-yet-enforced hardening decision per `check_actions_security`'s explicit exclusion of `unpinned-uses` findings).
- New `verify_repo.py` checks follow the existing pattern exactly: a `check_<name>(repo_path, fix=False)` function using `print_header`/`print_success`/`print_error` (from `tests/verify_repo.py`), registered in the `CHECKS` dict, blocking by default (only added to `NON_BLOCKING_WARNING_CHECKS` if a later task says so — none do here).

## Correction to the spec during planning

Spec §1.3 describes the meta-schema check as verifying "the `Study`/`Technical` structural split already used by `survey.schema.json`." Checking all six existing modality schemas shows this split is **not** universal: `eyetracking.schema.json` and `events.schema.json` use a flat property list with no `Study`/`Technical` wrapper at all. A meta-schema requiring `Study`/`Technical` would reject two of the six modalities that already ship. Task 2 below instead checks what genuinely is universal across all six: valid JSON Schema draft-07, and a `$schema`/`$id`/`version`/`title`/`description`/`type`/`properties`/`required` envelope where `required` is a subset of `properties` keys and `$id` ends in the same version as the `version` field. This is the same intent (catch a structurally broken submission) implemented against the real, verified constraint instead of an overgeneralization from one example.

Spec §1.5 describes the Issue Form fields as "repeatable." GitHub Issue Forms (YAML) have no native repeating-group widget — only fixed inputs, textareas, dropdowns, and checkboxes. Task 6 below uses one `textarea` field with a documented one-line-per-field syntax (`name | datatype | required | unit | extension`), parsed by Task 7's parser. Same contributor-facing outcome (list as many fields as needed in one form submission), implemented with the widget GitHub actually provides.

**A more significant correction**, found by actually running the validator against a hand-built "new modality" fixture before writing Task 8's tests: spec §1.2/§1.3 implicitly assume the dataset-level `prism-validator` check works the same way for a brand-new modality as for a new template under an existing modality. It does not. `entity_rules.py` derives the recognized suffix/extension grammar from `app/schemas/stable/entities.schema.json`, and `app/src/schema_manager.py:92-100` hardcodes the list of modalities it will even attempt to load a schema for. Both are on the "not community-editable, core-maintainer-only" list in spec §1.1 — so a genuinely new modality (e.g. `skintemp`) cannot be recognized by `validate_dataset` at all until a maintainer does that registration. Confirmed directly:

```
$ python3 -c "... build a sub-01/skintemp/... dataset ... validate_dataset(tmp) ..."
('ERROR', "dataset_description.json schema error: Name: 'x' is too short", ...)
('ERROR', 'No subjects found in dataset. Did you point the validator at the dataset root?', ...)
```

The subject isn't even recognized — an unregistered modality directory makes the whole `sub-01/` invisible to the scanner, not just the one file. So for a **brand-new modality**, the bot's automatic pre-check (Task 8) validates the draft schema's structural conventions and validates the generated example sidecar against that draft schema directly via `jsonschema.validate` — it does not and cannot run the full dataset-level `prism-validator` pipeline pre-registration. The minimal dataset fixture is still generated and included in the PR, but as a **ready-to-run fixture for the maintainer to validate once they've done the entities.schema.json/schema_manager.py registration**, not as something the bot itself proves passes. Task 5's `write_minimal_dataset` test against the `survey` modality remains valid and unaffected — `survey` is already registered, so that path (a **new template** under an **existing** modality) genuinely does validate end-to-end today, which is exactly the common case (spec §1.5's "Scope of the form" already limits the Issue Form to new modalities; new templates go through the existing Excel/Template-Editor path and hit this already-working case).

---

### Task 1: Remove the empty `survey_library` bundle entry (unrelated cleanup)

Both PyInstaller specs bundle a `survey_library` directory containing zero files (found during spec verification, unrelated to this feature, flagged for a separate commit).

**Files:**
- Modify: `PrismStudio.spec:8`
- Modify: `PrismValidator.spec:8`

**Interfaces:** None (no code consumes this).

- [ ] **Step 1: Confirm nothing references `survey_library`**

Run: `grep -rn "survey_library" --include="*.py" src app *.py`
Expected: no output (already confirmed during spec verification; re-confirm before editing since the tree may have changed).

- [ ] **Step 2: Remove the entry from both spec files**

In `PrismStudio.spec:8` and `PrismValidator.spec:8`, remove `('survey_library', 'survey_library'), ` from the `datas=[...]` list in each file. Leave every other entry unchanged.

- [ ] **Step 3: Verify the spec files still parse**

Run: `python3 -c "import ast; ast.parse(open('PrismStudio.spec').read()); ast.parse(open('PrismValidator.spec').read()); print('OK')"`
Expected: `OK`

- [ ] **Step 4: Commit**

```bash
git add PrismStudio.spec PrismValidator.spec
git commit -m "chore: remove empty survey_library bundle entry from PyInstaller specs

Co-Authored-By: Claude Sonnet 5 <noreply@anthropic.com>"
```

---

### Task 2: Modality schema convention check

A new `verify_repo.py` check that validates every community-extensible modality schema (survey, biometrics, environment, physio, eyetracking, events) is well-formed JSON Schema draft-07 with a consistent envelope — the CI gate a submitted `<modality>.schema.json` must pass (spec §1.3, corrected per "Correction to the spec" above).

**Files:**
- Modify: `tests/verify_repo.py` (add function + `CHECKS` entry)
- Create: `tests/test_verify_repo_modality_schema_conventions.py`

**Interfaces:**
- Produces: `check_modality_schema_conventions(repo_path, fix=False) -> None` in `tests/verify_repo.py`, called the same way every other check is called (see `run_check` at `tests/verify_repo.py:2619`). Reports failures via `print_error` (increments `CURRENT_CHECK_ERRORS`), successes via `print_success`. Registered in `CHECKS` under the key `"modality-schema-conventions"`.
- Consumes: `COMMUNITY_MODALITY_SCHEMAS = {"survey", "biometrics", "environment", "physio", "eyetracking", "events"}` — a new module-level constant in `tests/verify_repo.py`, placed near `CHECKS_SUPPORT_FIX` (around line 2558). Task 3 and Task 4 also reference this constant (Task 3 uses its complement as the restricted-file list).

- [ ] **Step 1: Write the failing tests**

Create `tests/test_verify_repo_modality_schema_conventions.py`:

```python
import json
from pathlib import Path


def _load_verify_repo_module():
    import importlib.util

    module_path = Path(__file__).with_name("verify_repo.py")
    spec = importlib.util.spec_from_file_location("verify_repo", module_path)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def _write_schema(schema_dir: Path, name: str, schema: dict) -> None:
    schema_dir.mkdir(parents=True, exist_ok=True)
    (schema_dir / f"{name}.schema.json").write_text(
        json.dumps(schema), encoding="utf-8"
    )


def _valid_schema(name: str) -> dict:
    return {
        "$schema": "http://json-schema.org/draft-07/schema#",
        "$id": f"https://prism.org/schemas/{name}/v1.0.0",
        "version": "1.0.0",
        "title": name.title(),
        "description": f"Schema for {name}.",
        "type": "object",
        "properties": {"Metadata": {"type": "object"}},
        "required": ["Metadata"],
    }


def test_passes_for_well_formed_modality_schema(tmp_path: Path, capsys) -> None:
    verify_repo = _load_verify_repo_module()
    schema_dir = tmp_path / "app" / "schemas" / "stable"
    _write_schema(schema_dir, "survey", _valid_schema("survey"))

    verify_repo.check_modality_schema_conventions(str(tmp_path))
    output = capsys.readouterr().out

    assert "[✗]" not in output
    assert "follow PRISM conventions" in output


def test_flags_required_field_not_in_properties(tmp_path: Path, capsys) -> None:
    verify_repo = _load_verify_repo_module()
    schema_dir = tmp_path / "app" / "schemas" / "stable"
    bad_schema = _valid_schema("survey")
    bad_schema["required"] = ["Metadata", "Nonexistent"]
    _write_schema(schema_dir, "survey", bad_schema)

    verify_repo.check_modality_schema_conventions(str(tmp_path))
    output = capsys.readouterr().out

    assert "Nonexistent" in output
    assert "not declared in 'properties'" in output


def test_flags_id_version_mismatch(tmp_path: Path, capsys) -> None:
    verify_repo = _load_verify_repo_module()
    schema_dir = tmp_path / "app" / "schemas" / "stable"
    bad_schema = _valid_schema("survey")
    bad_schema["$id"] = "https://prism.org/schemas/survey/v1.0.0"
    bad_schema["version"] = "2.0.0"
    _write_schema(schema_dir, "survey", bad_schema)

    verify_repo.check_modality_schema_conventions(str(tmp_path))
    output = capsys.readouterr().out

    assert "does not match" in output


def test_flags_invalid_json_schema_draft(tmp_path: Path, capsys) -> None:
    verify_repo = _load_verify_repo_module()
    schema_dir = tmp_path / "app" / "schemas" / "stable"
    bad_schema = _valid_schema("survey")
    bad_schema["type"] = "not-a-real-type"
    _write_schema(schema_dir, "survey", bad_schema)

    verify_repo.check_modality_schema_conventions(str(tmp_path))
    output = capsys.readouterr().out

    assert "not a valid JSON Schema" in output


def test_ignores_app_internal_schemas(tmp_path: Path, capsys) -> None:
    verify_repo = _load_verify_repo_module()
    schema_dir = tmp_path / "app" / "schemas" / "stable"
    # entities.schema.json has no $id/version/Study-Technical envelope at all
    # and must never be flagged by this check -- it is not community-extensible.
    _write_schema(schema_dir, "entities", {"entityOrder": ["sub"]})

    verify_repo.check_modality_schema_conventions(str(tmp_path))
    output = capsys.readouterr().out

    assert "[✗]" not in output


def test_skipped_when_schema_dir_missing(tmp_path: Path, capsys) -> None:
    verify_repo = _load_verify_repo_module()

    verify_repo.check_modality_schema_conventions(str(tmp_path))
    output = capsys.readouterr().out

    assert "skipped" in output
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_verify_repo_modality_schema_conventions.py -v`
Expected: every test fails with `AttributeError: module 'verify_repo' has no attribute 'check_modality_schema_conventions'`

- [ ] **Step 3: Add the constant and the check function**

In `tests/verify_repo.py`, add near `CHECKS_SUPPORT_FIX` (line 2558):

```python
# Modality schemas contributors are expected to add to or extend via PR
# (spec: docs/superpowers/specs/2026-09-11-modality-contribution-workflow-design.md
# section 1.1). Every other file under app/schemas/stable/ defines app
# behavior (filename grammar, project/dataset-description structure) and
# is intentionally excluded here -- see check_community_schema_boundary.
COMMUNITY_MODALITY_SCHEMAS = {
    "survey",
    "biometrics",
    "environment",
    "physio",
    "eyetracking",
    "events",
}
```

Add the check function directly above the `CHECKS = {` dict (around line 2500, alongside `check_library_uniqueness`):

```python
def check_modality_schema_conventions(repo_path, fix=False):
    """Validate community-extensible modality schemas are well-formed.

    Checks only the schemas contributors are expected to touch
    (COMMUNITY_MODALITY_SCHEMAS) -- app-internal schemas like
    entities.schema.json have a different, unrelated shape and are
    deliberately not held to this envelope.
    """
    print_header("Checking Modality Schema Conventions")

    schema_dir = Path(repo_path) / "app" / "schemas" / "stable"
    if not schema_dir.is_dir():
        print_success(
            "Modality schema conventions check skipped (app/schemas/stable not found)."
        )
        return

    import jsonschema

    checked_any = False
    for name in sorted(COMMUNITY_MODALITY_SCHEMAS):
        schema_path = schema_dir / f"{name}.schema.json"
        if not schema_path.is_file():
            continue
        checked_any = True

        try:
            schema = json.loads(schema_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError as e:
            print_error(f"{schema_path.name}: not valid JSON ({e}).")
            continue

        for required_key in (
            "$schema",
            "$id",
            "version",
            "title",
            "description",
            "type",
            "properties",
            "required",
        ):
            if required_key not in schema:
                print_error(f"{schema_path.name}: missing top-level '{required_key}'.")

        if schema.get("type") != "object":
            print_error(
                f"{schema_path.name}: top-level 'type' must be 'object', "
                f"got {schema.get('type')!r}."
            )

        properties = schema.get("properties")
        required = schema.get("required")
        if isinstance(properties, dict) and isinstance(required, list):
            missing = [key for key in required if key not in properties]
            if missing:
                print_error(
                    f"{schema_path.name}: required field(s) "
                    f"{missing} not declared in 'properties'."
                )

        version = schema.get("version")
        schema_id = schema.get("$id")
        if isinstance(version, str) and isinstance(schema_id, str):
            if not schema_id.endswith(f"/v{version}"):
                print_error(
                    f"{schema_path.name}: '$id' ({schema_id}) does not match "
                    f"'version' ({version}); expected it to end with /v{version}."
                )

        try:
            jsonschema.Draft7Validator.check_schema(schema)
        except jsonschema.exceptions.SchemaError as e:
            print_error(f"{schema_path.name}: not a valid JSON Schema draft-07 ({e.message}).")

    if not checked_any:
        print_success(
            "Modality schema conventions check skipped (no community modality schemas found)."
        )
    elif CURRENT_CHECK_ERRORS == 0:
        print_success("All community modality schemas follow PRISM conventions.")
```

- [ ] **Step 4: Register the check**

In `tests/verify_repo.py`, add to the `CHECKS` dict (near `"library-uniqueness": check_library_uniqueness,`):

```python
    "modality-schema-conventions": check_modality_schema_conventions,
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `pytest tests/test_verify_repo_modality_schema_conventions.py -v`
Expected: all 7 tests PASS

- [ ] **Step 6: Run the check against the real repo**

Run: `python tests/verify_repo.py --check modality-schema-conventions --no-fix`
Expected: passes against the current `app/schemas/stable/*.schema.json` files (they already follow this envelope — verified during spec research).

- [ ] **Step 7: Commit**

```bash
git add tests/verify_repo.py tests/test_verify_repo_modality_schema_conventions.py
git commit -m "test: add modality schema conventions check

Co-Authored-By: Claude Sonnet 5 <noreply@anthropic.com>"
```

---

### Task 3: Community-schema-boundary flag script

A standalone diff-based script (not a `verify_repo.py` check, since `verify_repo.py` checks operate on a repo snapshot and this needs the PR's changed-files list) that flags — never blocks — PRs touching app-internal schema files, per spec §1.1's "requires core-maintainer review rather than the template-contribution path."

**Files:**
- Create: `scripts/ci/flag_restricted_schema_changes.py`
- Create: `tests/test_flag_restricted_schema_changes.py`

**Interfaces:**
- Produces: `find_restricted_changes(changed_files: list[str]) -> list[str]` — pure function, importable, returns the subset of `changed_files` that are restricted schema paths. `RESTRICTED_SCHEMA_FILES` module-level constant (the six app-internal schema filenames under `app/schemas/`, any version folder).
- Consumes: nothing from earlier tasks.

- [ ] **Step 1: Write the failing tests**

Create `tests/test_flag_restricted_schema_changes.py`:

```python
import importlib.util
from pathlib import Path


def _load_module():
    module_path = (
        Path(__file__).resolve().parent.parent
        / "scripts"
        / "ci"
        / "flag_restricted_schema_changes.py"
    )
    spec = importlib.util.spec_from_file_location(
        "flag_restricted_schema_changes", module_path
    )
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def test_flags_entities_schema_change():
    mod = _load_module()
    changed = ["app/schemas/stable/entities.schema.json", "README.md"]
    assert mod.find_restricted_changes(changed) == [
        "app/schemas/stable/entities.schema.json"
    ]


def test_flags_files_across_version_folders():
    mod = _load_module()
    changed = ["app/schemas/v0.2/project.schema.json"]
    assert mod.find_restricted_changes(changed) == [
        "app/schemas/v0.2/project.schema.json"
    ]


def test_does_not_flag_community_modality_schema():
    mod = _load_module()
    changed = ["app/schemas/stable/survey.schema.json"]
    assert mod.find_restricted_changes(changed) == []


def test_does_not_flag_unrelated_file():
    mod = _load_module()
    changed = ["official/library/survey/survey-new-instrument.json"]
    assert mod.find_restricted_changes(changed) == []


def test_empty_change_list_returns_empty():
    mod = _load_module()
    assert mod.find_restricted_changes([]) == []
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_flag_restricted_schema_changes.py -v`
Expected: `ModuleNotFoundError` / file-not-found errors from `_load_module` (the script doesn't exist yet)

- [ ] **Step 3: Write the script**

Create `scripts/ci/flag_restricted_schema_changes.py`:

```python
"""Flag pull requests that touch app-internal (non-community) schema files.

Used by .github/workflows/ci.yml on pull_request events. This is advisory,
not blocking (exit code is always 0): app-internal schemas (filename
grammar, project/dataset-description structure) can legitimately need
changes, they just need a core maintainer's eyes rather than the
template-contribution review path.

See docs/superpowers/specs/2026-09-11-modality-contribution-workflow-design.md
section 1.1.
"""

from __future__ import annotations

import os
import subprocess
import sys

RESTRICTED_SCHEMA_FILENAMES = {
    "entities.schema.json",
    "project.schema.json",
    "dataset_description.schema.json",
    "instrument-registry.schema.json",
    "recipe.survey.schema.json",
    "tool-limesurvey.schema.json",
}


def find_restricted_changes(changed_files: list[str]) -> list[str]:
    """Return the subset of changed_files that are restricted schema paths."""
    return [
        path
        for path in changed_files
        if path.startswith("app/schemas/")
        and os.path.basename(path) in RESTRICTED_SCHEMA_FILENAMES
    ]


def get_changed_files(base_ref: str, head_ref: str) -> list[str]:
    """List files changed between base_ref and head_ref via git diff."""
    result = subprocess.run(
        ["git", "diff", "--name-only", f"{base_ref}...{head_ref}"],
        capture_output=True,
        text=True,
        check=True,
    )
    return [line for line in result.stdout.splitlines() if line]


def main() -> int:
    if len(sys.argv) != 3:
        print("Usage: flag_restricted_schema_changes.py <base_ref> <head_ref>")
        return 1

    changed = get_changed_files(sys.argv[1], sys.argv[2])
    restricted = find_restricted_changes(changed)

    if restricted:
        print("RESTRICTED_SCHEMA_CHANGES=true")
        print("The following file(s) define app behavior, not library content,")
        print("and need a core-maintainer review rather than the template-contribution path:")
        for path in restricted:
            print(f"  - {path}")
    else:
        print("RESTRICTED_SCHEMA_CHANGES=false")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/test_flag_restricted_schema_changes.py -v`
Expected: all 5 tests PASS

- [ ] **Step 5: Commit**

```bash
git add scripts/ci/flag_restricted_schema_changes.py tests/test_flag_restricted_schema_changes.py
git commit -m "feat: add script to flag PRs touching app-internal schema files

Co-Authored-By: Claude Sonnet 5 <noreply@anthropic.com>"
```

---

### Task 4: `index.json` freshness check

Blocks any PR where `official/library/survey/index.json` is out of sync with the actual template files (spec §1.4) — whether because a contributor hand-edited the index or added/changed a template without regenerating it.

**Files:**
- Modify: `tests/verify_repo.py` (add function + `CHECKS` entry)
- Create: `tests/test_verify_repo_index_json_freshness.py`

**Interfaces:**
- Produces: `check_index_json_freshness(repo_path, fix=False) -> None` in `tests/verify_repo.py`, registered under `"index-json-freshness"`.
- Consumes: `build_registry_index(library_dir: Path) -> dict` from `src/instrument_registry.py` (existing, unmodified — see `src/instrument_registry.py:38`).

- [ ] **Step 1: Write the failing tests**

Create `tests/test_verify_repo_index_json_freshness.py`:

```python
import json
from pathlib import Path


def _load_verify_repo_module():
    import importlib.util

    module_path = Path(__file__).with_name("verify_repo.py")
    spec = importlib.util.spec_from_file_location("verify_repo", module_path)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def _write_instrument(library_dir: Path, filename: str, task_name: str) -> None:
    library_dir.mkdir(parents=True, exist_ok=True)
    (library_dir / filename).write_text(
        json.dumps({"Study": {"TaskName": task_name, "OriginalName": task_name}}),
        encoding="utf-8",
    )


def test_passes_when_index_matches_library(tmp_path: Path, capsys) -> None:
    verify_repo = _load_verify_repo_module()
    library_dir = tmp_path / "official" / "library" / "survey"
    _write_instrument(library_dir, "survey-demo.json", "demo")

    from src.instrument_registry import write_registry_index

    write_registry_index(library_dir, library_dir / "index.json")

    verify_repo.check_index_json_freshness(str(tmp_path))
    output = capsys.readouterr().out

    assert "[✗]" not in output
    assert "up to date" in output


def test_fails_when_new_instrument_not_regenerated(tmp_path: Path, capsys) -> None:
    verify_repo = _load_verify_repo_module()
    library_dir = tmp_path / "official" / "library" / "survey"
    _write_instrument(library_dir, "survey-demo.json", "demo")

    from src.instrument_registry import write_registry_index

    write_registry_index(library_dir, library_dir / "index.json")

    # Contributor adds a new template but forgets to regenerate index.json.
    _write_instrument(library_dir, "survey-second.json", "second")

    verify_repo.check_index_json_freshness(str(tmp_path))
    output = capsys.readouterr().out

    assert "[✗]" in output
    assert "second" in output
    assert "out of date" in output


def test_ignores_generated_on_timestamp_only_diff(tmp_path: Path, capsys) -> None:
    verify_repo = _load_verify_repo_module()
    library_dir = tmp_path / "official" / "library" / "survey"
    _write_instrument(library_dir, "survey-demo.json", "demo")

    from src.instrument_registry import write_registry_index

    write_registry_index(library_dir, library_dir / "index.json")

    # Simulate a stale-but-content-identical GeneratedOn timestamp, e.g. from
    # a rebase that replayed the commit at a different time.
    index_path = library_dir / "index.json"
    index = json.loads(index_path.read_text(encoding="utf-8"))
    index["GeneratedOn"] = "2000-01-01T00:00:00+00:00"
    index_path.write_text(json.dumps(index), encoding="utf-8")

    verify_repo.check_index_json_freshness(str(tmp_path))
    output = capsys.readouterr().out

    assert "[✗]" not in output


def test_fails_when_index_json_missing(tmp_path: Path, capsys) -> None:
    verify_repo = _load_verify_repo_module()
    library_dir = tmp_path / "official" / "library" / "survey"
    _write_instrument(library_dir, "survey-demo.json", "demo")

    verify_repo.check_index_json_freshness(str(tmp_path))
    output = capsys.readouterr().out

    assert "[✗]" in output
    assert "does not exist" in output


def test_skipped_when_library_dir_missing(tmp_path: Path, capsys) -> None:
    verify_repo = _load_verify_repo_module()

    verify_repo.check_index_json_freshness(str(tmp_path))
    output = capsys.readouterr().out

    assert "skipped" in output
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_verify_repo_index_json_freshness.py -v`
Expected: every test fails with `AttributeError: module 'verify_repo' has no attribute 'check_index_json_freshness'`

- [ ] **Step 3: Write the check function**

In `tests/verify_repo.py`, add near `check_library_uniqueness`:

```python
def check_index_json_freshness(repo_path, fix=False):
    """Fail if official/library/survey/index.json is out of sync with the
    actual instrument templates -- whether hand-edited or simply not
    regenerated after a template was added/changed/removed.

    Comparison ignores 'GeneratedOn': it is a timestamp, not content, and a
    byte-for-byte comparison would always report a diff (see spec section
    1.4)."""
    print_header("Checking official/library/survey/index.json Freshness")

    library_dir = Path(repo_path) / "official" / "library" / "survey"
    if not library_dir.is_dir():
        print_success(
            "index.json freshness check skipped (official/library/survey not found)."
        )
        return

    index_path = library_dir / "index.json"
    if not index_path.is_file():
        print_error(f"{index_path} does not exist. Run scripts/generate_instrument_registry.py.")
        return

    repo_root = str(Path(repo_path).resolve())
    if repo_root not in sys.path:
        sys.path.insert(0, repo_root)
    from src.instrument_registry import build_registry_index

    committed = json.loads(index_path.read_text(encoding="utf-8"))
    expected = build_registry_index(library_dir)

    committed_comparable = {k: v for k, v in committed.items() if k != "GeneratedOn"}
    expected_comparable = {k: v for k, v in expected.items() if k != "GeneratedOn"}

    if committed_comparable == expected_comparable:
        print_success("index.json is up to date with official/library/survey/.")
        return

    committed_instruments = set(committed_comparable.get("Instruments", {}))
    expected_instruments = set(expected_comparable.get("Instruments", {}))
    added = expected_instruments - committed_instruments
    removed = committed_instruments - expected_instruments
    changed = {
        name
        for name in committed_instruments & expected_instruments
        if committed_comparable["Instruments"][name]
        != expected_comparable["Instruments"][name]
    }

    print_error(
        "index.json is out of date. Run: python scripts/generate_instrument_registry.py"
    )
    if added:
        print_error(f"  Missing from index.json (added to library): {sorted(added)}")
    if removed:
        print_error(f"  Stale in index.json (removed from library): {sorted(removed)}")
    if changed:
        print_error(f"  Out of date in index.json (library file changed): {sorted(changed)}")
```

- [ ] **Step 4: Register the check**

In `tests/verify_repo.py`'s `CHECKS` dict, add:

```python
    "index-json-freshness": check_index_json_freshness,
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `pytest tests/test_verify_repo_index_json_freshness.py -v`
Expected: all 5 tests PASS

- [ ] **Step 6: Run the check against the real repo**

Run: `python tests/verify_repo.py --check index-json-freshness --no-fix`
Expected: passes (the committed `official/library/survey/index.json` was regenerated `2026-09-10`, per its `GeneratedOn` field, and no library templates changed since).

- [ ] **Step 7: Commit**

```bash
git add tests/verify_repo.py tests/test_verify_repo_index_json_freshness.py
git commit -m "test: add index.json freshness check

Co-Authored-By: Claude Sonnet 5 <noreply@anthropic.com>"
```

---

### Task 5: Minimal-dataset fixture builder

Shared library code that builds a minimal valid PRISM dataset for a given modality/sidecar/data-file combination — the CI fixture format spec §1.2 item 3 requires, and the piece both the manual contribution path and the Issue-Form bot (Task 8) need identically.

**Files:**
- Create: `src/modality_contribution.py`
- Create: `tests/test_modality_contribution.py`

**Interfaces:**
- Produces: `write_minimal_dataset(dest_dir: Path, *, suffix: str, extension: str, sidecar: dict, data_content: str, task_name: str = "demo") -> Path` — writes a dataset under `dest_dir` and returns the path to the created data file. Used by Task 8.
- Consumes: nothing from earlier tasks (this is foundational for Tasks 7-8).

- [ ] **Step 1: Write the failing tests**

Create `tests/test_modality_contribution.py`:

```python
import json
import os
import sys
from pathlib import Path

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(__file__)), "app", "src"))


def test_write_minimal_dataset_creates_expected_files(tmp_path: Path) -> None:
    from src.modality_contribution import write_minimal_dataset

    sidecar = {
        "Study": {"TaskName": "skintemp", "OriginalName": "Skin Temperature"},
        "Metadata": {"SchemaVersion": "1.0.0", "CreationDate": "2026-09-11"},
    }

    data_path = write_minimal_dataset(
        tmp_path,
        suffix="skintemp",
        extension="tsv",
        sidecar=sidecar,
        data_content="temperature_c\n36.5\n",
        task_name="skintemp",
    )

    assert data_path.is_file()
    assert data_path.name == "sub-01_task-skintemp_skintemp.tsv"
    assert (tmp_path / "dataset_description.json").is_file()

    sidecar_path = data_path.with_suffix(".json")
    assert sidecar_path.is_file()
    assert json.loads(sidecar_path.read_text(encoding="utf-8")) == sidecar


def test_write_minimal_dataset_passes_validation(tmp_path: Path) -> None:
    """Uses suffix="survey" deliberately: survey is already a registered
    modality, so this exercises the "new template under an existing
    modality" path, which validates end-to-end today. A brand-new,
    unregistered modality cannot be checked this way -- see Task 8's
    "more significant correction" note."""
    from src.modality_contribution import write_minimal_dataset
    from runner import validate_dataset

    sidecar = {
        "Technical": {
            "StimulusType": "Questionnaire",
            "FileFormat": "tsv",
            "Language": "en",
            "Respondent": "self",
        },
        "Study": {"TaskName": "demo", "OriginalName": "Demo Survey"},
        "Metadata": {"SchemaVersion": "1.1.1", "CreationDate": "2026-09-11"},
    }

    write_minimal_dataset(
        tmp_path,
        suffix="survey",
        extension="tsv",
        sidecar=sidecar,
        data_content="item01\titem02\n1\t2\n",
        task_name="demo",
    )

    issues, stats = validate_dataset(str(tmp_path))

    errors = [i for i in issues if i[0] == "ERROR"]
    assert errors == []
    assert "sub-01" in stats.subjects


def test_write_minimal_dataset_uses_default_task_name(tmp_path: Path) -> None:
    from src.modality_contribution import write_minimal_dataset

    data_path = write_minimal_dataset(
        tmp_path,
        suffix="skintemp",
        extension="tsv",
        sidecar={"Metadata": {"SchemaVersion": "1.0.0", "CreationDate": "2026-09-11"}},
        data_content="x\n1\n",
    )

    assert data_path.name == "sub-01_task-demo_skintemp.tsv"
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_modality_contribution.py -v`
Expected: `ModuleNotFoundError: No module named 'src.modality_contribution'`

- [ ] **Step 3: Write the implementation**

Create `src/modality_contribution.py`:

```python
"""Build minimal valid PRISM datasets for a proposed modality or template.

Shared by the CI contribution-contract check and the Issue-Form-to-draft-PR
bot (spec: docs/superpowers/specs/2026-09-11-modality-contribution-workflow-design.md,
section 1.2 item 3) so the manual and guided contribution paths produce and
are held to the exact same dataset shape.
"""

from __future__ import annotations

import json
from pathlib import Path


def write_minimal_dataset(
    dest_dir: Path,
    *,
    suffix: str,
    extension: str,
    sidecar: dict,
    data_content: str,
    task_name: str = "demo",
) -> Path:
    """Write a minimal valid PRISM dataset for one subject/modality.

    Creates dataset_description.json and sub-01/<suffix>/ containing the
    data file plus its matching JSON sidecar. Returns the path to the
    created data file.
    """
    dest_dir = Path(dest_dir)
    dest_dir.mkdir(parents=True, exist_ok=True)

    dataset_description = {
        "Name": "PRISM Contribution Fixture",
        "BIDSVersion": "1.10.1",
        "DatasetType": "raw",
        "Authors": ["prism-contribution-fixture"],
        "Keywords": ["prism", "contribution-fixture"],
    }
    (dest_dir / "dataset_description.json").write_text(
        json.dumps(dataset_description, indent=2), encoding="utf-8"
    )

    modality_dir = dest_dir / "sub-01" / suffix
    modality_dir.mkdir(parents=True, exist_ok=True)

    stem = f"sub-01_task-{task_name}_{suffix}"
    data_path = modality_dir / f"{stem}.{extension}"
    data_path.write_text(data_content, encoding="utf-8")

    sidecar_path = modality_dir / f"{stem}.json"
    sidecar_path.write_text(json.dumps(sidecar, indent=2), encoding="utf-8")

    return data_path
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/test_modality_contribution.py -v`
Expected: all 3 tests PASS

- [ ] **Step 5: Commit**

```bash
git add src/modality_contribution.py tests/test_modality_contribution.py
git commit -m "feat: add minimal dataset fixture builder for modality contributions

Co-Authored-By: Claude Sonnet 5 <noreply@anthropic.com>"
```

---

### Task 6: New-modality Issue Form

The guided contribution entry point (spec §1.5). One `textarea` with a documented line syntax stands in for "repeatable fields" since GitHub Issue Forms have no repeating-group widget (see "Correction to the spec" above).

**Files:**
- Create: `.github/ISSUE_TEMPLATE/propose-modality.yml`
- Create: `tests/test_propose_modality_issue_form.py`

**Interfaces:** None (YAML consumed by GitHub's Issue Forms renderer; Task 7 parses the resulting issue body, not this file).

- [ ] **Step 1: Write the failing test**

Create `tests/test_propose_modality_issue_form.py`:

```python
from pathlib import Path

import yaml


def test_issue_form_is_valid_yaml_with_required_fields():
    form_path = (
        Path(__file__).resolve().parent.parent
        / ".github"
        / "ISSUE_TEMPLATE"
        / "propose-modality.yml"
    )
    form = yaml.safe_load(form_path.read_text(encoding="utf-8"))

    assert form["name"]
    assert "type: new-modality" in form["labels"]

    field_ids = {item["id"] for item in form["body"] if item.get("type") != "markdown"}
    assert {"modality_name", "suffix", "extensions", "fields"} <= field_ids

    fields_field = next(item for item in form["body"] if item.get("id") == "fields")
    assert fields_field["type"] == "textarea"
    assert "name | datatype | required | unit | extension" in fields_field["attributes"]["description"]
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_propose_modality_issue_form.py -v`
Expected: FAIL — file not found / `yaml.safe_load` on missing file

- [ ] **Step 3: Write the Issue Form**

Create `.github/ISSUE_TEMPLATE/propose-modality.yml`:

```yaml
name: Propose a New Modality
description: Propose a new PRISM modality (e.g. skin temperature, a new sensor type)
title: "[Modality]: "
labels: ["type: new-modality", "status: needs-triage"]
body:
  - type: markdown
    attributes:
      value: |
        Thanks for proposing a new PRISM modality! PRISM describes data
        belonging to a subject as a data file (any extension) plus a JSON
        sidecar describing it -- this form collects what your modality's
        sidecar needs to say.

        Filling this out generates a draft schema, an example sidecar, and
        a minimal test dataset, then opens a pull request automatically so
        a maintainer can review it with you.

  - type: input
    id: modality_name
    attributes:
      label: Modality name
      description: Short, lowercase, no spaces (e.g. "skintemp"). Becomes the schema filename and the BIDS-style suffix.
      placeholder: skintemp
    validations:
      required: true

  - type: input
    id: suffix
    attributes:
      label: Filename suffix
      description: The BIDS-style suffix used in data filenames (often the same as the modality name).
      placeholder: skintemp
    validations:
      required: true

  - type: input
    id: extensions
    attributes:
      label: Allowed data file extensions
      description: Comma-separated, no leading dot (e.g. "tsv, tsv.gz").
      placeholder: tsv
    validations:
      required: true

  - type: textarea
    id: fields
    attributes:
      label: Sidecar fields
      description: |
        One field per line, in this format:
        name | datatype | required | unit | extension
        (leave "unit" blank with a bare | if not applicable)
      placeholder: |
        SensorModel | string | yes | | 
        SamplingRateHz | number | yes | Hz | 
        AmbientTempC | number | no | degC | 
    validations:
      required: true

  - type: textarea
    id: rationale
    attributes:
      label: Why this modality?
      description: What kind of study or measurement does this support?
    validations:
      required: true
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_propose_modality_issue_form.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add .github/ISSUE_TEMPLATE/propose-modality.yml tests/test_propose_modality_issue_form.py
git commit -m "feat: add guided Issue Form for proposing a new PRISM modality

Co-Authored-By: Claude Sonnet 5 <noreply@anthropic.com>"
```

---

### Task 7: Proposal parser and schema/sidecar builders

Turns a submitted issue body into a draft modality schema and example sidecar. This is where the spec's security requirement lives: field names come from untrusted user text and must be validated before they ever reach a filename or a written schema (spec §1.5 "Security").

**Files:**
- Modify: `src/modality_contribution.py`
- Modify: `tests/test_modality_contribution.py`

**Interfaces:**
- Produces (added to `src/modality_contribution.py`):
  - `class ModalityField(NamedTuple)`: `name: str`, `datatype: str`, `required: bool`, `unit: str`
  - `class ModalityProposal(NamedTuple)`: `modality_name: str`, `suffix: str`, `extensions: list[str]`, `fields: list[ModalityField]`
  - `class ProposalParseError(Exception)`
  - `parse_proposal_issue_body(body: str) -> ModalityProposal` — raises `ProposalParseError` with a human-readable message on any invalid input (bad field name, malformed line, missing section).
  - `build_modality_schema(proposal: ModalityProposal) -> dict` — produces a schema satisfying Task 2's `check_modality_schema_conventions` by construction.
  - `build_example_sidecar(proposal: ModalityProposal) -> dict`
- Consumes: `write_minimal_dataset` (Task 5, same file).

- [ ] **Step 1: Write the failing tests**

Append to `tests/test_modality_contribution.py`:

```python
def test_parse_proposal_issue_body_extracts_all_fields():
    from src.modality_contribution import parse_proposal_issue_body

    body = """### Modality name

skintemp

### Filename suffix

skintemp

### Allowed data file extensions

tsv, tsv.gz

### Sidecar fields

SensorModel | string | yes |  |
SamplingRateHz | number | yes | Hz |
AmbientTempC | number | no | degC |

### Why this modality?

Continuous skin temperature recordings for thermoregulation studies.
"""

    proposal = parse_proposal_issue_body(body)

    assert proposal.modality_name == "skintemp"
    assert proposal.suffix == "skintemp"
    assert proposal.extensions == ["tsv", "tsv.gz"]
    assert len(proposal.fields) == 3
    assert proposal.fields[0].name == "SensorModel"
    assert proposal.fields[0].datatype == "string"
    assert proposal.fields[0].required is True
    assert proposal.fields[1].unit == "Hz"
    assert proposal.fields[2].required is False


def test_parse_proposal_issue_body_rejects_unsafe_field_name():
    from src.modality_contribution import parse_proposal_issue_body, ProposalParseError

    body = """### Modality name

skintemp

### Filename suffix

skintemp

### Allowed data file extensions

tsv

### Sidecar fields

../../etc/passwd | string | yes |  |

### Why this modality?

test
"""

    try:
        parse_proposal_issue_body(body)
        assert False, "expected ProposalParseError"
    except ProposalParseError as e:
        assert "field name" in str(e)


def test_parse_proposal_issue_body_rejects_unsafe_modality_name():
    from src.modality_contribution import parse_proposal_issue_body, ProposalParseError

    body = """### Modality name

skin temp; rm -rf /

### Filename suffix

skintemp

### Allowed data file extensions

tsv

### Sidecar fields

Foo | string | yes |  |

### Why this modality?

test
"""

    try:
        parse_proposal_issue_body(body)
        assert False, "expected ProposalParseError"
    except ProposalParseError as e:
        assert "modality name" in str(e)


def test_parse_proposal_issue_body_rejects_missing_section():
    from src.modality_contribution import parse_proposal_issue_body, ProposalParseError

    body = "### Modality name\n\nskintemp\n"

    try:
        parse_proposal_issue_body(body)
        assert False, "expected ProposalParseError"
    except ProposalParseError as e:
        assert "Filename suffix" in str(e)


def test_build_modality_schema_passes_conventions_check(tmp_path):
    from src.modality_contribution import (
        parse_proposal_issue_body,
        build_modality_schema,
    )

    body = """### Modality name

skintemp

### Filename suffix

skintemp

### Allowed data file extensions

tsv

### Sidecar fields

SensorModel | string | yes |  |

### Why this modality?

test
"""
    proposal = parse_proposal_issue_body(body)
    schema = build_modality_schema(proposal)

    import jsonschema

    jsonschema.Draft7Validator.check_schema(schema)
    assert schema["required"] == [
        key for key in schema["required"] if key in schema["properties"]
    ]
    assert schema["$id"].endswith(f"/v{schema['version']}")


def test_build_example_sidecar_matches_fields():
    from src.modality_contribution import (
        parse_proposal_issue_body,
        build_example_sidecar,
    )

    body = """### Modality name

skintemp

### Filename suffix

skintemp

### Allowed data file extensions

tsv

### Sidecar fields

SensorModel | string | yes |  |
SamplingRateHz | number | yes | Hz |

### Why this modality?

test
"""
    proposal = parse_proposal_issue_body(body)
    sidecar = build_example_sidecar(proposal)

    assert "SensorModel" in sidecar
    assert "SamplingRateHz" in sidecar
    assert sidecar["Metadata"]["SchemaVersion"]
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_modality_contribution.py -v -k "proposal or build_modality_schema or build_example_sidecar"`
Expected: `ImportError` — none of `parse_proposal_issue_body`, `build_modality_schema`, `build_example_sidecar`, `ProposalParseError` exist yet

- [ ] **Step 3: Write the implementation**

Append to `src/modality_contribution.py`:

```python
import re
from datetime import date, datetime, timezone
from typing import NamedTuple

_SAFE_NAME = re.compile(r"^[A-Za-z][A-Za-z0-9]*$")
_SAFE_MODALITY_NAME = re.compile(r"^[a-z][a-z0-9]*$")


class ProposalParseError(Exception):
    """Raised when an Issue Form submission can't be turned into a proposal."""


class ModalityField(NamedTuple):
    name: str
    datatype: str
    required: bool
    unit: str


class ModalityProposal(NamedTuple):
    modality_name: str
    suffix: str
    extensions: list
    fields: list


_SECTION_ORDER = [
    "Modality name",
    "Filename suffix",
    "Allowed data file extensions",
    "Sidecar fields",
]


def _extract_sections(body: str) -> dict:
    """Split a GitHub Issue Form body into {heading: content} by '### heading'."""
    sections = {}
    current_heading = None
    current_lines = []

    for line in body.splitlines():
        if line.startswith("### "):
            if current_heading is not None:
                sections[current_heading] = "\n".join(current_lines).strip()
            current_heading = line[4:].strip()
            current_lines = []
        elif current_heading is not None:
            current_lines.append(line)

    if current_heading is not None:
        sections[current_heading] = "\n".join(current_lines).strip()

    return sections


def parse_proposal_issue_body(body: str) -> ModalityProposal:
    sections = _extract_sections(body)

    for required_section in _SECTION_ORDER:
        if required_section not in sections or not sections[required_section]:
            raise ProposalParseError(
                f"Missing or empty required section: '{required_section}'."
            )

    modality_name = sections["Modality name"].strip()
    if not _SAFE_MODALITY_NAME.match(modality_name):
        raise ProposalParseError(
            f"Invalid modality name {modality_name!r}: must be lowercase "
            "letters/digits only, starting with a letter."
        )

    suffix = sections["Filename suffix"].strip()
    if not _SAFE_MODALITY_NAME.match(suffix):
        raise ProposalParseError(
            f"Invalid filename suffix {suffix!r}: must be lowercase "
            "letters/digits only, starting with a letter."
        )

    extensions = [
        ext.strip().lstrip(".")
        for ext in sections["Allowed data file extensions"].split(",")
        if ext.strip()
    ]
    if not extensions:
        raise ProposalParseError("At least one data file extension is required.")

    fields = []
    for line_no, line in enumerate(sections["Sidecar fields"].splitlines(), start=1):
        line = line.strip()
        if not line:
            continue
        parts = [part.strip() for part in line.split("|")]
        if len(parts) < 3:
            raise ProposalParseError(
                f"Sidecar fields line {line_no} is malformed (expected "
                f"'name | datatype | required | unit'): {line!r}"
            )
        name, datatype, required_str = parts[0], parts[1], parts[2]
        unit = parts[3] if len(parts) > 3 else ""

        if not _SAFE_NAME.match(name):
            raise ProposalParseError(
                f"Invalid field name {name!r} on line {line_no}: must be "
                "letters/digits only, starting with a letter."
            )

        required = required_str.strip().lower() in ("yes", "true", "required")
        fields.append(ModalityField(name=name, datatype=datatype, required=required, unit=unit))

    if not fields:
        raise ProposalParseError("At least one sidecar field is required.")

    return ModalityProposal(
        modality_name=modality_name,
        suffix=suffix,
        extensions=extensions,
        fields=fields,
    )


_JSON_SCHEMA_TYPES = {"string": "string", "number": "number", "boolean": "boolean"}


def build_modality_schema(proposal: ModalityProposal) -> dict:
    properties = {
        "Metadata": {
            "type": "object",
            "properties": {
                "SchemaVersion": {"type": "string"},
                "CreationDate": {"type": "string"},
            },
            "required": ["SchemaVersion", "CreationDate"],
        }
    }
    required = ["Metadata"]

    for field in proposal.fields:
        properties[field.name] = {
            "type": _JSON_SCHEMA_TYPES.get(field.datatype.strip().lower(), "string"),
            "description": f"{field.name}" + (f" ({field.unit})" if field.unit else ""),
        }
        if field.required:
            required.append(field.name)

    return {
        "$schema": "http://json-schema.org/draft-07/schema#",
        "$id": f"https://prism.org/schemas/{proposal.modality_name}/v0.1.0",
        "version": "0.1.0",
        "title": proposal.modality_name.title(),
        "description": f"Draft schema for the '{proposal.modality_name}' modality, "
        "generated from a contributor proposal.",
        "type": "object",
        "properties": properties,
        "required": required,
    }


def build_example_sidecar(proposal: ModalityProposal) -> dict:
    _EXAMPLE_VALUES = {"string": "example", "number": 1, "boolean": True}

    sidecar = {
        field.name: _EXAMPLE_VALUES.get(field.datatype.strip().lower(), "example")
        for field in proposal.fields
    }
    sidecar["Metadata"] = {
        "SchemaVersion": "0.1.0",
        "CreationDate": date.today().isoformat(),
    }
    return sidecar
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/test_modality_contribution.py -v`
Expected: all tests PASS (Task 5's 3 tests plus this task's 6 new tests)

- [ ] **Step 5: Commit**

```bash
git add src/modality_contribution.py tests/test_modality_contribution.py
git commit -m "feat: parse modality proposals and build draft schema/sidecar

Co-Authored-By: Claude Sonnet 5 <noreply@anthropic.com>"
```

---

### Task 8: Proposal-to-draft-PR script

The script the Action (Task 9) runs: takes a raw issue body, produces the schema/sidecar/dataset, validates them, and reports success or a clear failure reason. Kept separate from the workflow YAML so it has its own unit tests instead of only being exercisable inside CI.

**Files:**
- Create: `scripts/ci/generate_modality_proposal_pr.py`
- Create: `tests/test_generate_modality_proposal_pr.py`

**Interfaces:**
- Produces: `class ProposalResult(NamedTuple)`: `success: bool`, `message: str`, `output_dir: Path | None`. `generate_proposal(issue_body: str, output_root: Path) -> ProposalResult`.
- Consumes: `parse_proposal_issue_body`, `build_modality_schema`, `build_example_sidecar`, `write_minimal_dataset` (Task 5 & 7, `src/modality_contribution.py`); `jsonschema.Draft7Validator.check_schema` and `jsonschema.validate` directly (`jsonschema` package, already a dependency).
- **Does not** call `validate_dataset`/`prism-validator` — per "A more significant correction" above, a brand-new modality's suffix isn't recognized by the dataset-level validator until a maintainer registers it in `entities.schema.json`/`schema_manager.py`, both core-maintainer-only files this bot never touches. What this script *can* prove automatically: the draft schema is structurally valid (same rules as Task 2's `check_modality_schema_conventions`) and the generated example sidecar actually validates against that draft schema. The minimal dataset fixture is still generated and shipped in the PR as the fixture a maintainer runs `prism-validator` against by hand after registration.

- [ ] **Step 1: Write the failing tests**

Create `tests/test_generate_modality_proposal_pr.py`:

```python
import importlib.util
from pathlib import Path


def _load_module():
    module_path = (
        Path(__file__).resolve().parent.parent
        / "scripts"
        / "ci"
        / "generate_modality_proposal_pr.py"
    )
    spec = importlib.util.spec_from_file_location(
        "generate_modality_proposal_pr", module_path
    )
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


_VALID_BODY = """### Modality name

skintemp

### Filename suffix

skintemp

### Allowed data file extensions

tsv

### Sidecar fields

SensorModel | string | yes |  |
AmbientTempC | number | no | degC |

### Why this modality?

Continuous skin temperature recordings.
"""


def test_generate_proposal_succeeds_for_valid_body(tmp_path: Path) -> None:
    mod = _load_module()

    result = mod.generate_proposal(_VALID_BODY, tmp_path)

    assert result.success is True
    assert result.output_dir is not None
    assert (result.output_dir / "skintemp.schema.json").is_file()
    assert (result.output_dir / "skintemp.example.json").is_file()
    assert (result.output_dir / "dataset" / "dataset_description.json").is_file()


def test_generate_proposal_example_sidecar_matches_draft_schema(tmp_path: Path) -> None:
    """The bot can't run the full dataset-level validator pre-registration
    (see "A more significant correction" in this plan's header) -- what it
    can and must prove is that its own generated example actually satisfies
    its own generated schema."""
    import json

    import jsonschema

    mod = _load_module()

    result = mod.generate_proposal(_VALID_BODY, tmp_path)

    schema = json.loads((result.output_dir / "skintemp.schema.json").read_text())
    example = json.loads((result.output_dir / "skintemp.example.json").read_text())

    jsonschema.validate(instance=example, schema=schema)  # raises if invalid


def test_generate_proposal_dataset_fixture_is_ready_for_maintainer(tmp_path: Path) -> None:
    """The dataset fixture is generated so a maintainer has something to run
    prism-validator against by hand once they've registered the modality in
    entities.schema.json/schema_manager.py -- it is not validated by this
    script itself."""
    mod = _load_module()

    result = mod.generate_proposal(_VALID_BODY, tmp_path)

    dataset_dir = result.output_dir / "dataset"
    assert (dataset_dir / "dataset_description.json").is_file()
    assert (dataset_dir / "sub-01" / "skintemp").is_dir()


def test_generate_proposal_fails_for_malformed_body(tmp_path: Path) -> None:
    mod = _load_module()

    result = mod.generate_proposal("not a valid issue form body", tmp_path)

    assert result.success is False
    assert "Missing or empty required section" in result.message
    assert result.output_dir is None


def test_generate_proposal_fails_for_unsafe_field_name(tmp_path: Path) -> None:
    mod = _load_module()
    body = _VALID_BODY.replace(
        "SensorModel | string | yes |  |", "$(rm -rf /) | string | yes |  |"
    )

    result = mod.generate_proposal(body, tmp_path)

    assert result.success is False
    assert "field name" in result.message
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_generate_modality_proposal_pr.py -v`
Expected: file-not-found errors from `_load_module` (script doesn't exist yet). Note there is no test here calling `validate_dataset`/`prism-validator` — see this plan's "A more significant correction" section for why a brand-new modality can't be checked that way pre-registration.

- [ ] **Step 3: Write the script**

Create `scripts/ci/generate_modality_proposal_pr.py`:

```python
"""Turn a submitted "Propose a New Modality" issue body into a draft
schema + example sidecar + minimal test dataset, ready for a PR.

Invoked by .github/workflows/modality-proposal.yml with the issue body
passed via the MODALITY_ISSUE_BODY environment variable -- never
interpolated into a shell command -- per the security requirement in
docs/superpowers/specs/2026-09-11-modality-contribution-workflow-design.md
section 1.5.
"""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path
from typing import NamedTuple, Optional

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if REPO_ROOT not in sys.path:
    sys.path.insert(0, REPO_ROOT)

from src.modality_contribution import (  # noqa: E402
    ProposalParseError,
    build_example_sidecar,
    build_modality_schema,
    parse_proposal_issue_body,
    write_minimal_dataset,
)


class ProposalResult(NamedTuple):
    success: bool
    message: str
    output_dir: Optional[Path]


def generate_proposal(issue_body: str, output_root: Path) -> ProposalResult:
    import jsonschema

    try:
        proposal = parse_proposal_issue_body(issue_body)
    except ProposalParseError as e:
        return ProposalResult(success=False, message=str(e), output_dir=None)

    schema = build_modality_schema(proposal)
    try:
        jsonschema.Draft7Validator.check_schema(schema)
    except jsonschema.exceptions.SchemaError as e:
        return ProposalResult(
            success=False,
            message=f"Generated schema is not valid JSON Schema draft-07: {e.message}",
            output_dir=None,
        )

    example_sidecar = build_example_sidecar(proposal)
    try:
        jsonschema.validate(instance=example_sidecar, schema=schema)
    except jsonschema.exceptions.ValidationError as e:
        return ProposalResult(
            success=False,
            message=f"Generated example sidecar does not satisfy the generated schema: {e.message}",
            output_dir=None,
        )

    output_dir = Path(output_root) / proposal.modality_name
    output_dir.mkdir(parents=True, exist_ok=True)

    (output_dir / f"{proposal.modality_name}.schema.json").write_text(
        json.dumps(schema, indent=2), encoding="utf-8"
    )
    (output_dir / f"{proposal.modality_name}.example.json").write_text(
        json.dumps(example_sidecar, indent=2), encoding="utf-8"
    )

    dataset_dir = output_dir / "dataset"
    write_minimal_dataset(
        dataset_dir,
        suffix=proposal.suffix,
        extension=proposal.extensions[0],
        sidecar=example_sidecar,
        data_content="\t".join(f.name for f in proposal.fields) + "\n",
        task_name=proposal.modality_name,
    )

    return ProposalResult(
        success=True,
        message=f"Generated draft artifacts for modality '{proposal.modality_name}'.",
        output_dir=output_dir,
    )


def main() -> int:
    issue_body = os.environ.get("MODALITY_ISSUE_BODY")
    if not issue_body:
        print("MODALITY_ISSUE_BODY environment variable is required.", file=sys.stderr)
        return 1

    output_root = Path(os.environ.get("MODALITY_OUTPUT_ROOT", "modality-proposal-draft"))
    result = generate_proposal(issue_body, output_root)

    if result.success:
        print(f"SUCCESS: {result.message}")
        print(f"OUTPUT_DIR={result.output_dir}")
        return 0

    print(f"FAILURE: {result.message}", file=sys.stderr)
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/test_generate_modality_proposal_pr.py -v`
Expected: all 5 tests PASS

- [ ] **Step 5: Commit**

```bash
git add scripts/ci/generate_modality_proposal_pr.py tests/test_generate_modality_proposal_pr.py
git commit -m "feat: add script generating draft modality artifacts from an issue body

Co-Authored-By: Claude Sonnet 5 <noreply@anthropic.com>"
```

---

### Task 9: Wire everything into GitHub Actions

Registers Task 2 and Task 4's checks in `ci.yml`, wires Task 3's flag script into pull-request runs, adds the Issue-Form-triggered bot workflow (Task 8's script), and adds the merge-time `index.json` regeneration job. No new tests here (this task is CI configuration; its correctness is exercised by the checks/scripts already tested in Tasks 2-8) — verification is running the workflows and confirming behavior, per steps below.

**Files:**
- Modify: `.github/workflows/ci.yml`
- Create: `.github/workflows/modality-proposal.yml`
- Create: `.github/workflows/regenerate-instrument-index.yml`

**Interfaces:**
- Consumes: `--check modality-schema-conventions,index-json-freshness` (Task 2, Task 4); `scripts/ci/flag_restricted_schema_changes.py` (Task 3); `scripts/ci/generate_modality_proposal_pr.py` (Task 8); `scripts/generate_instrument_registry.py` (existing).

- [ ] **Step 1: Add the two new checks to `ci.yml`'s fast-pr-checks**

In `.github/workflows/ci.yml`, modify the `fast-pr-checks` job's "Fast repository verification" step (currently at line ~35) from:

```yaml
      - name: Fast repository verification
        run: |
          python tests/verify_repo.py --check git-status,entrypoints-smoke,import-boundaries,dual-tree-drift,library-uniqueness,pytest-modularity,linting,ruff,ruff-security,mypy --no-fix
```

to:

```yaml
      - name: Fast repository verification
        run: |
          python tests/verify_repo.py --check git-status,entrypoints-smoke,import-boundaries,dual-tree-drift,library-uniqueness,modality-schema-conventions,index-json-freshness,pytest-modularity,linting,ruff,ruff-security,mypy --no-fix
```

- [ ] **Step 2: Add the restricted-schema-flag step as a new job in `ci.yml`**

In `.github/workflows/ci.yml`, add a new job (after `fast-pr-checks`):

```yaml
  flag-restricted-schema-changes:
    name: Flag Restricted Schema Changes
    if: github.event_name == 'pull_request'
    runs-on: ubuntu-latest
    permissions:
      contents: read
      pull-requests: write

    steps:
      - name: Checkout
        uses: actions/checkout@v5
        with:
          fetch-depth: 0

      - name: Set up Python
        uses: actions/setup-python@v7
        with:
          python-version: "3.10"

      - name: Check for restricted schema changes
        id: flag
        run: |
          python scripts/ci/flag_restricted_schema_changes.py \
            "origin/${{ github.event.pull_request.base.ref }}" \
            "HEAD" | tee flag_output.txt
          if grep -q "RESTRICTED_SCHEMA_CHANGES=true" flag_output.txt; then
            echo "restricted=true" >> "$GITHUB_OUTPUT"
          else
            echo "restricted=false" >> "$GITHUB_OUTPUT"
          fi

      - name: Comment on PR
        if: steps.flag.outputs.restricted == 'true'
        env:
          GH_TOKEN: ${{ github.token }}
          PR_NUMBER: ${{ github.event.pull_request.number }}
        run: |
          gh pr comment "$PR_NUMBER" --body "$(cat <<'BODY'
          This PR touches one or more app-internal schema files (filename
          grammar, project/dataset-description structure). These need a
          core-maintainer review rather than the usual template-contribution
          review path -- see docs/superpowers/specs/2026-09-11-modality-contribution-workflow-design.md
          section 1.1 for why.
          BODY
          )"
```

- [ ] **Step 3: Create the Issue-Form-triggered bot workflow**

Create `.github/workflows/modality-proposal.yml`:

```yaml
name: Modality Proposal Bot

on:
  issues:
    types: [opened]

permissions:
  contents: write
  issues: write
  pull-requests: write

jobs:
  generate-draft-pr:
    name: Generate Draft PR from Modality Proposal
    if: contains(github.event.issue.labels.*.name, 'type: new-modality')
    runs-on: ubuntu-latest

    steps:
      - name: Checkout
        uses: actions/checkout@v5

      - name: Set up Python
        uses: actions/setup-python@v7
        with:
          python-version: "3.10"

      - name: Install dependencies
        run: |
          python -m pip install --upgrade pip
          pip install -r requirements.txt

      - name: Generate draft modality artifacts
        id: generate
        env:
          MODALITY_ISSUE_BODY: ${{ github.event.issue.body }}
          MODALITY_OUTPUT_ROOT: modality-proposal-draft
        run: |
          set +e
          python scripts/ci/generate_modality_proposal_pr.py > generate_output.txt 2>&1
          echo "exit_code=$?" >> "$GITHUB_OUTPUT"
          cat generate_output.txt

      - name: Comment failure on issue
        if: steps.generate.outputs.exit_code != '0'
        env:
          GH_TOKEN: ${{ github.token }}
          ISSUE_NUMBER: ${{ github.event.issue.number }}
        run: |
          {
            echo "Couldn't generate a draft PR from this proposal:"
            echo ""
            echo '```'
            cat generate_output.txt
            echo '```'
            echo ""
            echo "Please edit the issue to fix the problem above -- editing"
            echo "the issue will not currently re-trigger this bot; a"
            echo "maintainer can re-run it manually, or you can open the PR"
            echo "by hand using the same field format shown in the form."
          } > comment_body.txt
          gh issue comment "$ISSUE_NUMBER" --body-file comment_body.txt

      - name: Open draft PR
        if: steps.generate.outputs.exit_code == '0'
        env:
          GH_TOKEN: ${{ github.token }}
          ISSUE_NUMBER: ${{ github.event.issue.number }}
          ISSUE_AUTHOR: ${{ github.event.issue.user.login }}
        run: |
          MODALITY_DIR=$(grep '^OUTPUT_DIR=' generate_output.txt | cut -d= -f2)
          MODALITY_NAME=$(basename "$MODALITY_DIR")
          BRANCH="modality-proposal/${MODALITY_NAME}-${ISSUE_NUMBER}"

          git config user.name "prism-modality-bot"
          git config user.email "prism-modality-bot@users.noreply.github.com"
          git checkout -b "$BRANCH"
          mkdir -p "app/schemas/proposals/${MODALITY_NAME}"
          cp "${MODALITY_DIR}"/*.json "app/schemas/proposals/${MODALITY_NAME}/"
          cp -r "${MODALITY_DIR}/dataset" "app/schemas/proposals/${MODALITY_NAME}/dataset"
          git add "app/schemas/proposals/${MODALITY_NAME}"
          git commit -m "$(printf 'Draft modality proposal: %s\n\nCo-authored-by: %s <%s@users.noreply.github.com>' "$MODALITY_NAME" "$ISSUE_AUTHOR" "$ISSUE_AUTHOR")"
          git push origin "$BRANCH"

          gh pr create \
            --title "[Modality] ${MODALITY_NAME}" \
            --body "Draft generated from #${ISSUE_NUMBER}. What this bot already verified: the generated schema is valid JSON Schema draft-07 following PRISM conventions, and the generated example sidecar validates against that schema. What it could NOT verify: whether this modality works end-to-end through prism-validator -- that requires registering '${MODALITY_NAME}' in \`app/schemas/stable/entities.schema.json\` (suffix/extension grammar) and \`app/src/schema_manager.py\` (modality list), both core-maintainer-only files this bot never touches. After a maintainer does that registration and moves these files from \`app/schemas/proposals/${MODALITY_NAME}/\` into \`app/schemas/stable/\` and \`official/library/\`, run \`python prism.py app/schemas/proposals/${MODALITY_NAME}/dataset\` against the included fixture to confirm it validates cleanly before merging. Closes #${ISSUE_NUMBER} once merged." \
            --draft \
            --head "$BRANCH"
```

- [ ] **Step 4: Create the merge-time index regeneration workflow**

Create `.github/workflows/regenerate-instrument-index.yml`:

```yaml
name: Regenerate Instrument Index

on:
  push:
    branches: ["main"]
    paths:
      - "official/library/survey/**"

permissions:
  contents: write
  pull-requests: write

jobs:
  regenerate:
    name: Regenerate index.json if stale
    runs-on: ubuntu-latest

    steps:
      - name: Checkout
        uses: actions/checkout@v5

      - name: Set up Python
        uses: actions/setup-python@v7
        with:
          python-version: "3.10"

      - name: Install dependencies
        run: |
          python -m pip install --upgrade pip
          pip install -r requirements.txt

      - name: Regenerate index.json
        run: python scripts/generate_instrument_registry.py

      - name: Check for changes
        id: diff
        run: |
          if git diff --quiet -- official/library/survey/index.json; then
            echo "changed=false" >> "$GITHUB_OUTPUT"
          else
            echo "changed=true" >> "$GITHUB_OUTPUT"
          fi

      - name: Open PR with regenerated index
        if: steps.diff.outputs.changed == 'true'
        env:
          GH_TOKEN: ${{ github.token }}
        run: |
          BRANCH="regenerate-instrument-index-${{ github.run_id }}"
          git config user.name "prism-modality-bot"
          git config user.email "prism-modality-bot@users.noreply.github.com"
          git checkout -b "$BRANCH"
          git add official/library/survey/index.json
          git commit -m "chore: regenerate official/library/survey/index.json"
          git push origin "$BRANCH"
          gh pr create \
            --title "chore: regenerate instrument index" \
            --body "Auto-generated by scripts/generate_instrument_registry.py after a change to official/library/survey/ landed on main." \
            --head "$BRANCH"
```

Note (open item from spec, resolved here): this opens a follow-up PR rather than pushing directly to `main`, since `main` likely has branch protection requiring PRs — direct push would silently fail or need a bypass token. Confirm with the repo owner whether `main` actually allows direct pushes from `GITHUB_TOKEN`; if so, this can be simplified to a direct commit+push.

- [ ] **Step 5: Validate all three workflow files parse as valid YAML**

Run:
```bash
python3 -c "
import yaml
for f in ['.github/workflows/ci.yml', '.github/workflows/modality-proposal.yml', '.github/workflows/regenerate-instrument-index.yml']:
    yaml.safe_load(open(f))
    print(f, 'OK')
"
```
Expected: all three print `OK`

- [ ] **Step 6: Run the existing actions-security check against the new workflows**

Run: `python tests/verify_repo.py --check actions-security --no-fix`
Expected: no medium-or-higher findings. If zizmor flags template injection on `${{ github.event.issue.body }}` or `${{ github.event.pull_request.base.ref }}`, fix by routing that value through `env:` instead of inline `${{ }}` in the affected `run:` block before proceeding — do not suppress the finding.

- [ ] **Step 7: Run the full local test suite**

Run: `pytest tests/ -q`
Expected: all tests pass, including every test added in Tasks 2-8

- [ ] **Step 8: Commit**

```bash
git add .github/workflows/ci.yml .github/workflows/modality-proposal.yml .github/workflows/regenerate-instrument-index.yml
git commit -m "feat: wire modality contribution checks and bot into GitHub Actions

Co-Authored-By: Claude Sonnet 5 <noreply@anthropic.com>"
```

---

### Task 10: Documentation reframe

Serves the paper directly (spec §1.6): lead with the file+sidecar principle instead of survey-first, and document the contribution boundary/contract for contributors. Not TDD (documentation, not executable behavior) — verified via the existing `docs-build` check instead.

**Files:**
- Modify: `docs/WHAT_IS_PRISM.md`
- Modify: `docs/PROJECT_OVERVIEW.md`
- Create: `docs/CONTRIBUTING_MODALITIES.md`

**Interfaces:** None (documentation).

- [ ] **Step 1: Rewrite the opening of `docs/WHAT_IS_PRISM.md`**

Replace the current opening paragraph (currently leading with "Psychological studies often combine well-supported BIDS data with materials that do not have a shared practical structure: questionnaires...") with a paragraph stating the file+sidecar principle first, and presenting survey/biometrics/physio/environment as existing instances of it rather than the framing itself. Keep the rest of the "How PRISM relates to BIDS" table and "Supported modalities" table — those already list modalities in parallel, which is the structure to keep; only the opening framing needs to change.

- [ ] **Step 2: Add a "Contributing a new modality" pointer to `docs/PROJECT_OVERVIEW.md`**

In the existing "For contributors" table, add a row pointing to the new `docs/CONTRIBUTING_MODALITIES.md`.

- [ ] **Step 3: Write `docs/CONTRIBUTING_MODALITIES.md`**

Document: the file+sidecar principle; which schemas are community-extensible vs. core (spec §1.1's two lists, verbatim); the contribution contract (schema + example sidecar + minimal dataset fixture, spec §1.2); how to use the guided Issue Form (Task 6) versus opening a PR by hand; what CI checks (Task 2, Task 4) and the restricted-file flag (Task 3) will do to the PR. Be explicit about the two-stage reality for a **brand-new modality** (this plan's "A more significant correction" section): the bot/CI can only confirm the draft schema is well-formed and the example sidecar satisfies it — the dataset-level `prism-validator` check only becomes possible after a maintainer registers the modality in `app/schemas/stable/entities.schema.json` and `app/src/schema_manager.py` and moves the draft from `app/schemas/proposals/<name>/` into `app/schemas/stable/` and `official/library/`. A **new template under an existing modality** (e.g. another survey instrument) doesn't have this limitation — the existing modality is already registered, so `prism-validator` validates it end-to-end immediately.

- [ ] **Step 4: Build the docs and confirm no warnings**

Run: `sphinx-build -b html docs docs/_build/html -W`
Expected: builds successfully (the `-W` flag turns warnings into errors, matching `ci.yml`'s `docs-build` job, so this is the same check CI will run)

- [ ] **Step 5: Commit**

```bash
git add docs/WHAT_IS_PRISM.md docs/PROJECT_OVERVIEW.md docs/CONTRIBUTING_MODALITIES.md
git commit -m "docs: reframe PRISM around the file+sidecar principle, document modality contribution

Co-Authored-By: Claude Sonnet 5 <noreply@anthropic.com>"
```

---

## Self-Review Notes

**Spec coverage:** §1.1 (boundary) → Task 2 constant + Task 3 script + Task 10 docs. §1.2 (contract) → Task 5 + Task 10 docs. §1.3 (CI validation) → Task 2 (meta-schema-equivalent) + existing `validate_dataset` reused in Task 5's test (validator check, for the already-registered-modality case) + `jsonschema.validate` self-consistency check in Task 8 (for the brand-new-modality case, where `validate_dataset` cannot run pre-registration — see the correction above). §1.4 (index.json) → Task 4 (PR gate) + Task 9 Step 4 (merge-time regeneration). §1.5 (guided path + security) → Tasks 6-9. §1.6 (docs) → Task 10. Testing section's three bullets → should-pass/should-fail fixtures in Task 2 & 4; integration test in Task 8; `GeneratedOn`-insensitive test in Task 4. Unrelated bug → Task 1.

**Deferred/open items from the spec not actioned here (correctly, per spec's own Phase 2 section):** repo extraction, submodule wiring, standalone GUI, GitLab mirror, observation-unit generalization, and the spec's own open item about a written-proposal step before the schema PR for contested modalities (noted in Task 10's doc as a possible future addition, not built).

**Two corrections found by verifying against the running code before finalizing tasks** (not just reading the spec): the `Study`/`Technical` overgeneralization (Task 2), and — more significant — that `validate_dataset` cannot recognize a brand-new, unregistered modality at all (confirmed by actually running it against a hand-built fixture; it reports "No subjects found," not a validation error on the new fields). Task 8 was redesigned around this: the bot proves schema self-consistency (draft schema is valid, generated example satisfies it) and ships a ready-to-run dataset fixture, but explicitly does not and cannot claim the new modality passes `prism-validator` until a maintainer completes the core-only registration step. Task 5's `survey`-modality test is unaffected and remains the demonstration that the "new template under an existing modality" path already works end-to-end today.

**One open item surfaced during planning, not resolved by it:** Task 9 Step 4's note about whether `main` allows direct pushes from `GITHUB_TOKEN` — the plan defaults to the safer follow-up-PR approach and flags the alternative for the repo owner to confirm.
