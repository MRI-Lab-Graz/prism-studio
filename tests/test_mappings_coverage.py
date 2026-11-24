"""`terms coverage`: which IDs have a link to an outside vocabulary, and which do not (yet)."""

import json
import subprocess
import sys
from pathlib import Path

from src.mappings_coverage import coverage

REPO = Path(__file__).resolve().parent.parent

REGISTRY = {
    "a": {"TermID": "prism:a"},
    "a.serum": {"TermID": "prism:a.serum", "Parent": "prism:a"},
    "b": {"TermID": "prism:b"},
    "c": {"TermID": "prism:c"},
    "d": {"TermID": "prism:d"},
}
MAPPINGS = {
    "prism:a": {"SameAs": {"snomed": "https://snomed.info/id/1234567"}},
    "prism:b": {"Measures": [{"URL": "https://snomed.info/id/1234567"}]},
    "prism:c": {"ValueRules": [{"Name": "x"}], "SameAs": {}, "Measures": []},  # entries that are not links
}


def test_an_id_is_linked_directly_through_its_parent_or_not_at_all():
    result = coverage({"biosample": REGISTRY}, lambda term_id: MAPPINGS.get(term_id, {}))["biosample"]
    assert result == {"total": 5, "direct": 2, "inherited": 1, "none": 2, "missing": ["prism:c", "prism:d"]}


def test_a_modality_without_terms_is_empty():
    assert coverage({"environment": {}}, lambda term_id: {})["environment"] == {
        "total": 0, "direct": 0, "inherited": 0, "none": 0, "missing": []}


def _run(*args):
    r = subprocess.run([sys.executable, str(REPO / "prism_tools.py"), "terms", "coverage", *args],
                       capture_output=True, text=True, encoding="utf-8", errors="replace")
    return r.returncode, r.stdout


def test_the_command_reports_every_modality_by_default():
    code, out = _run("--json")
    data = json.loads(out)
    assert code == 0 and {"biosample", "environment", "survey"} <= set(data["modalities"])
    for m in data["modalities"].values():
        assert m["total"] == m["direct"] + m["inherited"] + m["none"] == m["direct"] + m["inherited"] + len(m["missing"])
    assert data["modalities"]["biosample"]["direct"] >= 10 and data["modalities"]["survey"]["direct"] > 0


def test_the_command_can_report_one_modality_and_list_what_is_missing():
    code, out = _run("--modality", "biosample", "--missing")
    assert code == 0 and "biosample:" in out and "environment:" not in out
    assert "prism:cortisol\n" in out or "prism:cortisol\t" in out  # an ID without a link is listed


def test_a_projects_own_link_counts(tmp_path):
    folder = tmp_path / "p" / "code" / "specification"
    (folder / "terms" / "biosample").mkdir(parents=True)
    (folder / "mappings" / "biosample").mkdir(parents=True)
    (folder / "terms" / "biosample" / "dhea-s.json").write_text(json.dumps(
        {"TermID": "local:dhea-s", "Label": "dhea-s", "Description": "x", "Level": "metric", "Units": "pg/mL",
         "SpecimenType": "saliva"}), encoding="utf-8")
    (folder / "mappings" / "biosample" / "dhea-s.json").write_text(json.dumps(
        {"local:dhea-s": {"SameAs": {"loinc": "https://loinc.org/2191-5"}}}), encoding="utf-8")
    before = json.loads(_run("--modality", "biosample", "--json")[1])["modalities"]["biosample"]
    after = json.loads(_run("--modality", "biosample", "--project", str(tmp_path / "p"), "--json")[1])["modalities"]["biosample"]
    assert after["total"] == before["total"] + 1 and after["direct"] == before["direct"] + 1
