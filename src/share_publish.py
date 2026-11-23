"""Who commits (the git identity), the audit trail and the validation behind the save gate.

Pushing and publishing live in Worldline Desktop; this module has no push path (see docs/DATALAD.md).
"""

from __future__ import annotations

import json
import os
import re
import subprocess
import sys
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path


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


def has_sibling(project_root, sibling_name: str) -> bool:
    return sibling_name in _git(Path(project_root), "remote").split()


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

    ponytail: PRISM checks only (run_bids=False stays explicit; the share check does not run the BIDS engine).
    """
    core = _core_validation()
    issues, _stats = core.validate_dataset(str(project_root), run_bids=False, run_prism=True)
    return [_describe(i) for i in issues if core.determine_exit_code([i])]


def _dataset_roots(root: Path) -> list[Path]:
    from src.project_manager import ProjectManager

    return ProjectManager()._iter_datalad_dataset_roots(root)


class HookExistsError(Exception):
    pass


class NotAGitRepoError(Exception):
    pass


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


