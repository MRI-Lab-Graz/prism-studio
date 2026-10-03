"""Save gate: a commit in a PRISM dataset is allowed only if the dataset validates.

Enforced by a git pre-commit hook in every dataset root (see install_save_hooks);
the hook calls `prism_tools save-gate --check`. One implementation: the CLI and
PRISM's own saves go through the same hook. See
docs/superpowers/specs/2026-10-02-save-gate-design.md.
"""

from __future__ import annotations

from dataclasses import dataclass
import os
import stat
import subprocess
from pathlib import Path

from src.datalad_execution import SAVE_GATE_MARKER
from src.share_publish import (
    HookExistsError,
    NotAGitRepoError,
    _core_validation,
    _dataset_roots,
    _describe,
    _audit,
    _hooks_dir,
    resolve_identity,
    validate_for_publish,
)

__all__ = [
    "SAVE_GATE_MARKER",
    "SAVE_HOOK_MARKER",
    "SaveCheck",
    "audit_save",
    "check_save",
    "has_save_hook",
    "install_save_hook",
    "install_save_hooks",
    "validate_subject_for_save",
]


@dataclass(frozen=True)
class SaveCheck:
    allowed: bool
    errors: list[str]
    reason: str


def _git_ok(root: Path, *args: str) -> tuple[bool, str]:
    """Run git in root; (returncode == 0, stripped stdout or short error detail)."""
    try:
        r = subprocess.run(["git", *args], cwd=root, capture_output=True, text=True)
    except OSError as exc:
        return False, str(exc)
    if r.returncode:
        return False, (r.stderr.strip() or f"git {args[0]} exited {r.returncode}")[:200]
    return True, r.stdout.strip()


def _commit_count(root: Path) -> int | None:
    ok, out = _git_ok(root, "rev-list", "--count", "HEAD")
    return int(out) if ok and out.isdigit() else None


def _is_initial_save(root: Path) -> tuple[bool, str]:
    """(exempt, error). Exempt only when git positively says empty repo or an unshallow 1-commit repo."""
    ok, detail = _git_ok(root, "rev-parse", "--git-dir")
    if not ok:
        return False, detail
    if not _git_ok(root, "rev-parse", "--verify", "-q", "HEAD")[0]:
        return True, ""  # git works but there is no HEAD yet
    count = _commit_count(root)
    if count is None:
        return False, "unreadable commit count"
    if count != 1:
        return False, ""  # history exists: gated
    ok, shallow = _git_ok(root, "rev-parse", "--is-shallow-repository")
    if not ok or shallow != "false":
        return False, "shallow or unknown history" if ok else shallow
    return True, ""


def validate_subject_for_save(super_root, subject_id: str) -> list[str]:
    core = _core_validation()
    issues, _stats = core.validate_subject_only(str(super_root), subject_id)
    return [_describe(i) for i in issues if core.determine_exit_code([i])]


def check_save(project_root) -> SaveCheck:
    root = Path(project_root)
    ok, sup_out = _git_ok(root, "rev-parse", "--show-superproject-working-tree")
    if not ok:
        return SaveCheck(False, [f"Cannot determine repository state: {sup_out}"], "git_error")
    sup = Path(sup_out) if sup_out else None
    nested_subject = sup is not None and root.name.startswith("sub-")
    # Only the first save of a top-level dataset is exempt (an empty scaffold cannot validate);
    # a nested sub-* dataset's first data save is exactly what must be checked.
    if not nested_subject:
        exempt, err = _is_initial_save(root)
        if exempt:
            return SaveCheck(True, [], "exempt_initial")
        if err:
            return SaveCheck(False, [f"Cannot determine repository state: {err}"], "git_error")
    try:
        errors = (
            validate_subject_for_save(sup, root.name) if nested_subject else validate_for_publish(root)
        )
    except (Exception, SystemExit) as exc:  # fail closed
        return SaveCheck(False, [f"Validation could not run: {exc}"], "validator_crash")
    return SaveCheck(not errors, errors, "valid" if not errors else "validation_errors")


SAVE_HOOK_MARKER = "# prism-save-gate-hook"


ANNEX_CHAIN_LINE = "git annex pre-commit ."


def _save_hook_script(chain_annex: bool = False) -> str:
    script = f"""#!/bin/sh
{SAVE_HOOK_MARKER}
# Refuses a commit unless the dataset validates (PRISM save gate).
TOOLS="${{PRISM_TOOLS:-prism_tools}}"
if ! command -v "$TOOLS" >/dev/null 2>&1; then
  echo "{SAVE_GATE_MARKER}: '$TOOLS' not found. Set PRISM_TOOLS to the prism_tools executable. Commit blocked." >&2
  exit 1
fi
ROOT="$(git rev-parse --show-toplevel)" || exit 1
( unset GIT_INDEX_FILE GIT_DIR GIT_WORK_TREE; "$TOOLS" save-gate --check --project "$ROOT" ) >&2 || exit 1
"""
    if chain_annex:
        # git-annex's own hook, run last in the original environment (it needs the commit's index)
        script += ANNEX_CHAIN_LINE + "\n"
    return script


def _read_hook(hook: Path) -> str | None:
    try:
        if hook.is_file() and not hook.is_symlink():
            return hook.read_text(encoding="utf-8", errors="replace")
    except OSError:
        pass
    return None


def _is_standard_annex_hook(text: str | None) -> bool:
    """Exactly git-annex's generated hook (shebang, optional annex comment, the one command)."""
    if text is None:
        return False
    lines = [ln.strip() for ln in text.replace("\r\n", "\n").strip().split("\n")]
    lines = [ln for ln in lines if ln != "# automatically configured by git-annex"]
    return lines == ["#!/bin/sh", ANNEX_CHAIN_LINE]


def _is_own_hook(hook: Path) -> bool:
    """True only for a regular, readable file carrying our marker (anything else is foreign)."""
    try:
        return (
            hook.is_file()
            and not hook.is_symlink()
            and SAVE_HOOK_MARKER in hook.read_text(encoding="utf-8", errors="replace")
        )
    except OSError:
        return False


def has_save_hook(root) -> bool:
    try:
        hook = _hooks_dir(Path(root)) / "pre-commit"
    except NotAGitRepoError:
        return False
    return _is_own_hook(hook)


def install_save_hook(root) -> Path:
    hooks = _hooks_dir(Path(root))  # raises NotAGitRepoError before anything is written
    hooks.mkdir(parents=True, exist_ok=True)
    hook = hooks / "pre-commit"
    existing = _read_hook(hook)
    chain = _is_standard_annex_hook(existing) or (
        _is_own_hook(hook) and ANNEX_CHAIN_LINE[:-2] in (existing or "")
    )
    if os.path.lexists(hook) and not _is_own_hook(hook) and not chain:
        raise HookExistsError(f"{hook} already exists and is not a PRISM hook; not overwriting.")
    hook.write_text(_save_hook_script(chain), encoding="utf-8")
    hook.chmod(hook.stat().st_mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)
    return hook


def install_save_hooks(project_root) -> dict:
    """Install the hook in the project and every nested dataset root (hooks are per repository)."""
    result: dict = {"installed": [], "foreign": [], "errors": []}
    for dataset_root in _dataset_roots(Path(project_root)):
        try:
            install_save_hook(dataset_root)
            result["installed"].append(str(dataset_root))
        except HookExistsError:
            result["foreign"].append(str(dataset_root))
        except NotAGitRepoError as exc:
            result["errors"].append(f"{dataset_root}: {exc}")
    return result


def audit_save(project_root, check: SaveCheck) -> None:
    """One audit line per checked commit (same file as publish). Never raises: an audit problem must not change the decision."""
    try:
        _audit(
            Path(project_root),
            identity=resolve_identity(),
            sibling="",
            result="save_allowed" if check.allowed else "save_refused",
            error_count=len(check.errors),
        )
    except Exception:
        pass


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
