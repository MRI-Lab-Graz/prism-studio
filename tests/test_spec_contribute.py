"""The Propose-changes catalog: what can be proposed, without any project."""

import pytest

from src.spec_contribute import proposal_for_new_metric, proposal_for_values, spec_catalog
from src.spec_overlay import OverlayError


def _entry(name):
    return next((m for m in spec_catalog()["modalities"] if m["name"] == name), None)


def test_catalog_lists_biosample_with_specimen_types():
    biosample = _entry("biosample")
    specimen = next(x for x in biosample["lists"] if x["field"] == "Technical.SpecimenType")
    assert specimen["label"] == "Specimen type" and "saliva" in specimen["values"]
    assert biosample["label"] == "Biosample"
    assert biosample["metrics"] and all(m["id"].startswith("prism:") for m in biosample["metrics"])


def test_catalog_values_have_no_empty_strings():
    assert all("" not in x["values"] for m in spec_catalog()["modalities"] for x in m["lists"])


def test_catalog_has_no_modality_without_lists():
    assert _entry("events") is None


def test_catalog_lists_only_kinds_the_vendored_check_supports():
    modalities = spec_catalog()["modalities"]
    assert modalities and all("Technical.SpecimenType" in [x["field"] for x in m["lists"]] for m in modalities)
    assert _entry("survey") is None and _entry("events") is None


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
        proposal_for_values("survey", "Technical.Respondent", ["caregiver-report"])


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


def test_metric_accepts_extra_specimens():
    official = spec_catalog()["specimens"]
    assert proposal_for_new_metric("DHEA", "d", "pg/mL", "sweat", specimens=[*official, "sweat"])["problems"] == []


def test_metric_for_a_kind_not_in_the_catalog_is_refused():
    with pytest.raises(OverlayError, match="biosample"):
        proposal_for_new_metric("DHEA", "d", "pg/mL", "saliva", modality="survey")
