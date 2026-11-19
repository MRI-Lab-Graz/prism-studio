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


def test_a_project_without_local_links_has_no_problems(tmp_path):
    assert check_links(project=tmp_path) == []


def test_a_folder_that_is_no_modality_is_reported_not_a_crash(tmp_path):
    project = tmp_path / "p"
    _put(project / "code" / "specification" / "mappings", "nosuchkind", "x", {"prism:x": {"SameAs": {"snomed": SNOMED}}})
    assert any("nosuchkind" in p for p in check_links(project=project))


def test_a_symlinked_mapping_file_is_never_read(tmp_path):
    secret = tmp_path / "secret.txt"
    secret.write_text("TOP-SECRET-CONTENT", encoding="utf-8")
    folder = tmp_path / "m" / "biosample"
    folder.mkdir(parents=True)
    (folder / "fsh.json").symlink_to(secret)
    problems = " | ".join(check_links(tmp_path / "m"))
    assert "symbolic link" in problems and "TOP-SECRET" not in problems


def test_problems_name_the_ids_as_the_user_wrote_them(tmp_path):
    project = tmp_path / "p"
    _put(project / "code" / "specification" / "mappings", "biosample", "ghost", {"local:ghost": {"SameAs": {"snomed": SNOMED}}})
    problems = " | ".join(check_links(project=project))
    assert "local:ghost" in problems and "prism:ghost" not in problems


def test_a_broken_file_in_the_folder_is_a_failure_message_not_a_traceback(tmp_path):
    _put(tmp_path, "biosample", "fsh", {"prism:fsh": {"SameAs": {"snomed": SNOMED}}})
    (tmp_path / "biosample" / "bad.json").write_bytes(b"\xff\xfe not json")
    code, out = _run("terms", "check-links", "--dir", str(tmp_path), "--json")
    assert code == 1 and "bad.json" in out and not json.loads(out)["success"]
