"""The links of mappings/ are part of the Specification: official ones, plus a project's own for that run only."""

import json
import os
import sys
from pathlib import Path

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(__file__)), "app", "src"))

from src.specification import load_specification, official_specification  # noqa: E402

FSH_SNOMED = "https://snomed.info/id/25217009"


def _project(root: Path, files: dict[str, object]) -> Path:
    """A project whose code/specification/ holds `files` ({relative path: JSON content})."""
    for rel, content in files.items():
        path = root / "code" / "specification" / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(content), encoding="utf-8")
    return root


def _local_term(stem: str) -> dict:
    return {"TermID": f"local:{stem}", "Label": stem, "Description": "x", "Level": "metric", "Units": "pg/mL",
            "SpecimenType": "saliva"}


def test_the_official_specification_carries_the_official_links_of_every_modality():
    spec = official_specification()
    assert spec.mappings["biosample"]["prism:fsh"]["SameAs"]["snomed"] == FSH_SNOMED
    assert "prism:dass21.dass2101" in spec.mappings["survey"]  # not only the term modalities


def test_mappings_for_finds_an_id_in_any_modality():
    spec = official_specification()
    assert spec.mappings_for("prism:fsh")["SameAs"]["snomed"] == FSH_SNOMED
    assert spec.mappings_for("prism:dass21.dass2101")["Measures"]
    assert spec.mappings_for("prism:no-such-id") == {}


def test_a_project_link_is_part_of_that_runs_specification_only(tmp_path):
    project = _project(tmp_path / "p", {
        "terms/biosample/dhea-s.json": _local_term("dhea-s"),
        "mappings/biosample/dhea-s.json": {"local:dhea-s": {"SameAs": {"loinc": "https://loinc.org/2191-5"}}},
    })
    spec = load_specification(project_root=project)
    assert spec.mappings_for("local:dhea-s")["SameAs"] == {"loinc": "https://loinc.org/2191-5"}
    assert spec.mappings_for("prism:fsh")["SameAs"]["snomed"] == FSH_SNOMED  # the official ones stay
    assert official_specification().mappings_for("local:dhea-s") == {}  # nothing leaked into the official one
    assert load_specification().mappings_for("local:dhea-s") == {}  # nor into the next project's run


def test_the_official_link_wins_over_a_project_link_for_the_same_id(tmp_path):
    project = _project(tmp_path / "p", {
        "mappings/biosample/fsh.json": {"prism:fsh": {"SameAs": {"snomed": "https://snomed.info/id/1"}}},
    })
    assert load_specification(project_root=project).mappings_for("prism:fsh")["SameAs"]["snomed"] == FSH_SNOMED


def test_a_broken_project_mapping_file_is_skipped_not_a_crash(tmp_path):
    project = _project(tmp_path / "p", {"mappings/biosample/bad.json": ["not", "an", "object"]})
    spec = load_specification(project_root=project)
    assert spec.mappings_for("prism:fsh")["SameAs"]["snomed"] == FSH_SNOMED
