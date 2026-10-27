"""The Propose-changes catalog: what can be proposed, without any project."""

import json

import pytest

from src.spec_contribute import _section, example_entries, proposal_for_new_kind, proposal_for_new_metric, proposal_for_values, spec_catalog
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
    assert {"biosample", "survey", "physio", "environment"} <= set(mods)
    assert mods["biosample"]["label"].startswith("Lab results")
    assert "biosample-inflammation" in mods["biosample"]["templates"]


def test_the_catalog_has_no_bids_kinds():
    assert not {"anat", "func", "dwi", "eeg", "fmap", "beh"} & {m["name"] for m in spec_catalog()["modalities"]}


def test_a_kind_with_nothing_to_propose_is_not_offered():
    names = {m["name"] for m in spec_catalog()["modalities"]}
    assert "events" not in names  # no list to extend and no measurements
    assert "environment" in names  # it has a list to extend
    assert all(m["lists"] or m["metrics"] for m in spec_catalog()["modalities"])


def test_example_entries_fill_the_example_from_the_library_template():
    ex = example_entries("biosample")
    by = {e["field"]: e for e in ex["entries"]}
    assert ex["template"] == "biosample-inflammation"
    assert by["Technical.SpecimenType"]["example"] == "serum" and "saliva" in by["Technical.SpecimenType"]["values"]
    assert by["Technical.Laboratory"]["values"] is None
    assert by["Technical.FastingRequired"]["example"] == "yes"
    assert by["Technical.StorageTemperature"]["example"] == "-80"
    assert not any(e["field"].startswith("Metadata") for e in ex["entries"])


def test_example_entries_carry_the_schema_descriptions_for_the_info_icons():
    ex = example_entries("biosample")
    by = {e["field"]: e for e in ex["entries"]}
    assert by["Technical.SpecimenType"]["description"]
    assert set(ex["sections"]) == {"Technical", "Study"}


def test_sections_have_plain_titles_and_say_what_they_hold():
    sections = example_entries("biosample")["sections"]
    assert sections["Technical"]["title"] == "How the data is collected"
    assert sections["Technical"]["summary"] == "Specimen type, Collection method, Anticoagulant, Fasting required, …"
    assert sections["Study"]["title"] == "About the measure"
    assert _section("SomeNewPart", ["A"], False)["title"] == "Some new part"  # a section without a plain title is spelled out


def test_only_sections_with_a_list_to_extend_are_proposable():
    assert {k: v["proposable"] for k, v in example_entries("biosample")["sections"].items()} == {"Technical": True, "Study": False}
    assert example_entries("survey")["sections"]["Study"]["proposable"] is True  # the license lists


def test_a_kind_without_a_library_example_still_lists_its_entries():
    ex = example_entries("physio")
    assert ex["template"] is None and ex["entries"] and all(e["example"] is None for e in ex["entries"])


def test_a_bids_kind_is_not_a_kind_of_this_page():
    with pytest.raises(OverlayError, match="not a kind of data"):
        example_entries("anat")


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


def test_context_lists_not_sure_and_the_entries_in_order():
    from src.spec_contribute import proposal_context
    text = proposal_context({"Technical.SpecimenType": "sweat", "Technical.Laboratory": "Unknown"}, not_sure=True, closest="biosample")
    assert text.splitlines() == ["Not sure which kind of data this belongs to (closest: biosample)",
                                 "Technical.SpecimenType: sweat", "Technical.Laboratory: Unknown"]
    assert proposal_context() is None


@pytest.mark.parametrize("entries", [{"a": 1}, {1: "a"}, {"a": "x" * 201}, {str(i): "v" for i in range(101)}])
def test_context_rejects_bad_entries(entries):
    from src.spec_contribute import proposal_context
    with pytest.raises(OverlayError):
        proposal_context(entries)


def test_the_issue_url_carries_the_context():
    url = proposal_for_values("survey", "Study.LicenseID", ["cc-by-nc-local"], entries={"Study.Category": "Unknown"})["issue_url"]
    assert "context=Study.Category%3A%20Unknown" in url


def test_a_context_too_long_for_the_url_gives_no_url_but_keeps_the_context():
    entries = {f"Field{i}": "x" * 200 for i in range(40)}  # 8,000 characters, over the 6,000 of a link
    result = proposal_for_values("survey", "Study.LicenseID", ["cc-by-nc-local"], entries=entries)
    assert result["issue_url"] is None and "Field39: " + "x" * 200 in result["context"]


def test_the_metric_proposal_carries_the_context_too():
    result = proposal_for_new_metric("DHEA", "d", "pg/mL", "saliva", entries={"Technical.Laboratory": "Unknown"})
    assert result["context"] == "Technical.Laboratory: Unknown" and "context=" in result["issue_url"]


def test_the_context_is_built_from_the_entries_only():
    import inspect

    for builder in (proposal_for_values, proposal_for_new_metric):
        assert "context" not in inspect.signature(builder).parameters, builder.__name__


@pytest.mark.parametrize("entries", [{"a": "x\nFake: y"}, {"a\nb": "x"}, {"a": "x\ty"}, {"a": "x\x00"}])
def test_context_rejects_control_characters(entries):
    from src.spec_contribute import proposal_context
    with pytest.raises(OverlayError):
        proposal_context(entries)


def test_a_new_kind_proposal_prefills_the_form_but_not_the_sample():
    result = proposal_for_new_kind("Skin temperature from a wrist sensor\nOne file per session.", "time\ttemp\n0\t33.1\n", "physio")
    assert result["problems"] == []
    url = result["issue_url"]
    assert "template=propose-new-kind-of-data.yml" in url and "closest_kind=physio" in url and "33.1" not in url
    assert "title=%5BNew%20kind%20of%20data%5D%3A%20Skin%20temperature" in url
    assert "Sample file:\ntime\ttemp" in result["text"] and "Closest kind of data: physio" in result["text"]


def test_an_empty_description_and_a_huge_sample_are_problems():
    result = proposal_for_new_kind("  ", "x" * 50_001)
    assert "the description is empty" in result["problems"] and any("larger than" in p for p in result["problems"])
    assert result["issue_url"] is None


@pytest.mark.parametrize("args", [("x", "a\tb\n", "../x"), (1, "a", None), ("x", None, None), ("x", "a", 5)])
def test_a_new_kind_proposal_refuses_a_bad_closest_or_non_text(args):
    with pytest.raises(OverlayError):
        proposal_for_new_kind(*args)


def test_a_too_long_link_says_why_without_a_problem():
    result = proposal_for_new_kind("long " * 2000, "a\tb\n")
    assert result["issue_url"] is None and result["problems"] == [] and "too long for a link" in result["note"]
    assert proposal_for_new_kind("short", "a\tb\n")["note"] is None


def test_the_title_stops_at_a_windows_line_end():
    url = proposal_for_new_kind("Skin temp\r\nsecond line", "a\tb\n")["issue_url"]
    assert "title=%5BNew%20kind%20of%20data%5D%3A%20Skin%20temp&" in url


@pytest.mark.parametrize("field, label", [
    ("Study.DOI", "DOI"), ("Study.LicenseID", "License ID"), ("Study.LicenseURL", "License URL"),
    ("StimulusPresentation.SoftwareRRID", "Software RRID"), ("Technical.SpecimenType", "Specimen type"),
    ("Technical.FileFormat", "File format"), ("I18n.TranslationMethod", "Translation method"),
    ("Privacy.IncludesExactGeo", "Includes exact geo"),
])
def test_labels_keep_acronyms_whole(field, label):
    from src.spec_contribute import _list_label

    assert _list_label(field) == label


def test_yes_no_entries_offer_yes_and_no():
    by = {e["field"]: e for e in example_entries("biosample")["entries"]}
    assert by["Technical.FastingRequired"]["values"] == ["yes", "no"]
    physio = {e["field"]: e for e in example_entries("physio")["entries"]}
    assert physio["Acquisition.EyesOpen"]["values"] == ["yes", "no"]


def test_an_empty_example_counts_as_no_example():
    from src.spec_contribute import _example_text

    assert _example_text("") is None and _example_text(False) == "no" and _example_text(0) == "0"


@pytest.mark.parametrize("name", ["anat", "MEG", "bold", "T1w", "events", "physio", "task", "ses", "acquisition", "participants", "survey", "biosample"])
def test_a_new_kind_name_taken_by_bids_or_prism_is_refused(name):
    with pytest.raises(OverlayError, match="already taken"):
        proposal_for_new_kind("Skin temperature", "a\tb\n", name=name)


@pytest.mark.parametrize("name", ["", "skin temp", "1skin", "x", "skin-temp", "a" * 40])
def test_a_new_kind_name_must_be_a_short_lowercase_label(name):
    with pytest.raises(OverlayError, match="name"):
        proposal_for_new_kind("Skin temperature", "a\tb\n", name=name)


def test_a_free_new_kind_name_goes_into_the_title_and_the_text():
    result = proposal_for_new_kind("Skin temperature from a wrist sensor", "a\tb\n", name="skintemp")
    assert "title=%5BNew%20kind%20of%20data%5D%20skintemp%3A%20Skin%20temperature" in result["issue_url"]
    assert "Suggested name: skintemp" in result["text"]


def test_a_new_kind_without_a_name_is_still_accepted():
    assert "Suggested name: not given" in proposal_for_new_kind("Skin temperature", "a\tb\n")["text"]


def test_catalog_environment_metrics():
    env = _entry("environment")
    temp = next(m for m in env["metrics"] if m["id"] == "prism:air-temperature")
    assert temp["units"] == "degC" and temp["specimens"] == []
    assert env["specimen_level"] is False and _entry("biosample")["specimen_level"] is True
    ex = example_entries("environment")
    assert not any(e["field"].startswith(("Privacy", "Provenance")) for e in ex["entries"])
    assert "Privacy" not in ex["sections"] and "Provenance" not in ex["sections"]


def test_new_environment_metric():
    r = proposal_for_new_metric("noise level", "Sound pressure level", "dB", modality="environment")
    assert r["problems"] == []
    [term] = r["proposal"]["terms"]
    assert term["TermID"] == "prism:noise-level" and term["Level"] == "variable" and term["Units"] == "dB"


def test_new_environment_metric_with_levels_and_cf_name():
    r = proposal_for_new_metric("sky state", "How the sky looks", modality="environment", levels={"c": "clear", "o": "overcast"}, cf_standard_name="cloud_area_fraction")
    assert r["problems"] == []
    [term] = r["proposal"]["terms"]
    assert term["Levels"] == {"c": "clear", "o": "overcast"} and "Units" not in term and term["CFStandardName"] == "cloud_area_fraction"


def test_environment_metric_refuses_specimen():
    with pytest.raises(OverlayError, match="sample type"):
        proposal_for_new_metric("noise level", "Sound pressure level", "dB", "saliva", modality="environment")


def test_units_or_levels_required():
    with pytest.raises(OverlayError, match="exactly one"):
        proposal_for_new_metric("noise level", "x", modality="environment")
    with pytest.raises(OverlayError, match="exactly one"):
        proposal_for_new_metric("noise level", "x", "dB", modality="environment", levels={"a": "b"})


def test_biosample_metric_without_specimen_is_refused_clearly():
    with pytest.raises(OverlayError, match="specimen|sample type"):
        proposal_for_new_metric("DHEA", "x", "pg/mL")


def test_two_level_kind_refuses_levels_and_cf_standard_name():
    with pytest.raises(OverlayError, match="levels"):
        proposal_for_new_metric("DHEA", "x", "pg/mL", "saliva", levels={"a": "b"})
    with pytest.raises(OverlayError, match="CF standard name"):
        proposal_for_new_metric("DHEA", "x", "pg/mL", "saliva", cf_standard_name="air_temperature")


def test_catalog_levels_variable_metric_lists_levels():
    metrics = _entry("environment")["metrics"]
    assert all("levels" in m for m in metrics)
