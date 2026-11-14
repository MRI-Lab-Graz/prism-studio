"""Every vendored spec page is in the docs table of contents (the docs build treats an orphan page as an error)."""

from pathlib import Path

DOCS = Path(__file__).resolve().parents[1] / "docs"


def test_every_spec_page_is_in_the_docs_toctree():
    index = (DOCS / "index.rst").read_text(encoding="utf-8")
    listed = {line.strip() for line in index.splitlines() if line.strip().startswith("specs/")}
    pages = {f"specs/{p.stem}" for p in (DOCS / "specs").glob("*.md")}
    assert pages - listed == set(), f"add these to a toctree in docs/index.rst: {sorted(pages - listed)}"
