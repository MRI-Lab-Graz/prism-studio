"""Keep machine-local files out of git/DataLad without a tracked .gitignore.

`.git/info/exclude` is read by git (and so by `datalad save`/push) but is never
committed, annexed or shared -- right for files that must stay on this machine
(the pseudonym map and its key, session logs with absolute paths).
"""

from __future__ import annotations

from pathlib import Path
import subprocess


def _exclude_file(root: Path) -> tuple[Path, str] | None:
    """``(info/exclude, prefix of root inside its repository)``; None outside git. No git process is started:
    this runs inside save and export, and a project may sit inside a larger repository or a linked worktree."""
    for repo in (root, *root.parents):
        git = repo / ".git"
        if not git.exists():
            continue
        if git.is_file():  # "gitdir: <path>" (worktree, submodule)
            git = repo / git.read_text(encoding="utf-8").partition("gitdir:")[2].strip()
            if (git / "commondir").is_file():
                git = git / (git / "commondir").read_text(encoding="utf-8").strip()
        prefix = "" if repo == root else root.relative_to(repo).as_posix() + "/"
        return git / "info" / "exclude", prefix
    return None


def ensure_git_excluded(project_root: str | Path, *patterns: str) -> None:
    """Idempotently add `patterns` to the repository's info/exclude (no-op if not a git repo)."""
    try:
        found = _exclude_file(Path(project_root).resolve())
        if found is None:
            return
        exclude, prefix = found
        patterns = tuple(prefix + p for p in patterns)
        existing = exclude.read_text(encoding="utf-8").splitlines() if exclude.exists() else []
        missing = [p for p in patterns if p not in existing]
        if missing:
            exclude.parent.mkdir(parents=True, exist_ok=True)
            with exclude.open("a", encoding="utf-8") as f:
                if existing and existing[-1] != "":
                    f.write("\n")
                f.write("\n".join(missing) + "\n")
    except OSError:
        pass  # best effort: never block an export/log on a read-only .git


SENSITIVE_PATHS = ("code/anonymization_map.json", "code/logs", "code/**/*[Cc][Oo][Dd][Ee]_[Mm][Aa][Pp]*")


def tracked_sensitive_files(project_root: str | Path) -> list[str]:
    """Files from SENSITIVE_PATHS that git already tracks (empty if not a repo)."""
    out = subprocess.run(
        ["git", "-C", str(project_root), "ls-files", "--",
         *(f":(glob){p}" if "*" in p else p for p in SENSITIVE_PATHS)],
        capture_output=True, text=True, check=False,
    )
    return out.stdout.split("\n")[:-1] if out.returncode == 0 and out.stdout else []


def sensitive_files_warning(tracked: list[str]) -> str:
    if not tracked:
        return ""
    return (
        f" WARNING: git already tracks {', '.join(tracked)} (pseudonym key/reverse map or session "
        "logs with local paths). Do not share this copy of the project. Stop tracking with "
        "`git rm --cached <file>`; they stay in older history, so start a fresh dataset to share."
    )
