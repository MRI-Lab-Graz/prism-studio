"""The 1.26.0 claim end to end: a PRISM ID has an address that resolves, and a checked link to an external vocabulary."""

import json
import subprocess
import sys
import urllib.error
import urllib.request
from pathlib import Path

import pytest

from src.mappings_check import check_links
from src.term_registry import mappings_root

REPO = Path(__file__).resolve().parent.parent
BASE = "https://w3id.org/prism-specification"
ITEM = "prism:dass21.dass2101"


def _iri(term_id: str) -> str:
    """survey IDs: terms/survey/<instrument>.<item> (docs/ONTOLOGY_READY.md)."""
    return f"{BASE}/terms/survey/{term_id.removeprefix('prism:')}"


def test_every_shipped_survey_mapping_points_at_a_library_instrument_so_its_address_resolves():
    library = REPO / "official" / "library" / "survey"
    for mapping in (mappings_root() / "survey").glob("*.json"):
        assert (library / f"survey-{mapping.stem}.json").is_file(), mapping.name


def test_the_item_has_a_link_and_the_shipped_mappings_pass_the_check():
    assert check_links(mappings_root()) == []
    mapping = json.loads((mappings_root() / "survey" / "dass21.json").read_text(encoding="utf-8"))
    assert mapping[ITEM]["Measures"][0]["URL"].startswith("https://snomed.info/id/")


def test_terms_show_prints_the_link_of_the_item():
    r = subprocess.run([sys.executable, str(REPO / "prism_tools.py"), "terms", "show", ITEM, "--modality", "survey"],
                       capture_output=True, text=True, encoding="utf-8", errors="replace")
    assert r.returncode == 0 and "Measures" in r.stdout and "snomed.info/id/" in r.stdout


def test_the_address_of_the_item_resolves_live():
    request = urllib.request.Request(_iri(ITEM), method="HEAD")
    try:
        with urllib.request.urlopen(request, timeout=15) as response:
            assert response.status == 200
            assert response.url.endswith("/library/survey/survey-dass21.json")
    except urllib.error.HTTPError as error:
        pytest.fail(f"{_iri(ITEM)} answered {error.code}")
    except (urllib.error.URLError, TimeoutError, OSError) as error:
        pytest.skip(f"offline: {error}")
