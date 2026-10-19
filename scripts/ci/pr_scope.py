"""Tell CI whether a pull request is a bare modality proposal from the bot.

Such a PR only adds content under proposals/ (schema, sidecar, fixture); the
heavy code-oriented jobs have nothing to check there. Prints content_only=true|false.
Usage: pr_scope.py <head_branch> <base_ref> <head_ref>
"""

from __future__ import annotations

import subprocess
import sys

BOT_BRANCH_PREFIX = "modality/issue-"  # written by .github/workflows/propose-modality.yml


def content_only(branch: str, changed_files: list[str]) -> bool:
    return (
        branch.startswith(BOT_BRANCH_PREFIX)
        and bool(changed_files)
        and all(f.startswith("proposals/") for f in changed_files)
    )


def main() -> int:
    branch, base, head = sys.argv[1:4]
    # fail closed: a git error means "run everything"
    try:
        out = subprocess.run(
            ["git", "diff", "--name-only", f"{base}...{head}"],
            capture_output=True, text=True, check=True,
        ).stdout
        files = [line for line in out.splitlines() if line]
    except subprocess.CalledProcessError:
        files = []
    print(f"content_only={str(content_only(branch, files)).lower()}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
