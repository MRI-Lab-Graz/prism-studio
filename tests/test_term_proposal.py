"""src/term_proposal.py: a sidecar column becomes a proposal for the term registry (`terms propose`)."""

import json
import os
import sys
from urllib.parse import parse_qs, urlparse

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(__file__)), "app", "src"))

from src.term_proposal import (  # noqa: E402
    ProposalError, as_v2, build_proposal, check_with_specification, issue_url, load_inherited_sidecar, slugify,
)
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
    assert json.loads(query["proposal"][0]) == as_v2(proposal)  # what is sent is format v2
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


# --- polish batch ---------------------------------------------------------------

def test_slugify_refuses_to_drop_letters_silently():
    for text in ("IL-1β", "β-endorphin", "µg/dL", "über"):
        with pytest.raises(ProposalError, match="--label"):
            slugify(text)
    assert slugify("IL-1b") == "il-1b"


def test_specimen_mismatch_error_suggests_the_parent_term():
    sidecar = _sidecar("x", {"Term": "prism:cortisol.saliva", "Description": "d", "Units": "u"}, "hair")
    with pytest.raises(ProposalError) as info:
        build_proposal(REGISTRY, sidecar, "x")
    assert "point Term at prism:cortisol" in str(info.value)


# --- inheritance: the sidecar of a data file, resolved like the validator does -----------------

def _dataset(tmp_path, root_sidecar=True, subject_sidecar=True):
    ds = tmp_path / "ds"
    folder = ds / "sub-01" / "ses-1" / "biosample"
    folder.mkdir(parents=True)
    (ds / "dataset_description.json").write_text("{}", encoding="utf-8")
    if root_sidecar:
        (ds / "biosample-iron_biosample.json").write_text(json.dumps(
            {"Technical": {"SpecimenType": "serum"}, "ferr": {"Description": "d", "Units": "ug/L"}}), encoding="utf-8")
    tsv = folder / "sub-01_ses-1_biosample-iron_biosample.tsv"
    tsv.write_text("ferr\n1\n", encoding="utf-8")
    if subject_sidecar:
        tsv.with_suffix(".json").write_text(json.dumps({"Study": {"BiosampleName": "iron"}}), encoding="utf-8")
    return tsv


def test_load_inherited_sidecar_merges_root_and_subject_sidecars(tmp_path):
    sidecar, path = load_inherited_sidecar(_dataset(tmp_path))
    assert sidecar["ferr"]["Units"] == "ug/L" and sidecar["Study"]["BiosampleName"] == "iron"
    assert path.endswith("_biosample.json")


def test_load_inherited_sidecar_uses_the_root_sidecar_alone(tmp_path):
    sidecar, _ = load_inherited_sidecar(_dataset(tmp_path, subject_sidecar=False))
    assert sidecar["Technical"]["SpecimenType"] == "serum"


def test_load_inherited_sidecar_without_any_sidecar_is_an_error(tmp_path):
    with pytest.raises(ProposalError, match="no sidecar"):
        load_inherited_sidecar(_dataset(tmp_path, root_sidecar=False, subject_sidecar=False))


# --- deliver_proposal: what `terms propose` and `spec propose` do with a finished proposal -----------------

def _proposal_for_delivery():
    return {"modality": "biosample", "terms": [{"TermID": "prism:x", "Level": "analyte", "Label": "x"}]}


def test_deliver_without_out_or_open_only_describes(monkeypatch):
    import webbrowser
    from src.term_proposal import deliver_proposal

    monkeypatch.setattr(webbrowser, "open", lambda url: (_ for _ in ()).throw(AssertionError("opened")))
    result = deliver_proposal(_proposal_for_delivery(), similar=["prism:cortisol"], alias="dhea_s")
    assert result["saved"] is None and result["opened"] is False and result["issue_url"].startswith("https://github.com/")
    text = result["text"]
    assert "nothing has been sent" in text.lower() and "run this again with --open" in text
    assert "Similar official terms: prism:cortisol" in text and '"dhea_s" is kept as an alias' in text


def test_deliver_writes_the_bare_proposal_and_opens_once(tmp_path, monkeypatch):
    import webbrowser
    from src.term_proposal import deliver_proposal

    opened = []
    monkeypatch.setattr(webbrowser, "open", lambda url: opened.append(url) or True)
    out = tmp_path / "p.json"
    result = deliver_proposal(_proposal_for_delivery(), out=out, open_browser=True)
    assert json.loads(out.read_text(encoding="utf-8")) == as_v2(_proposal_for_delivery()) and result["saved"] == out
    assert result["document"] == as_v2(_proposal_for_delivery())
    assert opened == [result["issue_url"]] and result["opened"] is True
    assert "Opened the prefilled form" in result["text"] and "Saved to" in result["text"]
    assert "Similar official terms" not in result["text"]  # not asked for


def test_deliver_says_so_when_the_browser_could_not_open(monkeypatch):
    import webbrowser
    from src.term_proposal import deliver_proposal

    monkeypatch.setattr(webbrowser, "open", lambda url: False)
    result = deliver_proposal(_proposal_for_delivery(), open_browser=True)
    assert result["opened"] is False and "Could not open a browser" in result["text"]


def test_deliver_a_proposal_too_long_for_a_link_asks_to_paste(monkeypatch):
    import webbrowser
    from src.term_proposal import deliver_proposal

    monkeypatch.setattr(webbrowser, "open", lambda url: (_ for _ in ()).throw(AssertionError("opened")))
    long = {"modality": "biosample", "terms": [{"TermID": "prism:x", "Label": "x", "Description": "y" * 7000}]}
    result = deliver_proposal(long, open_browser=True)
    assert result["issue_url"] is None and "too long for a link" in result["text"]


# --- format v2 on the way out (proposal format v2, Task B1) --------------------------------------------

def test_as_v2_converts_v1_and_keeps_v2():
    v1 = {"modality": "biosample", "terms": [{"TermID": "prism:x", "Level": "analyte"}, {"TermID": "prism:x.serum", "Level": "analyte-specimen"}]}
    doc = as_v2(v1)
    assert doc == {"format": "prism-proposal/2", "files": {
        "terms/biosample/x.json": v1["terms"][0], "terms/biosample/x.serum.json": v1["terms"][1]}}
    assert as_v2(doc) is doc


def test_a_proposal_of_many_terms_passes_the_vendored_checks_as_v2():
    registry = load_registry()
    terms = [{"TermID": "prism:ferritin", "Level": "analyte", "Label": "ferritin", "Aliases": [], "Description": "d"}] + [
        {"TermID": f"prism:ferritin.{s}", "Level": "analyte-specimen", "Parent": "prism:ferritin", "SpecimenType": s, "Units": "ug/L"}
        for s in ("serum", "plasma", "saliva")]
    assert check_with_specification({"modality": "biosample", "terms": terms}, registry) == []  # 4 terms: above the v1 cap


def test_the_issue_title_names_the_first_term_in_v2_too():
    doc = as_v2({"modality": "biosample", "terms": [{"TermID": "prism:x", "Level": "analyte", "Label": "Ferritin"}]})
    assert "Ferritin" in parse_qs(urlparse(issue_url(doc)).query)["title"][0]
