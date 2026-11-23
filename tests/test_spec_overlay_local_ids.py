"""A project's own terms are local:<slug> on disk and in the registry; a proposal for the maintainers is prism:<slug>."""

import json
import os
import sys
from pathlib import Path

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(__file__)), "app", "src"))

from src.spec_overlay import (  # noqa: E402
    OverlayError, add_local_term, load_local_terms, merge_terms, merged_registry, proposal_for_local_terms, remove_local_terms,
)
from src.term_registry import load_registry  # noqa: E402
from tests.test_spec_overlay_ops import DHEA, _dataset  # noqa: E402


def _added(tmp_path):
    tsv = _dataset(tmp_path / "p", DHEA)
    add_local_term(tmp_path / "p", column="dhea_s", data_file=str(tsv), label="DHEA-S")
    return tmp_path / "p"


def _file(project, name):
    return json.loads((project / "code" / "specification" / "terms" / "biosample" / name).read_text(encoding="utf-8"))


def test_local_terms_are_stored_as_local_ids(tmp_path):
    project = _added(tmp_path)
    parent, child = _file(project, "dhea-s.json"), _file(project, "dhea-s.saliva.json")
    assert parent["TermID"] == "local:dhea-s"
    assert child["TermID"] == "local:dhea-s.saliva" and child["Parent"] == "local:dhea-s"


def test_a_child_of_an_official_parent_keeps_the_official_parent(tmp_path):
    project = _added(tmp_path)
    path = project / "code" / "specification" / "terms" / "biosample" / "cortisol.plasma.json"
    path.write_text(json.dumps({**_file(project, "dhea-s.saliva.json"), "TermID": "prism:cortisol.plasma",
                                "Parent": "prism:cortisol", "SpecimenType": "plasma"}), encoding="utf-8")
    assert load_local_terms(project)[0]["cortisol.plasma"]["Parent"] == "prism:cortisol"


def test_old_prism_files_still_load_as_local(tmp_path):
    project = _added(tmp_path)
    folder = project / "code" / "specification" / "terms" / "biosample"
    for name in ("dhea-s.json", "dhea-s.saliva.json"):
        data = _file(project, name)
        data["TermID"] = data["TermID"].replace("local:", "prism:")
        data["Parent"] = data["Parent"].replace("local:", "prism:") if "Parent" in data else None
        (folder / name).write_text(json.dumps({k: v for k, v in data.items() if v is not None}), encoding="utf-8")
    terms, problems = load_local_terms(project)
    assert problems == [] and terms["dhea-s.saliva"]["TermID"] == "local:dhea-s.saliva"
    assert terms["dhea-s.saliva"]["Parent"] == "local:dhea-s"


def test_the_registry_resolves_local_ids(tmp_path):
    registry = merged_registry(_added(tmp_path))
    assert registry["dhea-s"]["TermID"] == "local:dhea-s"


def test_sharing_gives_prism_ids(tmp_path):
    shared = proposal_for_local_terms(_added(tmp_path))["proposal"]["terms"]
    assert [t["TermID"] for t in shared] == ["prism:dhea-s", "prism:dhea-s.saliva"]
    assert shared[1]["Parent"] == "prism:dhea-s"


def test_remove_takes_local_or_prism_names_and_the_children(tmp_path):
    project = _added(tmp_path)
    assert len(remove_local_terms(project, "biosample", "local:dhea-s")) == 2


def test_a_local_term_the_official_registry_has_is_reported_with_its_local_id():
    official = load_registry("biosample")
    local = {"cortisol": {"TermID": "local:cortisol", "Level": "analyte", "Label": "x"}}
    merged, in_use, ignored = merge_terms(official, local)
    assert ignored == ("local:cortisol",) and in_use == frozenset() and merged["cortisol"]["TermID"] == "prism:cortisol"


def test_a_new_specimen_of_an_existing_local_analyte_is_added(tmp_path):
    project = _added(tmp_path)
    sidecar = tmp_path / "p" / "biosample-saliva_biosample.json"
    data = json.loads(sidecar.read_text(encoding="utf-8"))
    data["Technical"]["SpecimenType"] = "plasma"
    data["dhea_p"] = {"Description": "Plasma DHEA-S", "Units": "pg/mL", "Term": "local:dhea-s"}
    sidecar.write_text(json.dumps(data), encoding="utf-8")
    add_local_term(project, column="dhea_p", sidecar_file=str(sidecar), label="DHEA-S")
    assert _file(project, "dhea-s.plasma.json")["Parent"] == "local:dhea-s"


LINK = {"loinc": "https://loinc.org/2191-5"}


def _sidecar(tmp_path):
    path = tmp_path / "sidecar.json"
    path.write_text(json.dumps({"Technical": {"SpecimenType": "saliva"},
                                "dhea_s": {"Description": "DHEA-S", "Units": "ug/dL"}}), encoding="utf-8")
    return path


def test_a_local_term_can_carry_links_to_any_vocabulary(tmp_path):
    project = tmp_path / "p"
    add_local_term(project, column="dhea_s", sidecar_file=str(_sidecar(tmp_path)), label="DHEA-S", links=LINK)
    mapping = project / "code" / "specification" / "mappings" / "biosample" / "dhea-s.json"
    assert json.loads(mapping.read_text(encoding="utf-8")) == {"local:dhea-s.saliva": {"SameAs": LINK}}
    assert "LOINC" not in _file(project, "dhea-s.saliva.json")


def test_sharing_a_local_term_shares_its_links(tmp_path):
    project = tmp_path / "p"
    add_local_term(project, column="dhea_s", sidecar_file=str(_sidecar(tmp_path)), label="DHEA-S", links=LINK)
    result = proposal_for_local_terms(project, None)
    assert result["problems"] == []
    assert result["document"]["files"]["mappings/biosample/dhea-s.json"] == {"prism:dhea-s.saliva": {"SameAs": LINK}}


def test_removing_a_local_term_removes_its_links(tmp_path):
    project = tmp_path / "p"
    add_local_term(project, column="dhea_s", sidecar_file=str(_sidecar(tmp_path)), label="DHEA-S", links=LINK)
    remove_local_terms(project, "biosample", "local:dhea-s")
    assert not (project / "code" / "specification" / "mappings" / "biosample" / "dhea-s.json").exists()


def test_the_sidecar_loinc_field_is_not_read(tmp_path):
    sidecar = tmp_path / "s.json"
    sidecar.write_text(json.dumps({"Technical": {"SpecimenType": "saliva"},
                                   "dhea_s": {"Description": "d", "Units": "ug/dL", "LOINC": "2191-5"}}), encoding="utf-8")
    add_local_term(tmp_path / "p", column="dhea_s", sidecar_file=str(sidecar), label="DHEA-S")
    assert "LOINC" not in _file(tmp_path / "p", "dhea-s.saliva.json")
    assert not (tmp_path / "p" / "code" / "specification" / "mappings").exists()


def test_a_failing_link_write_leaves_no_half_added_term(tmp_path):
    project = tmp_path / "p"
    broken = project / "code" / "specification" / "mappings" / "biosample"
    broken.mkdir(parents=True)
    (broken / "dhea-s.json").write_text("[]", encoding="utf-8")  # not an object: the links cannot be added
    with pytest.raises(OverlayError):
        add_local_term(project, column="dhea_s", sidecar_file=str(_sidecar(tmp_path)), label="DHEA-S", links=LINK)
    assert not (project / "code" / "specification" / "terms" / "biosample").exists() or not list((project / "code" / "specification" / "terms" / "biosample").glob("*.json"))


def test_adding_a_link_keeps_the_other_vocabularies_of_the_entry(tmp_path):
    project = tmp_path / "p"
    mapping = project / "code" / "specification" / "mappings" / "biosample" / "dhea-s.json"
    mapping.parent.mkdir(parents=True)
    mapping.write_text(json.dumps({"local:dhea-s.saliva": {"SameAs": {"snomed": "https://snomed.info/id/396820008"}}}), encoding="utf-8")
    add_local_term(project, column="dhea_s", sidecar_file=str(_sidecar(tmp_path)), label="DHEA-S", links=LINK)
    assert json.loads(mapping.read_text(encoding="utf-8"))["local:dhea-s.saliva"]["SameAs"] == {
        "snomed": "https://snomed.info/id/396820008", **LINK}


def test_removing_a_term_never_touches_a_mappings_folder_that_is_a_symlink(tmp_path):
    project = tmp_path / "p"
    add_local_term(project, column="dhea_s", sidecar_file=str(_sidecar(tmp_path)), label="DHEA-S")
    outside = tmp_path / "outside"
    outside.mkdir()
    victim = outside / "dhea-s.json"
    victim.write_text(json.dumps({"local:dhea-s": {"SameAs": LINK}}), encoding="utf-8")
    (project / "code" / "specification" / "mappings").symlink_to(outside)
    with pytest.raises(OverlayError):
        remove_local_terms(project, "biosample", "local:dhea-s")
    assert victim.exists()
