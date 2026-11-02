"""Init on an existing BIDS dataset reads what the dataset already says about itself.

CITATION.cff and README.md are generated from project.json; when a dataset arrives with its own, init must
take them over, or the next "Regenerate citation" / "Generate README" replaces them with placeholders.
"""

import json
import os
import sys
from pathlib import Path

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "app"))

from src.project_documents import generate_readme  # noqa: E402
from src.project_manager import ProjectManager  # noqa: E402

CITATION = """cff-version: 1.2.0
title: Colleague DS
message: Please cite
authors:
  - family-names: Doe
    given-names: Jane
    orcid: https://orcid.org/0000-0002-1825-0097
    affiliation: Uni Graz
  - family-names: Roe
    given-names: Rick
keywords: [mri, memory]
license: CC0-1.0
doi: 10.1234/abcd
abstract: Abstract from cff
"""


def _bids(tmp_path: Path) -> Path:
    (tmp_path / "dataset_description.json").write_text(
        json.dumps({"Name": "Colleague DS", "BIDSVersion": "1.10.0"}), encoding="utf-8"
    )
    return tmp_path


def test_init_takes_authors_and_metadata_from_existing_citation_cff(tmp_path):
    root = _bids(tmp_path)
    (root / "CITATION.cff").write_text(CITATION, encoding="utf-8")

    assert ProjectManager().init_on_existing_bids(str(root))["success"]

    project = json.loads((root / "project.json").read_text(encoding="utf-8"))
    basics = project["Basics"]
    contacts = project["governance"]["contacts"]
    assert [(c["given-names"], c["family-names"]) for c in contacts] == [("Jane", "Doe"), ("Rick", "Roe")]
    assert contacts[0]["orcid"] == "https://orcid.org/0000-0002-1825-0097"
    assert contacts[0]["affiliation"] == "Uni Graz"
    assert basics["Authors"] == ["Jane Doe", "Rick Roe"]
    assert basics["Keywords"] == ["mri", "memory"]
    assert basics["DatasetDOI"] == "10.1234/abcd"
    assert basics["Description"] == "Abstract from cff"
    assert basics["License"] == "CC0-1.0"


def test_regenerating_citation_after_init_keeps_the_original_authors(tmp_path):
    root = _bids(tmp_path)
    (root / "CITATION.cff").write_text(CITATION, encoding="utf-8")
    pm = ProjectManager()
    pm.init_on_existing_bids(str(root))

    pm.regenerate_citation_cff(root)

    citation = (root / "CITATION.cff").read_text(encoding="utf-8")
    assert "Doe" in citation and "0000-0002-1825-0097" in citation and "Roe" in citation
    assert "prism-studio" not in citation
    assert "10.1234/abcd" in citation


def test_dataset_description_wins_over_citation_cff(tmp_path):
    root = _bids(tmp_path)
    desc = {"Name": "Colleague DS", "BIDSVersion": "1.10.0", "Description": "From dd", "Authors": ["Ann Lee"]}
    (root / "dataset_description.json").write_text(json.dumps(desc), encoding="utf-8")
    (root / "CITATION.cff").write_text(CITATION, encoding="utf-8")

    ProjectManager().init_on_existing_bids(str(root))

    basics = json.loads((root / "project.json").read_text(encoding="utf-8"))["Basics"]
    assert basics["Description"] == "From dd"
    assert basics["Authors"] == ["Ann Lee"]


def test_unreadable_citation_cff_does_not_fail_init(tmp_path):
    root = _bids(tmp_path)
    (root / "CITATION.cff").write_text("not: [valid", encoding="utf-8")

    assert ProjectManager().init_on_existing_bids(str(root))["success"]
    assert (root / "CITATION.cff").read_text(encoding="utf-8") == "not: [valid"


def test_generate_readme_keeps_an_existing_readme_md(tmp_path):
    root = _bids(tmp_path)
    (root / "README.md").write_text("# Colleague DS\n\nOverview written by the lab.\n", encoding="utf-8")
    ProjectManager().init_on_existing_bids(str(root))

    generate_readme(root)
    generate_readme(root)  # a second run must neither lose nor duplicate it

    readme = (root / "README.md").read_text(encoding="utf-8")
    assert readme.count("Overview written by the lab.") == 1
    assert "Generated with" in readme


def test_merged_bare_readme_survives_a_second_generate(tmp_path):
    root = _bids(tmp_path)
    (root / "README").write_text("Plain BIDS readme text.", encoding="utf-8")
    ProjectManager().init_on_existing_bids(str(root))

    generate_readme(root)
    generate_readme(root)

    readme = (root / "README.md").read_text(encoding="utf-8")
    assert readme.count("Plain BIDS readme text.") == 1
    assert not (root / "README").exists()
