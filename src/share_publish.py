"""Validity-gated push from a department share to the DataLad server sibling.

One implementation: the CLI (`prism_tools publish`) and the Studio routes call
these functions. See docs/superpowers/specs/2026-10-02-share-publish-design.md.
"""

from __future__ import annotations

import json
import os
import re
import subprocess
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

from src.datalad_execution import (
    is_datalad_dataset,
    run_datalad_push,
    run_datalad_push_verify,
)


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


def audit_path(project_root) -> Path | None:
    """Audit log under the git dir (never dirties the tree); None if not a git repo."""
    git_dir = _git(Path(project_root), "rev-parse", "--absolute-git-dir")
    return Path(git_dir) / "prism" / "publish.jsonl" if git_dir else None


def _audit(root: Path, *, identity: Identity | None, sibling: str, result: str, error_count: int) -> None:
    path = audit_path(root)
    if path is None:
        return
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
