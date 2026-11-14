"""prism_tools.py terms list|show|suggest: thin adapter over src.term_registry."""

import json
import subprocess
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parent.parent


def _run(*args):
    r = subprocess.run(
        [sys.executable, str(REPO / "prism_tools.py"), "terms", *args],
        capture_output=True, text=True, encoding="utf-8", errors="replace",
    )
    return r.returncode, r.stdout


def test_terms_list_shows_seed_terms():
    code, out = _run("list")
    assert code == 0 and "prism:cortisol.saliva" in out


def test_terms_list_json():
    code, out = _run("list", "--json")
    data = json.loads(out)
    assert code == 0 and data["success"] and "prism:cortisol" in [t["TermID"] for t in data["terms"]]


def test_terms_show_prints_units():
    code, out = _run("show", "prism:cortisol.saliva")
    assert code == 0 and "nmol/L" in out


def test_terms_show_accepts_the_bare_slug():
    code, out = _run("show", "cortisol", "--json")
    assert code == 0 and json.loads(out)["term"]["TermID"] == "prism:cortisol"


def test_terms_show_unknown_id_exits_1():
    code, out = _run("show", "prism:nope", "--json")
    assert code == 1 and json.loads(out)["success"] is False


def test_terms_suggest_cort_points_to_cortisol():
    code, out = _run("suggest", "cort", "--specimen", "saliva", "--json")
    data = json.loads(out)
    assert code == 0 and data["kind"] == "suggestion" and data["similar"] == ["prism:cortisol"]


def test_terms_suggest_unknown_column():
    code, out = _run("suggest", "zzz_marker", "--json")
    data = json.loads(out)
    assert code == 0 and data["kind"] == "unknown" and data["similar"] == []


# --- terms propose -----------------------------------------------------------

import argparse
import webbrowser

FORM = "https://github.com/MRI-Lab-Graz/prism-specification/issues/new"


def _sidecar(tmp_path, column="ferr_ugl", definition=None, specimen="serum"):
    definition = definition or {"Description": "Ferritin", "Units": "ug/L", "MinValue": 0}
    path = tmp_path / "sidecar.json"
    path.write_text(json.dumps({"Technical": {"SpecimenType": specimen}, column: definition}), encoding="utf-8")
    return path


def _args(sidecar, column="ferr_ugl", **over):
    values = dict(sidecar=str(sidecar), data=None, column=column, label=None, modality="biosample", open=False, json=True)
    values.update(over)
    return argparse.Namespace(**values)


def _handler():
    sys.path.insert(0, str(REPO / "app"))
    from src.cli.commands.terms import cmd_terms_propose

    return cmd_terms_propose


def test_propose_prints_a_valid_proposal_and_opens_nothing(tmp_path):
    code, out = _run("propose", "--sidecar", str(_sidecar(tmp_path)), "--column", "ferr_ugl")
    assert code == 0 and "prism:ferr-ugl.serum" in out and "nothing has been sent" in out.lower() and "--open" in out
    assert "may choose a different" in out and "ferr_ugl" in out


def test_propose_json_has_issue_url_and_no_problems(tmp_path):
    code, out = _run("propose", "--sidecar", str(_sidecar(tmp_path)), "--column", "ferr_ugl", "--json")
    data = json.loads(out)
    assert code == 0 and data["success"] and data["problems"] == [] and data["issue_url"].startswith(FORM)
    assert [t["TermID"] for t in data["proposal"]["terms"]] == ["prism:ferr-ugl", "prism:ferr-ugl.serum"]


def test_propose_official_metric_exits_1_naming_the_term(tmp_path):
    sidecar = _sidecar(tmp_path, "cort", {"Description": "d", "Units": "nmol/L"}, specimen="saliva")
    code, out = _run("propose", "--sidecar", str(sidecar), "--column", "cort", "--json")
    data = json.loads(out)
    assert code == 1 and not data["success"] and "prism:cortisol" in data["error"]


def test_propose_missing_sidecar_exits_1(tmp_path):
    code, out = _run("propose", "--sidecar", str(tmp_path / "nope.json"), "--column", "x", "--json")
    assert code == 1 and not json.loads(out)["success"]


def test_propose_open_calls_webbrowser_once_with_the_form_url(tmp_path, monkeypatch, capsys):
    opened = []
    monkeypatch.setattr(webbrowser, "open", lambda url: opened.append(url) or True)
    _handler()(_args(_sidecar(tmp_path), open=True))
    assert len(opened) == 1 and opened[0].startswith(FORM)
    assert json.loads(capsys.readouterr().out)["opened"] is True


def test_propose_without_open_never_touches_the_browser(tmp_path, monkeypatch):
    def boom(url):
        raise AssertionError("the browser must not be opened without --open")

    monkeypatch.setattr(webbrowser, "open", boom)
    _handler()(_args(_sidecar(tmp_path)))


def test_propose_validation_problem_exits_1_and_opens_nothing(tmp_path, monkeypatch, capsys):
    monkeypatch.setattr(webbrowser, "open", lambda url: (_ for _ in ()).throw(AssertionError("opened")))
    with pytest.raises(SystemExit) as exit_info:
        _handler()(_args(_sidecar(tmp_path, "weird", {"Description": "d", "Units": "u"}), "weird", label="cortisol", open=True))
    data = json.loads(capsys.readouterr().out)
    assert exit_info.value.code == 1 and not data["success"] and any("official" in p for p in data["problems"])


def test_propose_too_long_for_a_url_falls_back_to_pasting(tmp_path, monkeypatch, capsys):
    monkeypatch.setattr(webbrowser, "open", lambda url: (_ for _ in ()).throw(AssertionError("opened")))
    sidecar = _sidecar(tmp_path, definition={"Description": "x" * 7000, "Units": "ug/L"})
    _handler()(_args(sidecar, open=True, json=False))
    out = capsys.readouterr().out
    assert "paste" in out.lower() and FORM in out


def test_propose_out_writes_the_bare_proposal_the_specification_check_accepts(tmp_path):
    out = tmp_path / "proposal.json"
    code, text = _run("propose", "--sidecar", str(_sidecar(tmp_path)), "--column", "ferr_ugl", "--out", str(out))
    assert code == 0 and out.is_file() and "proposal.json" in text
    assert set(json.loads(out.read_text(encoding="utf-8"))) == {"format", "files"}  # the document that is sent: format v2
    bundle = tmp_path / "bundle"
    subprocess.run(
        [sys.executable, str(REPO / "scripts" / "specification" / "term_proposal.py"), "check",
         "--terms", str(REPO / "official" / "library" / "terms" / "biosample"),
         "--schema", str(REPO / "app" / "schemas" / "stable" / "biosample.schema.json"),
         "--out", str(bundle), "--file", str(out)],
        check=True, capture_output=True, text=True,
    )
    assert (bundle / "status").read_text(encoding="utf-8").strip() == "ok"


def test_propose_out_is_not_written_when_the_proposal_cannot_be_made(tmp_path):
    out = tmp_path / "proposal.json"
    sidecar = _sidecar(tmp_path, "cort", {"Description": "d", "Units": "nmol/L"}, specimen="saliva")
    code, _ = _run("propose", "--sidecar", str(sidecar), "--column", "cort", "--out", str(out))
    assert code == 1 and not out.exists()


def test_propose_rejects_wrong_value_types_through_the_vendored_checks(tmp_path):
    """prism-specification v1.1.1 validates value types; a sidecar with Units: 5 must not become a proposal."""
    sidecar = _sidecar(tmp_path, definition={"Description": "d", "Units": 5, "MinValue": "zero"})
    code, out = _run("propose", "--sidecar", str(sidecar), "--column", "ferr_ugl", "--json")
    data = json.loads(out)
    assert code == 1 and not data["success"] and any("Units" in p for p in data["problems"])


def test_propose_array_sidecar_exits_1_without_a_traceback(tmp_path):
    path = tmp_path / "s.json"
    path.write_text("[1, 2]", encoding="utf-8")
    code, out = _run("propose", "--sidecar", str(path), "--column", "x", "--json")
    assert code == 1 and not json.loads(out)["success"]


def test_propose_modality_is_limited_to_biosample(tmp_path):
    code, _ = _run("propose", "--sidecar", str(_sidecar(tmp_path)), "--column", "ferr_ugl", "--modality", "eeg")
    assert code == 2  # argparse: invalid choice


def test_propose_says_so_when_the_browser_could_not_be_opened(tmp_path, monkeypatch, capsys):
    monkeypatch.setattr(webbrowser, "open", lambda url: False)
    _handler()(_args(_sidecar(tmp_path), open=True, json=False))
    out = capsys.readouterr().out
    assert "could not open" in out.lower() and "run this again" not in out.lower() and FORM in out


def _inherited_dataset(tmp_path):
    ds = tmp_path / "ds"
    folder = ds / "sub-01" / "ses-1" / "biosample"
    folder.mkdir(parents=True)
    (ds / "dataset_description.json").write_text("{}", encoding="utf-8")
    (ds / "biosample-iron_biosample.json").write_text(json.dumps(
        {"Technical": {"SpecimenType": "serum"}, "ferr": {"Description": "Ferritin", "Units": "ug/L"}}), encoding="utf-8")
    tsv = folder / "sub-01_ses-1_biosample-iron_biosample.tsv"
    tsv.write_text("ferr\n1\n", encoding="utf-8")
    tsv.with_suffix(".json").write_text(json.dumps({"Study": {"BiosampleName": "iron"}}), encoding="utf-8")  # no column here
    return tsv


def test_propose_data_resolves_the_inherited_sidecar(tmp_path):
    code, out = _run("propose", "--data", str(_inherited_dataset(tmp_path)), "--column", "ferr", "--json")
    data = json.loads(out)
    assert code == 0 and data["success"] and data["proposal"]["terms"][-1]["Units"] == "ug/L"


def test_propose_needs_exactly_one_of_sidecar_and_data(tmp_path):
    tsv = _inherited_dataset(tmp_path)
    assert _run("propose", "--column", "ferr")[0] == 2
    assert _run("propose", "--column", "ferr", "--sidecar", str(tmp_path / "s.json"), "--data", str(tsv))[0] == 2


def test_propose_environment_column_from_data_file(tmp_path):
    (tmp_path / "dataset_description.json").write_text(json.dumps({"Name": "T", "BIDSVersion": "1.10.1"}), encoding="utf-8")
    (tmp_path / "environment-site_environment.json").write_text(json.dumps({
        "Technical": {}, "noise_db": {"Description": "Noise level", "Units": "dB"}}), encoding="utf-8")
    folder = tmp_path / "sub-01" / "ses-1" / "environment"
    folder.mkdir(parents=True)
    tsv = folder / "sub-01_ses-1_environment-site_environment.tsv"
    tsv.write_text("subject_id\tsession_id\tnoise_db\nsub-01\tses-1\t40\n", encoding="utf-8")
    code, out = _run("propose", "--data", str(tsv), "--column", "noise_db", "--modality", "environment", "--json")
    data = json.loads(out)
    assert code == 0, out
    (term,) = data["proposal"]["terms"]
    assert term["Level"] == "variable" and term["Units"] == "dB" and term["TermID"] == "prism:noise-db"


# --- survey registry: instrument, item and score IDs -----------------------------

def test_terms_list_survey_shows_instrument_item_and_score():
    code, out = _run("list", "--modality", "survey")
    assert code == 0 and "prism:tipi\tinstrument" in out
    assert "prism:tipi.tipi02\titem" in out and "prism:tipi.score-extraversion\tscore" in out


def test_terms_show_survey_item_by_id_and_by_its_key():
    for name in ("prism:tipi.tipi02", "TIPI02"):
        code, out = _run("show", name, "--modality", "survey", "--json")
        assert code == 0 and json.loads(out)["term"]["Parent"] == "prism:tipi"


def test_terms_freeze_is_for_survey_only():
    code, out = _run("freeze", "--modality", "biosample")
    assert code == 1 and "only the survey registry" in out


def test_terms_freeze_refuses_when_a_released_id_is_gone(tmp_path, monkeypatch):
    # run in-process against a library that lost an item the released list still holds
    import argparse
    from src.cli.commands import terms as cmd
    monkeypatch.setattr(cmd, "released_ids", lambda: {"prism:tipi.gone"})
    with pytest.raises(SystemExit) as exc:
        cmd.cmd_terms_freeze(argparse.Namespace(modality="survey", json=True))
    assert exc.value.code == 1


def test_terms_resolve_cli(tmp_path):
    side = json.loads((REPO / "official" / "library" / "survey" / "survey-tipi.json").read_text(encoding="utf-8"))
    side["Study"]["TaskName"] = "tipi"   # a project sidecar carries it; the library file relies on its name
    side["TIPI02"]["MaxValue"] = 99
    path = tmp_path / "task-tipi_survey.json"
    path.write_text(json.dumps(side), encoding="utf-8")
    code, out = _run("resolve", "--sidecar", str(path))
    assert code == 0 and "TIPI01\tprism:tipi.tipi01\t" in out and "TIPI02\t-\tchanged scale" in out
    code, out = _run("resolve", "--sidecar", str(path), "--json")
    data = json.loads(out)
    assert code == 0 and data["success"] and data["instrument"] == "prism:tipi"


@pytest.mark.parametrize("content", [None, "[1]", "{"])
def test_terms_resolve_bad_file_exits_1(tmp_path, content):
    path = tmp_path / "x.json"
    if content is not None:
        path.write_text(content, encoding="utf-8")
    code, out = _run("resolve", "--sidecar", str(path))
    assert code == 1 and "Error:" in out and "Traceback" not in out


def test_terms_show_survey_dass21_is_the_instrument_in_any_case():
    for name in ("DASS21", "dass21"):
        code, out = _run("show", name, "--modality", "survey", "--json")
        assert code == 0 and json.loads(out)["term"]["TermID"] == "prism:dass21"


def test_terms_show_refuses_an_ambiguous_label(monkeypatch, capsys):
    import argparse
    from src.cli.commands import terms as cmd
    reg = {"a.q01": {"TermID": "prism:a.q01", "Label": "Q01"}, "b.q01": {"TermID": "prism:b.q01", "Label": "Q01"}}
    monkeypatch.setattr(cmd, "_registry", lambda modality: (reg, []))
    with pytest.raises(SystemExit) as exc:
        cmd.cmd_terms_show(argparse.Namespace(modality="survey", term="Q01", json=True))
    out = json.loads(capsys.readouterr().out)
    assert exc.value.code == 1 and out["success"] is False and set(out["candidates"]) == {"prism:a.q01", "prism:b.q01"}


def test_freeze_refusal_names_the_unreadable_template(monkeypatch, capsys):
    import argparse
    from src.cli.commands import terms as cmd
    monkeypatch.setattr(cmd, "build_survey_registry", lambda: ({}, ["survey-x.json: cannot read (boom)"]))
    monkeypatch.setattr(cmd, "released_ids", lambda: {"prism:x"})
    with pytest.raises(SystemExit):
        cmd.cmd_terms_freeze(argparse.Namespace(modality="survey", json=False))
    out = capsys.readouterr().out
    assert "survey-x.json: cannot read (boom)" in out and "prism:x: released ID is gone" in out


def test_terms_list_json_carries_the_survey_problems(monkeypatch, capsys):
    import argparse
    from src.cli.commands import terms as cmd
    monkeypatch.setattr(cmd, "_registry", lambda modality: ({}, ["survey-x.json: cannot read (boom)"]))
    cmd.cmd_terms_list(argparse.Namespace(modality="survey", json=True))
    assert json.loads(capsys.readouterr().out)["problems"] == ["survey-x.json: cannot read (boom)"]


def _show(term, capsys, **kw):
    import argparse
    from src.cli.commands import terms as cmd
    cmd.cmd_terms_show(argparse.Namespace(modality="biosample", term=term, json=kw.get("json", False)))
    return capsys.readouterr().out


@pytest.mark.xfail(strict=True, reason="v1.5.7 moved TermURL into mappings/; Task 7 makes `terms show` read it from there")
def test_terms_show_gives_a_child_the_links_of_its_parent(capsys):
    data = json.loads(_show("shbg.serum", capsys, json=True))
    assert data["links"]["snomed"] == {"url": "https://snomed.info/id/55503002", "from": "prism:shbg"}
    out = _show("shbg.serum", capsys)
    assert "https://snomed.info/id/55503002" in out and "prism:shbg" in out


def test_terms_show_without_links_prints_no_links_line(capsys):
    assert "Links" not in _show("cortisol.serum", capsys)
