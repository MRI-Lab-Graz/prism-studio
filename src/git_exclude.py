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
