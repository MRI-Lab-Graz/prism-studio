"""The absolute links in the vendored spec pages must still point at things that exist in this repository.

The specification repository cannot link relatively into Studio's docs, so its pages carry URLs of the
Read the Docs site and of GitHub raw files; renaming a doc or an example here would break them silently.
"""

import re
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
RTD = "https://prism-studio.readthedocs.io/en/latest/"
RAW = "https://github.com/MRI-Lab-Graz/prism-studio/raw/main/"
URL = re.compile(r"\]\((https://[^)\s]+)\)")


def _links():
    for md in sorted((REPO / "docs" / "specs").glob("*.md")):
        for url in URL.findall(md.read_text(encoding="utf-8")):
            yield md.name, url


def test_links_into_the_docs_site_resolve_to_docs_pages():
    checked = 0
    for name, url in _links():
        if url.startswith(RTD):
            page = re.sub(r"\.html(#.*)?$", "", url[len(RTD):])
            assert (REPO / "docs" / f"{page}.md").is_file(), f"{name}: {url} -> docs/{page}.md does not exist"
            checked += 1
    assert checked >= 5  # the vendored pages do carry such links; the test must not pass by finding none


def test_links_to_repository_files_resolve():
    checked = 0
    for name, url in _links():
        if url.startswith(RAW):
            assert (REPO / url[len(RAW):]).is_file(), f"{name}: {url} does not exist in this repository"
            checked += 1
    assert checked >= 2
