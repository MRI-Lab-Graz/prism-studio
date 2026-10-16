"""The modality proposal workflow must be findable: landing page, sidebar, README."""

import re
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
INDEX = (REPO / "docs" / "index.rst").read_text(encoding="utf-8")
README = (REPO / "README.md").read_text(encoding="utf-8")


def test_landing_page_has_a_propose_a_modality_section_with_a_link():
    assert "Propose it" in INDEX
    assert 'href="MODALITY_WORKFLOW.html"' in INDEX


def test_hero_has_a_propose_button():
    hero = INDEX.split("A concrete before and after")[0]
    assert 'href="MODALITY_WORKFLOW.html"' in hero


def test_the_landing_page_states_nothing_about_bids_process():
    section = INDEX.split("Propose it")[1].split("Citing PRISM")[0]
    assert not re.search(r"BIDS (is|are|take|has|extension)", section)


def test_sidebar_lists_the_proposal_pages_right_after_the_studio_guide():
    captions = re.findall(r":caption: (.+)", INDEX)
    assert captions[captions.index("Studio Guide") + 1] == "Propose a Modality"


def test_readme_points_to_the_proposal_docs():
    assert "MODALITY_WORKFLOW" in README
