# Save Gate, Phase 1 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** A git `pre-commit` hook in every PRISM dataset refuses any save (PRISM's or manual `datalad save`/`git commit`) that would leave the dataset with validator errors, and PRISM's own edit operations keep working on a tree left dirty by a refused save.

**Architecture:** One backend module `src/save_gate.py` (check, hook install, status) reusing `src/share_publish.py` (validation, git helpers, audit, hook plumbing). A nested `sub-*` commit validates only that subject (new `validate_subject_only` in `app/src/runner.py`); a top-level commit runs the full validation. The CLI (`prism_tools save-gate`) is the hook's entry point. `run_tracked_mutation` falls back to `datalad run --explicit` when the pre-run autosave is refused.

**Tech Stack:** Python, git hooks (POSIX sh), DataLad 1.6 (`datalad run --explicit`), argparse CLI, pytest with real git/DataLad fixtures.

**Spec:** `docs/superpowers/specs/2026-10-02-save-gate-design.md` (Phase 2, the per-HEAD validation cache, is a separate later plan.)

## Deviations from the spec (decided while planning, each cheaper and equivalent)

1. **Hook is the single enforcement point.** Every commit path (`datalad save`, `datalad run`, `ProjectManager._run_datalad_save`, manual git) reaches the hook, so no duplicate pre-check is added to `run_datalad_save`/`run_datalad_run`; the hook's refusal text comes back in their `message`.
2. **No explicit "scaffold" exemption flag.** Project creation is not gated because hooks are installed *after* the creation saves. The only exemption is the first save of a *top-level* dataset (commit count ≤ 1); nested `sub-*` datasets have no exemption.
3. **Fixing after a refusal** is implemented in `run_tracked_mutation` only (see Task 6). The separate runner in `src/repo_rewrite_datalad_runner.py` keeps its current behavior and is a follow-up.

## Global Constraints

- Strict: any validator **error** refuses; warnings never block; BIDS validator off (PRISM checks only).
- Exemption, exhaustive: the first save of a top-level dataset (`git rev-list --count HEAD` ≤ 1). Nothing else.
- The hook fails closed: if `prism_tools` cannot be found it blocks the commit, and the message contains `PRISM save gate`.
- Never overwrite a foreign hook; hooks are per repository, so install in every dataset root.
- Refusal text always contains the marker `PRISM save gate` (constant `SAVE_GATE_MARKER`).
- CLI code must not import `src.web.*` or `flask` (`tests/test_cli_no_web_layer_imports.py`).
- No tracked files are written into datasets; the audit log stays in `<git-dir>/prism/publish.jsonl`.
- Branch `feat/save-gate`; run `git branch --show-current` before every commit. Commit trailer: `Co-Authored-By: Claude Sonnet 5.5 <noreply@anthropic.com>`.
- Session labels are free-form strings; never normalize (not touched here).
- Dual-tree rule (CLAUDE.md): `src/save_gate.py` lives only under top-level `src/`; confirm with `python3 -c "import src.save_gate as m; print(m.__file__)"`. `validate_subject_only` goes into the existing `app/src/runner.py` (no mirror under `src/`).

## Review Focus

- The first save of each nested `sub-*` dataset must be gated, not exempted (Task 2).
- During project creation the scaffold saves must not be refused: hooks are installed last (Task 5).
- A missing `prism_tools` must block, and PRISM's own saves must still work, so PRISM sets `PRISM_TOOLS` for its child processes (Tasks 3, 5).
- After a refused save, a PRISM mutation must still apply its change, must not attempt a useless emergency save, and the final save stays gated (Task 6).
- A nested commit must not trigger a full-project validation (quadratic cost on `datalad save -r`); test that `validate_for_publish` is not called for it (Task 2).

---

### Task 1: `validate_subject_only`

**Files:**
- Modify: `app/src/runner.py` (add after `_validate_subject`, ~line 784)
- Modify: `app/src/core/validation.py` (re-export)
- Test: `tests/test_validate_subject_only.py`

**Interfaces:**
- Produces: `validate_subject_only(root_dir: str, subject_id: str, *, schema_version=None, library_path=None) -> tuple[list, DatasetStats]` (issues use the same tuple/Issue shapes as `validate_dataset`); re-exported from `src.core.validation` as `validate_subject_only`.

- [ ] **Step 1: Write the failing test**

```python
# tests/test_validate_subject_only.py
import sys
from pathlib import Path

APP = Path(__file__).resolve().parents[1] / "app"
for p in (APP, APP / "src"):
    if str(p) not in sys.path:
        sys.path.insert(0, str(p))

from src.core.validation import determine_exit_code, validate_subject_only  # noqa: E402


def test_empty_session_folder_is_an_error(tmp_path):
    root = tmp_path / "proj"
    (root / "sub-001" / "ses-01").mkdir(parents=True)
    issues, _stats = validate_subject_only(str(root), "sub-001")
    assert any("Empty directory" in issue[1] for issue in issues)
    assert determine_exit_code(issues) == 1


def test_subject_without_problems_is_clean(tmp_path):
    root = tmp_path / "proj"
    (root / "sub-001").mkdir(parents=True)
    issues, _stats = validate_subject_only(str(root), "sub-001")
    assert issues == []


def test_only_the_named_subject_is_looked_at(tmp_path):
    root = tmp_path / "proj"
    (root / "sub-001").mkdir(parents=True)
    (root / "sub-002" / "ses-01").mkdir(parents=True)  # broken, but not ours
    issues, _stats = validate_subject_only(str(root), "sub-001")
    assert issues == []
```

- [ ] **Step 2: Run to verify failure**

Run: `cd /Users/karl/work/github/prism-studio && python -m pytest tests/test_validate_subject_only.py -v`
Expected: FAIL (`ImportError: cannot import name 'validate_subject_only'`).

- [ ] **Step 3: Implement**

In `app/src/runner.py` after `_validate_subject`:

```python
def validate_subject_only(
    root_dir,
    subject_id,
    *,
    schema_version=None,
    library_path=None,
):
    """Validate one sub-* folder in isolation (what a nested-dataset commit changes).

    Same per-subject checks as `validate_dataset`'s subject loop; the cross-subject
    checks (consistency, participants alignment, procedure) need every subject and
    stay with the full validation. Returns (issues, stats).
    """
    root_dir = os.path.abspath(root_dir)
    schema_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), "schemas")
    schemas = load_all_schemas(schema_dir, version=schema_version)
    validator = DatasetValidator(schemas, library_path=library_path)
    stats = DatasetStats()
    issues = _validate_subject(
        os.path.join(root_dir, subject_id),
        subject_id,
        validator,
        stats,
        root_dir,
        run_prism=True,
        run_bids=False,
        need_procedure_tasks=_project_declares_sessions(root_dir),
    )
    return issues, stats
```

In `app/src/core/validation.py`, next to the existing `validate_dataset` import (same bare-first/`src.` fallback pattern):

```python
try:
    from runner import validate_dataset, validate_subject_only
except ImportError:
    from src.runner import validate_dataset, validate_subject_only
```

- [ ] **Step 4: Run to verify pass**

Run: `python -m pytest tests/test_validate_subject_only.py tests/test_api_runner_import.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git branch --show-current   # feat/save-gate
git add app/src/runner.py app/src/core/validation.py tests/test_validate_subject_only.py
git commit -m "feat(validation): validate_subject_only for nested-dataset commits

Co-Authored-By: Claude Sonnet 5.5 <noreply@anthropic.com>"
```

---

### Task 2: `check_save`

**Files:**
- Create: `src/save_gate.py`
- Modify: `src/share_publish.py` (extract the import-with-retry from `validate_for_publish` into `_core_validation()`)
- Modify: `src/datalad_execution.py` (add constant `SAVE_GATE_MARKER = "PRISM save gate"` near the other module constants)
- Test: `tests/test_save_gate_check.py`

**Interfaces:**
- Consumes: `_git`, `_describe`, `validate_for_publish` from `src.share_publish`; `validate_subject_only`, `determine_exit_code` via `src.core.validation` (Task 1).
- Produces: `SAVE_GATE_MARKER` (in `src.datalad_execution`, re-exported by `src.save_gate`); `SaveCheck(allowed: bool, errors: list[str], reason: str)` frozen dataclass, `reason` ∈ `"exempt_initial" | "valid" | "validation_errors" | "validator_crash"`; `check_save(project_root) -> SaveCheck`; `validate_subject_for_save(super_root, subject_id) -> list[str]`; `share_publish._core_validation() -> module` (the imported `src.core.validation`).

- [ ] **Step 1: Write the failing test**

```python
# tests/test_save_gate_check.py
import subprocess

import pytest

import src.save_gate as sg


def git(*args, cwd):
    subprocess.run(["git", "-c", "user.name=t", "-c", "user.email=t@t.t", *args],
                   cwd=cwd, check=True, capture_output=True)


def repo(path, commits):
    path.mkdir(parents=True, exist_ok=True)
    git("init", "-q", cwd=path)
    for i in range(commits):
        (path / f"f{i}").write_text(str(i))
        git("add", ".", cwd=path)
        git("commit", "-q", "-m", f"c{i}", cwd=path)
    return path


@pytest.fixture
def calls(monkeypatch):
    seen = {"full": 0, "subject": []}

    def full(root):
        seen["full"] += 1
        return seen.get("full_result", [])

    def subject(root, sid):
        seen["subject"].append((str(root), sid))
        return seen.get("subject_result", [])

    monkeypatch.setattr(sg, "validate_for_publish", full)
    monkeypatch.setattr(sg, "validate_subject_for_save", subject)
    return seen


def test_first_save_of_a_top_level_dataset_is_exempt(tmp_path, calls):
    result = sg.check_save(repo(tmp_path / "p", commits=1))
    assert result.allowed and result.reason == "exempt_initial" and calls["full"] == 0


def test_empty_repo_first_save_is_exempt(tmp_path, calls):
    result = sg.check_save(repo(tmp_path / "p", commits=0))
    assert result.allowed and result.reason == "exempt_initial"


def test_later_saves_are_gated_and_refused_on_errors(tmp_path, calls):
    calls["full_result"] = ["PRISM101 bad"]
    result = sg.check_save(repo(tmp_path / "p", commits=2))
    assert not result.allowed and result.reason == "validation_errors"
    assert result.errors == ["PRISM101 bad"]


def test_later_save_allowed_when_valid(tmp_path, calls):
    result = sg.check_save(repo(tmp_path / "p", commits=2))
    assert result.allowed and result.reason == "valid"


def test_validator_crash_is_refused(tmp_path, monkeypatch):
    def boom(root):
        raise RuntimeError("kaput")

    monkeypatch.setattr(sg, "validate_for_publish", boom)
    result = sg.check_save(repo(tmp_path / "p", commits=2))
    assert not result.allowed and result.reason == "validator_crash"
    assert "kaput" in result.errors[0]


def make_super_with_subject(tmp_path):
    sub_src = repo(tmp_path / "sub-src", commits=1)
    sup = repo(tmp_path / "proj", commits=1)
    subprocess.run(
        ["git", "-c", "protocol.file.allow=always", "-c", "user.name=t", "-c", "user.email=t@t.t",
         "submodule", "add", "-q", str(sub_src), "sub-001"],
        cwd=sup, check=True, capture_output=True,
    )
    git("commit", "-q", "-m", "add sub", cwd=sup)
    return sup, sup / "sub-001"


def test_nested_subject_is_validated_alone_and_never_exempt(tmp_path, calls):
    sup, sub = make_super_with_subject(tmp_path)
    assert sg._commit_count(sub) == 1  # would be exempt if it were top-level
    calls["subject_result"] = ["PRISM201 empty dir"]
    result = sg.check_save(sub)
    assert not result.allowed and result.errors == ["PRISM201 empty dir"]
    assert calls["full"] == 0  # no full-project validation for a nested commit
    assert calls["subject"] == [(str(sup.resolve()), "sub-001")] or calls["subject"][0][1] == "sub-001"


def test_non_subject_submodule_is_validated_as_a_whole(tmp_path, calls):
    sub_src = repo(tmp_path / "x-src", commits=2)
    sup = repo(tmp_path / "proj", commits=1)
    subprocess.run(
        ["git", "-c", "protocol.file.allow=always", "-c", "user.name=t", "-c", "user.email=t@t.t",
         "submodule", "add", "-q", str(sub_src), "derivatives"],
        cwd=sup, check=True, capture_output=True,
    )
    sg.check_save(sup / "derivatives")
    assert calls["full"] == 1 and calls["subject"] == []
```

- [ ] **Step 2: Run to verify failure**

Run: `python -m pytest tests/test_save_gate_check.py -v`
Expected: FAIL (`ModuleNotFoundError: src.save_gate`).

- [ ] **Step 3: Implement**

`src/datalad_execution.py`: add `SAVE_GATE_MARKER = "PRISM save gate"` next to `DATALAD_INSTALL_HINT`.

`src/share_publish.py`: replace the try/except import inside `validate_for_publish` with a helper and use it:

```python
def _core_validation():
    """`src.core.validation`, adding app/ and app/src to sys.path only if the import fails."""
    try:
        import src.core.validation as mod
    except ImportError:
        # Source checkout started without app/ on sys.path; frozen builds never get here.
        import sys

        repo = Path(__file__).resolve().parents[1]
        sys.path[:0] = [str(repo / "app"), str(repo / "app" / "src")]
        import src.core.validation as mod
    return mod


def validate_for_publish(project_root) -> list[str]:
    """Error messages from a full PRISM validation; empty list means valid.

    ponytail: PRISM checks only, no BIDS validator (needs deno on every share).
    """
    core = _core_validation()
    issues, _stats = core.validate_dataset(str(project_root), run_bids=False, run_prism=True)
    return [_describe(i) for i in issues if core.determine_exit_code([i])]
```

`src/save_gate.py`:

```python
"""Save gate: a commit in a PRISM dataset is allowed only if the dataset validates.

Enforced by a git pre-commit hook in every dataset root (see install_save_hooks);
the hook calls `prism_tools save-gate --check`. One implementation: the CLI and
PRISM's own saves go through the same hook. See
docs/superpowers/specs/2026-10-02-save-gate-design.md.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from src.datalad_execution import SAVE_GATE_MARKER
from src.share_publish import _core_validation, _describe, _git, validate_for_publish

__all__ = ["SAVE_GATE_MARKER", "SaveCheck", "check_save", "validate_subject_for_save"]


@dataclass(frozen=True)
class SaveCheck:
    allowed: bool
    errors: list[str]
    reason: str


def _commit_count(root: Path) -> int:
    out = _git(root, "rev-list", "--count", "HEAD")
    return int(out) if out.isdigit() else 0


def _superproject_root(root: Path) -> Path | None:
    out = _git(root, "rev-parse", "--show-superproject-working-tree")
    return Path(out) if out else None


def validate_subject_for_save(super_root, subject_id: str) -> list[str]:
    core = _core_validation()
    issues, _stats = core.validate_subject_only(str(super_root), subject_id)
    return [_describe(i) for i in issues if core.determine_exit_code([i])]


def check_save(project_root) -> SaveCheck:
    root = Path(project_root)
    sup = _superproject_root(root)
    nested_subject = sup is not None and root.name.startswith("sub-")
    # Only the first save of a top-level dataset is exempt (an empty scaffold cannot validate);
    # a nested sub-* dataset's first data save is exactly what must be checked.
    if not nested_subject and _commit_count(root) <= 1:
        return SaveCheck(True, [], "exempt_initial")
    try:
        errors = (
            validate_subject_for_save(sup, root.name) if nested_subject else validate_for_publish(root)
        )
    except Exception as exc:  # fail closed
        return SaveCheck(False, [f"Validation could not run: {exc}"], "validator_crash")
    return SaveCheck(not errors, errors, "valid" if not errors else "validation_errors")
```

Note on `test_nested_subject_is_validated_alone_and_never_exempt`: `git rev-parse --show-superproject-working-tree` may print a resolved path (e.g. `/private/var/...` on macOS); the test's second `or` clause accepts that. Keep both clauses.

- [ ] **Step 4: Run to verify pass**

Run: `python -m pytest tests/test_save_gate_check.py tests/test_share_publish_gate.py -v`
Expected: PASS (the publish-gate tests prove the `_core_validation` refactor changed nothing).

- [ ] **Step 5: Commit**

```bash
git branch --show-current
git add src/save_gate.py src/share_publish.py src/datalad_execution.py tests/test_save_gate_check.py
git commit -m "feat(save-gate): check_save (strict, nested sub-* validated alone)

Co-Authored-By: Claude Sonnet 5.5 <noreply@anthropic.com>"
```

---

### Task 3: pre-commit hook install

**Files:**
- Modify: `src/save_gate.py` (append)
- Test: `tests/test_save_gate_hook.py`

**Interfaces:**
- Consumes: `_hooks_dir`, `HookExistsError`, `NotAGitRepoError`, `_dataset_roots` from `src.share_publish`; `SAVE_GATE_MARKER`.
- Produces: `SAVE_HOOK_MARKER = "# prism-save-gate-hook"`; `install_save_hook(root) -> Path` (raises `HookExistsError` / `NotAGitRepoError`); `install_save_hooks(project_root) -> dict` with keys `installed: list[str]`, `foreign: list[str]` (dataset roots whose existing foreign hook was left alone); `has_save_hook(root) -> bool`.

The hook runs `"$TOOLS" save-gate --check --project "$ROOT" >&2` (refusal text reaches the committer through git/DataLad), blocks when the tool is missing, and never bakes in a path.

- [ ] **Step 1: Write the failing test**

```python
# tests/test_save_gate_hook.py
import os
import shutil
import stat
import subprocess

import pytest

import src.save_gate as sg
from src.share_publish import HookExistsError, NotAGitRepoError


def run(*args, cwd, env=None, check=True):
    return subprocess.run(list(args), cwd=cwd, capture_output=True, text=True, check=check, env=env)


@pytest.fixture
def repo(tmp_path):
    root = tmp_path / "ds"
    run("git", "init", "-q", str(root), cwd=tmp_path)
    (root / "f").write_text("x")
    run("git", "add", "f", cwd=root)
    return root


def fake_tool(tmp_path, exit_code):
    tool = tmp_path / f"prism_tools_{exit_code}"
    tool.write_text(f"#!/bin/sh\necho 'PRISM save gate: fake' \nexit {exit_code}\n")
    tool.chmod(tool.stat().st_mode | stat.S_IEXEC)
    return tool


def commit(root, tool=None):
    env = {**os.environ}
    env.pop("PRISM_TOOLS", None)
    if tool:
        env["PRISM_TOOLS"] = str(tool)
    return run("git", "-c", "user.name=t", "-c", "user.email=t@t.t", "commit", "-q", "-m", "m",
               cwd=root, env=env, check=False)


def test_hook_blocks_commit_when_check_fails(repo, tmp_path):
    sg.install_save_hook(repo)
    result = commit(repo, fake_tool(tmp_path, 1))
    assert result.returncode != 0 and "PRISM save gate" in result.stderr


def test_hook_allows_commit_when_check_passes(repo, tmp_path):
    sg.install_save_hook(repo)
    assert commit(repo, fake_tool(tmp_path, 0)).returncode == 0


def test_hook_fails_closed_when_tool_is_missing(repo):
    if shutil.which("prism_tools"):
        pytest.skip("prism_tools is on PATH here")
    sg.install_save_hook(repo)
    result = commit(repo, tool=None)
    assert result.returncode != 0
    assert "PRISM save gate" in result.stderr and "PRISM_TOOLS" in result.stderr


def test_foreign_hook_is_never_overwritten(repo):
    hook = repo / ".git" / "hooks" / "pre-commit"
    hook.write_text("#!/bin/sh\necho mine\n")
    with pytest.raises(HookExistsError):
        sg.install_save_hook(repo)
    assert "mine" in hook.read_text()


def test_install_is_idempotent_and_executable(repo):
    sg.install_save_hook(repo)
    hook = sg.install_save_hook(repo)
    assert sg.SAVE_HOOK_MARKER in hook.read_text()
    assert hook.stat().st_mode & stat.S_IXUSR
    assert sg.has_save_hook(repo)


def test_install_on_a_plain_folder_writes_nothing(tmp_path):
    plain = tmp_path / "plain"
    plain.mkdir()
    with pytest.raises(NotAGitRepoError):
        sg.install_save_hook(plain)
    assert list(plain.iterdir()) == []


def test_install_save_hooks_covers_every_dataset_root_and_reports_foreign(tmp_path, monkeypatch):
    roots = []
    for name in ("a", "b", "c"):
        r = tmp_path / name
        run("git", "init", "-q", str(r), cwd=tmp_path)
        roots.append(r)
    (roots[2] / ".git" / "hooks" / "pre-commit").write_text("#!/bin/sh\nexit 0\n")
    monkeypatch.setattr(sg, "_dataset_roots", lambda p: roots)
    result = sg.install_save_hooks(tmp_path)
    assert sorted(result["installed"]) == sorted(str(r) for r in roots[:2])
    assert result["foreign"] == [str(roots[2])]
    assert [sg.has_save_hook(r) for r in roots] == [True, True, False]
```

- [ ] **Step 2: Run to verify failure**

Run: `python -m pytest tests/test_save_gate_hook.py -v`
Expected: FAIL (`AttributeError: ... install_save_hook`).

- [ ] **Step 3: Implement** (append to `src/save_gate.py`; add `import os, stat` and `from src.share_publish import HookExistsError, NotAGitRepoError, _dataset_roots, _hooks_dir` at the top)

```python
SAVE_HOOK_MARKER = "# prism-save-gate-hook"


def _save_hook_script() -> str:
    return f"""#!/bin/sh
{SAVE_HOOK_MARKER}
# Refuses a commit unless the dataset validates (PRISM save gate).
TOOLS="${{PRISM_TOOLS:-prism_tools}}"
if ! command -v "$TOOLS" >/dev/null 2>&1; then
  echo "{SAVE_GATE_MARKER}: '$TOOLS' not found. Set PRISM_TOOLS to the prism_tools executable. Commit blocked." >&2
  exit 1
fi
ROOT="$(git rev-parse --show-toplevel)" || exit 1
"$TOOLS" save-gate --check --project "$ROOT" >&2 || exit 1
"""


def _save_hook_path(root: Path) -> Path:
    return _hooks_dir(root) / "pre-commit"


def has_save_hook(root) -> bool:
    try:
        hook = _save_hook_path(Path(root))
    except NotAGitRepoError:
        return False
    return hook.is_file() and SAVE_HOOK_MARKER in hook.read_text(encoding="utf-8", errors="replace")


def install_save_hook(root) -> Path:
    root = Path(root)
    hooks = _hooks_dir(root)  # raises NotAGitRepoError before anything is written
    hooks.mkdir(parents=True, exist_ok=True)
    hook = hooks / "pre-commit"
    if os.path.lexists(hook) and (
        hook.is_symlink() or SAVE_HOOK_MARKER not in hook.read_text(encoding="utf-8", errors="replace")
    ):
        raise HookExistsError(f"{hook} already exists and is not a PRISM hook; not overwriting.")
    hook.write_text(_save_hook_script(), encoding="utf-8")
    hook.chmod(hook.stat().st_mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)
    return hook


def install_save_hooks(project_root) -> dict:
    """Install the hook in the project and every nested dataset root (hooks are per repository)."""
    installed: list[str] = []
    foreign: list[str] = []
    for dataset_root in _dataset_roots(Path(project_root)):
        try:
            install_save_hook(dataset_root)
            installed.append(str(dataset_root))
        except HookExistsError:
            foreign.append(str(dataset_root))
    return {"installed": installed, "foreign": foreign}
```

Add the names to `__all__`.

- [ ] **Step 4: Run to verify pass**

Run: `python -m pytest tests/test_save_gate_hook.py tests/test_save_gate_check.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git branch --show-current
git add src/save_gate.py tests/test_save_gate_hook.py
git commit -m "feat(save-gate): pre-commit hook install (every dataset root, fail closed)

Co-Authored-By: Claude Sonnet 5.5 <noreply@anthropic.com>"
```

---

### Task 4: CLI `prism_tools save-gate`

**Files:**
- Create: `app/src/cli/commands/save_gate.py`
- Modify: `app/src/cli/parser.py` (subparser before `parser_environment`; dict entry `"save-gate": parser_save_gate`), `app/src/cli/dispatch.py` (branch), `app/src/cli/entrypoint.py` (import + handlers dict entry `"save_gate"`)
- Modify: `src/save_gate.py` (add `audit_save`), `docs/CLI_REFERENCE.md`
- Test: `tests/test_cli_save_gate.py`

**Interfaces:**
- Consumes: `check_save`, `install_save_hooks`, `has_save_hook`, `SAVE_GATE_MARKER` (Tasks 2-3); `_audit`, `resolve_identity` from `src.share_publish`; `_dataset_roots`.
- Produces: `cmd_save_gate(args)`; flags `--project` (required), `--check`, `--install-hooks`, `--status`, `--json`. Exit codes: `0` allowed/ok, `1` refused (validation errors), `2` any other problem. `--check` text output starts with `PRISM save gate: <N> validation error(s). Fix them, then save.` and lists at most 20 errors; JSON payload `{"allowed": bool, "reason": str, "errors": [...]}`. `audit_save(root, check: SaveCheck)` appends an audit line (`result` = `save_allowed` / `save_refused`, `sibling` = `""`).

- [ ] **Step 1: Write the failing test**

```python
# tests/test_cli_save_gate.py
import json
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

APP_ROOT = Path(__file__).resolve().parents[1] / "app"
if str(APP_ROOT) not in sys.path:
    sys.path.insert(0, str(APP_ROOT))

import src.cli.commands.save_gate as cmd  # noqa: E402
from src.cli.parser import build_prism_tools_parsers  # noqa: E402
from src.save_gate import SaveCheck  # noqa: E402


def args(**kw):
    base = dict(project="/p", check=False, install_hooks=False, status=False, json=True)
    base.update(kw)
    return SimpleNamespace(**base)


def run(capsys, **kw):
    with pytest.raises(SystemExit) as info:
        cmd.cmd_save_gate(args(**kw))
    return info.value.code, capsys.readouterr()


def test_parser_contract_used_by_the_hook():
    parser, _ = build_prism_tools_parsers(APP_ROOT)
    ns = parser.parse_args(["save-gate", "--check", "--project", "/p"])
    assert (ns.command, ns.check, ns.project, ns.install_hooks, ns.status) == ("save-gate", True, "/p", False, False)


def test_check_allowed_exit_0(monkeypatch, capsys):
    monkeypatch.setattr(cmd, "check_save", lambda p: SaveCheck(True, [], "valid"))
    monkeypatch.setattr(cmd, "audit_save", lambda *a, **k: None)
    code, out = run(capsys, check=True)
    assert code == 0 and json.loads(out.out)["allowed"] is True


def test_check_refused_exit_1_and_text_names_the_gate(monkeypatch, capsys):
    monkeypatch.setattr(cmd, "check_save", lambda p: SaveCheck(False, [f"E{i}" for i in range(30)], "validation_errors"))
    monkeypatch.setattr(cmd, "audit_save", lambda *a, **k: None)
    code, out = run(capsys, check=True, json=False)
    assert code == 1
    assert out.out.startswith("PRISM save gate: 30 validation error(s). Fix them, then save.")
    assert out.out.count("  - E") == 20


def test_check_audits_every_decision(monkeypatch, capsys):
    seen = []
    monkeypatch.setattr(cmd, "check_save", lambda p: SaveCheck(False, ["E"], "validation_errors"))
    monkeypatch.setattr(cmd, "audit_save", lambda root, check: seen.append((str(root), check.allowed)))
    run(capsys, check=True)
    assert seen == [("/p", False)]


def test_install_hooks_reports_foreign_as_exit_2(monkeypatch, capsys):
    monkeypatch.setattr(cmd, "install_save_hooks", lambda p: {"installed": ["/p"], "foreign": ["/p/sub-001"]})
    code, out = run(capsys, install_hooks=True)
    assert code == 2 and json.loads(out.out)["foreign"] == ["/p/sub-001"]


def test_install_hooks_ok_exit_0(monkeypatch, capsys):
    monkeypatch.setattr(cmd, "install_save_hooks", lambda p: {"installed": ["/p"], "foreign": []})
    assert run(capsys, install_hooks=True)[0] == 0


def test_status_lists_hook_per_dataset(monkeypatch, capsys):
    monkeypatch.setattr(cmd, "_dataset_roots", lambda p: [Path("/p"), Path("/p/sub-001")])
    monkeypatch.setattr(cmd, "has_save_hook", lambda r: str(r) == "/p")
    code, out = run(capsys, status=True)
    assert code == 0
    assert json.loads(out.out)["datasets"] == {"/p": True, "/p/sub-001": False}


def test_no_action_is_exit_2(capsys):
    assert run(capsys)[0] == 2


def test_not_a_git_repo_is_exit_2_not_a_traceback(tmp_path, capsys):
    code, out = run(capsys, project=str(tmp_path), install_hooks=True)
    assert code == 2 and json.loads(out.out)["errors"]
```

(The last test uses the real `install_save_hooks` on a plain folder; `_dataset_roots` must not crash on it. If `ProjectManager._iter_datalad_dataset_roots` returns `[folder]` for a non-git folder, `NotAGitRepoError` is raised by `install_save_hook`; make `install_save_hooks` catch it and put the folder into an `errors` list in its result: add `"errors": [str]` to the dict and to the Task 3 test expectations in the same commit if needed.)

- [ ] **Step 2: Run to verify failure**

Run: `python -m pytest tests/test_cli_save_gate.py -v`
Expected: FAIL (`ModuleNotFoundError: src.cli.commands.save_gate`).

- [ ] **Step 3: Implement**

`src/save_gate.py` (append; add `from src.share_publish import _audit, resolve_identity`):

```python
def audit_save(project_root, check: SaveCheck) -> None:
    """One audit line per checked commit (same file as publish; never fails the commit)."""
    _audit(
        Path(project_root),
        identity=resolve_identity(),
        sibling="",
        result="save_allowed" if check.allowed else "save_refused",
        error_count=len(check.errors),
    )
```

`app/src/cli/commands/save_gate.py`:

```python
"""prism_tools save-gate: thin adapter over src.save_gate (the git pre-commit hook calls --check)."""

from __future__ import annotations

import json
import sys
from pathlib import Path

from src.save_gate import (
    SAVE_GATE_MARKER,
    audit_save,
    check_save,
    has_save_hook,
    install_save_hooks,
)
from src.share_publish import _dataset_roots

_MAX_LISTED = 20


def _emit(args, payload: dict, text: str, code: int) -> None:
    print(json.dumps(payload, indent=2, ensure_ascii=False) if args.json else text)
    sys.exit(code)


def cmd_save_gate(args) -> None:
    root = Path(args.project)
    if args.check:
        check = check_save(root)
        audit_save(root, check)
        text = ""
        if not check.allowed:
            lines = [f"{SAVE_GATE_MARKER}: {len(check.errors)} validation error(s). Fix them, then save."]
            lines += [f"  - {e}" for e in check.errors[:_MAX_LISTED]]
            text = "\n".join(lines)
        _emit(args, {"allowed": check.allowed, "reason": check.reason, "errors": check.errors}, text, 0 if check.allowed else 1)
    if args.install_hooks:
        result = install_save_hooks(root)
        problems = result["foreign"] or result.get("errors")
        text = f"Installed in {len(result['installed'])} dataset(s)." + (
            f" Left alone (foreign hook or error): {', '.join([*result['foreign'], *result.get('errors', [])])}" if problems else ""
        )
        _emit(args, {**result, "errors": result.get("errors", [])}, text, 2 if problems else 0)
    if args.status:
        datasets = {str(r): has_save_hook(r) for r in _dataset_roots(root)}
        text = "\n".join(f"{'hook' if ok else 'NO HOOK'}  {path}" for path, ok in datasets.items())
        _emit(args, {"datasets": datasets}, text, 0)
    _emit(args, {"errors": ["Choose one of --check, --install-hooks, --status."]}, "Choose one of --check, --install-hooks, --status.", 2)
```

Parser block (before `parser_environment = subparsers.add_parser(`):

```python
    parser_save_gate = subparsers.add_parser(
        "save-gate",
        help="Save gate: commits are allowed only on valid datasets (git pre-commit hook)",
    )
    parser_save_gate.add_argument("--project", required=True, help="Dataset root")
    parser_save_gate.add_argument("--check", action="store_true", help="Validate; exit 1 if the commit must be refused (used by the hook)")
    parser_save_gate.add_argument("--install-hooks", action="store_true", help="Install the pre-commit hook in the project and every nested dataset")
    parser_save_gate.add_argument("--status", action="store_true", help="Show which datasets have the hook")
    parser_save_gate.add_argument("--json", action="store_true", help="Emit machine-readable JSON")
```

Add `"save-gate": parser_save_gate,` to the returned dict, the dispatch branch `elif args.command == "save-gate": handlers["save_gate"](args)`, and the entrypoint import/handler entry `"save_gate": cmd_save_gate`. Document the command and exit codes (0/1/2), the hook contract (`PRISM_TOOLS` must be an executable; the hook blocks when it is missing), and `--no-verify` in `docs/CLI_REFERENCE.md`, mirroring the `publish` section.

- [ ] **Step 4: Run to verify pass**

Run: `python -m pytest tests/test_cli_save_gate.py tests/test_save_gate_hook.py tests/test_cli_no_web_layer_imports.py tests/test_cli_dispatch_routing.py tests/test_cli_parity_commands.py -v`
Then by hand: `python app/prism_tools.py save-gate --project /nonexistent --status` must print an error payload / exit 2, never a traceback (put the output in the report).
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git branch --show-current
git add app/src/cli src/save_gate.py tests/test_cli_save_gate.py tests/test_save_gate_hook.py docs/CLI_REFERENCE.md
git commit -m "feat(save-gate): prism_tools save-gate (--check, --install-hooks, --status)

Co-Authored-By: Claude Sonnet 5.5 <noreply@anthropic.com>"
```

---

### Task 5: PRISM integration: `PRISM_TOOLS` for children, hooks after creation

**Files:**
- Modify: `src/save_gate.py` (append `ensure_prism_tools_env`)
- Modify: `app/src/cli/entrypoint.py` (`main()` next to `apply_env_identity()`, line ~117), `app/prism-studio.py` (`main()` next to `apply_env_identity()`, line ~1680)
- Modify: `app/src/project_manager.py` (install hooks after the project dataset is created and saved, and after each nested dataset is created and saved)
- Test: `tests/test_save_gate_integration.py`

**Interfaces:**
- Consumes: `install_save_hooks`, `install_save_hook` (Task 3).
- Produces: `ensure_prism_tools_env() -> str | None`: if `PRISM_TOOLS` is unset and the repo's `prism_tools.py` is executable, sets `os.environ["PRISM_TOOLS"]` to its absolute path and returns it; never overrides an existing value; returns `None` when nothing was set.

Without `PRISM_TOOLS` the hook would block PRISM's own saves (fail closed), so every PRISM process exports it before any git/datalad subprocess.

- [ ] **Step 1: Read first.** In `app/src/project_manager.py` read `create_project` (~265-330, it calls `_create_datalad_dataset` at ~320), the second caller at ~534 and ~3878, `_create_datalad_dataset` (~3928, note its result keys `initialized`/`saved`), and the nested creation function around ~5040-5140 (`datalad create -d . --force <rel>` then `_run_datalad_save(dataset_path, ...)` at ~5130 that returns `{"success": ...}` when saved). Identify the exact point in each where the *last* creation-time save has succeeded. Installing before it would gate the scaffold.

- [ ] **Step 2: Write the failing tests**

```python
# tests/test_save_gate_integration.py
import os
import stat

import src.save_gate as sg


def test_ensure_prism_tools_env_sets_the_repo_script(monkeypatch):
    monkeypatch.delenv("PRISM_TOOLS", raising=False)
    value = sg.ensure_prism_tools_env()
    assert value and os.path.basename(value) == "prism_tools.py"
    assert os.environ["PRISM_TOOLS"] == value
    assert os.access(value, os.X_OK)


def test_ensure_prism_tools_env_never_overrides(monkeypatch):
    monkeypatch.setenv("PRISM_TOOLS", "/custom/tool")
    assert sg.ensure_prism_tools_env() is None
    assert os.environ["PRISM_TOOLS"] == "/custom/tool"


def test_cli_main_exports_prism_tools(monkeypatch):
    import src.cli.entrypoint as ep

    called = []
    monkeypatch.setattr(ep, "ensure_prism_tools_env", lambda: called.append(1))
    monkeypatch.setattr(ep, "apply_env_identity", lambda: None)
    try:
        monkeypatch.setattr("sys.argv", ["prism_tools", "save-gate", "--help"])
        ep.main()
    except SystemExit:
        pass
    assert called == [1]
```

Plus project-manager tests following the pattern of existing ProjectManager/DataLad tests (`grep -l "_create_datalad_dataset" tests/*.py`; reuse their fixtures/monkeypatching):
- `test_hooks_are_installed_after_the_creation_saves`: monkeypatch `src.save_gate.install_save_hooks` to record the call; run the create flow; assert it was called exactly once, with the project path, **after** the last `_run_datalad_save` (record call order in one list with a fake saver).
- `test_nested_dataset_gets_the_hook_after_its_creation_save`: same for the nested path, `install_save_hook(dataset_path)` called after `_run_datalad_save`.
- `test_creation_continues_when_hook_install_fails`: installer raises `HookExistsError`; creation result is still success and carries a note (`save_gate_hook` key) so a foreign hook never aborts project creation.
- One real (skip if `datalad`/`git-annex` are missing) test: create a project through the create flow into a tmp dir, then `git commit --allow-empty` is refused only when the project is invalid... (keep it to: hook file exists in the project and in a created nested dataset).

- [ ] **Step 3: Run to verify failure**

Run: `python -m pytest tests/test_save_gate_integration.py -v`
Expected: FAIL.

- [ ] **Step 4: Implement**

```python
# src/save_gate.py (append)
def ensure_prism_tools_env() -> str | None:
    """Point PRISM_TOOLS at this checkout's prism_tools.py for child git/datalad processes.

    The hook blocks when it cannot find the tool, so without this PRISM's own saves would be
    refused. An existing value is never replaced. ponytail: source checkout only; a frozen
    build needs its own launcher path here.
    """
    if os.environ.get("PRISM_TOOLS"):
        return None
    script = Path(__file__).resolve().parents[1] / "prism_tools.py"
    if not os.access(script, os.X_OK):
        return None
    os.environ["PRISM_TOOLS"] = str(script)
    return str(script)
```

In `app/src/cli/entrypoint.py` import `ensure_prism_tools_env` at module top (like `apply_env_identity`) and call it right after `apply_env_identity()` in `main()`; same in `app/prism-studio.py` `main()`.

In `ProjectManager`, after the last creation-time save succeeded (identified in Step 1), add:

```python
        try:
            from src.save_gate import install_save_hooks

            result["save_gate_hook"] = install_save_hooks(project_path)
        except Exception as exc:  # a foreign hook or odd git state must never abort creation
            result["save_gate_hook"] = {"installed": [], "foreign": [], "errors": [str(exc)]}
```

and, in the nested-dataset creation function after its successful `_run_datalad_save` (~line 5130), the single-dataset equivalent using `install_save_hook(dataset_path)`.

- [ ] **Step 5: Run to verify pass**

Run: `python -m pytest tests/test_save_gate_integration.py tests/test_cli_no_web_layer_imports.py -v`, then the existing ProjectManager/DataLad tests (`python -m pytest tests -q -k "project_manager or datalad" --ignore=tests/e2e`).
Expected: PASS

- [ ] **Step 6: Commit**

```bash
git branch --show-current
git add src/save_gate.py app/src/cli/entrypoint.py app/prism-studio.py app/src/project_manager.py tests/test_save_gate_integration.py
git commit -m "feat(save-gate): export PRISM_TOOLS to children; install hooks after dataset creation

Co-Authored-By: Claude Sonnet 5.5 <noreply@anthropic.com>"
```

---

### Task 6: fixing after a refusal (`datalad run --explicit`)

**Files:**
- Modify: `src/datalad_execution.py` (`run_datalad_run`: add `explicit: bool = False`, `outputs: Sequence[str] = ()`)
- Modify: `src/datalad_mutation_policy.py` (`run_tracked_mutation`; new `SaveGateRefusedError`)
- Test: `tests/test_datalad_execution.py` (extend), `tests/test_datalad_mutation_policy.py` (extend), `tests/test_save_gate_fix_after_refusal.py` (real DataLad)

**Interfaces:**
- Consumes: `SAVE_GATE_MARKER` (Task 2); `run_datalad_save`/`run_datalad_run` result dicts (`success`, `message`).
- Produces: `run_datalad_run(..., explicit=False, outputs=())` builds `datalad run [--explicit -o P ...] -m MSG -- CMD`; `SaveGateRefusedError(ValueError)` in `src.datalad_mutation_policy`. Behavior of `run_tracked_mutation` when the pre-run autosave message contains `SAVE_GATE_MARKER`: skip the second (post-unlock) autosave, run the command with `explicit=True, outputs=autosave_scope_paths`; when that run's message contains `SAVE_GATE_MARKER`: do **not** attempt the emergency save, raise `SaveGateRefusedError("<what was applied> but not saved: the dataset has validation errors. Fix them, then run `datalad save`. <hook output>")`. Any other failure keeps today's behavior unchanged.

Spike result this relies on (DataLad 1.6.3): with a refusing `pre-commit` hook, `datalad run` on a dirty tree says "clean dataset required", but `datalad run --explicit -o out.txt ...` runs the command, exits 1 with the hook's text, leaves `out.txt` staged and uncommitted; a later `datalad save` on a valid tree commits everything.

- [ ] **Step 1: Write the failing tests**

`tests/test_datalad_execution.py` (match that file's fake-subprocess style; assertions on the built command):

```python
from types import SimpleNamespace

from src.datalad_execution import run_datalad_run


def _capture(monkeypatch):
    captured = {}

    def _fake_run(command, cwd=None, capture_output=True, text=True, timeout=None, check=False, env=None):
        captured["command"] = command
        return SimpleNamespace(returncode=0, stdout="", stderr="")

    monkeypatch.setattr("src.datalad_execution.subprocess.run", _fake_run)
    return captured


def test_run_datalad_run_explicit_builds_outputs_flags(monkeypatch, tmp_path):
    captured = _capture(monkeypatch)
    run_datalad_run(tmp_path, message="m", command=["echo", "x"], datalad_executable="datalad",
                    explicit=True, outputs=["a.tsv", "b/c.json"])
    cmd = captured["command"]
    assert cmd[:3] == ["datalad", "run", "--explicit"]
    assert cmd.count("-o") == 2 and "a.tsv" in cmd and "b/c.json" in cmd
    assert cmd[-3:] == ["--", "echo", "x"]


def test_run_datalad_run_default_is_unchanged(monkeypatch, tmp_path):
    captured = _capture(monkeypatch)
    run_datalad_run(tmp_path, message="m", command=["echo", "x"], datalad_executable="datalad")
    assert captured["command"] == ["datalad", "run", "-m", "m", "--", "echo", "x"]
```

(If `run_datalad_run` streams through a different subprocess entry point than `subprocess.run`, patch that one instead: look at lines ~340-370 of `src/datalad_execution.py`; today it calls `subprocess.run(... env=run_env)`.)

`tests/test_datalad_mutation_policy.py` (use that file's existing monkeypatch pattern for `run_datalad_save` / `run_datalad_run` / `run_datalad_get_paths`):

```python
import src.datalad_mutation_policy as pol
from src.datalad_mutation_policy import SaveGateRefusedError

GATE = "PRISM save gate: 2 validation error(s). Fix them, then save."


def _project(tmp_path, monkeypatch, save, run):
    root = tmp_path / "project"
    (root / ".datalad").mkdir(parents=True)
    monkeypatch.setattr(pol, "resolve_datalad_executable", lambda: "datalad")
    monkeypatch.setattr(pol, "run_datalad_save", save)
    monkeypatch.setattr(pol, "run_datalad_run", run)
    monkeypatch.setattr(pol, "run_datalad_get_paths", lambda *a, **k: {"attempted": True, "success": True})
    monkeypatch.setattr(pol, "paths_have_uncommitted_changes", lambda *a, **k: True)
    return root


def test_gate_refused_autosave_falls_back_to_explicit_run(tmp_path, monkeypatch):
    saves, runs = [], []

    def save(root, **kw):
        saves.append(kw["message"])
        return {"attempted": True, "success": False, "message": f"save failed: {GATE}"}

    def run(root, **kw):
        runs.append(kw)
        return {"attempted": True, "success": False, "message": GATE}

    root = _project(tmp_path, monkeypatch, save, run)
    with pytest.raises(SaveGateRefusedError, match="not saved"):
        run_tracked_mutation(root, get_paths=["a.tsv"], run_message="PRISM: rename", command=["echo"])
    assert runs[0]["explicit"] is True and runs[0]["outputs"] == ["a.tsv"]
    assert len(saves) == 1  # the autosave only: no post-unlock autosave, no emergency save


def test_other_autosave_failures_still_raise_as_before(tmp_path, monkeypatch):
    runs = []
    root = _project(
        tmp_path, monkeypatch,
        save=lambda root, **kw: {"attempted": True, "success": False, "message": "disk full"},
        run=lambda root, **kw: runs.append(kw) or {"success": True},
    )
    with pytest.raises(ValueError, match="disk full"):
        run_tracked_mutation(root, get_paths=["a.tsv"], run_message="m", command=["echo"])
    assert runs == []


def test_explicit_run_that_succeeds_returns_normally(tmp_path, monkeypatch):
    root = _project(
        tmp_path, monkeypatch,
        save=lambda root, **kw: {"attempted": True, "success": False, "message": GATE},
        run=lambda root, **kw: {"attempted": True, "success": True, "message": "ok", "command": "x"},
    )
    result = run_tracked_mutation(root, get_paths=["a.tsv"], run_message="m", command=["echo"])
    assert result["used_run"] is True and result["run"]["success"] is True


def test_run_commit_refused_by_the_gate_skips_the_emergency_save(tmp_path, monkeypatch):
    saves = []

    def save(root, **kw):
        saves.append(kw["message"])
        return {"attempted": True, "success": True, "no_changes": True, "message": "ok"}

    root = _project(
        tmp_path, monkeypatch, save,
        run=lambda root, **kw: {"attempted": True, "success": False, "message": GATE},
    )
    with pytest.raises(SaveGateRefusedError):
        run_tracked_mutation(root, get_paths=["a.tsv"], run_message="m", command=["echo"])
    assert not any("emergency" in m for m in saves)
```

`tests/test_save_gate_fix_after_refusal.py` (real DataLad; `pytest.skip` when `datalad`/`git-annex` are missing):

```python
import os
import stat
import subprocess

import pytest

import src.save_gate as sg
from src.datalad_mutation_policy import SaveGateRefusedError, run_tracked_mutation

pytestmark = pytest.mark.skipif(
    not (subprocess.run(["which", "datalad"], capture_output=True).returncode == 0
         and subprocess.run(["which", "git-annex"], capture_output=True).returncode == 0),
    reason="needs datalad and git-annex",
)


@pytest.fixture
def ds(tmp_path, monkeypatch):
    root = tmp_path / "ds"
    subprocess.run(["datalad", "create", str(root)], check=True, capture_output=True)
    (root / "a.txt").write_text("a")
    subprocess.run(["datalad", "save", "-m", "a"], cwd=root, check=True, capture_output=True)
    # fake tool: invalid while a file named BAD exists
    tool = tmp_path / "prism_tools"
    tool.write_text('#!/bin/sh\nif [ -e BAD ]; then echo "PRISM save gate: 1 validation error(s)." ; exit 1; fi\nexit 0\n')
    tool.chmod(tool.stat().st_mode | stat.S_IEXEC)
    monkeypatch.setenv("PRISM_TOOLS", str(tool))
    sg.install_save_hook(root)
    return root


def git_status(root):
    return subprocess.run(["git", "status", "--porcelain"], cwd=root, capture_output=True, text=True).stdout


def test_mutation_on_a_tree_dirty_from_a_refused_save_applies_the_change_but_is_not_saved(ds):
    (ds / "BAD").write_text("1")  # dataset is now invalid and dirty
    with pytest.raises(SaveGateRefusedError) as info:
        run_tracked_mutation(
            ds, get_paths=["out.txt"], run_message="write out",
            command=["sh", "-c", "echo y > out.txt"],
        )
    assert "not saved" in str(info.value).lower()
    assert (ds / "out.txt").exists()                       # the change was applied
    assert "out.txt" in git_status(ds)                      # ... and is uncommitted
    # now fix the dataset and save once: the gated save goes through
    (ds / "BAD").unlink()
    subprocess.run(["datalad", "save", "-m", "fixed"], cwd=ds, check=True, capture_output=True)
    assert git_status(ds).strip() == ""


def test_clean_valid_tree_still_uses_the_normal_run(ds):
    result = run_tracked_mutation(
        ds, get_paths=["out.txt"], run_message="write out", command=["sh", "-c", "echo y > out.txt"],
    )
    assert result["used_run"] and git_status(ds).strip() == ""
```

- [ ] **Step 2: Run to verify failure**

Run: `python -m pytest tests/test_datalad_execution.py tests/test_datalad_mutation_policy.py tests/test_save_gate_fix_after_refusal.py -q -k "explicit or gate or refused or dirty"`
Expected: FAIL (`unexpected keyword argument 'explicit'`, no `SaveGateRefusedError`).

- [ ] **Step 3: Implement**

`run_datalad_run` signature gains `explicit: bool = False, outputs: Sequence[str] = ()`; the command line becomes:

```python
    run_flags: list[str] = []
    if explicit:
        run_flags.append("--explicit")
        for path in outputs:
            run_flags.extend(["-o", str(path)])
    datalad_command = [resolved, "run", *run_flags, "-m", run_message, "--", *escaped_command]
```

`src/datalad_mutation_policy.py`:

```python
from src.datalad_execution import SAVE_GATE_MARKER  # add to the existing import block


class SaveGateRefusedError(ValueError):
    """The mutation was applied to the working tree but the save gate refused to commit it.

    Not a failure of the operation: the dataset has validation errors. The user fixes them
    and runs one `datalad save`; the changes are intact on disk.
    """
```

In `run_tracked_mutation`:
- After the first autosave:

```python
    gate_refused = (not autosave_result.get("success")) and SAVE_GATE_MARKER in str(
        autosave_result.get("message") or ""
    )
    if not autosave_result.get("success") and not gate_refused:
        raise ValueError(... existing message ...)
```
- Skip the second autosave (`pre_run_autosave_result`) when `gate_refused` (a dirty tree is the expected state; explicit mode does not need it).
- Call `run_datalad_run(..., explicit=gate_refused, outputs=autosave_scope_paths if gate_refused else ())`.
- In the failure branch, before computing `mutated`/emergency save:

```python
        if SAVE_GATE_MARKER in run_message_detail:
            raise SaveGateRefusedError(
                f'"{run_message}" was applied but not saved: the dataset has validation errors. '
                f"Fix them, then run `datalad save`. {run_message_detail}"
            )
```

(That branch also covers the case where the autosave was fine but the run's own commit was refused because the mutation made the dataset invalid; there too the emergency save would only be refused again.)

- [ ] **Step 4: Run to verify pass**

Run: `python -m pytest tests/test_datalad_execution.py tests/test_datalad_mutation_policy.py tests/test_save_gate_fix_after_refusal.py tests/test_bids_file_deleter.py tests/test_bids_entity_rewriter.py -q`
Expected: PASS (the last two exercise callers of `run_tracked_mutation`).

- [ ] **Step 5: Commit**

```bash
git branch --show-current
git add src/datalad_execution.py src/datalad_mutation_policy.py tests/test_datalad_execution.py tests/test_datalad_mutation_policy.py tests/test_save_gate_fix_after_refusal.py
git commit -m "feat(save-gate): PRISM mutations keep working on a tree left dirty by a refused save

Co-Authored-By: Claude Sonnet 5.5 <noreply@anthropic.com>"
```

---

### Task 7: docs and end-to-end check

**Files:**
- Modify: `docs/DATALAD.md` (new section "Save gate"), `docs/PROJECT_OVERVIEW.md` only if it lists backend modules (add `src/save_gate.py` in the same style)
- Test: `tests/test_save_gate_e2e.py` (real DataLad, skip when missing)

- [ ] **Step 1: Write the failing end-to-end test**

Fixtures verified while planning: `examples/wellbeing_multi_demo` validates with zero errors (full validation); a stray `sub-X/ses-NN/survey/foo.txt` in a subject yields several ERRORs in the per-subject check; the existing subject `sub-001` validates alone with no issues. The real CLI is used as the hook's tool (no fakes).

```python
# tests/test_save_gate_e2e.py
import json
import shutil
import stat
import subprocess
import sys
from pathlib import Path

import pytest

import src.save_gate as sg

pytestmark = pytest.mark.skipif(
    not (shutil.which("datalad") and shutil.which("git-annex")), reason="needs datalad and git-annex"
)

REPO = Path(__file__).resolve().parents[1]
DEMO = REPO / "examples" / "wellbeing_multi_demo"


def sh(*args, cwd, check=True):
    return subprocess.run(list(args), cwd=cwd, capture_output=True, text=True, check=check)


def commits(root) -> int:
    return int(sh("git", "rev-list", "--count", "HEAD", cwd=root).stdout)


@pytest.fixture
def ds(tmp_path, monkeypatch):
    # hook tool: the real prism_tools.py run with the interpreter that runs the tests
    tool = tmp_path / "prism_tools"
    tool.write_text(f'#!/bin/sh\nexec "{sys.executable}" "{REPO / "prism_tools.py"}" "$@"\n')
    tool.chmod(tool.stat().st_mode | stat.S_IEXEC)
    monkeypatch.setenv("PRISM_TOOLS", str(tool))
    root = tmp_path / "study"
    shutil.copytree(DEMO, root)
    sh("datalad", "create", "--force", ".", cwd=root)  # commit #1; the demo files are still untracked
    result = sg.install_save_hooks(root)
    assert str(root) in result["installed"]
    return root


def test_first_save_exempt_then_gated_then_fixed(ds):
    description = (ds / "dataset_description.json").read_text()
    (ds / "dataset_description.json").write_text("{}")  # invalid on purpose
    # 1. the first save of a top-level dataset is exempt, even though it is invalid
    sh("datalad", "save", "-m", "scaffold", cwd=ds)
    assert commits(ds) == 2
    # 2. from now on a save that leaves errors is refused, nothing is committed
    (ds / "README.md").write_text("hello\n")
    refused = sh("datalad", "save", "-m", "readme", cwd=ds, check=False)
    assert refused.returncode != 0
    assert "PRISM save gate" in refused.stdout + refused.stderr
    assert commits(ds) == 2
    # 3. fix the dataset in the working tree, then one save goes through
    (ds / "dataset_description.json").write_text(description)
    sh("datalad", "save", "-m", "fixed", cwd=ds)
    assert commits(ds) == 3
    assert sh("git", "status", "--porcelain", cwd=ds).stdout.strip() == ""
    # 4. the decisions are in the audit log, refusals included
    log = (ds / ".git" / "prism" / "publish.jsonl").read_text().splitlines()
    results = [json.loads(line)["result"] for line in log]
    assert "save_refused" in results and "save_allowed" in results


def test_nested_subject_commit_is_checked_per_subject(ds):
    sh("datalad", "save", "-m", "scaffold", cwd=ds)  # exempt first save; the demo is valid
    # PRISM's nested conversion: turn an existing subject folder into its own dataset
    sh("datalad", "create", "-d", ".", "--force", "sub-P01", cwd=ds)
    sg.install_save_hooks(ds)  # now also covers sub-P01
    nested = ds / "sub-P01"
    before = commits(nested)
    # valid content: allowed (no exemption for nested datasets: the check really ran)
    sh("datalad", "save", "-d", ".", "-r", "-m", "subject data", cwd=ds)
    assert commits(nested) == before + 1
    # invalid content in the subject: refused at the nested commit
    bad = nested / "ses-99" / "survey"
    bad.mkdir(parents=True)
    (bad / "foo.txt").write_text("x")
    refused = sh("datalad", "save", "-d", "sub-P01", "-m", "bad", cwd=ds, check=False)
    assert refused.returncode != 0 and "PRISM save gate" in refused.stdout + refused.stderr
    assert commits(nested) == before + 1
```

If DataLad's `create --force` / `-d` behave differently than assumed (for example if the nested conversion already commits the subject files, or the superdataset save validates and refuses), keep the assertions' intent (first save exempt; later save refused with the marker and unchanged commit count; nested subject refused on its own invalid content, allowed on valid) and adapt the commands; say what changed in the report.

- [ ] **Step 2: Run to verify failure**, **Step 3:** fix whatever the e2e reveals (bug fixes belong to the owning task's module; keep each fix minimal and covered by a new unit test first).

- [ ] **Step 4: Docs.** `docs/DATALAD.md`: the rule (strict; warnings don't block), the single exemption (first save of a top-level dataset), what gets refused and how to fix ("fix in the working tree, then `datalad save`"), `prism_tools save-gate --install-hooks/--status`, `PRISM_TOOLS` (must be an executable; the hook blocks without it), per-clone hooks (a fresh clone is ungated until `--install-hooks`), `--no-verify` bypass, nested datasets validated per subject, that the cross-subject checks run on the top-level save, that `src/repo_rewrite_datalad_runner.py` operations do not yet have the explicit-run fallback (follow-up), and that frozen builds need their own `PRISM_TOOLS` launcher.

- [ ] **Step 5: Full suite and commit**

Run: `python -m pytest tests -q --ignore=tests/e2e` (expect all green; note the test count) and `python tests/verify_repo.py --check dual-tree-drift --no-fix` (delete any `prism-studio_report_*.txt` it leaves).

```bash
git branch --show-current
git add docs tests/test_save_gate_e2e.py src app
git commit -m "docs+test(save-gate): end-to-end refusal/allow flow, save gate docs

Co-Authored-By: Claude Sonnet 5.5 <noreply@anthropic.com>"
```

---

## Self-review

- **Spec coverage:** rule + single exemption (T2), nested subject-only validation (T1, T2), pre-commit hook in every dataset root (T3), `save-gate` CLI with `--check/--install-hooks/--status` and audit (T4), hooks installed on creation and `PRISM_TOOLS` for children (T5), fixing after a refusal (T6), docs and the e2e (T7). Deferred by design: Phase 2 cache (separate plan), the `repo_rewrite_datalad_runner` fallback (documented follow-up), explicit scaffold flag and backend pre-check (replaced, see Deviations).
- **Interfaces:** `SaveCheck`, `check_save`, `validate_subject_for_save`, `install_save_hook(s)`, `has_save_hook`, `audit_save`, `ensure_prism_tools_env`, `SAVE_GATE_MARKER`, `SaveGateRefusedError`, `run_datalad_run(explicit, outputs)` are defined once and used with the same names later. `_core_validation`, `_describe`, `_git`, `_hooks_dir`, `_dataset_roots`, `HookExistsError`, `NotAGitRepoError`, `_audit`, `resolve_identity`, `validate_for_publish` already exist in `src/share_publish.py`.
- **Known soft spots to watch in review:** T5 insertion points inside `project_manager.py` are located by the implementer from the named anchors; T7 step 1 is described as a scenario list because the minimal valid fixture depends on the validator's current requirements and must be discovered, not guessed.
