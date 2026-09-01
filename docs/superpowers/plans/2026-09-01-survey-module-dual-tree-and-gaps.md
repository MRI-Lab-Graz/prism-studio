# Dual-Tree Drift Guard + Survey Module Gap Fixes Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Close the `src/` vs `app/src/` dual-tree drift hazard structurally (a CI-enforced check, not tribal knowledge in CLAUDE.md), then fix the concrete bugs and test-coverage gaps found during the 2026-09-01 survey-module deep assessment (schema/template, validation, import, LimeSurvey export/import).

**Architecture:** Phase 1 adds one new check function to the repo's existing `tests/verify_repo.py` audit framework (the same framework that already runs `import-boundaries`, `unsafe-patterns`, etc. in CI) — it flags any `.py` file that exists at the same relative path under both `src/` and `app/src/` without being resolved via a symlink or a recognized delegation shim (`load_canonical_module`/`spec_from_file_location`). Phase 2 is eight small, independent bug/gap fixes identified during the assessment, each with its own regression test.

**Tech Stack:** Python 3.10+, pytest, Flask (test client / direct handler calls), the repo's existing `tests/verify_repo.py` check framework, GitHub Actions (`.github/workflows/ci.yml`).

**Spec:** No separate spec doc — this plan is self-contained; the spec is the assessment findings summarized above and in each task's rationale.

## Global Constraints

- Every user-triggered action must have a real backend implementation, and every backend command must have a dedicated test (`tests/CLAUDE.md`) — this is exactly what Phase 2 is closing gaps against.
- `src/` is the canonical backend logic tree; `app/src/` is Flask/GUI adapter code. Never silently duplicate business logic between them — collapse into one real file + a symlink, or a `load_canonical_module`/`spec_from_file_location` delegation shim (CLAUDE.md).
- Prefer extracting small, focused, testable functions over growing monoliths in place (CLAUDE.md) — but this plan does not do opportunistic refactors unrelated to each specific fix.
- No behavior changes disguised as bug fixes: Task 10 (CLI `survey validate` scope) is documentation-only, not a validation-behavior change, because widening what the CLI command checks is a product decision outside this plan's scope.
- Cross-platform: all fixes must work on Windows, macOS, Linux (CLAUDE.md). The temp-file cleanup in Task 3 is best-effort (`try/except OSError`) for this reason — matching the existing `_build_zip_stream_response` pattern in `projects_export_blueprint.py`.
- Known, deliberately deferred (not part of this plan): the ~500-line near-duplicate sync/async handlers in `conversion_survey_convert_validate_handlers.py`, and the `# TODO` project-path-resolution branch in `survey_templates.py:1159`. Both need their own scoping pass before a safe fix can be written — bundling them here risked exactly the kind of unreviewable, oversized change this plan is trying to avoid.

---

## Phase 1 — Fundamental fix: structural dual-tree drift guard

### Task 1: Implement `check_dual_tree_drift` in `tests/verify_repo.py`

**Files:**
- Modify: `tests/verify_repo.py` (add helpers + check function before the `CHECKS` dict, register in `CHECKS` and the `"fast"` profile)
- Create: `tests/test_verify_repo_dual_tree_drift.py`

**Interfaces:**
- Produces: `check_dual_tree_drift(repo_path, fix=False) -> None` (same signature shape as the existing `check_import_boundaries`), plus internal helpers `_is_symlink_pair(path_a, path_b) -> bool` and `_has_delegation_shim_marker(content) -> bool`.
- Consumes existing `tests/verify_repo.py` helpers: `print_header`, `print_success`, `print_error`, `should_ignore(path, repo_path)`.

This check enumerates every `.py` file under `src/` and every `.py` file under `app/src/` (skipping `__init__.py` — those are legitimately independent on both sides, since their divergent presence/absence is exactly the mechanism that decides which side namespace-package resolution picks, per CLAUDE.md's dual-tree note). For every relative path present on **both** sides, it's "resolved" (fine) if either side is a symlink pointing at the other, or if either file's source contains a `load_canonical_module(` or `spec_from_file_location(` marker (the two delegation-shim patterns CLAUDE.md documents). Anything else is flagged as an unresolved duplicate. A dry run across the current repo (verified manually during planning) finds **zero** violations today, so this check can be wired into CI immediately with no exceptions list needed.

- [ ] **Step 1: Write the failing tests**

Create `tests/test_verify_repo_dual_tree_drift.py`:

```python
import os
from pathlib import Path

import pytest


def _load_verify_repo_module():
    import importlib.util

    module_path = Path(__file__).with_name("verify_repo.py")
    spec = importlib.util.spec_from_file_location("verify_repo", module_path)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def _make_pair(tmp_path, rel_path, src_content, app_content):
    src_file = tmp_path / "src" / rel_path
    app_file = tmp_path / "app" / "src" / rel_path
    src_file.parent.mkdir(parents=True, exist_ok=True)
    app_file.parent.mkdir(parents=True, exist_ok=True)
    src_file.write_text(src_content, encoding="utf-8")
    app_file.write_text(app_content, encoding="utf-8")
    return src_file, app_file


def test_flags_unresolved_independent_duplicate(tmp_path: Path, capsys) -> None:
    verify_repo = _load_verify_repo_module()

    _make_pair(
        tmp_path,
        "converters/widget.py",
        "def build():\n    return 'src version'\n",
        "def build():\n    return 'app version'\n",
    )

    verify_repo.check_dual_tree_drift(str(tmp_path))
    output = capsys.readouterr().out

    assert "converters/widget.py" in output
    assert "Unresolved dual-tree duplicate" in output


def test_accepts_symlinked_pair(tmp_path: Path, capsys) -> None:
    verify_repo = _load_verify_repo_module()

    src_file, app_file = _make_pair(
        tmp_path,
        "converters/widget.py",
        "def build():\n    return 'canonical'\n",
        "def build():\n    return 'canonical'\n",
    )
    src_file.unlink()
    try:
        src_file.symlink_to(os.path.relpath(app_file, src_file.parent))
    except OSError:
        pytest.skip("Symlinks not supported in this environment")

    verify_repo.check_dual_tree_drift(str(tmp_path))
    output = capsys.readouterr().out

    assert "widget.py" not in output
    assert "passed" in output


def test_accepts_delegation_shim_pair(tmp_path: Path, capsys) -> None:
    verify_repo = _load_verify_repo_module()

    _make_pair(
        tmp_path,
        "converters/widget.py",
        "def build():\n    return 'canonical'\n",
        "from src._compat import load_canonical_module\n"
        "load_canonical_module(current_file=__file__, "
        "canonical_rel_path='converters/widget.py', alias='converters.widget')\n",
    )

    verify_repo.check_dual_tree_drift(str(tmp_path))
    output = capsys.readouterr().out

    assert "widget.py" not in output
    assert "passed" in output


def test_ignores_init_py_duplicates(tmp_path: Path, capsys) -> None:
    verify_repo = _load_verify_repo_module()

    _make_pair(
        tmp_path,
        "maintenance/__init__.py",
        '"""Maintenance utilities."""\n',
        "from .sync_keys import sync_keys\n",
    )

    verify_repo.check_dual_tree_drift(str(tmp_path))
    output = capsys.readouterr().out

    assert "__init__.py" not in output
    assert "passed" in output


def test_skipped_when_trees_missing(tmp_path: Path, capsys) -> None:
    verify_repo = _load_verify_repo_module()

    verify_repo.check_dual_tree_drift(str(tmp_path))
    output = capsys.readouterr().out

    assert "skipped" in output
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `pytest tests/test_verify_repo_dual_tree_drift.py -v`
Expected: FAIL — `AttributeError: module 'verify_repo' has no attribute 'check_dual_tree_drift'`

- [ ] **Step 3: Implement the check in `tests/verify_repo.py`**

Insert immediately after `check_import_boundaries` (right before the `CHECKS = {` dict, i.e. after the existing line `print_success("Import boundary check passed (no app.src.* runtime imports).")` and its closing blank line):

```python
_DUAL_TREE_SHIM_MARKERS = ("load_canonical_module(", "spec_from_file_location(")


def _is_symlink_pair(path_a: Path, path_b: Path) -> bool:
    for link_path, other_path in ((path_a, path_b), (path_b, path_a)):
        if not link_path.is_symlink():
            continue
        try:
            if link_path.resolve() == other_path.resolve():
                return True
        except OSError:
            continue
    return False


def _has_delegation_shim_marker(content: str) -> bool:
    return any(marker in content for marker in _DUAL_TREE_SHIM_MARKERS)


def check_dual_tree_drift(repo_path, fix=False):
    """Flag .py files duplicated between src/ and app/src/ that aren't
    resolved via a symlink or a recognized delegation shim (see CLAUDE.md's
    src/ vs app/src/ dual-tree drift note)."""
    print_header("Checking src/ vs app/src/ Dual-Tree Drift")

    src_root = Path(repo_path) / "src"
    app_src_root = Path(repo_path) / "app" / "src"

    if not src_root.is_dir() or not app_src_root.is_dir():
        print_success("Dual-tree drift check skipped (src/ or app/src/ not found).")
        return

    def collect(root):
        files = {}
        for py_file in root.rglob("*.py"):
            if py_file.name == "__init__.py":
                continue
            if should_ignore(str(py_file), repo_path):
                continue
            files[py_file.relative_to(root)] = py_file
        return files

    src_files = collect(src_root)
    app_files = collect(app_src_root)

    unresolved = []
    for rel_path in sorted(set(src_files) & set(app_files)):
        src_file = src_files[rel_path]
        app_file = app_files[rel_path]

        if _is_symlink_pair(src_file, app_file):
            continue

        try:
            src_content = src_file.read_text(encoding="utf-8", errors="ignore")
        except OSError:
            src_content = ""
        try:
            app_content = app_file.read_text(encoding="utf-8", errors="ignore")
        except OSError:
            app_content = ""

        if _has_delegation_shim_marker(src_content) or _has_delegation_shim_marker(
            app_content
        ):
            continue

        unresolved.append(rel_path)

    if unresolved:
        for rel_path in unresolved:
            print_error(
                f"Unresolved dual-tree duplicate: src/{rel_path} and app/src/{rel_path} "
                "both exist as independent files. Collapse into one real file with a "
                "symlink for the other side, or use a load_canonical_module/"
                "spec_from_file_location delegation shim (see CLAUDE.md)."
            )
    else:
        print_success(
            "Dual-tree drift check passed (no unresolved src/ vs app/src/ duplicates)."
        )
```

Then register it in the `CHECKS` dict (add alongside `"import-boundaries": check_import_boundaries,`):

```python
    "import-boundaries": check_import_boundaries,
    "dual-tree-drift": check_dual_tree_drift,
```

And add it to the `"fast"` profile list in `DEFAULT_CHECK_PROFILES` (it's a pure static-analysis check like `import-boundaries`, so it belongs in the profile that runs on every push):

```python
        "import-boundaries",
        "dual-tree-drift",
        "unsafe-patterns",
```

- [ ] **Step 4: Run the tests to verify they pass**

Run: `pytest tests/test_verify_repo_dual_tree_drift.py -v`
Expected: PASS (all 5 tests)

- [ ] **Step 5: Commit**

```bash
git add tests/verify_repo.py tests/test_verify_repo_dual_tree_drift.py
git commit -m "feat: add dual-tree drift check to verify_repo audit framework"
```

---

### Task 2: Wire `dual-tree-drift` into CI and confirm it's clean today

**Files:**
- Modify: `.github/workflows/ci.yml:42` and `.github/workflows/ci.yml:77`

**Interfaces:**
- Consumes: `check_dual_tree_drift` registered as `"dual-tree-drift"` in `tests/verify_repo.py`'s `CHECKS` dict (Task 1).

- [ ] **Step 1: Add the check to both CI check lists**

In `.github/workflows/ci.yml`, line 42 currently reads:

```
          python tests/verify_repo.py --check git-status,entrypoints-smoke,import-boundaries,pytest-modularity,linting,ruff,ruff-security,mypy --no-fix
```

Change to:

```
          python tests/verify_repo.py --check git-status,entrypoints-smoke,import-boundaries,dual-tree-drift,pytest-modularity,linting,ruff,ruff-security,mypy --no-fix
```

Line 77 currently reads:

```
          python tests/verify_repo.py --check git-status,entrypoints-smoke,bids-compat-smoke,path-hygiene,system-file-filtering,import-boundaries,python-security,unsafe-patterns,ruff-security,secrets,secrets-history,actions-security,dependencies,pip-audit,pytest,linting,ruff,mypy,testing,todos,documentation --no-fix
```

Change to:

```
          python tests/verify_repo.py --check git-status,entrypoints-smoke,bids-compat-smoke,path-hygiene,system-file-filtering,import-boundaries,dual-tree-drift,python-security,unsafe-patterns,ruff-security,secrets,secrets-history,actions-security,dependencies,pip-audit,pytest,linting,ruff,mypy,testing,todos,documentation --no-fix
```

- [ ] **Step 2: Run the new check against the real repo to confirm it's clean**

Run: `python tests/verify_repo.py --check dual-tree-drift --no-fix`
Expected: `[✓] Dual-tree drift check passed (no unresolved src/ vs app/src/ duplicates).` and exit code 0. (Verified manually during planning — this step just re-confirms after the Task 1 implementation is in place, since a bug in the check itself would otherwise only surface in CI.)

If it unexpectedly reports violations, do not silence them — that means either the checker has a bug (fix it, back to Task 1) or a real unresolved duplicate exists (that becomes its own follow-up task; do not merge Task 2 until the check is genuinely green, since a check that starts CI-red is worse than no check).

- [ ] **Step 3: Commit**

```bash
git add .github/workflows/ci.yml
git commit -m "ci: enforce dual-tree drift check on every push"
```

---

## Phase 2 — Survey module bug/gap fixes

### Task 3: Fix `.lss` export temp-file leaks (Survey Customizer + Survey Generator)

Both `handle_survey_customizer_export` (`tools_survey_customizer_handlers.py`) and `handle_generate_lss_endpoint` (`tools_generation_handlers.py`) create a temp `.lss` file via `tempfile.mkstemp`, stream it back with `send_file`, and never delete it — every export leaks one file. The codebase already has an established pattern for exactly this (`_build_zip_stream_response` in `projects_export_blueprint.py`, best-effort `unlink` wrapped in `try/except OSError`); for a `send_file`-based (non-streamed) response, the equivalent idiom is Flask's `after_this_request`.

**Files:**
- Modify: `app/src/web/blueprints/tools_survey_customizer_handlers.py:10` (import) and `:303-312` (cleanup)
- Modify: `app/src/web/blueprints/tools_generation_handlers.py:6` (import) and `:95-99` (cleanup)
- Test: `tests/test_tools_survey_customizer_handlers.py` (new file)
- Test: `tests/test_tools_generation_handlers.py` (turned out to already exist — see the implementation's actual handling)

**Interfaces:**
- No signature changes to either handler — both remain drop-in replacements at their existing call sites in `tools.py`.

- [ ] **Step 1: Write the failing tests**

Create `tests/test_tools_survey_customizer_handlers.py`:

```python
import importlib
from pathlib import Path

from flask import Flask


def test_handle_survey_customizer_export_cleans_up_temp_file(monkeypatch) -> None:
    handlers = importlib.import_module(
        "src.web.blueprints.tools_survey_customizer_handlers"
    )
    exporter = importlib.import_module("src.limesurvey_exporter")

    created_paths = []

    def fake_generate_lss_from_customization(*, output_path, **kwargs):
        created_paths.append(output_path)
        Path(output_path).write_text("<xml/>", encoding="utf-8")

    monkeypatch.setattr(
        exporter,
        "generate_lss_from_customization",
        fake_generate_lss_from_customization,
    )

    app = Flask(__name__)
    app.add_url_rule(
        "/api/survey-customizer/export",
        view_func=lambda: handlers.handle_survey_customizer_export(
            data={
                "survey": {"title": "Demo Survey", "language": "en"},
                "groups": [{"id": "g1"}],
                "exportFormat": "limesurvey",
            },
            project_path=None,
        ),
        methods=["POST"],
    )

    with app.test_client() as client:
        response = client.post("/api/survey-customizer/export")

    assert response.status_code == 200
    assert len(created_paths) == 1
    assert not Path(created_paths[0]).exists()
```

Create `tests/test_tools_generation_handlers.py`:

```python
import importlib
from pathlib import Path

from flask import Flask


def test_handle_generate_lss_endpoint_cleans_up_temp_file(monkeypatch, tmp_path) -> None:
    handlers = importlib.import_module("src.web.blueprints.tools_generation_handlers")
    exporter = importlib.import_module("src.limesurvey_exporter")

    source_file = tmp_path / "survey-demo.json"
    source_file.write_text("{}", encoding="utf-8")

    created_paths = []

    def fake_generate_lss(file_paths, output_path, **kwargs):
        created_paths.append(output_path)
        Path(output_path).write_text("<xml/>", encoding="utf-8")

    monkeypatch.setattr(exporter, "generate_lss", fake_generate_lss)

    app = Flask(__name__)
    app.add_url_rule(
        "/api/generate-lss",
        view_func=handlers.handle_generate_lss_endpoint,
        methods=["POST"],
    )

    with app.test_client() as client:
        response = client.post(
            "/api/generate-lss",
            json={"files": [{"path": str(source_file)}], "survey_title": "Demo"},
        )

    assert response.status_code == 200
    assert len(created_paths) == 1
    assert not Path(created_paths[0]).exists()
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `pytest tests/test_tools_survey_customizer_handlers.py tests/test_tools_generation_handlers.py -v`
Expected: Both FAIL on `assert not Path(created_paths[0]).exists()` (the temp file is still there).

- [ ] **Step 3: Fix `tools_survey_customizer_handlers.py`**

Change the import line:

```python
from flask import jsonify, send_file
```

to:

```python
from flask import after_this_request, jsonify, send_file
```

Change the `send_file` block (currently):

```python
        response = send_file(
            temp_path,
            as_attachment=True,
            download_name=download_filename,
            mimetype="application/xml",
        )
        if templates_saved:
            response.headers["X-Templates-Saved"] = str(templates_saved)
            response.headers["Access-Control-Expose-Headers"] = "X-Templates-Saved"
        return response
```

to:

```python
        response = send_file(
            temp_path,
            as_attachment=True,
            download_name=download_filename,
            mimetype="application/xml",
        )

        @after_this_request
        def _cleanup_temp_export(resp):
            try:
                os.remove(temp_path)
            except OSError:
                pass
            return resp

        if templates_saved:
            response.headers["X-Templates-Saved"] = str(templates_saved)
            response.headers["Access-Control-Expose-Headers"] = "X-Templates-Saved"
        return response
```

- [ ] **Step 4: Fix `tools_generation_handlers.py`**

Change the import line:

```python
from flask import current_app, jsonify, request, send_file
```

to:

```python
from flask import after_this_request, current_app, jsonify, request, send_file
```

Change the `handle_generate_lss_endpoint` return block (currently):

```python
        return send_file(
            temp_path,
            as_attachment=True,
            download_name=download_filename,
            mimetype="application/xml",
        )
    except Exception as e:
        return jsonify({"error": str(e)}), 500
```

to:

```python
        response = send_file(
            temp_path,
            as_attachment=True,
            download_name=download_filename,
            mimetype="application/xml",
        )

        @after_this_request
        def _cleanup_temp_export(resp):
            try:
                os.remove(temp_path)
            except OSError:
                pass
            return resp

        return response
    except Exception as e:
        return jsonify({"error": str(e)}), 500
```

- [ ] **Step 5: Run the tests to verify they pass**

Run: `pytest tests/test_tools_survey_customizer_handlers.py tests/test_tools_generation_handlers.py -v`
Expected: PASS

- [ ] **Step 6: Commit**

```bash
git add app/src/web/blueprints/tools_survey_customizer_handlers.py app/src/web/blueprints/tools_generation_handlers.py tests/test_tools_survey_customizer_handlers.py tests/test_tools_generation_handlers.py
git commit -m "fix: clean up temp .lss files after survey export downloads"
```

---

### Task 4: Deduplicate the template-completion gate dict + strengthen its regression test

`conversion_survey_template_check_handlers.py`'s `handle_api_survey_check_project_templates` hand-builds a literal dict that's an exact copy of what `conversion_survey_template_helpers.build_template_completion_gate` already returns. It's currently identical, but nothing keeps it that way — a future edit to the shared builder silently won't reach this call site. The existing test (`test_reports_issues_with_workflow_gate` in `tests/test_web_blueprints_conversion.py`) only asserts `workflow_gate.blocked` is truthy, not the full shape, which is exactly why this could drift unnoticed.

**Files:**
- Modify: `app/src/web/blueprints/conversion_survey_template_check_handlers.py:1-5` (import) and `:192-208` (gate construction)
- Modify: `tests/test_web_blueprints_conversion.py` (strengthen `test_reports_issues_with_workflow_gate`, in class `TestSurveyProjectTemplateCheckEndpoint`)

**Interfaces:**
- Consumes: `build_template_completion_gate(*, tasks: list[str], issues: list[dict[str, str]]) -> dict[str, Any]` from `conversion_survey_template_helpers.py` (already exists, unchanged).

- [ ] **Step 1: Strengthen the existing test to assert full gate shape (write failing assertion)**

In `tests/test_web_blueprints_conversion.py`, in `TestSurveyProjectTemplateCheckEndpoint.test_reports_issues_with_workflow_gate`, after the existing `self.assertTrue(payload.get("workflow_gate", {}).get("blocked"))` line, add:

```python
            import importlib as _importlib

            template_helpers = _importlib.import_module(
                "src.web.blueprints.conversion_survey_template_helpers"
            )
            expected_gate = template_helpers.build_template_completion_gate(
                tasks=["pss"], issues=mocked_issues
            )
            self.assertEqual(payload.get("workflow_gate"), expected_gate)
```

This assertion already passes today (both dicts happen to be identical), but it doesn't yet *prove* the handler calls the shared builder rather than a hand-copied literal — that's what Step 3 changes.

- [ ] **Step 2: Run the test to confirm it currently passes (content is identical, just not sourced from the same function yet)**

Run: `pytest tests/test_web_blueprints_conversion.py -k test_reports_issues_with_workflow_gate -v`
Expected: PASS (this step is a checkpoint, not a red step — the goal of Step 1 is precision, not failure; the actual drift-prevention comes from Step 3's refactor plus this assertion staying green afterward)

- [ ] **Step 3: Replace the duplicated dict with a call to the shared builder**

Add the import to the top of `app/src/web/blueprints/conversion_survey_template_check_handlers.py`:

```python
from pathlib import Path

from flask import jsonify, request, session
from werkzeug.utils import secure_filename
from src.system_files import filter_system_files

from .conversion_survey_template_helpers import build_template_completion_gate
```

Replace:

```python
    if issues:
        gate = {
            "blocked": True,
            "reason": "project_template_completion_required",
            "title": "Template Completion Required",
            "message": (
                "Official templates were copied to your project library. "
                "Some required project-level fields still need to be completed in these templates before importing survey data."
            ),
            "tasks": sorted({task for task in tasks if task}),
            "issue_count": len(issues),
            "next_steps": [
                "Open Template Editor for the copied survey templates in code/library/survey.",
                "Fill project-specific administration fields in Technical (for example AdministrationMethod, SoftwarePlatform, SoftwareVersion) and any remaining required metadata.",
                "Run Preview again. Import is unlocked automatically after template validation passes.",
            ],
        }
```

with:

```python
    if issues:
        gate = build_template_completion_gate(tasks=tasks, issues=issues)
```

- [ ] **Step 4: Run the full test to confirm it still passes post-refactor**

Run: `pytest tests/test_web_blueprints_conversion.py -k TestSurveyProjectTemplateCheckEndpoint -v`
Expected: PASS (all tests in the class)

- [ ] **Step 5: Commit**

```bash
git add app/src/web/blueprints/conversion_survey_template_check_handlers.py tests/test_web_blueprints_conversion.py
git commit -m "fix: stop hand-duplicating the template-completion gate dict"
```

---

### Task 5: Add a dedicated test for `handle_survey_customizer_load`

This is the backend for `/api/survey-customizer/load` and has no test at all today — the only file with "customizer" in its name (`test_survey_customizer_workflow_wiring.py`) only greps JS/HTML strings, never calls the handler.

**Files:**
- Test: `tests/test_tools_survey_customizer_handlers.py` (created in Task 3 — add to it)

**Interfaces:**
- Consumes: `handle_survey_customizer_load(data: dict, detect_languages_from_template: Callable[[dict], set]) -> flask.Response`

- [ ] **Step 1: Write the failing test**

Add to `tests/test_tools_survey_customizer_handlers.py`:

```python
import json


def test_handle_survey_customizer_load_builds_groups_from_template(tmp_path) -> None:
    handlers = importlib.import_module(
        "src.web.blueprints.tools_survey_customizer_handlers"
    )
    info_helpers = importlib.import_module(
        "src.web.blueprints.tools_template_info_helpers"
    )

    template_path = tmp_path / "survey-demo.json"
    template_path.write_text(
        json.dumps(
            {
                "Study": {"OriginalName": "Demo Survey"},
                "Q1": {
                    "Description": {"en": "How are you?"},
                    "Levels": {"1": "Bad", "2": "Good"},
                    "Mandatory": True,
                },
            }
        ),
        encoding="utf-8",
    )

    app = Flask(__name__)
    with app.app_context():
        response = handlers.handle_survey_customizer_load(
            data={"files": [{"path": str(template_path)}]},
            detect_languages_from_template=info_helpers.detect_languages_from_template,
        )
        payload = response.get_json()

    assert response.status_code == 200
    assert payload["totalQuestions"] == 1
    assert payload["groups"][0]["name"] == "Demo Survey"
    assert payload["groups"][0]["questions"][0]["questionCode"] == "Q1"
    assert payload["groups"][0]["questions"][0]["description"] == "How are you?"


def test_handle_survey_customizer_load_rejects_empty_files() -> None:
    handlers = importlib.import_module(
        "src.web.blueprints.tools_survey_customizer_handlers"
    )

    app = Flask(__name__)
    with app.app_context():
        response, status = handlers.handle_survey_customizer_load(
            data={"files": []},
            detect_languages_from_template=lambda template: set(),
        )
        payload = response.get_json()

    assert status == 400
    assert payload["error"] == "No files provided"
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `pytest tests/test_tools_survey_customizer_handlers.py -k customizer_load -v`
Expected: FAIL — `handle_survey_customizer_load` not yet imported/exercised in this way should actually work already since the handler exists; if it fails, it's most likely `ImportError: cannot import name 'json'` or similar setup mistake to fix, not a missing implementation (this handler already exists and is correct — this task only adds coverage, no production code changes).

- [ ] **Step 3: Run again after fixing any test-only issues; no production code changes are expected**

Run: `pytest tests/test_tools_survey_customizer_handlers.py -k customizer_load -v`
Expected: PASS

- [ ] **Step 4: Commit**

```bash
git add tests/test_tools_survey_customizer_handlers.py
git commit -m "test: add direct coverage for handle_survey_customizer_load"
```

---

### Task 6: Add a dedicated test for `get_survey_customizer_formats_payload`

**Files:**
- Test: `tests/test_tools_survey_customizer_handlers.py` (add to it)

**Interfaces:**
- Consumes: `get_survey_customizer_formats_payload() -> dict`

- [ ] **Step 1: Write the failing test**

Add to `tests/test_tools_survey_customizer_handlers.py`:

```python
def test_get_survey_customizer_formats_payload_lists_limesurvey_format() -> None:
    handlers = importlib.import_module(
        "src.web.blueprints.tools_survey_customizer_handlers"
    )

    payload = handlers.get_survey_customizer_formats_payload()

    assert payload["formats"][0]["id"] == "limesurvey"
    assert payload["formats"][0]["extension"] == ".lss"
    option_ids = {opt["id"] for opt in payload["formats"][0]["options"]}
    assert option_ids == {"ls_version", "matrix", "matrix_global"}
```

- [ ] **Step 2: Run the test to verify it fails or passes**

Run: `pytest tests/test_tools_survey_customizer_handlers.py -k formats_payload -v`
Expected: PASS immediately (this function is a static payload builder with no bugs found — this task is pure coverage, no production code change).

- [ ] **Step 3: Commit**

```bash
git add tests/test_tools_survey_customizer_handlers.py
git commit -m "test: add direct coverage for get_survey_customizer_formats_payload"
```

---

### Task 7: Add a functional test for the `/api/limesurvey-to-prism` web route

`handle_limesurvey_to_prism` has its own inline `.lsa` unzip + `.lss` XML parsing logic, separate from the well-tested `convert_lsa_to_prism`/`batch_convert_lsa` CLI path. The only existing "test" touching it (`test_converter_workflow_wiring.py`) greps source text for route/JS strings — it never uploads a real file through the Flask test client.

**Files:**
- Test: `tests/test_tools_limesurvey_handlers.py` (new file)

**Interfaces:**
- Consumes: `handle_limesurvey_to_prism()` (reads `flask.request.files`/`request.form` directly, no injected args), and reuses the `LSS_XML` fixture already defined in `tests/test_limesurvey_e2e.py`.

- [ ] **Step 1: Write the failing test**

Create `tests/test_tools_limesurvey_handlers.py`:

```python
import importlib
import io

from flask import Flask

from test_limesurvey_e2e import LSS_XML


def test_handle_limesurvey_to_prism_combined_mode_from_lss_upload() -> None:
    handlers = importlib.import_module("src.web.blueprints.tools_limesurvey_handlers")

    app = Flask(__name__)
    app.add_url_rule(
        "/api/limesurvey-to-prism",
        view_func=handlers.handle_limesurvey_to_prism,
        methods=["POST"],
    )

    with app.test_client() as client:
        response = client.post(
            "/api/limesurvey-to-prism",
            data={
                "file": (io.BytesIO(LSS_XML.encode("utf-8")), "e2e_test_survey.lss"),
                "mode": "combined",
                "task_name": "wellbeing",
            },
            content_type="multipart/form-data",
        )

    assert response.status_code == 200
    payload = response.get_json()
    assert payload.get("success") is True
    assert payload.get("mode") == "combined"
    assert payload.get("question_count", 0) >= 1
    assert "error" not in payload


def test_handle_limesurvey_to_prism_rejects_unsupported_extension() -> None:
    handlers = importlib.import_module("src.web.blueprints.tools_limesurvey_handlers")

    app = Flask(__name__)
    app.add_url_rule(
        "/api/limesurvey-to-prism",
        view_func=handlers.handle_limesurvey_to_prism,
        methods=["POST"],
    )

    with app.test_client() as client:
        response = client.post(
            "/api/limesurvey-to-prism",
            data={"file": (io.BytesIO(b"not a survey"), "notes.txt")},
            content_type="multipart/form-data",
        )

    assert response.status_code == 400
    payload = response.get_json()
    assert "error" in payload
```

- [ ] **Step 2: Run the tests to verify they fail or pass**

Run: `pytest tests/test_tools_limesurvey_handlers.py -v`
Expected: PASS — this exercises existing, correct behavior (this task is pure coverage; the earlier assessment found no bug here, only a coverage gap). If it fails, treat that as a real regression finding to investigate (systematic-debugging), not something to paper over with a weaker assertion.

- [ ] **Step 3: Commit**

```bash
git add tests/test_tools_limesurvey_handlers.py
git commit -m "test: add functional coverage for the limesurvey-to-prism web route"
```

---

### Task 8: Move the misleading "manual" LimeSurvey integration script out of pytest collection

`tests/test_limesurvey_integration_manual.py` has zero `test_*` functions (it's a `if __name__ == "__main__":` script requiring a live server on `localhost:5001` and hardcoded personal Windows paths). Its `test_`-prefixed filename under `tests/` makes it look like automated coverage when pytest silently collects zero tests from it.

**Files:**
- Move: `tests/test_limesurvey_integration_manual.py` → `scripts/limesurvey_integration_manual_check.py`

**Interfaces:** None (standalone script, no importers found elsewhere in the repo).

- [ ] **Step 1: Confirm nothing else references the old path**

Run: `grep -rn "test_limesurvey_integration_manual" --include="*.py" --include="*.md" --include="*.yml" . | grep -v __pycache__`
Expected: only the file itself (already verified during planning — no other references exist).

- [ ] **Step 2: Move the file and update its own docstring**

```bash
git mv tests/test_limesurvey_integration_manual.py scripts/limesurvey_integration_manual_check.py
```

In the moved file, update the header docstring from:

```python
"""
Comprehensive integration test for all LimeSurvey flows.
Tests against running PRISM Studio instance (http://localhost:5001).

Run with: python tests/test_limesurvey_integration_manual.py
"""
```

to:

```python
"""
Comprehensive manual check for all LimeSurvey flows.
Tests against a running PRISM Studio instance (http://localhost:5001).
Not part of the pytest suite (it needs a live server and local files) —
run it by hand from the repo root when validating LimeSurvey changes.

Run with: python scripts/limesurvey_integration_manual_check.py
"""
```

- [ ] **Step 3: Confirm pytest no longer even considers it and the full suite composition is otherwise unchanged**

Run: `pytest --collect-only -q | tail -5`
Expected: no `limesurvey_integration_manual` entries (there were none contributing actual test items before either, since pytest already found 0 `test_*` functions in it — this step confirms the move didn't add or remove any real collected test, it only relocates a non-test script to where `scripts/` already lives, which `pytest.ini`'s `norecursedirs` already excludes).

- [ ] **Step 4: Commit**

```bash
git add -A scripts/limesurvey_integration_manual_check.py tests/test_limesurvey_integration_manual.py
git commit -m "chore: move manual LimeSurvey integration script out of tests/"
```

---

### Task 9: Remove the always-dead relative-import attempt in `excel_to_survey.py`

`from ...src.converters.item_registry import ...` (three dots) always raises `ImportError` when this module is loaded as `src.converters.excel_to_survey` or `app.src.converters.excel_to_survey` (three dots exceed the top-level package depth in both cases) — the `except ImportError` fallback to an absolute import always runs instead. Confirmed working end-to-end via the fallback branch; the first attempt is dead and misleading (a future "fix" to the dot-count could break the working fallback without anyone noticing, since the outer try silently swallows all failures either way).

**Files:**
- Modify: `app/src/converters/excel_to_survey.py:27-46`

**Interfaces:** None — pure internal cleanup, `ItemRegistry`/`ItemCollisionError`/`merge_survey_versions`/`save_merged_template`/`detect_version_name_from_import` remain module-level names with identical runtime values.

- [ ] **Step 1: Confirm current behavior with the existing test suite (baseline)**

Run: `pytest tests/test_excel_to_survey_multisheet.py -v`
Expected: PASS (baseline — this task must not change this outcome)

- [ ] **Step 2: Simplify the import block**

Replace:

```python
# Import item registry for collision detection
try:
    from ...src.converters.item_registry import ItemRegistry, ItemCollisionError
    from ...src.converters.version_merger import (
        merge_survey_versions,
        save_merged_template,
        detect_version_name_from_import,
    )
except ImportError:
    # Fallback for standalone script usage
    try:
        from src.converters.item_registry import ItemRegistry, ItemCollisionError
        from src.converters.version_merger import (
            merge_survey_versions,
            save_merged_template,
            detect_version_name_from_import,
        )
    except ImportError:
        ItemRegistry = None
        ItemCollisionError = None
```

with:

```python
# Import item registry for collision detection
try:
    from src.converters.item_registry import ItemRegistry, ItemCollisionError
    from src.converters.version_merger import (
        merge_survey_versions,
        save_merged_template,
        detect_version_name_from_import,
    )
except ImportError:
    ItemRegistry = None
    ItemCollisionError = None
```

- [ ] **Step 3: Run the existing test suite to confirm no behavior change**

Run: `pytest tests/test_excel_to_survey_multisheet.py tests/test_survey_id_normalizers.py -v`
Expected: PASS, identical results to Step 1's baseline

- [ ] **Step 4: Commit**

```bash
git add app/src/converters/excel_to_survey.py
git commit -m "chore: remove always-dead relative-import attempt in excel_to_survey"
```

---

### Task 10: Clarify that CLI `survey validate` only checks uniqueness, not answer values

`cmd_survey_validate` (CLI) only runs `check_uniqueness` (ID/key uniqueness + schema compliance); it never runs `DatasetValidator`'s allowed-value/range/dtype checks, which only run during Studio GUI conversion. Same command name (`validate`) as the GUI's far more thorough check, with no indication of the difference — anyone scripting around the CLI command to catch bad values would get a false pass. This is a documentation fix, not a behavior change (widening the CLI check is a separate product decision, out of scope here).

**Files:**
- Modify: `app/src/cli/commands/survey.py:549-550` (docstring)
- Modify: `app/src/cli/parser.py:1303-1305` (help text)
- Test: `tests/test_cli_survey_commands_remaining.py` (add to it)

**Interfaces:** None — no signature or behavior change.

- [ ] **Step 1: Write the failing test**

Add to `tests/test_cli_survey_commands_remaining.py` (inside or near the existing `TestCmdSurveyValidate` class):

```python
def test_cmd_survey_validate_docstring_states_uniqueness_only_scope(self):
    from src.cli.commands.survey import cmd_survey_validate

    doc = cmd_survey_validate.__doc__ or ""
    self.assertIn("uniqueness", doc.lower())
    self.assertIn("does not check", doc.lower())


def test_survey_validate_help_states_uniqueness_only_scope(self):
    parser_source = Path("app/src/cli/parser.py").read_text(encoding="utf-8")
    validate_parser_block = parser_source.split('"validate",', 1)[1][:400]
    self.assertIn("uniqueness", validate_parser_block.lower())
```

(Add `from pathlib import Path` to the file's imports if not already present.)

- [ ] **Step 2: Run the tests to verify they fail**

Run: `pytest tests/test_cli_survey_commands_remaining.py -k "uniqueness_only_scope" -v`
Expected: FAIL — current docstring/help text don't mention "uniqueness" or "does not check"

- [ ] **Step 3: Update the docstring in `app/src/cli/commands/survey.py`**

Replace:

```python
def cmd_survey_validate(args):
    """Validate survey library."""
```

with:

```python
def cmd_survey_validate(args):
    """Validate survey library for item-key uniqueness and schema compliance.

    This does not check answer values, allowed-value ranges, or data types —
    those checks run only during Studio GUI survey conversion (DatasetValidator).
    """
```

- [ ] **Step 4: Update the help text in `app/src/cli/parser.py`**

Replace:

```python
    parser_survey_validate = survey_subparsers.add_parser(
        "validate", help="Validate survey library"
    )
```

with:

```python
    parser_survey_validate = survey_subparsers.add_parser(
        "validate",
        help="Validate survey library for item-key uniqueness and schema "
        "compliance (not answer-value/range checks; those run in the Studio "
        "GUI's convert-and-validate step)",
    )
```

- [ ] **Step 5: Run the tests to verify they pass**

Run: `pytest tests/test_cli_survey_commands_remaining.py -k "uniqueness_only_scope or TestCmdSurveyValidate" -v`
Expected: PASS

- [ ] **Step 6: Commit**

```bash
git add app/src/cli/commands/survey.py app/src/cli/parser.py tests/test_cli_survey_commands_remaining.py
git commit -m "docs: clarify CLI survey validate only checks uniqueness, not values"
```

---

## Self-Review Notes

- **Coverage of assessment findings:** temp-file leak (Task 3, both instances found), duplicated gate dict (Task 4), missing `handle_survey_customizer_load` test (Task 5), missing `get_survey_customizer_formats_payload` test (Task 6), missing functional `/api/limesurvey-to-prism` test (Task 7), misleading manual test file (Task 8), dead import (Task 9), CLI/GUI validate scope confusion (Task 10, documentation-only by design). `handle_api_survey_check_project_templates` coverage gap turned out to already be adequately covered by existing tests in `TestSurveyProjectTemplateCheckEndpoint` (verified during planning) — folded into Task 4's regression test instead of a separate task, to avoid duplicating coverage that already exists.
- **Deliberately deferred** (see Global Constraints): the ~500-line duplicate sync/async validate handlers, and the `survey_templates.py:1159` TODO — both need their own investigation pass before a safe fix can be scoped.
- **Task independence:** Tasks 3–10 touch entirely different files and can be executed in any order or in parallel (subagent-driven-development), with one exception: Tasks 3, 5, and 6 share `tests/test_tools_survey_customizer_handlers.py` in a create-then-append relationship (Task 3 creates it, Tasks 5 and 6 each append to it) and must be done in that order. Phase 1 (Tasks 1–2) is sequential internally but independent of all of Phase 2.
