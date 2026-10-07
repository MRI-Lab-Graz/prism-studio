# prism-validator: BIDS check integral and on by default — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** `prism-validator` runs the BIDS check on every run by default, through the single, pip-installed engine `bids-validator-deno` (no system Deno, no jsr download, no Node fallback), and fails closed (`PRISM902`) when the check cannot run.

**Architecture:** `app/src/bids_validator.py` keeps its issue filtering but loses both old backends; it runs the `bids-validator-deno` program (found next to the running Python, then on `PATH`). The standalone command line flips its default (`PrismConfig.run_bids = True`, new `--no-bids`); the library function `validate_dataset(run_bids=False)` and every Studio caller stay as they are. The dependency is declared in `requirements-validator.txt` / `requirements-runtime.txt` with platform markers; the wheel builder and the hash-locked release file follow.

**Tech Stack:** Python 3.10+, argparse, `bids-validator-deno` 3.0.x (PyPI, wraps the PyPI `deno` wheel), pytest, `uv` (lock file), `packaging` (marker test).

**Spec:** `docs/superpowers/specs/2026-10-07-validator-bids-integral-design.md` (the plan corrects one claim of the spec in Task 3: the engine info key is *added* to the machine outputs, it does not exist there yet).

## Global Constraints

- Work on branch `validator-bids-default` (already created from `main`; check `git branch --show-current` before every commit). Every commit message ends with the session's attribution trailer (`Co-Authored-By: ...`); the `git commit -m` lines below omit it for brevity. Never stage `.superpowers/` or any `prism-studio_report_*.txt` (delete those that `tests/verify_repo.py` writes).
- TDD: every task writes its failing tests first and watches them fail for the expected reason.
- **PRISM902 is never a pass.** If the BIDS check is on and cannot run or its output is unreadable, the issue is an ERROR starting with `PRISM902 `.
- The library function `validate_dataset(..., run_bids=False)` keeps its default; `src/api.py`, `src/share_publish.py`, `app/src/web/validation.py`, `app/src/web/blueprints/projects_export_blueprint.py`, `app/src/project_manager.py` and `app/src/web/blueprints/tools_recipes_surveys_handlers.py` are **not edited**. Only the standalone command line changes its default.
- One engine: `bids-validator-deno`. No `deno` lookup, no `jsr:` spec, no `bids-validator` (Node) command anywhere in the code after Task 1.
- Dual-tree rules (CLAUDE.md): `app/src/` files are the live ones (`src.X` resolves to `app/src/X`); new modules would go under `app/src/`. `tests/test_validator_manifest_closure.py` and `.venv/bin/python tests/verify_repo.py --check dual-tree-drift --no-fix` must stay green. `scripts/validator_manifest.txt` needs no new entry (no new module files).
- Item IDs, session labels and similar free strings are untouched by this work.
- The engine reports `exit code 16` with a **valid JSON report** when it found errors: a non-zero exit code with parseable output is a normal result, not a failure.
- Run Python via `.venv/bin/python`; JS tests are not involved. Do not copy or read `.venv/survey_archive_939812.lsa`.
- Platforms: `deno` wheels exist for macOS (x86_64, arm64), Linux (x86_64, aarch64, glibc >= 2.27) and Windows AMD64 only; elsewhere the dependency is skipped by its marker and a run gives `PRISM902` with the hint to use `--no-bids`.

## Review Focus

1. The default flip must not leak into library callers or Studio (Task 2 pins the library default and the explicit values by test).
2. A report with errors comes with exit code 16 — it must keep the issues and not turn into `PRISM902` (Task 1).
3. The `NOT_INCLUDED` filtering of PRISM folders and the citation/recommended-key suppression must still work on the **real 3.0.2 output**, not only on hand-made reports (Task 1 fixture, Task 5 integration).
4. Platforms without a `deno` wheel: the install must still succeed (marker) and a run must fail closed with a clear message (Tasks 1 and 4).
5. `--no-bids` together with `--no-prism` (or `runBids: false` plus `--no-prism`) runs no check at all: exit 2, never `valid: true` (Task 2).

---

### Task 1: The single engine in `app/src/bids_validator.py`

**Files:**
- Modify: `app/src/bids_validator.py` (delete the Deno-`run` and legacy paths; add `find_bids_engine`, `bids_engine_version`)
- Create: `tests/data/bids_validator_3_0_2_wellbeing_report.json` (real engine output, generated in Step 1)
- Rewrite: `tests/test_bids_validator.py`, `tests/test_bids_validator_fail_closed.py`
- Modify: `tests/test_runner.py` (≈ lines 695-715: the `backend_info` mock)

**Interfaces:**
- Produces:
  - `find_bids_engine() -> str | None`
  - `bids_engine_version() -> str` (`"unknown"` when the package metadata is missing)
  - `run_bids_validator(root_dir, verbose=False, placeholders=None, structure_only=False, check_nifti_headers=False, backend_info=None) -> list[tuple[str, str, str]]` — same signature and tuple shape; `backend_info` is filled with `{"engine": "bids-validator-deno", "version": <v>, "spec": "bids-validator-deno@<v>"}` (`spec` stays: `ProjectManager` compares `validator_info["bids_validator"]["spec"]`).
- Consumes: nothing new.

- [ ] **Step 1: Install the engine and save a real report fixture**

```bash
.venv/bin/pip install "bids-validator-deno>=3.0.2,<4"
.venv/bin/bids-validator-deno --version
(cd /tmp && /Users/karl/work/github/prism-studio/.venv/bin/bids-validator-deno /Users/karl/work/github/prism-studio/examples/wellbeing_multi_demo --json --ignoreNiftiHeaders) > tests/data/bids_validator_3_0_2_wellbeing_report.json
grep -c "/Users/\|/private/" tests/data/bids_validator_3_0_2_wellbeing_report.json   # must print 0
.venv/bin/python -c "import json;d=json.load(open('tests/data/bids_validator_3_0_2_wellbeing_report.json'));print(list(d), len(d['issues']['issues']))"
```
Expected: the version line `bids-validator 3.0.x`, `0`, then `['issues', 'summary'] 20` (the count may differ by a few; it must contain `NOT_INCLUDED` entries under `/survey/` folders, a `/DEMO_GUIDE.md` `NOT_INCLUDED`, and a `PARTICIPANT_ID_MISMATCH`). If absolute paths appear (count > 0), replace the dataset root prefix in the file with nothing before committing.

- [ ] **Step 2: Write the failing tests**

Replace `tests/test_bids_validator_fail_closed.py` with:

```python
"""--bids must fail closed: no runnable BIDS engine is an ERROR, not a warning (#162)."""

import os
import sys
from types import SimpleNamespace

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(__file__)), "app", "src"))

import bids_validator
from src.core.validation import determine_exit_code, normalize_issues

ENGINE = "/fake/bin/bids-validator-deno"


def _assert_fails_closed(issues):
    errors = [i for i in issues if i[0] == "ERROR" and i[1].startswith("PRISM902")]
    assert errors, issues
    normalized = normalize_issues(issues)
    assert any(i.code == "PRISM902" for i in normalized)
    assert determine_exit_code(normalized) == 1


def _engine(monkeypatch, run):
    monkeypatch.setattr(bids_validator, "find_bids_engine", lambda: ENGINE)
    monkeypatch.setattr(bids_validator, "bids_engine_version", lambda: "3.0.2")
    monkeypatch.setattr(bids_validator.subprocess, "run", run)


def test_engine_not_found_is_an_error_that_names_the_fix(monkeypatch, tmp_path):
    monkeypatch.setattr(bids_validator, "find_bids_engine", lambda: None)
    issues = bids_validator.run_bids_validator(str(tmp_path))
    _assert_fails_closed(issues)
    assert "bids-validator-deno" in issues[0][1] and "--no-bids" in issues[0][1]


def test_engine_without_output_is_an_error_and_keeps_stderr(monkeypatch, tmp_path):
    _engine(monkeypatch, lambda cmd, **kw: SimpleNamespace(stdout="", stderr="boom", returncode=1))
    issues = bids_validator.run_bids_validator(str(tmp_path))
    _assert_fails_closed(issues)
    assert any("boom" in i[1] for i in issues)


def test_unparseable_output_is_an_error(monkeypatch, tmp_path):
    _engine(monkeypatch, lambda cmd, **kw: SimpleNamespace(stdout="not json", stderr="", returncode=0))
    _assert_fails_closed(bids_validator.run_bids_validator(str(tmp_path)))


def test_engine_that_cannot_be_started_is_an_error(monkeypatch, tmp_path):
    def run(cmd, **kw):
        raise OSError("exec format error")

    _engine(monkeypatch, run)
    issues = bids_validator.run_bids_validator(str(tmp_path))
    _assert_fails_closed(issues)
    assert any("exec format error" in i[1] for i in issues)
```

Rewrite `tests/test_bids_validator.py` as follows. **Keep** the five existing tests that exercise the *Deno-structure* parser, with their assertions unchanged: `test_deno_parser_suppresses_recommended_key_warnings`, `test_deno_parser_suppresses_citation_precedence_conflict`, `test_deno_parser_downgrades_unfetched_annex_content_to_warning`, `test_deno_parser_keeps_genuinely_broken_file_as_error`, and the backend-info test (rewritten below). **Delete** every `test_legacy_*` test and `test_deno_validator_uses_node_modules_directory`. In each kept test, replace the `fake_run` that answers `cmd[:2] == ["deno", "--version"]` / `["deno", "run"]` by the shared helper below (same report dict, same assertions):

```python
import json
import os
import sys
from pathlib import Path
from types import SimpleNamespace

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(__file__)), "app", "src"))

import bids_validator

ENGINE = "/fake/bin/bids-validator-deno"
ROOT = Path(__file__).resolve().parents[1]


def use_engine(monkeypatch, report=None, stdout=None, returncode=0):
    """Pretend bids-validator-deno is installed and prints `report`; return the recorded commands."""
    calls = []
    monkeypatch.setattr(bids_validator, "find_bids_engine", lambda: ENGINE)
    monkeypatch.setattr(bids_validator, "bids_engine_version", lambda: "3.0.2")

    def fake_run(cmd, **kw):
        calls.append(cmd)
        out = stdout if stdout is not None else json.dumps(report or {"issues": {"issues": []}})
        return SimpleNamespace(stdout=out, stderr="", returncode=returncode)

    monkeypatch.setattr(bids_validator.subprocess, "run", fake_run)
    return calls
```

(e.g. a kept parser test becomes `use_engine(monkeypatch, deno_report); issues = bids_validator.run_bids_validator(str(tmp_path)); <unchanged assertions>`; the annex test keeps creating its broken symlink and passing the same arguments.) Then add these new tests:

```python
def test_engine_is_found_next_to_python_before_path(monkeypatch, tmp_path):
    name = "bids-validator-deno.exe" if sys.platform == "win32" else "bids-validator-deno"
    local = tmp_path / name
    local.write_text("")
    monkeypatch.setattr(sys, "executable", str(tmp_path / "python"))
    monkeypatch.setattr(bids_validator.shutil, "which", lambda n: "/elsewhere/" + n)
    assert bids_validator.find_bids_engine() == str(local)


def test_engine_falls_back_to_path_then_none(monkeypatch, tmp_path):
    monkeypatch.setattr(sys, "executable", str(tmp_path / "python"))
    monkeypatch.setattr(bids_validator.shutil, "which", lambda n: "/usr/bin/" + n)
    assert bids_validator.find_bids_engine() == "/usr/bin/bids-validator-deno"
    monkeypatch.setattr(bids_validator.shutil, "which", lambda n: None)
    assert bids_validator.find_bids_engine() is None


def test_command_line_is_the_engine_and_ignores_nifti_headers_by_default(monkeypatch, tmp_path):
    calls = use_engine(monkeypatch)
    bids_validator.run_bids_validator(str(tmp_path))
    bids_validator.run_bids_validator(str(tmp_path), check_nifti_headers=True)
    assert calls == [
        [ENGINE, str(tmp_path), "--json", "--ignoreNiftiHeaders"],
        [ENGINE, str(tmp_path), "--json"],
    ]


def test_backend_info_names_the_engine_and_its_version(monkeypatch, tmp_path):
    use_engine(monkeypatch)
    info = {}
    bids_validator.run_bids_validator(str(tmp_path), backend_info=info)
    assert info == {
        "engine": "bids-validator-deno",
        "version": "3.0.2",
        "spec": "bids-validator-deno@3.0.2",
    }


def test_a_report_with_errors_and_exit_code_16_keeps_its_issues(monkeypatch, tmp_path):
    report = {"issues": {"issues": [{"code": "JSON_KEY_REQUIRED", "severity": "error", "location": "/dataset_description.json"}]}}
    use_engine(monkeypatch, report, returncode=16)
    issues = bids_validator.run_bids_validator(str(tmp_path))
    assert [i[0] for i in issues] == ["ERROR"]
    assert not any(i[1].startswith("PRISM902") for i in issues)


def test_real_3_0_2_output_keeps_real_problems_and_silences_prism_folders(monkeypatch):
    dataset = ROOT / "examples" / "wellbeing_multi_demo"
    fixture = ROOT / "tests" / "data" / "bids_validator_3_0_2_wellbeing_report.json"
    use_engine(monkeypatch, stdout=fixture.read_text(encoding="utf-8"), returncode=16)
    messages = [i[1] for i in bids_validator.run_bids_validator(str(dataset))]
    not_included = [m for m in messages if m.startswith("[BIDS] NOT_INCLUDED")]
    assert not_included, "the real DEMO_GUIDE.md problem must stay"
    assert all("/survey/" not in m for m in not_included)
    assert any("PARTICIPANT_ID_MISMATCH" in m for m in messages)
    assert not any("JSON_KEY_RECOMMENDED" in m for m in messages)
```

In `tests/test_runner.py` replace the mock's `backend_info.update({"engine": "deno", "spec": "jsr:@bids/validator@2.4.1"})` and the matching expected dict (≈ lines 701 and 712) by `{"engine": "bids-validator-deno", "version": "3.0.2", "spec": "bids-validator-deno@3.0.2"}`.

- [ ] **Step 3: Run to verify failure**

Run: `.venv/bin/python -m pytest tests/test_bids_validator.py tests/test_bids_validator_fail_closed.py tests/test_runner.py -q -p no:cacheprovider`
Expected: FAIL (`AttributeError: module 'bids_validator' has no attribute 'find_bids_engine'`, and the unchanged runner expectations).

- [ ] **Step 4: Implement**

In `app/src/bids_validator.py`:

1. Replace the imports and the `DENO_BIDS_VALIDATOR_SPEC` line (lines 6-12) with:

```python
import importlib.metadata
import json
import os
import shutil
import subprocess
import sys
from functools import lru_cache
from pathlib import Path
from typing import List, Optional, Set, Tuple

BIDS_ENGINE_COMMAND = "bids-validator-deno"
BIDS_ENGINE_PACKAGE = "bids-validator-deno"


def find_bids_engine() -> Optional[str]:
    """The bids-validator-deno program: next to the running Python first, then on PATH."""
    name = BIDS_ENGINE_COMMAND + (".exe" if sys.platform == "win32" else "")
    local = Path(sys.executable).parent / name
    if local.is_file():
        return str(local)
    return shutil.which(BIDS_ENGINE_COMMAND)


def bids_engine_version() -> str:
    try:
        return importlib.metadata.version(BIDS_ENGINE_PACKAGE)
    except importlib.metadata.PackageNotFoundError:
        return "unknown"
```

2. Update the module docstring to "BIDS validator integration for PRISM: runs the bids-validator-deno engine and filters its report." and the `backend_info` docstring entry to `({"engine": "bids-validator-deno", "version": ..., "spec": ...})`.
3. Remove the local variable `deno_failure_message = None` (≈ line 200).
4. Replace everything from `# 1. Try Deno-based validator (modern)` (≈ line 219) down to and including the final `return issues` (≈ line 608) by the block below. The report-parsing loop (the body of `for issue in issue_list:` and the three `if verbose and silenced_...` prints) is **moved unchanged** into the `else`-less main flow after the guards — copy it as it is today, only de-indented one level and reading `bids_report` from the parsed JSON:

```python
    def _fail(reason: str) -> List[Tuple[str, str, str]]:
        issues.append(("ERROR", f"PRISM902 BIDS validator requested but {reason}", root_dir))
        return issues

    engine = find_bids_engine()
    if engine is None:
        return _fail(
            "not available: the bids-validator-deno program was not found next to "
            "Python or on PATH. Reinstall prism-validator (it depends on "
            "bids-validator-deno) or run with --no-bids"
        )

    version = bids_engine_version()
    print(f"   Using bids-validator-deno {version}")
    if backend_info is not None:
        backend_info.update(
            {
                "engine": "bids-validator-deno",
                "version": version,
                "spec": f"bids-validator-deno@{version}",
            }
        )

    command = [engine, root_dir, "--json"]
    if not check_nifti_headers:
        command.append("--ignoreNiftiHeaders")
    try:
        process = subprocess.run(
            command, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True
        )
    except OSError as exc:
        return _fail(f"could not be started: {exc}")

    if not process.stdout:
        stderr_msg = (process.stderr or "").strip()
        detail = f" Stderr: {stderr_msg}" if stderr_msg else ""
        return _fail(f"produced no output (exit code {process.returncode}).{detail}")
    try:
        bids_report = json.loads(process.stdout)
    except json.JSONDecodeError:
        return _fail(f"its output could not be parsed (exit code {process.returncode})")

    # (moved unchanged: the issue_list extraction, the for-loop over issues with the
    # citation / recommended-key / placeholder / NOT_INCLUDED filtering and message
    # building, and the three verbose "Silenced ..." prints; ends with `return issues`)
```

Delete the legacy-report block entirely (the `bids-validator --version` check, the `errors`/`warnings` loop, and the `BIDS Validator failed to run` fallback). Remove `from functools import lru_cache` only if it is no longer used (it is, by `_is_prism_only_container_location`; keep it).

- [ ] **Step 5: Run tests**

Run: `.venv/bin/python -m pytest tests/test_bids_validator.py tests/test_bids_validator_fail_closed.py tests/test_runner.py tests/test_validator_manifest_closure.py -q -p no:cacheprovider`
Then: `grep -n "deno\|jsr:\|legacy" app/src/bids_validator.py` — the only hits allowed are the `bids-validator-deno` names and comments about the Deno-structure report (rename that comment to "engine report").
Expected: all PASS. If a kept parser test fails because its hand-made report lacks keys the engine always has, extend the report, never the production code.

- [ ] **Step 6: Commit**

```bash
git add app/src/bids_validator.py tests/test_bids_validator.py tests/test_bids_validator_fail_closed.py tests/test_runner.py tests/data/bids_validator_3_0_2_wellbeing_report.json
git commit -m "feat(validator): run only the bids-validator-deno engine; drop system Deno and the Node fallback"
```

---

### Task 2: BIDS on by default; `--no-bids`

**Files:**
- Modify: `app/src/config.py` (l.81, l.204, `merge_cli_args` l.316)
- Modify: `app/prism.py` (the `--bids` argument ≈ l.196-200, `--no-prism` help ≈ l.217-220, flags block ≈ l.446-447)
- Create: `tests/test_cli_bids_flags.py`
- Modify: `tests/test_config_app_settings.py` (l.61), and any test that runs `app/prism.py` on a synthetic dataset and expects PRISM-only results (add `--no-bids`)

**Interfaces:**
- Consumes: Task 1 (nothing at the call level).
- Produces: `PrismConfig.run_bids` defaults to `True`; `.prismrc.json` `runBids` defaults to `true`; CLI flags `--bids` / `--no-bids` (mutually exclusive); exit code 2 with a message on stderr when no check would run (`--no-bids --no-prism`, or `runBids: false` with `--no-prism`).

- [ ] **Step 1: Write the failing tests**

Create `tests/test_cli_bids_flags.py`:

```python
"""The command line runs the BIDS check by default; --no-bids skips it (spec 2026-10-07)."""

import inspect
import json
import os
import sys

import pytest

APP = os.path.join(os.path.dirname(os.path.dirname(__file__)), "app")
sys.path.insert(0, APP)
sys.path.insert(0, os.path.join(APP, "src"))

import prism  # noqa: E402
from stats import DatasetStats  # noqa: E402


@pytest.fixture
def seen(monkeypatch):
    calls = {}

    def spy(dataset, **kwargs):
        calls.update(kwargs)
        return [], DatasetStats()

    monkeypatch.setattr(prism, "validate_dataset", spy)
    return calls


def run(monkeypatch, tmp_path, *flags, config=None):
    if config is not None:
        (tmp_path / ".prismrc.json").write_text(json.dumps(config), encoding="utf-8")
    monkeypatch.setattr(sys, "argv", ["prism", str(tmp_path), "--json", *flags])
    with pytest.raises(SystemExit) as exc:
        prism.main()
    return exc.value.code


def test_bids_runs_by_default(monkeypatch, tmp_path, seen):
    run(monkeypatch, tmp_path)
    assert seen["run_bids"] is True and seen["run_prism"] is True


def test_no_bids_skips_it(monkeypatch, tmp_path, seen):
    run(monkeypatch, tmp_path, "--no-bids")
    assert seen["run_bids"] is False and seen["run_prism"] is True


def test_bids_flag_is_still_accepted(monkeypatch, tmp_path, seen):
    run(monkeypatch, tmp_path, "--bids")
    assert seen["run_bids"] is True


def test_config_can_turn_it_off_and_the_flag_turns_it_back_on(monkeypatch, tmp_path, seen):
    run(monkeypatch, tmp_path, config={"runBids": False})
    assert seen["run_bids"] is False
    seen.clear()
    run(monkeypatch, tmp_path, "--bids", config={"runBids": False})
    assert seen["run_bids"] is True


def test_bids_and_no_bids_together_are_a_usage_error(monkeypatch, tmp_path, seen):
    assert run(monkeypatch, tmp_path, "--bids", "--no-bids") == 2
    assert not seen


def test_a_run_with_no_checks_is_an_error_never_valid(monkeypatch, tmp_path, seen, capsys):
    assert run(monkeypatch, tmp_path, "--no-bids", "--no-prism") == 2
    assert run(monkeypatch, tmp_path, "--no-prism", config={"runBids": False}) == 2
    assert not seen
    assert "no checks" in capsys.readouterr().err.lower()


def test_library_default_and_studio_callers_are_untouched():
    from runner import validate_dataset

    assert inspect.signature(validate_dataset).parameters["run_bids"].default is False
```

In `tests/test_config_app_settings.py` change line 61 `assert config.run_bids is False` to `assert config.run_bids is True`.

- [ ] **Step 2: Run to verify failure**

Run: `.venv/bin/python -m pytest tests/test_cli_bids_flags.py tests/test_config_app_settings.py -q -p no:cacheprovider`
Expected: FAIL (default is still False; `--no-bids` unknown).

- [ ] **Step 3: Implement**

`app/src/config.py`: `run_bids: bool = True  # The BIDS check is part of every run; --no-bids / "runBids": false skips it`; `run_bids=data.get("runBids", True),`; in `merge_cli_args` replace the `bids` branch with

```python
    if getattr(args, "bids", False):
        config.run_bids = True
    if getattr(args, "no_bids", False):
        config.run_bids = False
```

`app/prism.py`: replace the `--bids` `add_argument` block with

```python
    bids_group = parser.add_mutually_exclusive_group()
    bids_group.add_argument(
        "--bids",
        action="store_true",
        help="Run the BIDS validator (this is the default; use it to override "
        '"runBids": false in .prismrc.json)',
    )
    bids_group.add_argument(
        "--no-bids",
        action="store_true",
        help="Skip the BIDS validator and run only the PRISM checks",
    )
```

change the `--no-prism` help to `"Skip PRISM-specific validation (only the BIDS validator runs)"`, and after `run_prism = not args.no_prism` add

```python
    if not run_bids and not run_prism:
        print(
            "❌ No checks to run: --no-prism skips PRISM and BIDS is switched off "
            "(--no-bids or runBids=false)",
            file=sys.stderr,
        )
        sys.exit(2)
```

- [ ] **Step 4: Run the new tests, then adapt the rest of the suite**

Run: `.venv/bin/python -m pytest tests/test_cli_bids_flags.py tests/test_config_app_settings.py -q -p no:cacheprovider` — Expected: PASS.
Then run the whole suite `.venv/bin/python -m pytest -q -p no:cacheprovider` (needs Task 1's engine in the venv; it is installed). Tests that call `app/prism.py` as a subprocess on tiny synthetic datasets and assert PRISM-only results (start with `tests/test_validator_cli_json_contract.py`, `tests/test_validator_wheel.py` is separate, Task 4) now also run the BIDS check: add `--no-bids` to those commands when the test is about PRISM behaviour or the JSON contract, **do not weaken any assertion**. A test that is about "valid"/exit 0 on a synthetic dataset keeps BIDS on only if the dataset is truly BIDS-valid (add `README`/authors as needed); otherwise add `--no-bids`. Report every test you touched and why. Expected failures after this step: only the three known pre-existing ones (`tests/test_verify_repo_dual_tree_drift.py::test_accepts_symlinked_pair`, `tests/test_validator_no_fake_environment.py::test_fake_environment_package_is_gone`, `tests/e2e/test_validate_flows.py::test_an_empty_project_says_there_is_no_data_instead_of_passing`).

- [ ] **Step 5: Commit**

```bash
git add app/src/config.py app/prism.py tests/
git commit -m "feat(validator): run the BIDS check by default; add --no-bids"
```

---

### Task 3: Engine info in the machine-readable outputs

**Files:**
- Modify: `app/src/stats.py` (module-level helper), `app/src/core/validation.py` (`build_validation_report`), `src/formatters.py` (`to_json`)
- Test: `tests/test_formatters.py`, `tests/test_validator_cli_json_contract.py`
- Modify: `docs/superpowers/specs/2026-10-07-validator-bids-integral-design.md` (correct one sentence)

**Interfaces:**
- Produces: `stats.bids_validator_info(stats) -> dict` (empty dict when BIDS did not run); both JSON outputs (`--json`, `--format json`) gain a top-level `"bids_validator"` object (`{"engine", "version", "spec"}`) **only when the BIDS check ran**.

- [ ] **Step 1: Write the failing tests**

Add to `tests/test_formatters.py` (adapt the import style to the file's existing one):

```python
from types import SimpleNamespace

INFO = {"engine": "bids-validator-deno", "version": "3.0.2", "spec": "bids-validator-deno@3.0.2"}


def test_json_format_reports_the_bids_engine_only_when_it_ran():
    ran = SimpleNamespace(validator_info={"bids_validator": INFO})
    assert json.loads(format_output([], "/d", "json", stats=ran))["bids_validator"] == INFO
    skipped = SimpleNamespace(validator_info={"prism_schema_versions": {}})
    assert "bids_validator" not in json.loads(format_output([], "/d", "json", stats=skipped))
    assert "bids_validator" not in json.loads(format_output([], "/d", "json", stats=None))
```

and to `tests/test_validator_cli_json_contract.py` a unit-level test for the other output:

```python
def test_json_report_carries_the_bids_engine_only_when_it_ran():
    from types import SimpleNamespace
    from src.core.validation import build_validation_report

    ran = SimpleNamespace(validator_info={"bids_validator": {"engine": "bids-validator-deno", "version": "3.0.2", "spec": "x"}})
    assert build_validation_report("/d", "stable", [], ran)["bids_validator"]["version"] == "3.0.2"
    assert "bids_validator" not in build_validation_report("/d", "stable", [], SimpleNamespace())
```

- [ ] **Step 2: Run to verify failure**

Run: `.venv/bin/python -m pytest tests/test_formatters.py tests/test_validator_cli_json_contract.py -q -p no:cacheprovider -k bids_engine`
Expected: FAIL (`KeyError: 'bids_validator'`).

- [ ] **Step 3: Implement**

Append to `app/src/stats.py`:

```python
def bids_validator_info(stats) -> dict:
    """{"engine", "version", "spec"} of the BIDS engine that ran, or {} when BIDS did not run."""
    info = (getattr(stats, "validator_info", None) or {}).get("bids_validator")
    return dict(info) if info else {}
```

In `src/formatters.py` add `from stats import bids_validator_info` next to its other bare imports, and change `to_json`:

```python
def to_json(issues, path, stats) -> str:
    """JSON report; `valid` is True iff no ERROR-severity issue (as the exit code)."""
    summary = summarize_issues(issues)
    report = {
        "valid": summary["errors"] == 0,
        "issues": [i.to_dict() for i in issues],
        "summary": summary,
    }
    if bids_validator_info(stats):
        report["bids_validator"] = bids_validator_info(stats)
    return json.dumps(report, indent=2)
```

In `app/src/core/validation.py` import the helper with the same bare-first/`src.` fallback style the file already uses (`from stats import bids_validator_info` / `from src.stats import ...`) and, in `build_validation_report`, build the dict as `report = {...}` (unchanged keys) then `if bids_validator_info(stats): report["bids_validator"] = bids_validator_info(stats)`; `return report`.

In the spec, replace the sentence "(the existing `bids_validator` key keeps its place)" by "(a new top-level `bids_validator` key in `--json` and `--format json`, absent with `--no-bids`)".

- [ ] **Step 4: Run tests**

Run: `.venv/bin/python -m pytest tests/test_formatters.py tests/test_validator_cli_json_contract.py tests/test_validator_manifest_closure.py tests/test_web_formatting.py -q -p no:cacheprovider`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add app/src/stats.py app/src/core/validation.py src/formatters.py tests docs/superpowers/specs/2026-10-07-validator-bids-integral-design.md
git commit -m "feat(validator): report the BIDS engine and version in --json and --format json"
```

---

### Task 4: Packaging — dependency, lock file, wheel

**Files:**
- Modify: `requirements-validator.txt`, `requirements-runtime.txt`, `requirements-release.lock` (regenerated), `scripts/build_validator_wheel.py`
- Create: `tests/test_validator_requirements.py`
- Modify: `tests/test_validator_wheel.py`

**Interfaces:**
- Consumes: Task 1 (the engine name), Task 3 (`bids_validator` key in the JSON).
- Produces: both requirements files declare `bids-validator-deno>=3.0.2,<4` with the platform marker below and no longer list the PyPI `bids-validator`; the wheel metadata carries that requirement; the wheel builder writes dependencies as JSON strings so markers with quotes survive.

The marker (one line, used verbatim in both files):

```
bids-validator-deno>=3.0.2,<4; sys_platform == "darwin" or (sys_platform == "linux" and platform_machine in "x86_64 aarch64") or (sys_platform == "win32" and platform_machine == "AMD64")
```

- [ ] **Step 1: Write the failing tests**

`tests/test_validator_requirements.py`:

```python
"""The validator depends on bids-validator-deno exactly where a deno wheel exists (spec 2026-10-07)."""

from pathlib import Path

import pytest

packaging_requirements = pytest.importorskip("packaging.requirements")

ROOT = Path(__file__).resolve().parents[1]


def _requirement(name):
    for line in (ROOT / name).read_text(encoding="utf-8").splitlines():
        if line.strip() and not line.lstrip().startswith("#"):
            req = packaging_requirements.Requirement(line)
            if req.name == "bids-validator-deno":
                return req
    raise AssertionError(f"bids-validator-deno missing from {name}")


@pytest.mark.parametrize("name", ["requirements-validator.txt", "requirements-runtime.txt"])
def test_bids_engine_is_declared_with_a_version_range(name):
    req = _requirement(name)
    assert req.specifier.contains("3.0.2") and not req.specifier.contains("4.0.0")
    assert req.specifier.contains("3.9.9") and not req.specifier.contains("3.0.1")


def _supported(machine, platform):
    env = {"sys_platform": platform, "platform_machine": machine, "platform_system": ""}
    return _requirement("requirements-validator.txt").marker.evaluate(env)


@pytest.mark.parametrize(
    "platform,machine,expected",
    [
        ("darwin", "arm64", True),
        ("darwin", "x86_64", True),
        ("linux", "x86_64", True),
        ("linux", "aarch64", True),
        ("win32", "AMD64", True),
        ("win32", "ARM64", False),
        ("linux", "riscv64", False),
        ("linux", "s390x", False),
    ],
)
def test_marker_matches_the_platforms_with_a_deno_wheel(platform, machine, expected):
    assert _supported(machine, platform) is expected


def test_the_unused_pypi_bids_validator_is_gone_from_both_files():
    for name in ("requirements-validator.txt", "requirements-runtime.txt"):
        names = {
            packaging_requirements.Requirement(l).name
            for l in (ROOT / name).read_text(encoding="utf-8").splitlines()
            if l.strip() and not l.lstrip().startswith("#")
        }
        assert "bids-validator" not in names, name


def test_both_files_use_the_same_marker():
    a, b = (_requirement(n) for n in ("requirements-validator.txt", "requirements-runtime.txt"))
    assert str(a.marker) == str(b.marker)
```

Add to `tests/test_validator_wheel.py` (reuse its `wheel` fixture and imports):

```python
def test_wheel_depends_on_bids_validator_deno_not_on_the_pypi_bids_validator(wheel):
    import re

    zf = zipfile.ZipFile(wheel)
    meta = zf.read(next(n for n in zf.namelist() if n.endswith("/METADATA"))).decode()
    assert re.search(r"^Requires-Dist: bids-validator-deno", meta, re.M)
    assert "sys_platform" in re.search(r"^Requires-Dist: bids-validator-deno.*$", meta, re.M).group(0)
    assert not re.search(r"^Requires-Dist: bids-validator(?!-deno)", meta, re.M)
```

and, inside `test_installed_wheel_runs_in_clean_venv` after the existing `project.json` block, a BIDS-on run:

```python
    run = subprocess.run([exe, str(ds), "--format", "json"], capture_output=True, text=True)
    report = json.loads(run.stdout)
    assert report["bids_validator"]["engine"] == "bids-validator-deno", run.stdout
    assert not any(i["code"] == "PRISM902" for i in report["issues"]), run.stdout
```

(add `import json` at the top of the file.)

- [ ] **Step 2: Run to verify failure**

Run: `.venv/bin/python -m pytest tests/test_validator_requirements.py tests/test_validator_wheel.py -q -p no:cacheprovider`
Expected: FAIL (dependency missing; the wheel test needs network, as before).

- [ ] **Step 3: Implement**

`requirements-validator.txt` becomes (keep the existing header comment, update it to say the BIDS engine is part of the validator):

```
jsonschema
PyYAML>=6.0.3
defusedxml
# The BIDS check runs by default and needs this engine; the PyPI package `deno` it depends on
# ships the Deno runtime as a wheel for these platforms only, so the requirement is skipped elsewhere
# (a run then reports PRISM902 and the hint to use --no-bids).
bids-validator-deno>=3.0.2,<4; sys_platform == "darwin" or (sys_platform == "linux" and platform_machine in "x86_64 aarch64") or (sys_platform == "win32" and platform_machine == "AMD64")
```

`requirements-runtime.txt`: delete the bare `bids-validator` line and add the same comment and `bids-validator-deno` line (keep `bidsschematools>=2.0.0`; check with `grep -rn "bidsschematools" app src --include=*.py` — if nothing imports it, **leave it anyway**, removing it is out of scope).

`scripts/build_validator_wheel.py`: add `import json` and replace `deps=repr(deps).replace("'", '"')` by `deps=json.dumps(deps)` (JSON strings are valid TOML strings and keep the quotes inside markers).

Regenerate the hash-locked release file with the command from its own header and check the diff:

```bash
uv pip compile requirements-runtime.txt requirements-build.txt --universal --python-version 3.10 --generate-hashes -o requirements-release.lock
git diff --stat requirements-release.lock
git diff requirements-release.lock | grep -E "^[+-][a-z0-9-]+==" 
```
Expected: `bids-validator-deno` and `deno` added, `bids-validator` removed (and nothing else, or only packages that were pulled in solely by it); any unrelated version bump means `uv` upgraded pins — redo the command adding `--upgrade-package` for nothing, i.e. keep the existing pins by running it once more (uv keeps pins found in the output file); never commit unrelated bumps. Then `.venv/bin/python -m pytest tests/test_workflow_hardening.py -q -p no:cacheprovider` must pass.

- [ ] **Step 4: Run tests**

Run: `.venv/bin/python -m pytest tests/test_validator_requirements.py tests/test_validator_wheel.py tests/test_workflow_hardening.py tests/test_validator_runs_without_pandas.py -q -p no:cacheprovider` (network needed for the wheel tests).
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add requirements-validator.txt requirements-runtime.txt requirements-release.lock scripts/build_validator_wheel.py tests/test_validator_requirements.py tests/test_validator_wheel.py
git commit -m "build(validator): depend on bids-validator-deno where a deno wheel exists; drop the unused bids-validator"
```

---

### Task 5: Real integration tests with the installed engine

**Files:**
- Create: `tests/test_bids_validator_integration.py`

**Interfaces:**
- Consumes: Task 1 (`find_bids_engine`, `run_bids_validator`), the installed engine.

- [ ] **Step 1: Write the tests**

```python
"""bids-validator-deno for real: no mocks (spec 2026-10-07). Skipped locally when the engine
is not installed, but CI must have it (the dependency is an ordinary one)."""

import json
import os
import sys
from pathlib import Path

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(__file__)), "app", "src"))

import bids_validator

ROOT = Path(__file__).resolve().parents[1]
ENGINE = bids_validator.find_bids_engine()
needs_engine = pytest.mark.skipif(ENGINE is None, reason="bids-validator-deno is not installed")


def test_engine_is_installed_in_ci():
    if os.environ.get("CI"):
        assert ENGINE is not None, "CI must install bids-validator-deno (requirements-runtime.txt)"


@needs_engine
def test_a_minimal_dataset_has_no_bids_error(tmp_path):
    (tmp_path / "dataset_description.json").write_text(
        json.dumps({"Name": "T", "BIDSVersion": "1.9.0", "DatasetType": "raw", "Authors": ["A", "B"]})
    )
    issues = bids_validator.run_bids_validator(str(tmp_path))
    assert not [i for i in issues if i[0] == "ERROR"], issues


@needs_engine
def test_a_real_bids_error_is_reported_as_an_error(tmp_path):
    (tmp_path / "dataset_description.json").write_text(json.dumps({"Name": "T"}))  # no BIDSVersion
    issues = bids_validator.run_bids_validator(str(tmp_path))
    assert [i for i in issues if i[0] == "ERROR"], issues
    assert not any(i[1].startswith("PRISM902") for i in issues)


@needs_engine
def test_prism_folders_of_the_demo_dataset_draw_no_false_not_included_errors():
    info = {}
    issues = bids_validator.run_bids_validator(
        str(ROOT / "examples" / "wellbeing_multi_demo"), backend_info=info
    )
    assert info["engine"] == "bids-validator-deno" and info["version"] != "unknown"
    not_included = [i[1] for i in issues if i[1].startswith("[BIDS] NOT_INCLUDED")]
    assert all("/survey/" not in m for m in not_included), not_included
    assert not any(i[1].startswith("PRISM902") for i in issues)
```

- [ ] **Step 2: Run**

Run: `.venv/bin/python -m pytest tests/test_bids_validator_integration.py -q -p no:cacheprovider`
Expected: PASS (3 passed, 1 passed — the engine is installed in the venv). If `test_a_real_bids_error_...` does not see an ERROR for a missing `BIDSVersion`, run the engine by hand on that folder, pick the dataset change that really produces an error, and use it (never loosen the assertion).

- [ ] **Step 3: Commit**

```bash
git add tests/test_bids_validator_integration.py
git commit -m "test(validator): integration tests with the real bids-validator-deno engine"
```

---

### Task 6: Installers, docs and housekeeping

**Files:**
- Modify: `install.sh` (the Deno block ≈ l.378-396), `scripts/setup/windows.ps1` (≈ l.127-149)
- Modify: `docs/CLI_REFERENCE.md`, `docs/INSTALLATION.md`, `docs/SECURITY.md` (if it does not exist at the repo root level use `SECURITY.md`), `docs/ERROR_CODES.md` (l.123), `docs/studio/validator.md`, `app/src/issues.py` (l.247), `src/share_publish.py` (l.201 comment), `.gitignore` (l.139-140), `tests/verify_repo.py` (BIDS smoke ≈ l.1700-1775), `docs/superpowers/specs/2026-10-07-validator-bids-integral-design.md` (status line)
- Test: `tests/test_installers_no_deno.py` (create)

**Interfaces:** none (docs and scripts).

- [ ] **Step 1: Write the failing test**

`tests/test_installers_no_deno.py`:

```python
"""Installing PRISM no longer downloads or runs the deno.land installer (spec 2026-10-07)."""

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_installers_do_not_run_the_deno_installer_script():
    for rel in ("install.sh", "scripts/setup/windows.ps1"):
        text = (ROOT / rel).read_text(encoding="utf-8").lower()
        assert "deno.land" not in text, rel
        assert "install_deno" not in text.replace("$installdeno", "install_deno"), rel


def test_code_has_no_system_deno_or_node_validator_path():
    text = (ROOT / "app" / "src" / "bids_validator.py").read_text(encoding="utf-8")
    assert '"deno"' not in text and "jsr:" not in text and "'bids-validator'" not in text
    assert '"bids-validator"' not in text.replace("bids-validator-deno", "")


def test_error_text_points_at_the_new_fix():
    for rel in ("docs/ERROR_CODES.md", "app/src/issues.py"):
        text = (ROOT / rel).read_text(encoding="utf-8")
        assert "--no-bids" in text, rel
        assert "legacy" not in text.split("PRISM902")[-1][:400].lower(), rel
```

- [ ] **Step 2: Run to verify failure**

Run: `.venv/bin/python -m pytest tests/test_installers_no_deno.py -q -p no:cacheprovider`
Expected: FAIL.

- [ ] **Step 3: Implement**

- `install.sh`: delete the whole step "2. Check for Deno ..." block (the `if ! command -v deno ... fi`); renumber nothing else. `bash -n install.sh` must pass. `scripts/setup/windows.ps1`: delete the matching block; no replacement is needed because the dependency comes with `requirements-runtime.txt`.
- `app/src/issues.py` PRISM902 `fix_hint`: `"Reinstall prism-validator (it includes the BIDS engine bids-validator-deno) or run with --no-bids"`. `docs/ERROR_CODES.md` row: `| \`PRISM902\` | BIDS validator requested but not available | The bids-validator-deno program was not found or failed to run: reinstall prism-validator, or run with \`--no-bids\` |`.
- `src/share_publish.py` l.201: change the comment to `ponytail: PRISM checks only (run_bids=False stays explicit; the share check does not run the BIDS engine).`
- `.gitignore`: delete the two `deno.lock` lines (comment + entry).
- `docs/CLI_REFERENCE.md`: in the validator section document `--no-bids`, that the BIDS check now runs by default (`--bids` is accepted and only overrides `"runBids": false`), that `--no-prism` and `--no-bids` cannot be combined (exit 2), the new `bids_validator` key in both JSON outputs, and how `PRISM902` arises. `docs/INSTALLATION.md`: one paragraph "`pip install prism-validator` includes the BIDS engine (bids-validator-deno and the Deno runtime, about 80 MB installed); platforms without a Deno wheel (Windows on ARM, Alpine/musl, glibc older than 2.27) install but need `--no-bids`". `SECURITY.md`: a paragraph "The BIDS check starts the bundled Deno through the `bids-validator-deno` launcher with read, env, net and write access and permission to run `git` only; network access is allowed, no other program may be started." `docs/studio/validator.md`: update any sentence about `--bids` or about installing Deno (`grep -n "bids\|deno" docs/studio/validator.md`).
- `tests/verify_repo.py`: in the BIDS smoke check (find it with `grep -n "bids-validator" tests/verify_repo.py`) run `bids-validator-deno` instead of `bids-validator`, drop the `has_python_pkg` / `BIDSValidator` fallback branch, and make the "not available" message say `pip install prism-validator`. Keep the rest of the check as it is.
- Spec status line: add "Status: approved, implemented on branch `validator-bids-default`".

- [ ] **Step 4: Run tests**

Run: `bash -n install.sh && .venv/bin/python -m pytest tests/test_installers_no_deno.py tests/test_unit.py tests/test_validator_manifest_closure.py -q -p no:cacheprovider`
Then `.venv/bin/python tests/verify_repo.py --check dual-tree-drift --no-fix` and `--check issue-codes-consistency --no-fix` (delete the report files), then the whole suite (`.venv/bin/python -m pytest -q -p no:cacheprovider`) — only the three known failures may remain.

- [ ] **Step 5: Commit**

```bash
git add install.sh scripts/setup/windows.ps1 docs SECURITY.md app/src/issues.py src/share_publish.py .gitignore tests docs/superpowers/specs
git commit -m "docs(validator): installers and docs for the integral BIDS check; remove the Deno installer steps"
```

---

## After the tasks (not part of this plan's tasks)

Open one pull request for the branch. Release preparation for **1.20.0** is a separate follow-up PR after it merges (same pattern as 1.19.2): the six version strings (`src/__init__.py`, `app/src/__init__.py`, `setup.py`, `CITATION.cff` incl. `date-released`, `codemeta.json`, `docs/conf.py`), `docs/RELEASE_NOTES_v1.20.0.md` (BIDS check on by default and why; `--no-bids` and `"runBids": false` keep the old behaviour; BIDS validator 2.4.1 → 3.0.2 so check codes may differ; the package now includes Deno, ~80 MB; DataLad Desktop and the neurocloud can drop their own Deno download, lock file, `DENO_DIR` and `PATH` handling), the changelog entry, and `tests/test_no_intel_mac_build.py` pointing at the new notes file. The tag `v1.20.0` and the PyPI publish approval stay the project owner's decision.
