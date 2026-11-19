"""`terms check-links`: a lab checks its own mapping files with the specification's own checker."""

import json
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO / "app"))
sys.path.insert(0, str(REPO))

from src.mappings_check import check_links  # noqa: E402
from src.spec_overlay import add_local_term  # noqa: E402
from src.term_registry import mappings_root  # noqa: E402

SNOMED = "https://snomed.info/id/25217009"


def _put(root: Path, modality: str, family: str, data) -> Path:
    path = root / modality / f"{family}.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data), encoding="utf-8")
    return path


def test_the_shipped_mappings_pass():
    assert check_links(mappings_root()) == []


def test_a_valid_lab_file_passes(tmp_path):
    _put(tmp_path, "biosample", "cortisol", {"prism:cortisol": {"SameAs": {"snomed": SNOMED}}})
    assert check_links(tmp_path) == []


def test_an_unknown_id_an_unknown_vocabulary_and_a_bad_address_are_named(tmp_path):
    _put(tmp_path, "biosample", "cortisol", {"prism:cortisol": {"SameAs": {"nosuch": SNOMED, "loinc": "https://example.org/x"}}})
    _put(tmp_path, "biosample", "nothere", {"prism:nothere": {"SameAs": {"snomed": SNOMED}}})
    problems = " | ".join(check_links(tmp_path))
    assert "nosuch" in problems and "loinc" in problems and "prism:nothere" in problems


def test_the_vocabulary_list_of_the_lab_folder_is_not_needed(tmp_path):
    _put(tmp_path, "biosample", "fsh", {"prism:fsh": {"SameAs": {"snomed": SNOMED}}})
    assert not (tmp_path / "vocabularies.json").exists()
    assert check_links(tmp_path) == []


def test_a_project_checks_its_local_links_against_its_local_terms(tmp_path):
    project = tmp_path / "p"
    sidecar = tmp_path / "s.json"
    sidecar.write_text(json.dumps({"Technical": {"SpecimenType": "saliva"},
                                   "dhea_s": {"Description": "d", "Units": "ug/dL"}}), encoding="utf-8")
    add_local_term(project, column="dhea_s", sidecar_file=str(sidecar), label="DHEA-S", links={"loinc": "https://loinc.org/2191-5"})
    assert check_links(project=project) == []
    _put(project / "code" / "specification" / "mappings", "biosample", "ghost", {"local:ghost": {"SameAs": {"snomed": SNOMED}}})
    assert any("ghost" in p for p in check_links(project=project))


def _run(*args):
    import subprocess

    result = subprocess.run([sys.executable, str(REPO / "prism_tools.py"), *args], capture_output=True, text=True, encoding="utf-8")
    return result.returncode, result.stdout


def test_the_command_exits_0_for_good_files_and_1_with_the_problems(tmp_path):
    _put(tmp_path, "biosample", "fsh", {"prism:fsh": {"SameAs": {"snomed": SNOMED}}})
    code, out = _run("terms", "check-links", "--dir", str(tmp_path))
    assert code == 0 and "no problems" in out.lower()
    _put(tmp_path, "biosample", "nothere", {"prism:nothere": {"SameAs": {"snomed": SNOMED}}})
    code, out = _run("terms", "check-links", "--dir", str(tmp_path), "--json")
    data = json.loads(out)
    assert code == 1 and not data["success"] and any("prism:nothere" in p for p in data["problems"])


def test_the_command_needs_exactly_one_of_dir_and_project(tmp_path):
    assert _run("terms", "check-links")[0] == 2
    assert _run("terms", "check-links", "--dir", str(tmp_path), "--project", str(tmp_path))[0] == 2
    code, out = _run("terms", "check-links", "--dir", str(tmp_path / "nope"), "--json")
    assert code == 1 and not json.loads(out)["success"]
