"""`terms export-links`: the links of mappings/ as SSSOM (the standard form of an ID-to-vocabulary link)."""

import json
import subprocess
import sys
from pathlib import Path

import pytest
import yaml

from src.mappings_export import sssom_table
from src.specification import official_specification

REPO = Path(__file__).resolve().parent.parent


def _parse(text: str) -> tuple[dict, list[dict]]:
    """(the YAML header, the rows) of an SSSOM TSV."""
    header = [line[1:] for line in text.splitlines() if line.startswith("#")]
    body = [line.split("\t") for line in text.splitlines() if line and not line.startswith("#")]
    return yaml.safe_load("\n".join(header)), [dict(zip(body[0], row)) for row in body[1:]]


def _expand(curie: str, curie_map: dict) -> str:
    prefix, _, local = curie.partition(":")
    return curie_map[prefix] + local


MAPPINGS = {
    "biosample": {"prism:fsh": {"SameAs": {"snomed": "https://snomed.info/id/25217009"}}},
    "survey": {
        "prism:t.item01": {
            "Measures": [{"URL": "https://snomed.info/id/416767005", "Match": "broader", "Higher": "more",
                          "Source": "the authors", "Checked": "2026-11-19", "Status": "unreviewed"}],
            "ValueRules": [{"Name": "x", "Source": "s", "Rules": []}],
        },
        "prism:t.item02": {"ValueRules": [{"Name": "x", "Source": "s", "Rules": []}], "Levels": {"1": {}}},
    },
}


def test_a_same_as_link_is_an_exact_match_row():
    header, rows = _parse(sssom_table({"biosample": MAPPINGS["biosample"]}))
    assert header["mapping_set_id"].startswith("https://w3id.org/prism-specification/")
    assert rows == [{
        "subject_id": "prism_biosample:fsh", "predicate_id": "skos:exactMatch", "object_id": "snomed:25217009",
        "mapping_justification": "semapv:ManualMappingCuration", "author_label": "", "mapping_date": "", "comment": "",
    }]
    assert header["curie_map"]["prism_biosample"] == "https://w3id.org/prism-specification/terms/biosample/"
    assert header["curie_map"]["snomed"] == "https://snomed.info/id/"


def test_a_measures_entry_keeps_match_source_date_and_status():
    _, rows = _parse(sssom_table({"survey": MAPPINGS["survey"]}))
    assert rows == [{
        "subject_id": "prism_survey:t.item01", "predicate_id": "skos:broadMatch", "object_id": "snomed:416767005",
        "mapping_justification": "semapv:ManualMappingCuration", "author_label": "the authors",
        "mapping_date": "2026-11-19", "comment": "Status: unreviewed; Higher: more",
    }]  # ValueRules and Levels are not links: no row for them


@pytest.mark.parametrize("match,predicate", [("exact", "skos:exactMatch"), ("broader", "skos:broadMatch"),
                                             ("narrower", "skos:narrowMatch"), ("related", "skos:relatedMatch"),
                                             (None, "skos:relatedMatch")])
def test_match_becomes_the_skos_predicate(match, predicate):
    entry = {"URL": "https://snomed.info/id/1234567", **({"Match": match} if match else {})}
    _, rows = _parse(sssom_table({"survey": {"prism:t.a": {"Measures": [entry]}}}))
    assert rows[0]["predicate_id"] == predicate


def test_a_project_local_id_has_a_prefix_too():
    header, rows = _parse(sssom_table({"biosample": {"local:dhea-s": {"SameAs": {"loinc": "https://loinc.org/2191-5"}}}}))
    assert rows[0]["subject_id"] == "local:dhea-s" and header["curie_map"]["local"] == "urn:prism-local:"


def test_one_vocabulary_with_two_address_shapes_gets_two_prefixes():
    mappings = {"survey": {"prism:t.a": {"Measures": [{"URL": "https://snomed.info/id/1234567"}]},
                           "prism:t.b": {"Measures": [{"URL": "https://snomed.info/sct/1234567"}]}}}
    header, rows = _parse(sssom_table(mappings))
    assert {_expand(r["object_id"], header["curie_map"]) for r in rows} == {
        "https://snomed.info/id/1234567", "https://snomed.info/sct/1234567"}


def test_every_shipped_link_survives_the_round_trip():
    spec = official_specification()
    header, rows = _parse(sssom_table(spec.mappings))
    expected = set()
    for modality, entries in spec.mappings.items():
        for term_id, entry in entries.items():
            for url in (entry.get("SameAs") or {}).values():
                expected.add((term_id.partition(":")[2], url))
            for m in entry.get("Measures") or []:
                expected.add((term_id.partition(":")[2], m["URL"]))
    got = {(_expand(r["subject_id"], header["curie_map"]).rsplit("/", 1)[1], _expand(r["object_id"], header["curie_map"]))
           for r in rows}
    assert got == expected and len(rows) >= 40


def test_the_output_is_stable():
    spec = official_specification()
    assert sssom_table(spec.mappings) == sssom_table(spec.mappings)


def _run(*args):
    r = subprocess.run([sys.executable, str(REPO / "prism_tools.py"), "terms", *args],
                       capture_output=True, text=True, encoding="utf-8", errors="replace")
    return r.returncode, r.stdout


def test_the_command_writes_the_table_to_a_file(tmp_path):
    out = tmp_path / "links.sssom.tsv"
    code, text = _run("export-links", "--out", str(out), "--json")
    assert code == 0 and json.loads(text)["rows"] > 40
    assert out.read_text(encoding="utf-8") == sssom_table(official_specification().mappings)


def test_the_command_adds_a_projects_own_links(tmp_path):
    folder = tmp_path / "p" / "code" / "specification"
    (folder / "terms" / "biosample").mkdir(parents=True)
    (folder / "mappings" / "biosample").mkdir(parents=True)
    (folder / "terms" / "biosample" / "dhea-s.json").write_text(json.dumps(
        {"TermID": "local:dhea-s", "Label": "dhea-s", "Description": "x", "Level": "metric", "Units": "pg/mL",
         "SpecimenType": "saliva"}), encoding="utf-8")
    (folder / "mappings" / "biosample" / "dhea-s.json").write_text(json.dumps(
        {"local:dhea-s": {"SameAs": {"loinc": "https://loinc.org/2191-5"}}}), encoding="utf-8")
    code, text = _run("export-links", "--project", str(tmp_path / "p"))
    assert code == 0 and "local:dhea-s\tskos:exactMatch\tloinc:2191-5" in text
