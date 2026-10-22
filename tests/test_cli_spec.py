"""prism_tools.py spec local list|add-term|remove and spec propose (phase 1, Task 5): thin adapters over src.spec_overlay."""

import json
import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
FORM = "https://github.com/MRI-Lab-Graz/prism-specification/issues/new"


def _run(*args, script="prism_tools.py"):
    result = subprocess.run(
        [sys.executable, str(REPO / script), *args], capture_output=True, text=True, encoding="utf-8", errors="replace")
    return result.returncode, result.stdout


def _project(root: Path, columns=None) -> Path:
    columns = columns or {"dhea_s": {"Description": "Salivary DHEA-S", "Units": "pg/mL", "MinValue": 0}}
    root.mkdir(parents=True)
    (root / "dataset_description.json").write_text(
        json.dumps({"Name": "T", "BIDSVersion": "1.10.1", "DatasetType": "raw", "Authors": ["A", "B"]}), encoding="utf-8")
    (root / "participants.tsv").write_text("participant_id\nsub-01\n", encoding="utf-8")
    (root / "biosample-saliva_biosample.json").write_text(json.dumps({
        "Technical": {"SpecimenType": "saliva", "CollectionMethod": "passive-drool", "StorageTemperature": -80,
                      "Laboratory": "l", "AssayMethod": "ELISA", "AssayKit": "k", "ProcessingProtocol": "p"},
        "Study": {"BiosampleName": "saliva"},
        "Metadata": {"SchemaVersion": "1.1.0", "CreationDate": "2026-10-23"},
        "sample_id": {"Description": "Tube", "Units": "n/a"}, **columns}), encoding="utf-8")
    folder = root / "sub-01" / "ses-1" / "biosample"
    folder.mkdir(parents=True)
    tsv = folder / "sub-01_ses-1_biosample-saliva_biosample.tsv"
    tsv.write_text("sample_id\t" + "\t".join(columns) + "\nS-1\t" + "\t".join("5" for _ in columns) + "\n", encoding="utf-8")
    return root


def _tsv(project: Path) -> str:
    return str(project / "sub-01" / "ses-1" / "biosample" / "sub-01_ses-1_biosample-saliva_biosample.tsv")


def test_list_on_a_project_without_an_overlay(tmp_path):
    code, out = _run("spec", "local", "list", "--project", str(_project(tmp_path / "p")), "--json")
    assert code == 0 and json.loads(out) == {"success": True, "items": []}


def test_add_term_then_list_then_the_validator_uses_it(tmp_path):
    project = _project(tmp_path / "p")
    code, out = _run("spec", "local", "add-term", "--project", str(project), "--data", _tsv(project),
                     "--column", "dhea_s", "--label", "DHEA-S", "--json")
    data = json.loads(out)
    assert code == 0 and data["success"] and len(data["written"]) == 2
    code, out = _run("spec", "local", "list", "--project", str(project), "--json")
    assert [(i["id"], i["status"]) for i in json.loads(out)["items"]] == [("prism:dhea-s", "local"), ("prism:dhea-s.saliva", "local")]
    _code, report = _run(str(project), script="prism.py")
    assert "dhea_s" in report and "is not an official metric" not in report  # the column is known now
    assert "uses the local term" not in report  # the column itself still has no Term: only a suggestion


def test_a_column_that_names_the_local_term_is_validated_with_it(tmp_path):
    project = _project(tmp_path / "p", {"dhea_s": {"Term": "prism:dhea-s"}})
    sidecar = project / "biosample-saliva_biosample.json"
    # the metric is unknown until the term is added; give the column a definition just for the add step
    donor = _project(tmp_path / "donor")
    _run("spec", "local", "add-term", "--project", str(project), "--data", _tsv(donor), "--column", "dhea_s", "--label", "DHEA-S")
    _code, report = _run(str(project), script="prism.py")
    assert "uses the local term prism:dhea-s.saliva" in report, report
    assert sidecar.exists()


def test_add_term_for_an_official_metric_exits_1_naming_the_term(tmp_path):
    project = _project(tmp_path / "p", {"cort": {"Description": "d", "Units": "nmol/L"}})
    code, out = _run("spec", "local", "add-term", "--project", str(project), "--data", _tsv(project), "--column", "cort", "--json")
    assert code == 1 and not json.loads(out)["success"] and "prism:cortisol" in json.loads(out)["error"]


def test_add_term_needs_exactly_one_of_data_and_sidecar(tmp_path):
    project = _project(tmp_path / "p")
    assert _run("spec", "local", "add-term", "--project", str(project), "--column", "dhea_s")[0] == 2
    assert _run("spec", "local", "add-term", "--project", str(project), "--column", "dhea_s",
                "--data", _tsv(project), "--sidecar", str(project / "biosample-saliva_biosample.json"))[0] == 2


def test_remove_then_list_is_empty_and_unknown_ids_fail(tmp_path):
    project = _project(tmp_path / "p")
    _run("spec", "local", "add-term", "--project", str(project), "--data", _tsv(project), "--column", "dhea_s", "--label", "DHEA-S")
    code, out = _run("spec", "local", "remove", "--project", str(project), "prism:dhea-s", "--json")
    assert code == 0 and len(json.loads(out)["removed"]) == 2
    assert json.loads(_run("spec", "local", "list", "--project", str(project), "--json")[1])["items"] == []
    assert _run("spec", "local", "remove", "--project", str(project), "prism:dhea-s", "--json")[0] == 1


def test_propose_describes_and_saves_but_sends_nothing(tmp_path):
    project = _project(tmp_path / "p")
    _run("spec", "local", "add-term", "--project", str(project), "--data", _tsv(project), "--column", "dhea_s", "--label", "DHEA-S")
    out_file = tmp_path / "proposal.json"
    code, out = _run("spec", "propose", "--project", str(project), "--term", "prism:dhea-s", "--out", str(out_file), "--json")
    data = json.loads(out)
    assert code == 0 and data["success"] and data["opened"] is False and data["problems"] == []
    assert data["issue_url"].startswith(FORM) and out_file.is_file()
    check = subprocess.run(
        [sys.executable, str(REPO / "scripts" / "specification" / "term_proposal.py"), "check",
         "--terms", str(REPO / "official" / "library" / "terms" / "biosample"),
         "--schema", str(REPO / "app" / "schemas" / "stable" / "biosample.schema.json"),
         "--out", str(tmp_path / "bundle"), "--file", str(out_file)], capture_output=True, text=True)
    assert check.returncode == 0 and (tmp_path / "bundle" / "status").read_text(encoding="utf-8").strip() == "ok"


def test_propose_an_unknown_term_exits_1(tmp_path):
    code, out = _run("spec", "propose", "--project", str(_project(tmp_path / "p")), "--term", "prism:nope", "--json")
    assert code == 1 and not json.loads(out)["success"]
