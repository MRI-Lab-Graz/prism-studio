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
