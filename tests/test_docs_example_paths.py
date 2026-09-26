"""Every `examples/...` path the docs mention must actually exist.

The docs and the example folders drifted apart repeatedly: chapter folders got
renamed, `assets/hero-*.svg` was referenced after deletion, and a mystery-file
README pointed at a `demo/templates/survey/` directory that never existed.
"""

import re
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent

# Paths under examples/, repo-relative or written relative to the doc
# (`../examples/...`), stopping before trailing sentence punctuation.
PATH_RE = re.compile(r"((?:\.\./)*examples/[A-Za-z0-9_./-]*[A-Za-z0-9_/-])")


def _docs():
    for md in sorted(REPO.glob("docs/**/*.md")) + sorted(
        REPO.glob("examples/**/*.md")
    ):
        if "_archive" in md.parts:
            continue
        yield md


def test_example_paths_in_docs_exist():
    missing = []
    for md in _docs():
        for lineno, line in enumerate(
            md.read_text(encoding="utf-8").splitlines(), 1
        ):
            for hit in PATH_RE.findall(line):
                if not ((REPO / hit).exists() or (md.parent / hit).exists()):
                    rel = md.relative_to(REPO)
                    missing.append(f"{rel}:{lineno} -> {hit}")
    assert not missing, "docs reference nonexistent example paths:\n" + "\n".join(
        missing
    )


def test_workshop_source_spreadsheet_exists_once():
    """The wellbeing spreadsheet is shared by chapters 2 and 3.

    Two copies is how it drifted before: 21 rows with a `sleep` column on one
    side, a stale 10-row subset on the other, both named `wellbeing.tsv`.
    """
    copies = sorted(
        p.relative_to(REPO).as_posix()
        for p in REPO.glob("examples/**/wellbeing.*")
        if p.suffix in {".tsv", ".xlsx"}
    )
    assert copies == [
        "examples/workshop/raw_data/wellbeing.tsv",
        "examples/workshop/raw_data/wellbeing.xlsx",
    ], f"wellbeing spreadsheet must exist exactly once, found: {copies}"
