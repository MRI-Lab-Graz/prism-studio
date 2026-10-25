"""The Propose-changes catalog: what can be proposed, without any project."""

import json

import pytest

from src.spec_contribute import example_entries, proposal_for_new_metric, proposal_for_values, spec_catalog
from src.spec_overlay import add_local_values
from src.spec_overlay import OverlayError


def _entry(name):
    return next((m for m in spec_catalog()["modalities"] if m["name"] == name), None)


def test_catalog_lists_biosample_with_specimen_types():
    biosample = _entry("biosample")
    specimen = next(x for x in biosample["lists"] if x["field"] == "Technical.SpecimenType")
    assert specimen["label"] == "Specimen type" and "saliva" in specimen["values"]
    assert biosample["label"].startswith("Lab results")
    assert biosample["metrics"] and all(m["id"].startswith("prism:") for m in biosample["metrics"])


def test_catalog_values_have_no_empty_strings():
    assert all("" not in x["values"] for m in spec_catalog()["modalities"] for x in m["lists"])


def test_the_catalog_lists_every_kind_of_data_with_a_description():
    mods = {m["name"]: m for m in spec_catalog()["modalities"]}
    assert {"biosample", "survey", "physio", "events", "anat"} <= set(mods)
    assert mods["anat"]["kind"] == "bids" and mods["anat"]["lists"] == []
    assert mods["biosample"]["label"].startswith("Lab results")
    assert "biosample-inflammation" in mods["biosample"]["templates"]


def test_example_entries_fill_the_example_from_the_library_template():
    ex = example_entries("biosample")
    by = {e["field"]: e for e in ex["entries"]}
    assert ex["template"] == "biosample-inflammation"
    assert by["Technical.SpecimenType"]["example"] == "serum" and "saliva" in by["Technical.SpecimenType"]["values"]
    assert by["Technical.Laboratory"]["values"] is None
    assert by["Technical.FastingRequired"]["example"] == "yes"
    assert by["Technical.StorageTemperature"]["example"] == "-80"
    assert not any(e["field"].startswith("Metadata") for e in ex["entries"])


def test_a_kind_without_a_library_example_still_lists_its_entries():
    ex = example_entries("physio")
    assert ex["template"] is None and ex["entries"] and all(e["example"] is None for e in ex["entries"])


def test_a_bids_kind_has_no_entries():
    assert example_entries("anat")["entries"] == []


@pytest.mark.parametrize("bad", ["../x", "Survey-AAI", "a/b"])
def test_a_bad_template_name_is_refused(bad):
    with pytest.raises(OverlayError):
        example_entries("survey", bad)


def test_an_unknown_kind_is_refused_for_the_example():
    with pytest.raises(OverlayError):
        example_entries("../x")


def test_project_writes_accept_only_prism_kinds(tmp_path):
    with pytest.raises(OverlayError):
        add_local_values(tmp_path, "Name", ["x"], modality="project")


def test_catalog_units_sorted_and_unique():
    units = spec_catalog()["units"]
    assert "nmol/L" in units and units == sorted(set(units))


def test_catalog_specimens_match_the_biosample_list():
    specimen = next(x for x in _entry("biosample")["lists"] if x["field"] == "Technical.SpecimenType")
    assert spec_catalog()["specimens"] == specimen["values"]


def test_values_proposal_builds_a_patch_document():
    r = proposal_for_values("biosample", "Technical.SpecimenType", ["sweat"])
    assert r["document"]["files"]["patches/biosample.json"] == r["proposal"]["patch"]
    assert r["problems"] == [] and r["skipped"] == []
    assert r["issue_url"].startswith("https://github.com/MRI-Lab-Graz/prism-specification/issues/new")
    assert r["proposal"] == {"modality": "biosample", "terms": [], "patch": {"operations": [
        {"op": "add_enum_values", "path": "Technical.SpecimenType", "values": ["sweat"]}]}}


def test_values_for_a_kind_not_in_the_catalog_is_refused():
    with pytest.raises(OverlayError, match="biosample"):
        proposal_for_values("events", "Technical.Respondent", ["caregiver-report"])


def test_values_already_official_are_skipped():
    with pytest.raises(OverlayError, match="saliva"):
        proposal_for_values("biosample", "Technical.SpecimenType", ["saliva"])
    assert proposal_for_values("biosample", "Technical.SpecimenType", ["saliva", "sweat"])["skipped"] == ["saliva"]


@pytest.mark.parametrize("bad", ["", "Sweat", "sw eat", "1sweat", "schweiß", "<img src=x>"])
def test_values_reject_bad_text(bad):
    with pytest.raises(OverlayError):
        proposal_for_values("biosample", "Technical.SpecimenType", [bad])


def test_values_reject_no_values():
    with pytest.raises(OverlayError):
        proposal_for_values("biosample", "Technical.SpecimenType", [])


def test_values_unknown_field_names_valid_ones():
    with pytest.raises(OverlayError, match="Technical.SpecimenType"):
        proposal_for_values("biosample", "Nope", ["sweat"])
    with pytest.raises(OverlayError, match="biosample"):
        proposal_for_values("nope", "Technical.SpecimenType", ["sweat"])


def test_values_write_nothing(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    proposal_for_values("biosample", "Technical.SpecimenType", ["sweat"])
    assert list(tmp_path.iterdir()) == []


def test_metric_proposal_builds_parent_and_child():
    r = proposal_for_new_metric("DHEA", "Steroid hormone, a marker of adrenal activity.", "pg/mL", "saliva", ["dehydroepiandrosterone"])
    assert set(r["document"]["files"]) == {"terms/biosample/dhea.json", "terms/biosample/dhea.saliva.json"}
    assert r["problems"] == []
    parent, child = r["proposal"]["terms"]
    assert parent["Aliases"] == ["dehydroepiandrosterone"] and child["Parent"] == "prism:dhea"
    assert child["SpecimenType"] == "saliva" and child["Units"] == "pg/mL"


def test_metric_without_aliases_omits_the_field():
    r = proposal_for_new_metric("DHEA", "Steroid hormone.", "pg/mL", "saliva")
    assert "Aliases" not in r["proposal"]["terms"][0]


@pytest.mark.parametrize("name", ["cortisol", "hscrp"])  # hscrp: official alias of prism:crp
def test_metric_matching_an_official_term_is_refused(name):
    with pytest.raises(OverlayError, match="prism:(cortisol|crp)"):
        proposal_for_new_metric(name, "x", "pg/mL", "saliva")


def test_metric_alias_matching_an_official_term_is_refused():
    with pytest.raises(OverlayError, match="prism:crp"):
        proposal_for_new_metric("DHEA", "x", "pg/mL", "saliva", ["hscrp"])


@pytest.mark.parametrize(
    "args",
    [("", "d", "u", "saliva"), ("1abc", "d", "u", "saliva"), ("schweiß", "d", "u", "saliva"),
     ("DHEA", "d", "", "saliva"), ("DHEA", "d", "u", ""), ("DHEA", "", "u", "saliva")],
)
def test_metric_bad_input(args):
    with pytest.raises(OverlayError):
        proposal_for_new_metric(*args)


@pytest.mark.parametrize("name,term", [("Cortisol!", "cortisol"), ("_cortisol_", "cortisol"), ("Alpha Amylase", "alpha-amylase")])
def test_metric_whose_id_is_an_official_term_is_refused(name, term):
    with pytest.raises(OverlayError, match=f"prism:{term}"):
        proposal_for_new_metric(name, "d", "u", "saliva")


def test_metric_specimen_is_trimmed():
    r = proposal_for_new_metric("DHEA", "d", "pg/mL", " saliva ")
    assert r["proposal"]["terms"][1]["TermID"] == "prism:dhea.saliva" and r["problems"] == []


@pytest.mark.parametrize("specimen", ["Sa liva", "saliva/x"])
def test_metric_bad_specimen_text_is_refused(specimen):
    with pytest.raises(OverlayError):
        proposal_for_new_metric("DHEA", "d", "pg/mL", specimen)


def test_metric_inputs_are_trimmed():
    r = proposal_for_new_metric(" DHEA ", " d ", " pg/mL ", "saliva")
    parent, child = r["proposal"]["terms"]
    assert parent["Label"] == "DHEA" and parent["Description"] == "d" and child["Units"] == "pg/mL"


def test_metric_whitespace_only_name_is_refused():
    with pytest.raises(OverlayError):
        proposal_for_new_metric("   ", "d", "u", "saliva")


def test_metric_aliases_are_cleaned():
    r = proposal_for_new_metric("DHEA", "d", "pg/mL", "saliva", ["DHEA", "dhea", "x", "x", " "])
    assert r["proposal"]["terms"][0]["Aliases"] == ["x"]


def test_metric_writes_nothing(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    proposal_for_new_metric("DHEA", "d", "pg/mL", "saliva")
    assert list(tmp_path.iterdir()) == []


def test_metric_unknown_specimen_is_a_problem_not_a_crash():
    assert proposal_for_new_metric("DHEA", "d", "pg/mL", "sweat")["problems"]


def _sweat_project(root):
    patch = root / "code" / "specification" / "patches" / "biosample.json"
    patch.parent.mkdir(parents=True)
    patch.write_text(json.dumps({"operations": [
        {"op": "add_enum_values", "path": "Technical.SpecimenType", "values": ["sweat"]}]}), encoding="utf-8")
    return root


def test_metric_accepts_the_projects_own_specimens(tmp_path):
    project = _sweat_project(tmp_path)
    assert proposal_for_new_metric("DHEA", "d", "pg/mL", "sweat", project_root=project)["problems"] == []


def test_metric_checks_the_kind_before_reading_the_project(tmp_path, monkeypatch):
    def read(*args):
        raise AssertionError("the project was read for an unknown kind of data")

    monkeypatch.setattr("src.spec_contribute._project_specimens", read)
    for bad in ("../../../../evil", "x" * 5000):
        with pytest.raises(OverlayError, match="unknown kind"):
            proposal_for_new_metric("DHEA", "d", "pg/mL", "saliva", modality=bad, project_root=tmp_path)


def test_values_are_deduplicated_keeping_order():
    r = proposal_for_values("biosample", "Technical.SpecimenType", ["sweat", "tears", "sweat"])
    assert r["proposal"]["patch"]["operations"][0]["values"] == ["sweat", "tears"]


def test_metric_for_a_kind_without_measurements_is_refused():
    with pytest.raises(OverlayError, match="no known measurements"):
        proposal_for_new_metric("DHEA", "d", "pg/mL", "saliva", modality="survey")
