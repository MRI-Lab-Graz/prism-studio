"""Add, list, find and propose local metrics (phase 1, Task 4)."""

import json
import os
import sys
from pathlib import Path

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(__file__)), "app", "src"))

from src.spec_overlay import (  # noqa: E402
    OverlayError, add_local_term, find_unknown_metrics, list_local_items, load_local_terms,
    proposal_for_local_terms, write_local_terms,
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
    for folder in ("derivatives", "sourcedata", ".git", "code"):  # never project data
        junk = tmp_path / "p" / folder / "x" / "sub-01_biosample-saliva_biosample.tsv"
        junk.parent.mkdir(parents=True)
        junk.write_text("dhea_s\n1\n", encoding="utf-8")
    found = find_unknown_metrics(tmp_path / "p")
    assert [m["column"] for m in found] == ["dhea_s"]  # cort is an alias of an official term; one entry for two TSVs
    entry = found[0]
    assert entry["specimen"] == "saliva" and entry["units"] == "pg/mL" and entry["similar"] == []
    assert entry["data_file"].endswith("_biosample-saliva_biosample.tsv") and not any(part in entry["data_file"] for part in ("derivatives", "sourcedata", ".git", "/code/"))


def test_find_unknown_metrics_ignores_columns_that_a_local_term_covers(tmp_path):
    tsv = _dataset(tmp_path / "p", DHEA)
    add_local_term(tmp_path / "p", column="dhea_s", data_file=str(tsv), label="DHEA-S")
    assert find_unknown_metrics(tmp_path / "p") == []


def test_proposal_for_a_local_parent_and_child(tmp_path):
    tsv = _dataset(tmp_path / "p", DHEA)
    add_local_term(tmp_path / "p", column="dhea_s", data_file=str(tsv), label="DHEA-S")
    for term_id in ("prism:dhea-s", "prism:dhea-s.saliva"):  # a child pulls in its local parent
        result = proposal_for_local_terms(tmp_path / "p", [term_id])
        assert [t["TermID"] for t in result["proposal"]["terms"]] == ["prism:dhea-s", "prism:dhea-s.saliva"]
        assert result["problems"] == [] and result["issue_url"].startswith(FORM)


def _many(project, specimens=("saliva", "serum", "plasma")):
    parent = {"TermID": "prism:dhea-s", "Level": "analyte", "Label": "DHEA-S", "Aliases": [], "Description": "d"}
    kids = [{"TermID": f"prism:dhea-s.{s}", "Level": "analyte-specimen", "Parent": "prism:dhea-s", "SpecimenType": s, "Units": "pg/mL"} for s in specimens]
    write_local_terms(project, "biosample", [parent, *kids])


def test_a_parent_with_three_local_children_is_shared_as_one_proposal(tmp_path):
    _many(tmp_path / "p")
    result = proposal_for_local_terms(tmp_path / "p", ["prism:dhea-s"])
    ids = [t["TermID"] for t in result["proposal"]["terms"]]
    assert ids == ["prism:dhea-s", "prism:dhea-s.plasma", "prism:dhea-s.saliva", "prism:dhea-s.serum"]
    assert result["problems"] == [] and result["document"]["format"] == "prism-proposal/2"
    assert sorted(result["document"]["files"]) == [f"terms/biosample/{i.partition(':')[2]}.json" for i in sorted(ids)]


def test_a_child_pulls_in_its_local_parent_only(tmp_path):
    _many(tmp_path / "p")
    ids = [t["TermID"] for t in proposal_for_local_terms(tmp_path / "p", ["prism:dhea-s.serum"])["proposal"]["terms"]]
    assert ids == ["prism:dhea-s", "prism:dhea-s.serum"]


def test_all_local_terms_in_one_proposal(tmp_path):
    _many(tmp_path / "p")
    result = proposal_for_local_terms(tmp_path / "p")
    assert len(result["proposal"]["terms"]) == 4 and result["skipped"] == []
    assert result["issue_url"].startswith(FORM)  # four terms still fit in a prefilled link


def test_forty_local_terms_are_too_long_for_a_link_but_still_a_proposal(tmp_path):
    project = tmp_path / "p"
    terms = [{"TermID": f"prism:m{n}-x", "Level": "analyte", "Label": f"m{n}x", "Aliases": [], "Description": "d" * 300} for n in range(40)]
    write_local_terms(project, "biosample", terms)
    result = proposal_for_local_terms(project)
    assert len(result["document"]["files"]) == 40 and result["problems"] == [] and result["issue_url"] is None


def test_several_ids_are_deduplicated(tmp_path):
    _many(tmp_path / "p")
    result = proposal_for_local_terms(tmp_path / "p", ["prism:dhea-s.serum", "prism:dhea-s.saliva", "prism:dhea-s.serum"])
    assert [t["TermID"] for t in result["proposal"]["terms"]] == ["prism:dhea-s", "prism:dhea-s.saliva", "prism:dhea-s.serum"]


def test_terms_the_official_registry_adopted_are_skipped_and_reported(tmp_path):
    project = tmp_path / "p"
    _many(project, ("saliva",))
    write_local_terms(project, "biosample", [{"TermID": "prism:cortisol", "Level": "analyte", "Label": "mine", "Aliases": [], "Description": "d"}])
    result = proposal_for_local_terms(project)
    assert [t["TermID"] for t in result["proposal"]["terms"]] == ["prism:dhea-s", "prism:dhea-s.saliva"]
    assert result["skipped"] == ["prism:cortisol"]
    named = proposal_for_local_terms(project, ["prism:cortisol", "prism:dhea-s"])
    assert named["skipped"] == ["prism:cortisol"] and len(named["proposal"]["terms"]) == 2


def test_nothing_to_share_is_an_error(tmp_path):
    with pytest.raises(OverlayError, match="nothing to share"):
        proposal_for_local_terms(tmp_path / "p")
    project = tmp_path / "q"
    write_local_terms(project, "biosample", [{"TermID": "prism:cortisol", "Level": "analyte", "Label": "mine", "Aliases": [], "Description": "d"}])
    with pytest.raises(OverlayError, match="nothing to share"):
        proposal_for_local_terms(project)


def test_more_than_forty_files_is_reported_by_the_specification_check(tmp_path):
    project = tmp_path / "p"
    terms = [{"TermID": f"prism:m{n}-x", "Level": "analyte", "Label": f"m{n}x", "Aliases": [], "Description": "d"} for n in range(41)]
    write_local_terms(project, "biosample", terms)
    result = proposal_for_local_terms(project)  # the limit is upstream's rule, reported as a problem: no second copy here
    assert any("at most 40" in p for p in result["problems"])
    assert len(proposal_for_local_terms(project, ["prism:m0-x"])["proposal"]["terms"]) == 1


def test_an_unknown_id_among_several_is_an_error(tmp_path):
    _many(tmp_path / "p")
    with pytest.raises(OverlayError, match="prism:nope"):
        proposal_for_local_terms(tmp_path / "p", ["prism:dhea-s", "prism:nope"])


def test_a_local_child_of_an_official_parent_is_proposed_alone(tmp_path):
    _dataset(tmp_path / "p", {"cortisol_hair": {"Description": "d", "Units": "pg/mg", "Term": "cortisol"}}, specimen="hair")
    add_local_term(tmp_path / "p", column="cortisol_hair", sidecar_file=str(tmp_path / "p" / "biosample-saliva_biosample.json"))
    result = proposal_for_local_terms(tmp_path / "p", ["prism:cortisol.hair"])
    assert [t["TermID"] for t in result["proposal"]["terms"]] == ["prism:cortisol.hair"] and result["problems"] == []


def test_proposal_for_an_unknown_or_bad_id_is_an_error(tmp_path):
    with pytest.raises(OverlayError):
        proposal_for_local_terms(tmp_path / "p", ["prism:nope"])
    with pytest.raises(OverlayError):
        proposal_for_local_terms(tmp_path / "p", ["prism:../x"])


def test_a_second_metric_can_be_added_after_the_first(tmp_path):
    """Regression: the registry the check sees contains the first local term, which has no Status by design."""
    columns = {**DHEA, "ferr_ugl": {"Description": "Ferritin", "Units": "ug/L"}}
    tsv = _dataset(tmp_path / "p", columns)
    add_local_term(tmp_path / "p", column="dhea_s", data_file=str(tsv), label="DHEA-S")
    second = add_local_term(tmp_path / "p", column="ferr_ugl", data_file=str(tsv), label="Ferritin")
    assert [t["TermID"] for t in second["proposal"]["terms"]] == ["prism:ferritin", "prism:ferritin.saliva"]
    assert set(load_local_terms(tmp_path / "p")[0]) == {"dhea-s", "dhea-s.saliva", "ferritin", "ferritin.saliva"}


# --- review fixes: honest "official now", one broken local file does not block every add --------------

def test_a_local_term_that_only_shares_an_official_name_is_not_called_official_by_id(tmp_path):
    project = tmp_path / "p"
    write_local_terms(project, "biosample", [{"TermID": "prism:mycort", "Level": "analyte", "Label": "Cortisol", "Aliases": [], "Description": "d"}])
    assert [i["status"] for i in list_local_items(project)] == ["now-official"]  # its label is an official name: same decision as the validator
    with pytest.raises(OverlayError, match="covered by official"):
        proposal_for_local_terms(project)


def test_one_broken_local_term_does_not_block_adding_an_unrelated_metric(tmp_path):
    columns = {**DHEA, "ferr_ugl": {"Description": "Ferritin", "Units": "ug/L"}}
    tsv = _dataset(tmp_path / "p", columns)
    add_local_term(tmp_path / "p", column="dhea_s", data_file=str(tsv), label="DHEA-S")
    (tmp_path / "p" / "code" / "specification" / "terms" / "biosample" / "dhea-s.json").unlink()  # orphans its child
    result = add_local_term(tmp_path / "p", column="ferr_ugl", data_file=str(tsv), label="Ferritin")
    assert [t["TermID"] for t in result["proposal"]["terms"]] == ["prism:ferritin", "prism:ferritin.saliva"]


def test_a_real_problem_with_the_new_terms_still_blocks_the_add(tmp_path):
    columns = {**DHEA, "dhea2": {"Description": "d", "Units": "pg/mL"}}
    tsv = _dataset(tmp_path / "p", columns)
    add_local_term(tmp_path / "p", column="dhea_s", data_file=str(tsv), label="DHEA-S")
    with pytest.raises(OverlayError):
        add_local_term(tmp_path / "p", column="dhea2", data_file=str(tsv), label="DHEA-S")  # same ID as the first


def test_an_over_long_name_is_refused_when_adding_and_nothing_is_written(tmp_path):
    """The vendored v1.2.1 caps IDs at 63 characters; the add must surface that (shape problems name no stem)."""
    tsv = _dataset(tmp_path / "p", DHEA)
    with pytest.raises(OverlayError, match="path"):
        add_local_term(tmp_path / "p", column="dhea_s", data_file=str(tsv), label="a" * 100)
    assert not (tmp_path / "p" / "code").exists()


def test_a_survey_list_addition_is_shared_without_problems():
    from src.spec_contribute import proposal_for_values
    result = proposal_for_values("survey", "Study.LicenseID", ["cc-by-nc-local"])
    assert result["problems"] == [] and result["issue_url"]


def test_the_catalog_lists_every_modality_with_a_list():
    from src.spec_contribute import spec_catalog
    names = {m["name"] for m in spec_catalog()["modalities"]}
    assert {"biosample", "survey", "biometrics", "physio", "environment"} <= names and "events" not in names
