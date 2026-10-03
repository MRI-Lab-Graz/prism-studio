"""Validity-gated push from a department share to the DataLad server sibling.

One implementation: the CLI (`prism_tools publish`) and the Studio routes call
these functions. See docs/superpowers/specs/2026-10-02-share-publish-design.md.
"""

from __future__ import annotations

import json
import os
import re
import shlex
import stat
import subprocess
import sys
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


def _git_identity_env_keys() -> tuple[str, ...]:
    return tuple(identity_env(Identity("", "")))


def apply_env_identity() -> Identity | None:
    """Apply PRISM_USER_NAME/PRISM_USER_EMAIL if both are set (git's own config is untouched)."""
    name = os.environ.get("PRISM_USER_NAME", "").strip()
    email = os.environ.get("PRISM_USER_EMAIL", "").strip()
    if not (name and email):
        return None
    identity = Identity(name, email)
    apply_identity(identity)
    return identity


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


_PUBLIC_HOSTS = ("github.com", "gitlab.com", "gin.g-node.org", "bitbucket.org", "codeberg.org", "openneuro.org")


def _is_public_target(url: str) -> bool:
    """True for web URLs and well-known public code hosts (the lab server is neither)."""
    from src.datalad_doctor import parse_ssh_target

    url = str(url or "").strip()
    url = url[4:] if url.startswith("ria+") else url
    if url.lower().startswith(("http://", "https://", "git://")):
        return True
    target = parse_ssh_target(url)
    return bool(target) and target[1].lower().endswith(_PUBLIC_HOSTS)


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
    entry = {
        "timestamp": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "identity": f"{identity.name} <{identity.email}>" if identity else None,
        "sibling": sibling,
        "result": result,
        "error_count": error_count,
    }
    try:
        _write_audit(path, entry)
    except OSError as exc:  # never turn a finished push (or a hook check) into a crash
        print(f"PRISM: could not write audit log: {exc}", file=sys.stderr)


def _share_mode(path: Path, extra: int) -> None:
    """Give the audit dir/file the git dir's group/other access (shared share); best effort."""
    try:
        mode = path.parent.parent.stat().st_mode if path.name == "prism" else path.parent.stat().st_mode
        os.chmod(path, ((mode & 0o7777) | extra) & ~(0o111 if path.is_file() else 0))
    except OSError:
        pass


def _write_audit(path: Path, entry: dict) -> None:
    new_dir = not path.parent.exists()
    path.parent.mkdir(parents=True, exist_ok=True)
    if new_dir:
        _share_mode(path.parent, 0o070)
    new_file = not path.exists()
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(entry, ensure_ascii=False) + "\n")
    if new_file:
        _share_mode(path, 0o060)


def _describe(issue) -> str:
    if isinstance(issue, tuple):
        return " ".join(str(part) for part in issue[1:2]) or str(issue)
    code = getattr(issue, "code", "")
    return f"{code} {getattr(issue, 'message', issue)}".strip()


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


def uncommitted_changes(root: Path) -> list[str]:
    """Paths git sees as modified/untracked (incl. inside submodules); the push only sends commits."""
    out = subprocess.run(
        ["git", "-C", str(root), "status", "--porcelain", "--ignore-submodules=none"],
        capture_output=True, text=True, check=False,
    ).stdout
    return [line for line in out.splitlines() if line.strip()]


def _uncommitted_message(paths: list[str]) -> str:
    return (
        f"{len(paths)} uncommitted change(s). Save the dataset first (`datalad save`), then publish."
    )


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
    # sourcedata/ (raw, identifiable data) is tracked in plain git by design and is for
    # the internal lab server only: never send it to a public host.
    if _git(root, "ls-files", "--", "sourcedata") and _is_public_target(
        _git(root, "remote", "get-url", sibling)
    ):
        return finish(
            "public_target_with_sourcedata",
            f'"{sibling}" is a public host and this project tracks sourcedata/ (raw data). '
            "Publish only to the internal lab server.",
            audit_result="refused",
        )
    dirty = uncommitted_changes(root)
    if dirty:
        return finish(
            "uncommitted_changes", _uncommitted_message(dirty), audit_result="refused", errors=dirty[:20]
        )
    try:
        errors = validate_for_publish(root)
    except Exception as exc:  # a crashed validator must refuse, not escape unaudited
        errors = [f"Validation could not run: {exc}"]
    if errors:
        return finish(
            "validation_errors",
            f"{len(errors)} validation error(s). Fix them before publishing.",
            audit_result="refused",
            errors=errors,
        )

    # identity applies for this call only (spec section 4): restore whatever was there before
    saved = {k: os.environ.get(k) for k in _git_identity_env_keys()}
    apply_identity(identity)
    try:
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
    finally:
        for key, value in saved.items():
            if value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = value


HOOK_MARKER = "# prism-publish-hook"


class HookExistsError(Exception):
    pass


class NotAGitRepoError(Exception):
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
ROOT="$(git rev-parse --show-toplevel)" || exit 1
exec "$TOOLS" publish --check --project "$ROOT"
"""


def _hooks_dir(root: Path) -> Path:
    # A folder inside some other repo must not borrow that repo's hooks dir.
    top = _git(root, "rev-parse", "--show-toplevel")
    if not top or Path(top).resolve() != root.resolve():
        raise NotAGitRepoError(f"{root} is not a git repository; nothing installed.")
    out = _git(root, "rev-parse", "--path-format=absolute", "--git-path", "hooks")
    if out:
        return Path(out)
    # git < 2.31 does not know --path-format
    rel = _git(root, "rev-parse", "--git-path", "hooks")
    if not rel:
        raise NotAGitRepoError(f"{root} is not a git repository; nothing installed.")
    path = Path(rel)
    return path if path.is_absolute() else root / path


def install_hook(project_root, sibling_name: str | None = None) -> Path:
    root = Path(project_root)
    sibling = _sibling_for(root, sibling_name)
    hooks = _hooks_dir(root)
    hooks.mkdir(parents=True, exist_ok=True)
    hook = hooks / "pre-push"
    if os.path.lexists(hook) and (
        hook.is_symlink() or HOOK_MARKER not in hook.read_text(encoding="utf-8", errors="replace")
    ):
        raise HookExistsError(f"{hook} already exists and is not a PRISM hook; not overwriting.")
    hook.write_text(_hook_script(sibling), encoding="utf-8")
    hook.chmod(hook.stat().st_mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)
    return hook


def check_for_hook(project_root, sibling_name: str | None = None) -> list[str]:
    """Validate only (no identity needed); used by the pre-push hook."""
    root = Path(project_root)
    errors = uncommitted_changes(root)
    errors = [_uncommitted_message(errors), *errors[:20]] if errors else []
    if not errors:
        try:
            errors = validate_for_publish(root)
        except Exception as exc:  # fail closed, no traceback
            errors = [f"Validation could not run: {exc}"]
    _audit(
        root,
        identity=resolve_identity(),
        sibling=_sibling_for(root, sibling_name),
        result="hook_refused" if errors else "hook_allowed",
        error_count=len(errors),
    )
    return errors
