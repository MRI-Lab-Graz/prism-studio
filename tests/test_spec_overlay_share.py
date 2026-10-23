"""Schema additions travel in a proposal: patches/<modality>.json next to the term files (layer 2, B4)."""

import json
import os
import subprocess
import sys
from pathlib import Path
from urllib.parse import parse_qs, urlparse

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(__file__)), "app", "src"))

from src.spec_overlay import OverlayError, add_local_values, proposal_for_local_terms, write_local_terms  # noqa: E402
from src.term_proposal import as_v2, issue_url  # noqa: E402

REPO = Path(__file__).resolve().parent.parent
FIELD = "Technical.SpecimenType"
PARENT = {"TermID": "prism:dhea-s", "Level": "analyte", "Label": "DHEA-S", "Aliases": ["dhea_s"], "Description": "d"}


def _child(specimen: str, slug="dhea-s") -> dict:
    return {"TermID": f"prism:{slug}.{specimen}", "Level": "analyte-specimen", "Parent": f"prism:{slug}",
            "SpecimenType": specimen, "Units": "pg/mL", "MinValue": 0}


def _project(root: Path, specimen="sweat") -> Path:
    add_local_values(root, FIELD, [specimen])
    write_local_terms(root, "biosample", [PARENT, _child(specimen)])
    return root


def test_all_shares_the_terms_and_the_patch(tmp_path):
    result = proposal_for_local_terms(_project(tmp_path), None, include_patch=True)
    assert result["problems"] == []
    assert sorted(result["document"]["files"]) == [
        "patches/biosample.json", "terms/biosample/dhea-s.json", "terms/biosample/dhea-s.sweat.json"]
    assert result["document"]["files"]["patches/biosample.json"]["operations"][0]["values"] == ["sweat"]


def test_the_patch_alone(tmp_path):
    add_local_values(tmp_path, FIELD, ["sweat"])
    result = proposal_for_local_terms(tmp_path, [], include_patch=True)
    assert list(result["document"]["files"]) == ["patches/biosample.json"] and result["problems"] == []


def test_a_term_on_a_local_specimen_brings_the_patch_along(tmp_path):
    result = proposal_for_local_terms(_project(tmp_path), ["prism:dhea-s.sweat"])
    assert "patches/biosample.json" in result["document"]["files"] and result["problems"] == []


def test_a_term_on_an_official_specimen_does_not_bring_the_patch(tmp_path):
    add_local_values(tmp_path, FIELD, ["sweat"])
    write_local_terms(tmp_path, "biosample", [PARENT, _child("saliva")])
    result = proposal_for_local_terms(tmp_path, ["prism:dhea-s"])
    assert "patches/biosample.json" not in result["document"]["files"]


def test_nothing_to_share_when_the_only_addition_is_official_now(tmp_path):
    path = tmp_path / "code" / "specification" / "patches" / "biosample.json"
    path.parent.mkdir(parents=True)
    path.write_text(json.dumps({"operations": [{"op": "add_enum_values", "path": FIELD, "values": ["saliva"]}]}), encoding="utf-8")
    with pytest.raises(OverlayError, match="nothing to share"):
        proposal_for_local_terms(tmp_path, [], include_patch=True)


def test_the_file_limit_counts_the_patch(tmp_path):
    add_local_values(tmp_path, FIELD, ["sweat"])
    terms = [{**PARENT, "TermID": f"prism:m{i}", "Label": f"m{i}", "Aliases": [f"m{i}x"]} for i in range(40)]
    write_local_terms(tmp_path, "biosample", terms)
    result = proposal_for_local_terms(tmp_path, None, include_patch=True)  # 40 terms + 1 patch = 41 files
    assert any("40" in p for p in result["problems"]), result["problems"]


def test_the_form_link_for_a_patch_only_proposal_names_the_modality(tmp_path):
    add_local_values(tmp_path, FIELD, ["sweat"])
    url = issue_url(proposal_for_local_terms(tmp_path, [], include_patch=True)["document"])
    query = parse_qs(urlparse(url).query)
    assert "biosample" in query["title"][0] and "patches/biosample.json" in query["proposal"][0]


def test_as_v2_adds_the_patch_file():
    patch = {"operations": []}
    assert as_v2({"modality": "biosample", "terms": [PARENT], "patch": patch})["files"]["patches/biosample.json"] is patch


def _run(*args):
    result = subprocess.run([sys.executable, str(REPO / "prism_tools.py"), *args], capture_output=True, text=True, encoding="utf-8", errors="replace")
    return result.returncode, result.stdout


def test_cli_patch_and_all(tmp_path):
    _project(tmp_path)
    code, out = _run("spec", "propose", "--project", str(tmp_path), "--patch", "--json")
    assert code == 0 and list(json.loads(out)["document"]["files"]) == ["patches/biosample.json"]
    code, out = _run("spec", "propose", "--project", str(tmp_path), "--all", "--json")
    assert code == 0 and "patches/biosample.json" in json.loads(out)["document"]["files"]
    code, out = _run("spec", "propose", "--project", str(tmp_path), "--term", "prism:dhea-s.sweat", "--json")
    assert code == 0 and "patches/biosample.json" in json.loads(out)["document"]["files"]


def test_cli_patch_without_additions_exits_1(tmp_path):
    code, out = _run("spec", "propose", "--project", str(tmp_path), "--patch", "--json")
    assert code == 1 and json.loads(out)["success"] is False


def test_cli_needs_one_of_term_all_patch(tmp_path):
    code, _out = _run("spec", "propose", "--project", str(tmp_path))
    assert code == 1
