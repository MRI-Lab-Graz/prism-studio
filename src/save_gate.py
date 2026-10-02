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
