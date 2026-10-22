"""src/term_proposal.py: a sidecar column becomes a proposal for the term registry (`terms propose`)."""

import json
import os
import sys
from urllib.parse import parse_qs, urlparse

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(__file__)), "app", "src"))

from src.term_proposal import ProposalError, build_proposal, check_with_specification, issue_url, slugify  # noqa: E402
from src.term_registry import load_registry  # noqa: E402


def _term(local, **over):
    t = {"TermID": f"prism:{local}", "Status": "official"}
    t.update(over)
    return t


REGISTRY = {
    "cortisol": _term("cortisol", Level="analyte", Label="cortisol", Aliases=["cort"]),
    "cortisol.saliva": _term("cortisol.saliva", Level="analyte-specimen", Parent="prism:cortisol",
                             SpecimenType="saliva", Units="nmol/L"),
}


def _sidecar(column, definition, specimen="saliva"):
    technical = {"SpecimenType": specimen} if specimen else {}
    return {"Technical": technical, "Study": {"BiosampleName": "x"}, column: definition}


def test_unknown_metric_becomes_parent_and_child():
    sidecar = _sidecar("ferr_ugl", {"Description": "Ferritin", "Units": "ug/L", "MinValue": 0, "LOINC": "2276-4"}, "serum")
    p = build_proposal(REGISTRY, sidecar, "ferr_ugl")
    parent, child = p["terms"]
    assert p["modality"] == "biosample"
    assert parent == {"TermID": "prism:ferr-ugl", "Level": "analyte", "Label": "ferr_ugl",
                      "Aliases": ["ferr_ugl"], "Description": "Ferritin"}
    assert child == {"TermID": "prism:ferr-ugl.serum", "Level": "analyte-specimen", "Parent": "prism:ferr-ugl",
                     "SpecimenType": "serum", "Units": "ug/L", "MinValue": 0, "LOINC": "2276-4"}


def test_known_analyte_new_specimen_becomes_child_only():
    sidecar = _sidecar("cortisol_hair", {"Description": "d", "Units": "pg/mg", "Term": "cortisol"}, "hair")
    p = build_proposal(REGISTRY, sidecar, "cortisol_hair")
    assert [t["TermID"] for t in p["terms"]] == ["prism:cortisol.hair"]
    assert p["terms"][0]["Parent"] == "prism:cortisol" and p["terms"][0]["Units"] == "pg/mg"


def test_official_term_is_refused_with_the_term_to_use():
    with pytest.raises(ProposalError, match=r"prism:cortisol\b"):  # alias: only suggests
        build_proposal(REGISTRY, _sidecar("cort", {"Description": "d", "Units": "nmol/L"}), "cort")
    with pytest.raises(ProposalError, match=r"prism:cortisol\.saliva"):  # explicit Term, resolved
        build_proposal(REGISTRY, _sidecar("x", {"Term": "cortisol"}), "x")


def test_label_option_changes_the_slug_not_the_alias():
    sidecar = _sidecar("ferr_ugl", {"Description": "d", "Units": "ug/L"}, "serum")
    parent = build_proposal(REGISTRY, sidecar, "ferr_ugl", label="Ferritin (serum)")["terms"][0]
    assert parent["TermID"] == "prism:ferritin-serum" and parent["Label"] == "Ferritin (serum)"
    assert parent["Aliases"] == ["ferr_ugl"]


def test_missing_specimen_units_or_column_is_an_error():
    with pytest.raises(ProposalError, match="not found"):
        build_proposal(REGISTRY, _sidecar("a", {"Units": "u"}), "b")
    with pytest.raises(ProposalError, match="not found"):
        build_proposal(REGISTRY, {"Technical": {"SpecimenType": "saliva"}, "a": "text"}, "a")
    with pytest.raises(ProposalError, match="SpecimenType"):
        build_proposal(REGISTRY, _sidecar("a", {"Description": "d", "Units": "u"}, specimen=None), "a")
    with pytest.raises(ProposalError, match="Units"):
        build_proposal(REGISTRY, _sidecar("a", {"Description": "d"}), "a")


def test_slugify():
    assert slugify("Ferritin (serum)") == "ferritin-serum"
    assert slugify("  IL-6 ") == "il-6"
    assert slugify("a__b") == "a-b"
    assert slugify("µg/dL") == "g-dl"  # characters outside a-z0-9 are dropped; the maintainer picks the final ID
    for bad in ("123", "___", "", "µ"):
        with pytest.raises(ProposalError):
            slugify(bad)


def test_issue_url_encodes_unicode_and_json_and_round_trips():
    proposal = {"modality": "biosample", "terms": [{"TermID": "prism:x", "Units": "µg/dL", "Description": "a & b # c"}]}
    url = issue_url(proposal)
    parts = urlparse(url)
    assert parts.netloc == "github.com" and parts.path == "/MRI-Lab-Graz/prism-specification/issues/new"
    query = parse_qs(parts.query)
    assert query["template"] == ["propose-metric.yml"] and query["title"][0].startswith("[Metric]: ")
    assert json.loads(query["proposal"][0]) == proposal
    assert " " not in url and "µ" not in url


def test_issue_url_over_the_limit_is_none():
    assert issue_url({"modality": "biosample", "terms": [{"TermID": "prism:x"}]}, limit=50) is None


def test_check_with_specification_accepts_a_built_proposal_and_rejects_forbidden_fields():
    registry = load_registry()
    sidecar = _sidecar("ferr_ugl", {"Description": "d", "Units": "ug/L"}, "serum")
    proposal = build_proposal(registry, sidecar, "ferr_ugl")
    assert check_with_specification(proposal, registry) == []
    proposal["terms"][0]["Status"] = "official"
    assert any("Status" in p for p in check_with_specification(proposal, registry))


def test_check_with_specification_names_an_already_official_id():
    registry = load_registry()
    proposal = build_proposal(registry, _sidecar("weird", {"Description": "d", "Units": "u"}), "weird", label="cortisol")
    assert any("prism:cortisol" in p and "official" in p for p in check_with_specification(proposal, registry))


# --- review fixes: a dangling Term decides the ID; errors point at the root-level sidecar -------

def test_dangling_term_decides_the_id():
    sidecar = _sidecar("zon_s", {"Term": "prism:zonulin", "Description": "d", "Units": "ng/mL"}, "serum")
    parent, child = build_proposal(REGISTRY, sidecar, "zon_s")["terms"]
    assert parent["TermID"] == "prism:zonulin" and parent["Aliases"] == ["zon_s"]
    assert child["TermID"] == "prism:zonulin.serum" and child["Parent"] == "prism:zonulin"


def test_dangling_child_style_and_bare_terms_propose_their_parent():
    for ref in ("prism:zonulin.serum", "zonulin"):
        sidecar = _sidecar("zon_s", {"Term": ref, "Description": "d", "Units": "ng/mL"}, "serum")
        assert build_proposal(REGISTRY, sidecar, "zon_s")["terms"][0]["TermID"] == "prism:zonulin", ref


def test_label_wins_over_a_dangling_term():
    sidecar = _sidecar("zon_s", {"Term": "prism:zonulin", "Description": "d", "Units": "ng/mL"}, "serum")
    assert build_proposal(REGISTRY, sidecar, "zon_s", label="Zonulin Z")["terms"][0]["TermID"] == "prism:zonulin-z"


def test_errors_for_a_sidecar_without_the_column_or_technical_point_at_the_root_level_sidecar():
    with pytest.raises(ProposalError, match="root-level"):
        build_proposal(REGISTRY, _sidecar("a", {"Units": "u"}), "b")
    with pytest.raises(ProposalError, match="root-level"):
        build_proposal(REGISTRY, _sidecar("a", {"Description": "d", "Units": "u"}, specimen=None), "a")
