# Share → Server Publish Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Let users push a DataLad dataset from a department share to the server sibling only when it validates, with a git identity on every attempt and a pre-push hook that enforces the same rule for plain git.

**Architecture:** One backend module `src/share_publish.py` (identity, validation gate, audit, push, hook install). The CLI (`prism_tools publish`) and the GUI (one Flask route plus two buttons) are thin adapters over it. Pushing reuses `run_datalad_push` / `run_datalad_push_verify`; validation reuses `src.core.validation`.

**Tech Stack:** Python, argparse CLI (`app/src/cli`), Flask blueprints, pytest, real `git` in tests (no DataLad needed except one optional integration test).

**Spec:** `docs/superpowers/specs/2026-10-02-share-publish-design.md`

## Global Constraints

- Errors-only gate: any validator **error** blocks; warnings never block.
- BIDS validator is **off** for the gate (PRISM checks only); no `--bids` flag (YAGNI).
- Identity is **never** written to any git config; resolution order is `--as` → `PRISM_USER_NAME`/`PRISM_USER_EMAIL` → global git config → refuse.
- Audit log at `<git-dir>/prism/publish.jsonl`, one JSON object per line, written for allowed **and** refused attempts.
- The backend always re-validates; no caller passes a trusted "valid" flag.
- CLI code must not import `src.web.*` or `flask` (enforced by `tests/test_cli_no_web_layer_imports.py`).
- Session IDs are free-form strings, never normalized (not touched here, do not introduce any).
- Text-file/annex policy (CLAUDE.md): this plan writes no tracked files into datasets.
- Branch: `feat/share-publish`. Check `git branch --show-current` before every commit.

## Review Focus

- Plain `git push` to a non-server remote must pass the hook untouched (test in Task 3).
- Hook installed on a share where `PRISM_TOOLS` is unset and `prism_tools` is not on PATH must **block** (fail closed), not silently allow (Task 3).
- Two users on the same share, different `--as`: the second user's commits must not carry the first user's identity (Task 1/6).
- Validation passes only in BIDS-only display mode must not show an enabled Publish button (Task 5, `run_prism` false → not publishable).
- Folder-upload validations (temp dir, no `.datalad`) must never show Publish (Task 5).
- Known gap, not fixed: `datalad push -r` pushes nested `sub-*` datasets before the superdataset, and the hook sits on the superdataset only (spec, open items).

---

### Task 1: Identity resolution

**Files:**
- Create: `src/share_publish.py`
- Test: `tests/test_share_publish_identity.py`

**Interfaces:**
- Produces: `Identity(name: str, email: str)` (frozen dataclass); `parse_identity(text: str) -> Identity` (raises `ValueError`); `resolve_identity(as_text: str | None = None) -> Identity | None`; `identity_env(identity: Identity) -> dict[str, str]`; `apply_identity(identity: Identity) -> None` (updates `os.environ`).

- [ ] **Step 1: Write the failing test**

```python
# tests/test_share_publish_identity.py
import os
import subprocess

import pytest

from src.share_publish import (
    Identity,
    apply_identity,
    identity_env,
    parse_identity,
    resolve_identity,
)


@pytest.fixture(autouse=True)
def clean_env(monkeypatch, tmp_path):
    for key in ("PRISM_USER_NAME", "PRISM_USER_EMAIL"):
        monkeypatch.delenv(key, raising=False)
    # empty global git config so the machine's own identity never leaks in
    empty = tmp_path / "gitconfig"
    empty.write_text("")
    monkeypatch.setenv("GIT_CONFIG_GLOBAL", str(empty))
    monkeypatch.setenv("GIT_CONFIG_SYSTEM", os.devnull)
    return empty


def test_parse_identity():
    assert parse_identity("Ada Lovelace <ada@uni.at>") == Identity("Ada Lovelace", "ada@uni.at")


@pytest.mark.parametrize("bad", ["", "Ada", "<ada@uni.at>", "Ada <nope>"])
def test_parse_identity_rejects_garbage(bad):
    with pytest.raises(ValueError):
        parse_identity(bad)


def test_resolution_order(monkeypatch, clean_env):
    assert resolve_identity() is None
    clean_env.write_text("[user]\n\tname = Global\n\temail = g@x.at\n")
    assert resolve_identity() == Identity("Global", "g@x.at")
    monkeypatch.setenv("PRISM_USER_NAME", "Env")
    monkeypatch.setenv("PRISM_USER_EMAIL", "e@x.at")
    assert resolve_identity() == Identity("Env", "e@x.at")
    assert resolve_identity("Flag <f@x.at>") == Identity("Flag", "f@x.at")


def test_apply_identity_is_seen_by_child_git_and_leaves_repo_config_alone(tmp_path, monkeypatch):
    repo = tmp_path / "r"
    subprocess.run(["git", "init", "-q", str(repo)], check=True)
    (repo / "f").write_text("x")
    subprocess.run(["git", "-C", str(repo), "add", "f"], check=True)
    for key in identity_env(Identity("a", "a@b.c")):
        monkeypatch.delenv(key, raising=False)  # restored after the test
    apply_identity(Identity("Ada", "ada@uni.at"))
    subprocess.run(["git", "-C", str(repo), "commit", "-q", "-m", "m"], check=True)
    author = subprocess.run(
        ["git", "-C", str(repo), "log", "-1", "--format=%an <%ae>|%cn <%ce>"],
        capture_output=True, text=True, check=True,
    ).stdout.strip()
    assert author == "Ada <ada@uni.at>|Ada <ada@uni.at>"
    cfg = (repo / ".git" / "config").read_text()
    assert "Ada" not in cfg and "[user]" not in cfg
```

- [ ] **Step 2: Run to verify failure**

Run: `cd /Users/karl/work/github/prism-studio && python -m pytest tests/test_share_publish_identity.py -v`
Expected: FAIL (`ModuleNotFoundError: src.share_publish`). If `src.share_publish` imports fail for another reason, run `python3 -c "import src; print(src.__path__)"` and check `tests/conftest.py` sys.path setup (other tests under `tests/` import `src.*` the same way).

- [ ] **Step 3: Implement**

```python
# src/share_publish.py
"""Validity-gated push from a department share to the DataLad server sibling.

One implementation: the CLI (`prism_tools publish`) and the Studio routes call
these functions. See docs/superpowers/specs/2026-10-02-share-publish-design.md.
"""

from __future__ import annotations

import os
import re
import subprocess
from dataclasses import dataclass


@dataclass(frozen=True)
class Identity:
    name: str
    email: str


_IDENTITY_RE = re.compile(r"^\s*(?P<name>[^<>]+?)\s*<(?P<email>[^<>@\s]+@[^<>\s]+)>\s*$")


def parse_identity(text: str) -> Identity:
    match = _IDENTITY_RE.match(text or "")
    if not match:
        raise ValueError(f'Identity must look like "Name <email@host>", got {text!r}.')
    return Identity(match["name"], match["email"])


def _global_git(key: str) -> str:
    out = subprocess.run(
        ["git", "config", "--global", key], capture_output=True, text=True, check=False
    )
    return out.stdout.strip() if out.returncode == 0 else ""


def resolve_identity(as_text: str | None = None) -> Identity | None:
    """--as, then PRISM_USER_NAME/EMAIL, then global git config; None if nothing."""
    if as_text:
        return parse_identity(as_text)
    name, email = os.environ.get("PRISM_USER_NAME", "").strip(), os.environ.get("PRISM_USER_EMAIL", "").strip()
    if name and email:
        return Identity(name, email)
    name, email = _global_git("user.name"), _global_git("user.email")
    return Identity(name, email) if name and email else None


def identity_env(identity: Identity) -> dict[str, str]:
    return {
        "GIT_AUTHOR_NAME": identity.name,
        "GIT_AUTHOR_EMAIL": identity.email,
        "GIT_COMMITTER_NAME": identity.name,
        "GIT_COMMITTER_EMAIL": identity.email,
    }


def apply_identity(identity: Identity) -> None:
    """Export the identity into this process so child git/datalad inherit it.

    ponytail: process-global; fine because Studio/CLI is one local process per
    user. Switch to per-call env if Studio ever serves several users at once.
    """
    os.environ.update(identity_env(identity))
```

- [ ] **Step 4: Run to verify pass**

Run: `python -m pytest tests/test_share_publish_identity.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git branch --show-current   # must be feat/share-publish
git add src/share_publish.py tests/test_share_publish_identity.py
git commit -m "feat(publish): identity resolution for share publishing

Co-Authored-By: Claude Sonnet 5.5 <noreply@anthropic.com>"
```

---

### Task 2: Validation gate, audit log, publish

**Files:**
- Modify: `src/share_publish.py` (append)
- Test: `tests/test_share_publish_gate.py`

**Interfaces:**
- Consumes: `Identity`, `resolve_identity`, `apply_identity` (Task 1); `is_datalad_dataset`, `run_datalad_push`, `run_datalad_push_verify` from `src.datalad_execution`; `load_config` from `src.config` (`.datalad_sibling_name`); `src.core.validation.validate_dataset`, `determine_exit_code`.
- Produces: `validate_for_publish(project_root) -> list[str]` (error messages, empty = valid); `has_sibling(project_root, sibling_name) -> bool`; `can_publish(project_root) -> bool` (datalad dataset **and** configured sibling present); `audit_path(project_root) -> Path`; `publish_to_server(project_root, *, sibling_name=None, identity=None, line_callback=None) -> dict` with keys `success: bool`, `reason: str` (`"pushed" | "no_identity" | "not_a_dataset" | "no_sibling" | "validation_errors" | "push_failed"`), `errors: list[str]`, `message: str`, `push: dict | None`, `verify: dict | None`.

- [ ] **Step 1: Read before writing.** Read `ProjectManager._iter_datalad_dataset_roots` (`app/src/project_manager.py:5759`) and confirm `from src.core.validation import validate_dataset, determine_exit_code` imports in a test (`python3 -c "from src.core.validation import validate_dataset"` from `app/` on path; if it only works as bare `core.validation`, use that form and keep it identical in the module). Run `python3 -c "import src.core.validation as m; print(m.__file__)"` per CLAUDE.md dual-tree rule.

- [ ] **Step 2: Write the failing test**

```python
# tests/test_share_publish_gate.py
import json
import os
import subprocess

import pytest

import src.share_publish as sp
from src.share_publish import Identity

ADA = Identity("Ada", "ada@uni.at")


def git(*args, cwd):
    subprocess.run(["git", *args], cwd=cwd, check=True, capture_output=True)


@pytest.fixture
def share(tmp_path, monkeypatch):
    server = tmp_path / "server.git"
    subprocess.run(["git", "init", "-q", "--bare", str(server)], check=True)
    root = tmp_path / "share" / "study"
    root.mkdir(parents=True)
    git("init", "-q", cwd=root)
    git("remote", "add", "ria-store", str(server), cwd=root)
    (root / ".datalad").mkdir()
    monkeypatch.setattr(sp, "is_datalad_dataset", lambda p: True)
    pushes = []

    def fake_push(project_root, **kw):
        pushes.append(kw)
        return {"success": True, "message": "ok"}

    monkeypatch.setattr(sp, "run_datalad_push", fake_push)
    monkeypatch.setattr(
        sp, "run_datalad_push_verify",
        lambda *a, **kw: {"success": True, "verified": True, "message": "ok"},
    )
    monkeypatch.setattr(sp, "_dataset_roots", lambda p: [p])
    monkeypatch.setattr(sp, "validate_for_publish", lambda p: [])
    root.pushes = pushes  # type: ignore[attr-defined]
    return root


def audit_lines(root):
    return [json.loads(l) for l in sp.audit_path(root).read_text().splitlines()]


def test_valid_dataset_is_pushed_and_audited(share):
    result = sp.publish_to_server(share, identity=ADA)
    assert result["success"] and result["reason"] == "pushed"
    assert share.pushes and share.pushes[0]["sibling_name"] == "ria-store"
    [line] = audit_lines(share)
    assert line["result"] == "pushed" and line["identity"] == "Ada <ada@uni.at>"
    assert line["error_count"] == 0 and line["sibling"] == "ria-store"


def test_invalid_dataset_is_refused_and_nothing_is_pushed(share, monkeypatch):
    monkeypatch.setattr(sp, "validate_for_publish", lambda p: ["PRISM101 bad", "PRISM102 worse"])
    result = sp.publish_to_server(share, identity=ADA)
    assert not result["success"] and result["reason"] == "validation_errors"
    assert result["errors"] == ["PRISM101 bad", "PRISM102 worse"]
    assert share.pushes == []
    [line] = audit_lines(share)
    assert line["result"] == "refused" and line["error_count"] == 2


def test_missing_identity_is_refused_before_validation_and_audited(share, monkeypatch):
    monkeypatch.setattr(sp, "resolve_identity", lambda *a: None)
    monkeypatch.setattr(sp, "validate_for_publish", lambda p: pytest.fail("must not validate"))
    result = sp.publish_to_server(share)
    assert result["reason"] == "no_identity" and share.pushes == []
    assert audit_lines(share)[0]["identity"] is None


def test_missing_sibling_is_refused(share):
    result = sp.publish_to_server(share, sibling_name="nope", identity=ADA)
    assert result["reason"] == "no_sibling" and share.pushes == []


def test_not_a_dataset_is_refused(share, monkeypatch):
    monkeypatch.setattr(sp, "is_datalad_dataset", lambda p: False)
    assert sp.publish_to_server(share, identity=ADA)["reason"] == "not_a_dataset"


def test_failed_push_is_reported_and_audited(share, monkeypatch):
    monkeypatch.setattr(sp, "run_datalad_push", lambda *a, **k: {"success": False, "message": "boom"})
    result = sp.publish_to_server(share, identity=ADA)
    assert not result["success"] and result["reason"] == "push_failed"
    assert audit_lines(share)[0]["result"] == "push_failed"


def test_publishing_does_not_dirty_the_working_tree(share):
    sp.publish_to_server(share, identity=ADA)
    status = subprocess.run(
        ["git", "status", "--porcelain"], cwd=share, capture_output=True, text=True, check=True
    ).stdout
    assert status.strip() == ".datalad/" or status.strip() == "" or "publish" not in status


def test_can_publish_needs_dataset_and_sibling(share, monkeypatch):
    assert sp.can_publish(share) is True
    monkeypatch.setattr(sp, "is_datalad_dataset", lambda p: False)
    assert sp.can_publish(share) is False
```

(Note: the dirty-tree test only asserts the audit file does not show up in `git status`; `.datalad/` empty dir is untracked-invisible. Keep as written.)

- [ ] **Step 3: Run to verify failure**

Run: `python -m pytest tests/test_share_publish_gate.py -v`
Expected: FAIL (`AttributeError: module 'src.share_publish' has no attribute 'publish_to_server'`).

- [ ] **Step 4: Implement** (append to `src/share_publish.py`; add imports at top of file)

```python
import json
import subprocess
from datetime import datetime, timezone
from pathlib import Path

from src.datalad_execution import (
    is_datalad_dataset,
    run_datalad_push,
    run_datalad_push_verify,
)


def _git(root: Path, *args: str) -> str:
    out = subprocess.run(
        ["git", "-C", str(root), *args], capture_output=True, text=True, check=False
    )
    return out.stdout.strip() if out.returncode == 0 else ""


def _sibling_for(root: Path, sibling_name: str | None) -> str:
    if sibling_name:
        return sibling_name
    from src.config import load_config

    return str(load_config(str(root)).datalad_sibling_name or "").strip() or "ria-store"


def has_sibling(project_root, sibling_name: str) -> bool:
    return sibling_name in _git(Path(project_root), "remote").split()


def can_publish(project_root, sibling_name: str | None = None) -> bool:
    root = Path(project_root)
    return is_datalad_dataset(root) and has_sibling(root, _sibling_for(root, sibling_name))


def audit_path(project_root) -> Path:
    git_dir = Path(_git(Path(project_root), "rev-parse", "--absolute-git-dir"))
    return git_dir / "prism" / "publish.jsonl"


def _audit(root: Path, *, identity: Identity | None, sibling: str, result: str, error_count: int) -> None:
    path = audit_path(root)
    path.parent.mkdir(parents=True, exist_ok=True)
    entry = {
        "timestamp": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "identity": f"{identity.name} <{identity.email}>" if identity else None,
        "sibling": sibling,
        "result": result,
        "error_count": error_count,
    }
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(entry, ensure_ascii=False) + "\n")


def _describe(issue) -> str:
    if isinstance(issue, tuple):
        return " ".join(str(part) for part in issue[1:2]) or str(issue)
    code = getattr(issue, "code", "")
    return f"{code} {getattr(issue, 'message', issue)}".strip()


def validate_for_publish(project_root) -> list[str]:
    """Error messages from a full PRISM validation; empty list means valid.

    ponytail: PRISM checks only, no BIDS validator (needs deno on every share).
    """
    from src.core.validation import determine_exit_code, validate_dataset

    issues, _stats = validate_dataset(str(project_root), run_bids=False, run_prism=True)
    return [_describe(i) for i in issues if determine_exit_code([i])]


def _dataset_roots(root: Path) -> list[Path]:
    from src.project_manager import ProjectManager

    return ProjectManager()._iter_datalad_dataset_roots(root)


def publish_to_server(
    project_root, *, sibling_name: str | None = None, identity: Identity | None = None, line_callback=None
) -> dict:
    root = Path(project_root)
    sibling = _sibling_for(root, sibling_name)
    identity = identity or resolve_identity()
    outcome = {"success": False, "reason": "", "errors": [], "message": "", "push": None, "verify": None}

    def finish(reason: str, message: str, *, audit_result: str, errors=()) -> dict:
        outcome.update(reason=reason, message=message, errors=list(errors))
        _audit(root, identity=identity, sibling=sibling, result=audit_result, error_count=len(outcome["errors"]))
        return outcome

    if not is_datalad_dataset(root):
        return finish("not_a_dataset", "This folder is not a DataLad dataset.", audit_result="refused")
    if identity is None:
        return finish(
            "no_identity",
            'No identity. Pass --as "Name <email>", set PRISM_USER_NAME/PRISM_USER_EMAIL, or configure git user.name/user.email.',
            audit_result="refused",
        )
    if not has_sibling(root, sibling):
        return finish("no_sibling", f'No sibling named "{sibling}" in this dataset.', audit_result="refused")
    errors = validate_for_publish(root)
    if errors:
        return finish(
            "validation_errors",
            f"{len(errors)} validation error(s). Fix them before publishing.",
            audit_result="refused",
            errors=errors,
        )

    apply_identity(identity)
    push = run_datalad_push(root, sibling_name=sibling, line_callback=line_callback)
    outcome["push"] = push
    if push.get("success"):
        # ponytail: plain (non-RIA) share sibling assumed; RIA would need is_ria=True.
        verify = run_datalad_push_verify(
            root, sibling_name=sibling, dataset_roots=_dataset_roots(root), is_ria=False
        )
        outcome["verify"] = verify
        if verify.get("verified"):
            outcome["success"] = True
            return finish("pushed", "Published to the server.", audit_result="pushed")
        return finish("push_failed", f"Push not verified: {verify.get('message')}", audit_result="push_failed")
    return finish("push_failed", str(push.get("message") or "Push failed."), audit_result="push_failed")
```

Fix as you go: `finish` sets `success` only in the pushed branch (done via `outcome["success"] = True` before calling).

- [ ] **Step 5: Run to verify pass**

Run: `python -m pytest tests/test_share_publish_gate.py tests/test_share_publish_identity.py -v`
Expected: PASS

- [ ] **Step 6: Commit**

```bash
git add src/share_publish.py tests/test_share_publish_gate.py
git commit -m "feat(publish): validity-gated push with audit log

Co-Authored-By: Claude Sonnet 5.5 <noreply@anthropic.com>"
```

---

### Task 3: Pre-push hook

**Files:**
- Modify: `src/share_publish.py` (append)
- Test: `tests/test_share_publish_hook.py`

**Interfaces:**
- Consumes: `audit_path`, `_audit`, `validate_for_publish` (Task 2).
- Produces: `HOOK_MARKER = "# prism-publish-hook"`; `HookExistsError(Exception)`; `install_hook(project_root, sibling_name: str | None = None) -> Path`; `check_for_hook(project_root, sibling_name: str | None = None) -> list[str]` (validate only, audit `hook_allowed`/`hook_refused`, returns error messages).

The hook script is `sh`, runs only for the server remote, and calls `"$PRISM_TOOLS" publish --check --project "$(git rev-parse --show-toplevel)"` (default `prism_tools` on PATH). The project root is **not** baked in: the share mounts at different paths per user. If the tool cannot be found, the hook **blocks**.

- [ ] **Step 1: Write the failing test**

```python
# tests/test_share_publish_hook.py
import os
import stat
import subprocess

import pytest

import src.share_publish as sp


def run(*args, cwd, env=None, check=True):
    return subprocess.run(
        list(args), cwd=cwd, capture_output=True, text=True, check=check, env=env
    )


@pytest.fixture
def repos(tmp_path):
    server = tmp_path / "server.git"
    other = tmp_path / "other.git"
    for bare in (server, other):
        run("git", "init", "-q", "--bare", str(bare), cwd=tmp_path)
    share = tmp_path / "share"
    run("git", "init", "-q", str(share), cwd=tmp_path)
    run("git", "remote", "add", "ria-store", str(server), cwd=share)
    run("git", "remote", "add", "elsewhere", str(other), cwd=share)
    (share / "f").write_text("x")
    run("git", "add", "f", cwd=share)
    run("git", "-c", "user.name=t", "-c", "user.email=t@t.t", "commit", "-q", "-m", "m", cwd=share)
    run("git", "branch", "-M", "main", cwd=share)
    return share


def fake_tool(tmp_path, exit_code):
    tool = tmp_path / f"prism_tools_{exit_code}"
    tool.write_text(f"#!/bin/sh\nexit {exit_code}\n")
    tool.chmod(tool.stat().st_mode | stat.S_IEXEC)
    return tool


def push(share, remote, tool=None):
    env = {**os.environ}
    env.pop("PRISM_TOOLS", None)
    if tool:
        env["PRISM_TOOLS"] = str(tool)
    else:
        env["PATH"] = "/usr/bin:/bin"  # no prism_tools anywhere
    return run("git", "push", remote, "main", cwd=share, env=env, check=False)


def test_hook_blocks_server_push_when_check_fails(repos, tmp_path):
    sp.install_hook(repos, "ria-store")
    assert push(repos, "ria-store", fake_tool(tmp_path, 1)).returncode != 0


def test_hook_allows_server_push_when_check_passes(repos, tmp_path):
    sp.install_hook(repos, "ria-store")
    assert push(repos, "ria-store", fake_tool(tmp_path, 0)).returncode == 0


def test_hook_ignores_other_remotes(repos, tmp_path):
    sp.install_hook(repos, "ria-store")
    assert push(repos, "elsewhere", fake_tool(tmp_path, 1)).returncode == 0


def test_hook_fails_closed_when_tool_is_missing(repos):
    sp.install_hook(repos, "ria-store")
    result = push(repos, "ria-store", tool=None)
    assert result.returncode != 0 and "PRISM_TOOLS" in result.stderr


def test_install_refuses_to_overwrite_a_foreign_hook(repos):
    hook = repos / ".git" / "hooks" / "pre-push"
    hook.write_text("#!/bin/sh\necho mine\n")
    with pytest.raises(sp.HookExistsError):
        sp.install_hook(repos, "ria-store")
    assert "mine" in hook.read_text()


def test_install_is_idempotent_for_our_own_hook(repos):
    sp.install_hook(repos, "ria-store")
    sp.install_hook(repos, "ria-store")  # no error
    assert sp.HOOK_MARKER in (repos / ".git" / "hooks" / "pre-push").read_text()


def test_check_for_hook_audits_and_returns_errors(repos, monkeypatch):
    monkeypatch.setattr(sp, "validate_for_publish", lambda p: ["PRISM1 bad"])
    assert sp.check_for_hook(repos, "ria-store") == ["PRISM1 bad"]
    assert "hook_refused" in sp.audit_path(repos).read_text()
```

- [ ] **Step 2: Run to verify failure**

Run: `python -m pytest tests/test_share_publish_hook.py -v`
Expected: FAIL (`AttributeError: ... install_hook`).

- [ ] **Step 3: Implement** (append)

```python
import shlex
import stat

HOOK_MARKER = "# prism-publish-hook"


class HookExistsError(Exception):
    pass


def _hook_script(sibling_name: str) -> str:
    return f"""#!/bin/sh
{HOOK_MARKER}
# Blocks pushes to "{sibling_name}" unless the dataset validates.
[ "$1" = {shlex.quote(sibling_name)} ] || exit 0
TOOLS="${{PRISM_TOOLS:-prism_tools}}"
if ! command -v "$TOOLS" >/dev/null 2>&1; then
  echo "PRISM publish gate: '$TOOLS' not found. Set PRISM_TOOLS to the prism_tools executable. Push blocked." >&2
  exit 1
fi
exec "$TOOLS" publish --check --project "$(git rev-parse --show-toplevel)"
"""


def install_hook(project_root, sibling_name: str | None = None) -> Path:
    root = Path(project_root)
    sibling = _sibling_for(root, sibling_name)
    hooks = Path(_git(root, "rev-parse", "--path-format=absolute", "--git-path", "hooks"))
    hooks.mkdir(parents=True, exist_ok=True)
    hook = hooks / "pre-push"
    if hook.exists() and HOOK_MARKER not in hook.read_text(encoding="utf-8", errors="replace"):
        raise HookExistsError(f"{hook} already exists and is not a PRISM hook; not overwriting.")
    hook.write_text(_hook_script(sibling), encoding="utf-8")
    hook.chmod(hook.stat().st_mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)
    return hook


def check_for_hook(project_root, sibling_name: str | None = None) -> list[str]:
    """Validate only (no identity needed); used by the pre-push hook."""
    root = Path(project_root)
    errors = validate_for_publish(root)
    _audit(
        root,
        identity=resolve_identity(),
        sibling=_sibling_for(root, sibling_name),
        result="hook_refused" if errors else "hook_allowed",
        error_count=len(errors),
    )
    return errors
```

Note: `check_for_hook` uses `resolve_identity()`; if `--as` is malformed that is not involved here, so it cannot raise.

- [ ] **Step 4: Run to verify pass**

Run: `python -m pytest tests/test_share_publish_hook.py -v`
Expected: PASS. (`--path-format=absolute` needs git ≥ 2.31; if the test machine is older, replace with `git rev-parse --git-path hooks` joined to `root` when relative.)

- [ ] **Step 5: Commit**

```bash
git add src/share_publish.py tests/test_share_publish_hook.py
git commit -m "feat(publish): pre-push hook that gates the server sibling on validity

Co-Authored-By: Claude Sonnet 5.5 <noreply@anthropic.com>"
```

---

### Task 4: CLI `prism_tools publish`

**Files:**
- Create: `app/src/cli/commands/publish.py`
- Modify: `app/src/cli/parser.py` (add subparser before `parser_environment`; add `"publish": parser_publish` to the returned parsers dict at ~line 2138)
- Modify: `app/src/cli/dispatch.py` (add `elif args.command == "publish": handlers["publish"](args)` after the `session-map` branch)
- Modify: `app/src/cli/entrypoint.py` (import `cmd_publish` near line 63; add `"publish": cmd_publish,` to the handlers dict near line 147)
- Modify: `docs/CLI_REFERENCE.md` (a short `publish` section; mirror an existing section's layout), `docs/DATALAD.md` (a "Publishing from a department share" section: the rule, `PRISM_USER_NAME/EMAIL`, hook install, `--no-verify` caveat, nested-dataset gap)
- Test: `tests/test_cli_publish.py`

**Interfaces:**
- Consumes: `publish_to_server`, `check_for_hook`, `install_hook`, `HookExistsError`, `parse_identity` (Tasks 1-3).
- Produces: `cmd_publish(args)` exit codes: `0` success/valid, `1` refused because of validation errors, `2` any other refusal/usage error. Flags: `--project` (required), `--sibling`, `--as`, `--check`, `--install-hook`, `--json`.

- [ ] **Step 1: Write the failing test**

```python
# tests/test_cli_publish.py
import json
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

APP_ROOT = Path(__file__).resolve().parents[1] / "app"
if str(APP_ROOT) not in sys.path:
    sys.path.insert(0, str(APP_ROOT))

import src.cli.commands.publish as pub  # noqa: E402
from src.cli.parser import build_prism_tools_parsers  # noqa: E402


def args(**kw):
    base = dict(project="/p", sibling=None, as_identity=None, check=False, install_hook=False, json=True)
    base.update(kw)
    return SimpleNamespace(**base)


def run(monkeypatch, capsys, **kw):
    with pytest.raises(SystemExit) as info:
        pub.cmd_publish(args(**kw))
    return info.value.code, json.loads(capsys.readouterr().out)


def test_parser_accepts_publish_flags():
    parser, _ = build_prism_tools_parsers()
    ns = parser.parse_args(
        ["publish", "--project", "/p", "--as", "A <a@b.c>", "--sibling", "s", "--check", "--install-hook"]
    )
    assert (ns.command, ns.project, ns.as_identity, ns.sibling, ns.check, ns.install_hook) == (
        "publish", "/p", "A <a@b.c>", "s", True, True,
    )


def test_publish_success_exit_0(monkeypatch, capsys):
    monkeypatch.setattr(pub, "publish_to_server", lambda *a, **k: {"success": True, "reason": "pushed", "errors": [], "message": "ok"})
    code, out = run(monkeypatch, capsys, as_identity="A <a@b.c>")
    assert code == 0 and out["reason"] == "pushed"


@pytest.mark.parametrize("reason, code", [("validation_errors", 1), ("no_identity", 2), ("no_sibling", 2)])
def test_publish_refusal_exit_codes(monkeypatch, capsys, reason, code):
    monkeypatch.setattr(pub, "publish_to_server", lambda *a, **k: {"success": False, "reason": reason, "errors": ["e"], "message": "m"})
    assert run(monkeypatch, capsys)[0] == code


def test_bad_identity_is_exit_2(monkeypatch, capsys):
    assert run(monkeypatch, capsys, as_identity="garbage")[0] == 2


def test_check_mode_uses_validate_only(monkeypatch, capsys):
    monkeypatch.setattr(pub, "check_for_hook", lambda *a, **k: ["PRISM1 bad"])
    monkeypatch.setattr(pub, "publish_to_server", lambda *a, **k: pytest.fail("must not push"))
    code, out = run(monkeypatch, capsys, check=True)
    assert code == 1 and out["errors"] == ["PRISM1 bad"]


def test_install_hook_reports_existing_hook_as_exit_2(monkeypatch, capsys):
    def boom(*a, **k):
        raise pub.HookExistsError("already there")

    monkeypatch.setattr(pub, "install_hook", boom)
    assert run(monkeypatch, capsys, install_hook=True)[0] == 2
```

- [ ] **Step 2: Run to verify failure**

Run: `python -m pytest tests/test_cli_publish.py -v`
Expected: FAIL (`ModuleNotFoundError: src.cli.commands.publish`).

- [ ] **Step 3: Implement**

```python
# app/src/cli/commands/publish.py
"""prism_tools publish: thin adapter over src.share_publish."""

from __future__ import annotations

import json
import sys

from src.share_publish import (
    HookExistsError,
    check_for_hook,
    install_hook,
    parse_identity,
    publish_to_server,
)


def _emit(args, payload: dict, code: int) -> None:
    if getattr(args, "json", False):
        print(json.dumps(payload, indent=2, ensure_ascii=False))
    else:
        print(payload.get("message", ""))
        for error in payload.get("errors", []):
            print(f"  - {error}")
    sys.exit(code)


def cmd_publish(args) -> None:
    if args.install_hook:
        try:
            hook = install_hook(args.project, args.sibling)
        except HookExistsError as exc:
            _emit(args, {"success": False, "reason": "hook_exists", "errors": [], "message": str(exc)}, 2)
        _emit(args, {"success": True, "reason": "hook_installed", "errors": [], "message": f"Installed {hook}"}, 0)

    if args.check:
        errors = check_for_hook(args.project, args.sibling)
        message = "Valid." if not errors else f"{len(errors)} validation error(s)."
        _emit(args, {"success": not errors, "reason": "valid" if not errors else "validation_errors", "errors": errors, "message": message}, 1 if errors else 0)

    try:
        identity = parse_identity(args.as_identity) if args.as_identity else None
    except ValueError as exc:
        _emit(args, {"success": False, "reason": "bad_identity", "errors": [], "message": str(exc)}, 2)

    result = publish_to_server(args.project, sibling_name=args.sibling, identity=identity)
    code = 0 if result["success"] else 1 if result["reason"] == "validation_errors" else 2
    _emit(args, result, code)
```

Parser (insert before `parser_environment = subparsers.add_parser(`):

```python
    parser_publish = subparsers.add_parser(
        "publish",
        help="Push a department-share dataset to the DataLad server (only if it validates)",
    )
    parser_publish.add_argument("--project", required=True, help="Dataset root on the share")
    parser_publish.add_argument("--sibling", help="Server sibling name (default: project's configured sibling)")
    parser_publish.add_argument(
        "--as", dest="as_identity", help='Who is publishing: "Name <email>" (else PRISM_USER_NAME/EMAIL, else git config)'
    )
    parser_publish.add_argument("--check", action="store_true", help="Validate only; exit 1 on errors (used by the pre-push hook)")
    parser_publish.add_argument("--install-hook", action="store_true", help="Install the git pre-push hook that enforces the same rule")
    parser_publish.add_argument("--json", action="store_true", help="Emit machine-readable JSON")
```

Then add the dict entry `"publish": parser_publish,`, the dispatch branch, and the entrypoint import/handler entries exactly as listed under **Files**.

- [ ] **Step 4: Run to verify pass**

Run: `python -m pytest tests/test_cli_publish.py tests/test_cli_no_web_layer_imports.py tests/test_cli_dispatch_routing.py tests/test_cli_parity_commands.py -v`
Expected: PASS

- [ ] **Step 5: Docs, then commit**

```bash
git add app/src/cli tests/test_cli_publish.py docs/CLI_REFERENCE.md docs/DATALAD.md
git commit -m "feat(publish): prism_tools publish command (--check, --install-hook, --as)

Co-Authored-By: Claude Sonnet 5.5 <noreply@anthropic.com>"
```

---

### Task 5: GUI: route, `publishable`, validator-results button

**Files:**
- Modify: `app/src/web/blueprints/projects_datalad_server_blueprint.py` (new route `POST /api/projects/datalad-server/publish`)
- Modify: `app/src/web/blueprints/validation.py` (`_build_validation_results_payload`: add `results["publishable"]`; `show_results`: pass `publish_path`)
- Create: `app/static/js/publish.js` (shared by both pages)
- Modify: `app/templates/results.html` (Publish button next to the action buttons around line 53-62)
- Test: `tests/test_publish_routes.py`

**Interfaces:**
- Consumes: `can_publish`, `publish_to_server`, `parse_identity` (Tasks 1-2); `_resolve_project_root_path` (already in the blueprint module).
- Produces: `POST /api/projects/datalad-server/publish` body `{project_path, name?, email?}` → JSON `publish_to_server` result (HTTP 200 on success, 409 on `validation_errors`, 400 on other refusals); `results["publishable"]: bool`; JS `window.prismPublish(projectPath, identity?) -> Promise<object>`.

- [ ] **Step 1: Read first.** Read how an existing test drives these blueprints (`grep -ln "datalad-server\|validation_bp\|_validation_results" tests/*.py`) and copy its Flask-client fixture; read `_resolve_project_root_path` in the datalad-server blueprint; confirm `results["summary"]["total_errors"]` exists in the payload (`validation.py:292-312`).

- [ ] **Step 2: Write the failing tests**

```python
# tests/test_publish_routes.py
# Use the Flask client fixture pattern found in Step 1 (called `client` below).
import pytest

import src.web.blueprints.validation as val
import src.web.blueprints.projects_datalad_server_blueprint as srv


def build(monkeypatch, *, errors, run_prism=True, publishable_dataset=True):
    monkeypatch.setattr(val, "can_publish", lambda p: publishable_dataset)
    monkeypatch.setattr(
        val, "format_validation_results",
        lambda issues, stats, root: {"summary": {"total_errors": errors, "bids_errors": 0}, "errors": [], "warnings": []},
    )
    return val._build_validation_results_payload(
        issues=[], dataset_stats=None, dataset_path="/p", schema_version="stable", job_id="j",
        library_path=None, run_bids=not run_prism, run_prism=run_prism, show_bids_warnings=False,
    )


def test_publishable_only_for_clean_prism_run_on_a_publishable_dataset(monkeypatch):
    assert build(monkeypatch, errors=0)["publishable"] is True
    assert build(monkeypatch, errors=2)["publishable"] is False
    assert build(monkeypatch, errors=0, run_prism=False)["publishable"] is False  # BIDS-only hides PRISM errors
    assert build(monkeypatch, errors=0, publishable_dataset=False)["publishable"] is False  # e.g. temp upload


def test_publish_route_refused_returns_errors_409(client, monkeypatch):
    monkeypatch.setattr(srv, "_resolve_project_root_path", lambda p: __import__("pathlib").Path("/p"))
    monkeypatch.setattr(
        srv, "publish_to_server",
        lambda *a, **k: {"success": False, "reason": "validation_errors", "errors": ["PRISM1"], "message": "m"},
    )
    resp = client.post("/api/projects/datalad-server/publish", json={"project_path": "/p", "name": "A", "email": "a@b.c"})
    assert resp.status_code == 409 and resp.get_json()["errors"] == ["PRISM1"]


def test_publish_route_ignores_any_client_valid_flag(client, monkeypatch):
    seen = {}
    monkeypatch.setattr(srv, "_resolve_project_root_path", lambda p: __import__("pathlib").Path("/p"))

    def fake(root, **kw):
        seen.update(kw)
        return {"success": True, "reason": "pushed", "errors": [], "message": "ok"}

    monkeypatch.setattr(srv, "publish_to_server", fake)
    resp = client.post("/api/projects/datalad-server/publish", json={"project_path": "/p", "valid": True})
    assert resp.status_code == 200 and "valid" not in seen


def test_publish_route_bad_email_is_400(client, monkeypatch):
    monkeypatch.setattr(srv, "_resolve_project_root_path", lambda p: __import__("pathlib").Path("/p"))
    resp = client.post("/api/projects/datalad-server/publish", json={"project_path": "/p", "name": "A", "email": "nope"})
    assert resp.status_code == 400
```

- [ ] **Step 3: Run to verify failure**

Run: `python -m pytest tests/test_publish_routes.py -v`
Expected: FAIL (`AttributeError ... can_publish` / 404 on the route).

- [ ] **Step 4: Implement**

`validation.py`, import at top `from src.share_publish import can_publish`, and inside `_build_validation_results_payload` right after the two `_apply_*` filters:

```python
    results["publishable"] = bool(
        run_prism
        and int(results.get("summary", {}).get("total_errors", 0)) == 0
        and can_publish(dataset_path)
    )
```

`show_results`: pass `publish_path=data.get("dataset_path") if results.get("publishable") else ""` to `render_template`.

Blueprint route (add to `projects_datalad_server_blueprint.py`, import `publish_to_server`, `Identity`, `parse_identity` from `src.share_publish` at module top):

```python
@projects_datalad_server_bp.route("/api/projects/datalad-server/publish", methods=["POST"])
def datalad_server_publish():
    """Validity-gated push of a share dataset (same code path as `prism_tools publish`).

    ponytail: synchronous; move onto the _ria_jobs machinery if share pushes get slow.
    """
    data = request.get_json() or {}
    resolved = _resolve_project_root_path(str(data.get("project_path") or ""))
    if resolved is None:
        return jsonify({"error": "Invalid project path"}), 400
    identity = None
    if data.get("name") or data.get("email"):
        try:
            identity = parse_identity(f'{data.get("name", "")} <{data.get("email", "")}>')
        except ValueError as exc:
            return jsonify({"error": str(exc)}), 400
    result = publish_to_server(resolved, sibling_name=data.get("sibling_name") or None, identity=identity)
    status = 200 if result["success"] else 409 if result["reason"] == "validation_errors" else 400
    return jsonify(result), status
```

`app/static/js/publish.js`:

```javascript
// Shared by the validator results page and the project page.
// Backend re-validates on every call; this only transports the request.
window.prismPublish = async function (projectPath, identity) {
  const resp = await fetch('/api/projects/datalad-server/publish', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ project_path: projectPath, ...(identity || {}) }),
  });
  const body = await resp.json();
  body.http_status = resp.status;
  return body;
};
```

`results.html` (next to the Download Report button, line ~53): render only when `publish_path`:

```html
{% if publish_path %}
<button type="button" class="btn btn-warning" id="publishBtn" data-result-action
        data-project-path="{{ publish_path }}" title="Push this dataset to the server (validated again first)">
    <i class="fas fa-cloud-upload-alt me-2"></i>Publish to server
</button>
{% elif results.get('summary', {}).get('total_errors', 0) > 0 and results.get('run_prism') %}
<button type="button" class="btn btn-outline-secondary" disabled title="Fix the errors first">
    <i class="fas fa-cloud-upload-alt me-2"></i>Fix {{ results.summary.total_errors }} error(s) before publishing
</button>
{% endif %}
```

and at the end of the template's script block:

```html
<script src="{{ url_for('static', filename='js/publish.js') }}"></script>
<script>
document.getElementById('publishBtn')?.addEventListener('click', async (ev) => {
  const btn = ev.currentTarget;
  let identity = null;
  let res = await window.prismPublish(btn.dataset.projectPath);
  if (res.reason === 'no_identity') {
    const name = prompt('Your name for the audit log:');
    const email = name && prompt('Your email:');
    if (!name || !email) return;
    identity = { name, email };
    res = await window.prismPublish(btn.dataset.projectPath, identity);
  }
  if (res.success) { alert(res.message); return; }
  alert(res.message + (res.errors?.length ? '\n\n' + res.errors.join('\n') : ''));
  if (res.reason === 'validation_errors') location.reload();  // stale result: re-run validation view
});
</script>
```

(`prompt`/`alert` is the lazy dialog; swap for a Bootstrap modal if the team wants styling.)

- [ ] **Step 5: Run to verify pass**

Run: `python -m pytest tests/test_publish_routes.py tests/test_cli_no_web_layer_imports.py -v`
Expected: PASS

- [ ] **Step 6: Commit**

```bash
git add app/src/web app/static/js/publish.js app/templates/results.html tests/test_publish_routes.py
git commit -m "feat(publish): Studio publish route and validator-results Publish button

Co-Authored-By: Claude Sonnet 5.5 <noreply@anthropic.com>"
```

---

### Task 6: Attribute all PRISM edits + project-page button

**Files:**
- Modify: `app/src/cli/entrypoint.py` (apply identity env at start of `main`)
- Modify: `app/prism-studio.py` or the Flask app factory where startup happens (apply the same at startup; find with `grep -n "create_app\|def main" app/prism-studio.py`)
- Modify: `app/templates/projects.html` (Publish button inside the existing "Push to DataLad Server" panel, calling `window.prismPublish` the same way as Task 5)
- Create: `src/share_publish.py` addition `apply_env_identity() -> Identity | None`
- Test: `tests/test_share_publish_env_identity.py`

**Interfaces:**
- Consumes: `resolve_identity`, `apply_identity` (Task 1).
- Produces: `apply_env_identity() -> Identity | None`: if `PRISM_USER_NAME` and `PRISM_USER_EMAIL` are both set, applies them and returns the identity, else does nothing and returns `None` (never reads global git config here: git already uses it by itself).

- [ ] **Step 1: Write the failing test**

```python
# tests/test_share_publish_env_identity.py
import os

import src.share_publish as sp


def test_applies_only_when_both_prism_vars_are_set(monkeypatch):
    for key in ("PRISM_USER_NAME", "PRISM_USER_EMAIL", "GIT_AUTHOR_NAME"):
        monkeypatch.delenv(key, raising=False)
    assert sp.apply_env_identity() is None and "GIT_AUTHOR_NAME" not in os.environ
    monkeypatch.setenv("PRISM_USER_NAME", "Ada")
    assert sp.apply_env_identity() is None
    monkeypatch.setenv("PRISM_USER_EMAIL", "ada@uni.at")
    assert sp.apply_env_identity() == sp.Identity("Ada", "ada@uni.at")
    assert os.environ["GIT_COMMITTER_EMAIL"] == "ada@uni.at"
    monkeypatch.delenv("GIT_AUTHOR_NAME"); monkeypatch.delenv("GIT_AUTHOR_EMAIL")
    monkeypatch.delenv("GIT_COMMITTER_NAME"); monkeypatch.delenv("GIT_COMMITTER_EMAIL")
```

- [ ] **Step 2: Run to verify failure**

Run: `python -m pytest tests/test_share_publish_env_identity.py -v`
Expected: FAIL (`no attribute 'apply_env_identity'`).

- [ ] **Step 3: Implement**

```python
def apply_env_identity() -> Identity | None:
    name, email = os.environ.get("PRISM_USER_NAME", "").strip(), os.environ.get("PRISM_USER_EMAIL", "").strip()
    if not (name and email):
        return None
    identity = Identity(name, email)
    apply_identity(identity)
    return identity
```

Call `apply_env_identity()` as the first statement of the CLI `main` in `entrypoint.py` and at Studio startup (import it from `src.share_publish`; the CLI-boundary test still passes, since it is not a `src.web` import). Add the project-page button by copying the Task 5 handler to `projects.html` (button id `publishProjectBtn`, project path from the page's existing current-project variable; find how the existing "Sync to server" button reads it and use the same).

- [ ] **Step 4: Run to verify pass**

Run: `python -m pytest tests/test_share_publish_env_identity.py tests/test_cli_no_web_layer_imports.py -v`
Expected: PASS

- [ ] **Step 5: Full suite and manual smoke**

Run: `python -m pytest tests -x -q --ignore=tests/e2e`
Expected: PASS (no regressions). Then manually: create a dataset with a bare-repo sibling named `ria-store`, `prism_tools publish --project <ds> --as "Ada <a@b.c>"`: refused with errors on an invalid dataset; pushed on a valid one; check `<ds>/.git/prism/publish.jsonl` has both lines.

- [ ] **Step 6: Commit**

```bash
git add src/share_publish.py app tests/test_share_publish_env_identity.py
git commit -m "feat(publish): attribute PRISM edits via process identity; project-page Publish button

Co-Authored-By: Claude Sonnet 5.5 <noreply@anthropic.com>"
```

---

## Self-review notes

- Spec coverage: gate (T2), hook (T3), identity + audit (T1, T2, T6), CLI (T4), validator-results button + project-page button + re-validation (T5, T6), parity/boundary tests (T4), docs (T4). Open items carried verbatim into Review Focus.
- Resolved vs. the spec: audit log moved from `.prism/publish.log` to `<git-dir>/prism/publish.jsonl` (spec updated); identity for PRISM edits via process env rather than parameter threading (spec updated).
- Decision needed from the owner (not in any task): the existing **"Push to DataLad Server" / `sync_project_to_ria`** flow (`app/src/project_manager.py:6347`, blueprint `/api/projects/datalad-server/sync/start`) pushes **without** validation. It is a separate backup flow that also (re)creates the sibling. Left untouched so existing behaviour does not change; on a share where the gate matters it is a GUI bypass.
