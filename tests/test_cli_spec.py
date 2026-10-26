"""prism_tools.py spec local list|add-term|remove and spec propose (phase 1, Task 5): thin adapters over src.spec_overlay."""

import argparse
import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

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


# --- proposal format v2: several terms in one proposal --------------------------------------------

TWO = {
    "dhea_s": {"Description": "Salivary DHEA-S", "Units": "pg/mL", "MinValue": 0},
    "ferr_ugl": {"Description": "Ferritin", "Units": "ug/L", "MinValue": 0},
}


def _two_local(tmp_path: Path) -> Path:
    project = _project(tmp_path / "p", TWO)
    for column, label in (("dhea_s", "DHEA-S"), ("ferr_ugl", "Ferritin")):
        assert _run("spec", "local", "add-term", "--project", str(project), "--data", _tsv(project), "--column", column, "--label", label)[0] == 0
    return project


def _vendored_check(proposal_file: Path, out: Path) -> str:
    subprocess.run(
        [sys.executable, str(REPO / "scripts" / "specification" / "term_proposal.py"), "check",
         "--terms", str(REPO / "official" / "library" / "terms" / "biosample"),
         "--schema", str(REPO / "app" / "schemas" / "stable" / "biosample.schema.json"),
         "--out", str(out), "--file", str(proposal_file)], capture_output=True, text=True)
    return (out / "status").read_text(encoding="utf-8").strip()


def test_propose_all_shares_every_local_term_as_one_v2_document(tmp_path):
    project = _two_local(tmp_path)
    out_file = tmp_path / "all.json"
    code, out = _run("spec", "propose", "--project", str(project), "--all", "--out", str(out_file), "--json")
    data = json.loads(out)
    assert code == 0 and data["success"] and data["skipped"] == [] and data["opened"] is False
    assert sorted(data["document"]["files"]) == [
        "terms/biosample/dhea-s.json", "terms/biosample/dhea-s.saliva.json",
        "terms/biosample/ferritin.json", "terms/biosample/ferritin.saliva.json",
    ]
    assert json.loads(out_file.read_text(encoding="utf-8")) == data["document"] and data["document"]["format"] == "prism-proposal/2"
    assert _vendored_check(out_file, tmp_path / "bundle") == "ok"


def test_propose_term_can_be_repeated(tmp_path):
    project = _two_local(tmp_path)
    code, out = _run("spec", "propose", "--project", str(project), "--term", "prism:dhea-s", "--term", "prism:ferritin", "--json")
    data = json.loads(out)
    assert code == 0 and len(data["document"]["files"]) == 4


def test_propose_needs_term_all_or_patch_but_not_term_with_all(tmp_path):
    project = _two_local(tmp_path)
    assert _run("spec", "propose", "--project", str(project))[0] == 1
    assert _run("spec", "propose", "--project", str(project), "--all", "--term", "prism:dhea-s")[0] == 2


def test_propose_all_reports_what_the_official_registry_adopted(tmp_path):
    project = _two_local(tmp_path)
    adopted = project / "code" / "specification" / "terms" / "biosample" / "cortisol.json"  # the official registry has prism:cortisol
    adopted.write_text(json.dumps({"TermID": "prism:cortisol", "Level": "analyte", "Label": "mine", "Aliases": [], "Description": "d"}), encoding="utf-8")
    code, out = _run("spec", "propose", "--project", str(project), "--all", "--json")
    data = json.loads(out)
    assert code == 0 and data["skipped"] == ["prism:cortisol"] and len(data["document"]["files"]) == 4


def test_propose_with_nothing_local_exits_1(tmp_path):
    code, out = _run("spec", "propose", "--project", str(_project(tmp_path / "p")), "--all", "--json")
    assert code == 1 and "nothing to share" in json.loads(out)["error"]

def test_spec_catalog_json_runs_without_a_project():
    code, out = _run("spec", "catalog", "--json")
    data = json.loads(out)
    assert code == 0 and data["success"] and "biosample" in [m["name"] for m in data["modalities"]]


def test_spec_propose_values_json():
    code, out = _run("spec", "propose-values", "--modality", "biosample", "--field", "Technical.SpecimenType", "--value", "sweat", "--json")
    data = json.loads(out)
    assert code == 0 and data["success"] and data["issue_url"].startswith(FORM)


def test_spec_propose_values_bad_value_exits_1():
    code, out = _run("spec", "propose-values", "--modality", "biosample", "--field", "Technical.SpecimenType", "--value", "Sweat", "--json")
    assert code == 1 and not json.loads(out)["success"]


def test_spec_propose_metric_json():
    code, out = _run(
        "spec", "propose-metric", "--name", "DHEA", "--description", "Steroid hormone.", "--units", "pg/mL",
        "--specimen", "saliva", "--alias", "dehydroepiandrosterone", "--json",
    )
    data = json.loads(out)
    assert code == 0 and data["success"] and data["issue_url"].startswith(FORM)
    assert "terms/biosample/dhea.saliva.json" in data["document"]["files"]


def test_cli_propose_metric_environment():
    code, out = _run("spec", "propose-metric", "--modality", "environment", "--name", "noise level",
                     "--description", "Sound pressure level", "--units", "dB", "--json")
    assert code == 0, out
    assert json.loads(out)["proposal"]["terms"][0]["TermID"] == "prism:noise-level"


def test_cli_propose_metric_environment_with_levels():
    code, out = _run("spec", "propose-metric", "--modality", "environment", "--name", "sky state", "--description", "d",
                     "--level", "c=clear", "--level", "o=overcast", "--cf-standard-name", "cloud_area_fraction", "--json")
    assert code == 0, out
    term = json.loads(out)["proposal"]["terms"][0]
    assert term["Levels"] == {"c": "clear", "o": "overcast"} and term["CFStandardName"] == "cloud_area_fraction"


def test_cli_propose_metric_biosample_without_specimen_exits_1():
    code, out = _run("spec", "propose-metric", "--name", "DHEA", "--description", "d", "--units", "pg/mL", "--json")
    assert code == 1 and "sample type" in out


def test_spec_propose_metric_official_exits_1():
    code, out = _run("spec", "propose-metric", "--name", "cortisol", "--description", "d", "--units", "u", "--specimen", "saliva", "--json")
    assert code == 1 and "prism:cortisol" in json.loads(out)["error"]


def test_spec_propose_metric_with_project_knows_its_sample_types(tmp_path):
    project = _project(tmp_path / "p")
    code, _ = _run("spec", "local", "add-values", "--project", str(project), "--field", "Technical.SpecimenType", "--value", "sweat")
    assert code == 0
    args = ["spec", "propose-metric", "--name", "DHEA", "--description", "d", "--units", "pg/mL", "--specimen", "sweat", "--json"]
    code, out = _run(*args, "--project", str(project))
    assert code == 0 and json.loads(out)["problems"] == []
    code, out = _run(*args)
    assert code == 1 and not json.loads(out)["success"]


def test_spec_propose_values_repeated_value_works():
    code, out = _run("spec", "propose-values", "--modality", "biosample", "--field", "Technical.SpecimenType",
                     "--value", "sweat", "--value", "sweat", "--json")
    assert code == 0 and json.loads(out)["success"]


def test_a_survey_list_addition_is_listed_and_shared_from_the_command_line(tmp_path):
    project = str(_project(tmp_path / "p"))
    code, out = _run("spec", "local", "add-values", "--project", project, "--modality", "survey",
                     "--field", "Study.LicenseID", "--value", "cc-by-nc-local")
    assert code == 0 and "--modality survey" in out
    code, out = _run("spec", "local", "list", "--project", project, "--modality", "survey", "--json")
    assert code == 0 and [i["value"] for i in json.loads(out)["items"]] == ["cc-by-nc-local"]
    code, out = _run("spec", "propose", "--project", project, "--patch", "--modality", "survey", "--json")
    result = json.loads(out)
    assert code == 0 and result["success"] and result["proposal"]["patch"]["operations"][0]["values"] == ["cc-by-nc-local"]


def test_a_term_request_for_a_kind_without_terms_is_a_clear_error(tmp_path):
    code, out = _run("spec", "propose", "--project", str(_project(tmp_path / "p")), "--term", "prism:x", "--modality", "survey", "--json")
    assert code == 1 and "prism:x" in json.loads(out)["error"]
    code, out = _run("spec", "local", "list", "--project", str(tmp_path / "p"), "--modality", "../x", "--json")
    assert code == 1 and "not a kind of data" in json.loads(out)["error"]


def test_spec_example_json():
    code, out = _run("spec", "example", "--modality", "biosample", "--json")
    data = json.loads(out)
    assert code == 0 and data["template"] == "biosample-inflammation" and data["entries"]


def test_spec_example_text_and_bad_modality():
    code, out = _run("spec", "example", "--modality", "biosample")
    assert code == 0 and "Technical.SpecimenType" in out and "serum" in out
    code, _ = _run("spec", "example", "--modality", "../x", "--json")
    assert code == 1


def test_spec_propose_values_carries_not_sure_and_entries_into_the_url():
    code, out = _run("spec", "propose-values", "--modality", "biosample", "--field", "Technical.SpecimenType", "--value", "sweat",
                     "--not-sure", "--closest", "biosample", "--entry", "Technical.Laboratory=Unknown", "--json")
    data = json.loads(out)
    assert code == 0 and "context=Not%20sure" in data["issue_url"] and "Technical.Laboratory%3A%20Unknown" in data["issue_url"]


def test_spec_propose_entry_without_equals_exits_1():
    code, out = _run("spec", "propose-values", "--modality", "biosample", "--field", "Technical.SpecimenType", "--value", "sweat",
                     "--entry", "oops", "--json")
    assert code == 1 and not json.loads(out)["success"]


_PV = ("spec", "propose-values", "--modality", "biosample", "--field", "Technical.SpecimenType", "--value", "sweat")


def _long_entries():
    return [x for i in range(40) for x in ("--entry", f"F{i}=" + "x" * 190)]


def test_json_result_keeps_the_context_when_the_url_is_too_long():
    code, out = _run(*_PV, *_long_entries(), "--json")
    data = json.loads(out)
    assert code == 0 and data["issue_url"] is None and data["context"].count("\n") == 39 and "F39: " in data["context"]


def test_text_result_prints_the_context_when_the_url_is_too_long():
    code, out = _run(*_PV, *_long_entries())
    assert code == 0 and "Context field" in out and "F39: " in out


def test_a_repeated_entry_field_exits_1():
    code, out = _run(*_PV, "--entry", "A=1", "--entry", "A=2", "--json")
    assert code == 1 and not json.loads(out)["success"]


def test_spec_propose_new_kind_json_and_out(tmp_path):
    sample = tmp_path / "s.tsv"
    sample.write_text("time\ttemp\n0\t33.1\n", encoding="utf-8")
    out = tmp_path / "proposal.txt"
    code, text = _run("spec", "propose-new-kind", "--description", "Skin temperature", "--sample", str(sample),
                      "--closest", "physio", "--out", str(out), "--json")
    data = json.loads(text)
    assert code == 0 and data["success"] and data["problems"] == [] and data["issue_url"].startswith(FORM)
    assert out.read_text(encoding="utf-8") == data["text"] and "Sample file:\ntime" in data["text"]


def test_spec_propose_new_kind_refuses_an_oversize_sample_and_an_empty_description(tmp_path):
    sample = tmp_path / "big.tsv"
    sample.write_text("x" * 50_001, encoding="utf-8")
    code, text = _run("spec", "propose-new-kind", "--description", " ", "--sample", str(sample), "--json")
    data = json.loads(text)
    assert code == 1 and not data["success"] and "the description is empty" in data["problems"] and data["issue_url"] is None
    binary = tmp_path / "b.bin"
    binary.write_bytes(b"\xff\xfe\x00")
    code, text = _run("spec", "propose-new-kind", "--description", "d", "--sample", str(binary), "--json")
    assert code == 1 and "UTF-8" in json.loads(text)["error"]


def _kind_args(sample, description="Skin temperature", *extra):
    return ["spec", "propose-new-kind", "--description", description, "--sample", str(sample), "--json", *extra]


def test_spec_propose_new_kind_takes_a_name_and_refuses_a_bids_name(tmp_path):
    sample = tmp_path / "s.tsv"
    sample.write_text("time\ttemp\n0\t33.1\n", encoding="utf-8")
    code, text = _run(*_kind_args(sample, "Skin temperature", "--name", "skintemp"))
    assert code == 0 and "Suggested name: skintemp" in json.loads(text)["text"]
    code, text = _run(*_kind_args(sample, "Skin temperature", "--name", "eeg"))
    assert code == 1 and "already taken" in json.loads(text)["error"]


def test_spec_propose_new_kind_refuses_a_sample_cut_inside_a_character(tmp_path):
    sample = tmp_path / "s.tsv"
    sample.write_bytes(("a" * 49_998 + "é" * 5).encode("utf-8"))  # 50,008 bytes; the read limit falls inside an é
    code, text = _run(*_kind_args(sample))
    data = json.loads(text)
    assert code == 1 and any("larger than" in p for p in data["problems"])


def test_spec_propose_new_kind_accepts_a_multibyte_sample_at_the_limit(tmp_path):
    sample = tmp_path / "s.tsv"
    sample.write_bytes(("a" * 49_998 + "é").encode("utf-8"))  # exactly 50,000 bytes
    code, text = _run(*_kind_args(sample))
    assert code == 0 and json.loads(text)["problems"] == []


@pytest.fixture
def opened(monkeypatch):
    monkeypatch.syspath_prepend(str(REPO / "app"))
    monkeypatch.syspath_prepend(str(REPO))
    from src.cli.commands import spec as spec_commands

    calls = []
    monkeypatch.setattr(spec_commands.webbrowser, "open", lambda url: calls.append(url) or True)
    return spec_commands, calls


def _call(spec_commands, tmp_path, description, sample_text="t\tv\n0\t1\n", open_=True):
    sample = tmp_path / "s.tsv"
    sample.write_text(sample_text, encoding="utf-8")
    args = argparse.Namespace(description=description, sample=str(sample), closest=None, name=None, out=None, open=open_, json=True)
    try:
        spec_commands.cmd_spec_propose_new_kind(args)
    except SystemExit as exc:
        return exc.code


def test_open_opens_the_form_once_on_success(opened, tmp_path):
    spec_commands, calls = opened
    assert _call(spec_commands, tmp_path, "Skin temperature") is None
    assert len(calls) == 1 and calls[0].startswith(FORM)


def test_open_is_not_called_when_there_are_problems(opened, tmp_path):
    spec_commands, calls = opened
    assert _call(spec_commands, tmp_path, " ") == 1 and calls == []


def test_open_is_not_called_when_the_link_is_too_long(opened, tmp_path):
    spec_commands, calls = opened
    assert _call(spec_commands, tmp_path, "long " * 2000) is None and calls == []


def test_propose_patch_names_a_bad_kind_of_data_as_such(tmp_path):
    project = str(_project(tmp_path / "p"))
    code, out = _run("spec", "propose", "--project", project, "--patch", "--modality", "../x", "--json")
    assert code == 1 and "not a kind of data" in json.loads(out)["error"]
    code, out = _run("spec", "propose", "--project", project, "--patch", "--json")
    assert code == 1 and "no schema additions" in json.loads(out)["error"]


def test_add_term_accepts_the_environment_modality(tmp_path):
    project = _project(tmp_path / "p")
    sidecar = tmp_path / "env.json"
    sidecar.write_text(json.dumps({"Technical": {}, "noise_db": {"Description": "Noise", "Units": "dB"}}), encoding="utf-8")
    code, out = _run("spec", "local", "add-term", "--project", str(project), "--sidecar", str(sidecar),
                     "--column", "noise_db", "--modality", "environment", "--json")
    data = json.loads(out)
    assert code == 0 and data["success"] and [t["TermID"] for t in data["proposal"]["terms"]] == ["prism:noise-db"]
