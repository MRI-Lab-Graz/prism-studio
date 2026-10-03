"""Keep machine-local files out of git/DataLad without a tracked .gitignore.

`.git/info/exclude` is read by git (and so by `datalad save`/push) but is never
committed, annexed or shared -- right for files that must stay on this machine
(the pseudonym map and its key, session logs with absolute paths).
"""

from __future__ import annotations

from pathlib import Path


def ensure_git_excluded(project_root: str | Path, *patterns: str) -> None:
    """Idempotently add `patterns` to the project's .git/info/exclude (no-op if not a git repo)."""
    git_dir = Path(project_root) / ".git"
    if not git_dir.is_dir():
        return
    exclude = git_dir / "info" / "exclude"
    try:
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


SENSITIVE_PATHS = ("code/anonymization_map.json", "code/logs")


def tracked_sensitive_files(project_root: str | Path) -> list[str]:
    """Files from SENSITIVE_PATHS that git already tracks (empty if not a repo)."""
    import subprocess

    out = subprocess.run(
        ["git", "-C", str(project_root), "ls-files", "--", *SENSITIVE_PATHS],
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
