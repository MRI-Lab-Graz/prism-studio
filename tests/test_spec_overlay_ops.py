"""Add, list, find and propose local metrics (phase 1, Task 4)."""

import json
import os
import sys
from pathlib import Path

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(__file__)), "app", "src"))

from src.spec_overlay import (  # noqa: E402
    OverlayError, add_local_term, find_unknown_metrics, list_local_items, load_local_terms,
    proposal_for_local_term, write_local_terms,
)

FORM = "https://github.com/MRI-Lab-Graz/prism-specification/issues/new"


def _dataset(root: Path, columns: dict, specimen="saliva", tsvs=1) -> Path:
    """A project with a root-level sidecar and `tsvs` data files that share it. Returns the first TSV."""
    root.mkdir(parents=True, exist_ok=True)
    (root / "dataset_description.json").write_text("{}", encoding="utf-8")
    (root / "biosample-saliva_biosample.json").write_text(json.dumps({
        "Technical": {"SpecimenType": specimen}, "Study": {"BiosampleName": "saliva"},
        "Metadata": {"SchemaVersion": "1.1.0", "CreationDate": "2026-10-23"},
        "sample_id": {"Description": "Tube", "Units": "n/a"}, **columns}), encoding="utf-8")
    first = None
    for n in range(1, tsvs + 1):
        folder = root / f"sub-0{n}" / "ses-1" / "biosample"
        folder.mkdir(parents=True, exist_ok=True)
        tsv = folder / f"sub-0{n}_ses-1_biosample-saliva_biosample.tsv"
        tsv.write_text("sample_id\t" + "\t".join(columns) + "\nS-1\t" + "\t".join("1" for _ in columns) + "\n", encoding="utf-8")
        first = first or tsv
    return first


DHEA = {"dhea_s": {"Description": "Salivary DHEA-S", "Units": "pg/mL", "MinValue": 0}}


def test_add_from_a_data_file_reads_the_inherited_sidecar(tmp_path):
    tsv = _dataset(tmp_path / "p", DHEA)
    result = add_local_term(tmp_path / "p", column="dhea_s", data_file=str(tsv), label="DHEA-S")
    assert [t["TermID"] for t in result["proposal"]["terms"]] == ["prism:dhea-s", "prism:dhea-s.saliva"]
    assert sorted(Path(p).name for p in result["written"]) == ["dhea-s.json", "dhea-s.saliva.json"]
    assert set(load_local_terms(tmp_path / "p")[0]) == {"dhea-s", "dhea-s.saliva"}


def test_add_from_a_sidecar_file(tmp_path):
    _dataset(tmp_path / "p", DHEA)
    result = add_local_term(tmp_path / "p", column="dhea_s", sidecar_file=str(tmp_path / "p" / "biosample-saliva_biosample.json"))
    assert result["proposal"]["terms"][0]["TermID"] == "prism:dhea-s"


def test_add_refuses_an_official_metric_naming_the_term(tmp_path):
    tsv = _dataset(tmp_path / "p", {"cort": {"Description": "d", "Units": "nmol/L"}})
    with pytest.raises(OverlayError, match="prism:cortisol"):
        add_local_term(tmp_path / "p", column="cort", data_file=str(tsv))
    assert not (tmp_path / "p" / "code").exists()


def test_add_refuses_a_term_a_local_term_already_owns(tmp_path):
    tsv = _dataset(tmp_path / "p", {**DHEA, "dhea2": {"Description": "d", "Units": "pg/mL"}})
    add_local_term(tmp_path / "p", column="dhea_s", data_file=str(tsv), label="DHEA-S")
    with pytest.raises(OverlayError, match="prism:dhea-s"):
        add_local_term(tmp_path / "p", column="dhea_s", data_file=str(tsv))  # its alias now resolves
    with pytest.raises(OverlayError, match="prism:dhea-s"):
        add_local_term(tmp_path / "p", column="dhea2", data_file=str(tsv), label="DHEA-S")  # same ID


def test_add_needs_exactly_one_source(tmp_path):
    tsv = _dataset(tmp_path / "p", DHEA)
    with pytest.raises(OverlayError, match="exactly one"):
        add_local_term(tmp_path / "p", column="dhea_s")
    with pytest.raises(OverlayError, match="exactly one"):
        add_local_term(tmp_path / "p", column="dhea_s", data_file=str(tsv), sidecar_file=str(tsv))


def test_list_shows_local_now_official_and_invalid(tmp_path):
    project = tmp_path / "p"
    write_local_terms(project, "biosample", [
        {"TermID": "prism:dhea-s", "Level": "analyte", "Label": "DHEA-S", "Aliases": [], "Description": "d"},
        {"TermID": "prism:cortisol", "Level": "analyte", "Label": "mine", "Aliases": [], "Description": "d"},
    ])
    (project / "code" / "specification" / "terms" / "biosample" / "broken.json").write_text("{no", encoding="utf-8")
    status = {item["id"] or item["path"].split("/")[-1]: item["status"] for item in list_local_items(project)}
    assert status == {"prism:dhea-s": "local", "prism:cortisol": "now-official", "broken.json": "invalid"}
    assert all(item["layer"] == 3 and item["modality"] == "biosample" for item in list_local_items(project))


def test_find_unknown_metrics(tmp_path):
    columns = {**DHEA, "cort": {"Description": "d", "Units": "nmol/L"}}
    _dataset(tmp_path / "p", columns, tsvs=2)
    junk = tmp_path / "p" / "derivatives" / "x" / "sub-01_biosample-saliva_biosample.tsv"
    junk.parent.mkdir(parents=True)
    junk.write_text("dhea_s\n1\n", encoding="utf-8")
    found = find_unknown_metrics(tmp_path / "p")
    assert [m["column"] for m in found] == ["dhea_s"]  # cort is an alias of an official term; one entry for two TSVs
    entry = found[0]
    assert entry["specimen"] == "saliva" and entry["units"] == "pg/mL" and entry["similar"] == []
    assert entry["data_file"].endswith("_biosample-saliva_biosample.tsv") and "derivatives" not in entry["data_file"]


def test_find_unknown_metrics_ignores_columns_that_a_local_term_covers(tmp_path):
    tsv = _dataset(tmp_path / "p", DHEA)
    add_local_term(tmp_path / "p", column="dhea_s", data_file=str(tsv), label="DHEA-S")
    assert find_unknown_metrics(tmp_path / "p") == []


def test_proposal_for_a_local_parent_and_child(tmp_path):
    tsv = _dataset(tmp_path / "p", DHEA)
    add_local_term(tmp_path / "p", column="dhea_s", data_file=str(tsv), label="DHEA-S")
    for term_id in ("prism:dhea-s", "prism:dhea-s.saliva"):  # a child pulls in its local parent
        result = proposal_for_local_term(tmp_path / "p", term_id)
        assert [t["TermID"] for t in result["proposal"]["terms"]] == ["prism:dhea-s", "prism:dhea-s.saliva"]
        assert result["problems"] == [] and result["issue_url"].startswith(FORM)


def test_proposal_above_two_terms_must_be_made_in_two_steps(tmp_path):
    project = tmp_path / "p"
    parent = {"TermID": "prism:dhea-s", "Level": "analyte", "Label": "DHEA-S", "Aliases": [], "Description": "d"}
    child = {"TermID": "prism:dhea-s.saliva", "Level": "analyte-specimen", "Parent": "prism:dhea-s",
             "SpecimenType": "saliva", "Units": "pg/mL"}
    write_local_terms(project, "biosample", [parent, child, {**child, "TermID": "prism:dhea-s.serum", "SpecimenType": "serum"}])
    with pytest.raises(OverlayError, match="two steps"):
        proposal_for_local_term(project, "prism:dhea-s")
    assert len(proposal_for_local_term(project, "prism:dhea-s.serum")["proposal"]["terms"]) == 2


def test_a_local_child_of_an_official_parent_is_proposed_alone(tmp_path):
    _dataset(tmp_path / "p", {"cortisol_hair": {"Description": "d", "Units": "pg/mg", "Term": "cortisol"}}, specimen="hair")
    add_local_term(tmp_path / "p", column="cortisol_hair", sidecar_file=str(tmp_path / "p" / "biosample-saliva_biosample.json"))
    result = proposal_for_local_term(tmp_path / "p", "prism:cortisol.hair")
    assert [t["TermID"] for t in result["proposal"]["terms"]] == ["prism:cortisol.hair"] and result["problems"] == []


def test_proposal_for_an_unknown_or_bad_id_is_an_error(tmp_path):
    with pytest.raises(OverlayError):
        proposal_for_local_term(tmp_path / "p", "prism:nope")
    with pytest.raises(OverlayError):
        proposal_for_local_term(tmp_path / "p", "prism:../x")
