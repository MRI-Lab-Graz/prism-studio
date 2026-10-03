"""Third-party actions run with our tokens (release write, SignPath, PyPI OIDC,
GHCR). A tag or branch can be moved by whoever controls that repo; a commit SHA
cannot. Dependabot's github-actions ecosystem keeps SHA pins current."""

import re
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
FILES = [*sorted((ROOT / ".github" / "workflows").glob("*.yml")), ROOT / "action.yml"]
USES = re.compile(r"uses:\s+([\w.-]+/[\w./-]+)@(\S+)")


@pytest.mark.parametrize("path", FILES, ids=lambda p: p.name)
def test_every_action_is_pinned_to_a_full_commit_sha(path):
    unpinned = [
        f"{repo}@{ref}"
        for repo, ref in USES.findall(path.read_text(encoding="utf-8"))
        if not re.fullmatch(r"[0-9a-f]{40}", ref)
    ]
    assert unpinned == []
