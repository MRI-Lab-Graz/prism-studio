"""Studio no longer takes new kinds of data itself: prism-specification does."""

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OLD_LINK = "prism-studio/issues/new?template=propose-modality.yml"


def test_studio_issue_form_bot_and_script_are_gone():
    for rel in (
        ".github/ISSUE_TEMPLATE/propose-modality.yml",
        ".github/workflows/propose-modality.yml",
        "scripts/ci/modality_issue_to_files.py",
    ):
        assert not (ROOT / rel).exists(), rel


def test_nothing_links_the_old_studio_form():
    superpowers = ROOT / "docs" / "superpowers"
    hits = [
        str(p.relative_to(ROOT))
        for base in (ROOT / ".github", ROOT / "docs")
        for p in base.rglob("*")
        if p.is_file() and superpowers not in p.parents and OLD_LINK in p.read_text(errors="ignore")
    ]
    assert not hits, hits
