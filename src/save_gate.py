"""Save gate: a commit in a PRISM dataset is allowed only if the dataset validates.

Enforced by a git pre-commit hook in every dataset root (see install_save_hooks);
the hook calls `prism_tools save-gate --check`. One implementation: the CLI and
PRISM's own saves go through the same hook. See
docs/superpowers/specs/2026-10-02-save-gate-design.md.
"""

from __future__ import annotations

from dataclasses import dataclass
import subprocess
from pathlib import Path

from src.datalad_execution import SAVE_GATE_MARKER
from src.share_publish import _core_validation, _describe, validate_for_publish

__all__ = ["SAVE_GATE_MARKER", "SaveCheck", "check_save", "validate_subject_for_save"]


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
