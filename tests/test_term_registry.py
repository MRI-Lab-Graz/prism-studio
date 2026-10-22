"""Term registry: loader, registry check, column resolution (docs/superpowers/specs/2026-10-22-biosample-term-registry-design.md)."""

import json
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(__file__)), "app", "src"))

from src.term_registry import check_registry, load_registry, resolve_column  # noqa: E402


def _write(root, modality, name, content):
    folder = root / modality
    folder.mkdir(parents=True, exist_ok=True)
    (folder / f"{name}.json").write_text(
        content if isinstance(content, str) else json.dumps(content), encoding="utf-8"
    )


def test_load_registry_reads_one_file_per_term(tmp_path):
    a = {"TermID": "prism:cortisol", "Level": "analyte"}
    b = {"TermID": "prism:cortisol.saliva", "Level": "analyte-specimen"}
    _write(tmp_path, "biosample", "cortisol", a)
    _write(tmp_path, "biosample", "cortisol.saliva", b)
    assert load_registry(root=tmp_path) == {"cortisol": a, "cortisol.saliva": b}


def test_load_registry_missing_folder_is_empty(tmp_path):
    assert load_registry(root=tmp_path / "nope") == {}


def test_load_registry_skips_broken_json(tmp_path):
    _write(tmp_path, "biosample", "bad", "{")
    _write(tmp_path, "biosample", "good", {"TermID": "prism:good"})
    assert list(load_registry(root=tmp_path)) == ["good"]


# --- check_registry --------------------------------------------------------

SEED_IDS = {
    "cortisol", "cortisol.saliva", "cortisol.serum",
    "alpha-amylase", "alpha-amylase.saliva",
    "crp", "crp.serum", "il6", "il6.serum", "tnfa", "tnfa.serum",
}


def _parent(local="cortisol", **over):
    t = {"TermID": f"prism:{local}", "Level": "analyte", "Label": local, "Aliases": [],
         "Description": "d", "Status": "official"}
    t.update(over)
    return t


def _child(parent="cortisol", specimen="saliva", **over):
    t = {"TermID": f"prism:{parent}.{specimen}", "Level": "analyte-specimen",
         "Parent": f"prism:{parent}", "SpecimenType": specimen, "Units": "nmol/L",
         "MinValue": 0, "Status": "official"}
    t.update(over)
    return t


def _ok():
    return {"cortisol": _parent(), "cortisol.saliva": _child()}


def _text(problems):
    return " | ".join(problems)


def test_shipped_registry_is_valid():
    registry = load_registry()
    assert SEED_IDS <= set(registry)
    assert check_registry(registry) == []


def test_check_registry_accepts_a_clean_registry():
    assert check_registry(_ok()) == []


def test_check_registry_flags_orphan_child():
    reg = {"cortisol.saliva": _child()}
    assert "parent" in _text(check_registry(reg)).lower()


def test_check_registry_flags_alias_collision():
    reg = {"cortisol": _parent(Aliases=["Cort"]), "hormone": _parent("hormone", Aliases=["cort"])}
    assert "cort" in _text(check_registry(reg)).lower()


def test_check_registry_flags_alias_equal_to_other_term_id():
    reg = {"cortisol": _parent(Aliases=["crp"]), "crp": _parent("crp")}
    assert "crp" in _text(check_registry(reg))


def test_check_registry_flags_bad_specimen():
    reg = {"cortisol": _parent(), "cortisol.nails": _child(specimen="nails")}
    assert "nails" in _text(check_registry(reg))


def test_check_registry_flags_deprecated_without_replacedby():
    reg = _ok()
    reg["cortisol"]["Status"] = "deprecated"
    assert "ReplacedBy" in _text(check_registry(reg))


def test_check_registry_flags_dangling_replacedby():
    reg = _ok()
    reg["cortisol"].update(Status="deprecated", ReplacedBy="prism:gone")
    assert "prism:gone" in _text(check_registry(reg))


def test_check_registry_flags_id_not_matching_filename():
    reg = {"cort": _parent("cortisol")}
    assert "cort" in _text(check_registry(reg))


def test_check_registry_flags_bad_id_format():
    assert check_registry({"Cortisol": _parent("Cortisol")})  # uppercase local part
    assert check_registry({"cortisol": _parent(TermID="foo:cortisol")})  # unknown prefix
    reg = _ok()
    reg["cortisol.saliva"]["TermID"] = "prism:cortisol.serum"  # child id != parent.specimen
    assert check_registry(reg)


def test_check_registry_flags_equivalent_collision():
    reg = _ok()
    reg["cortisol"]["Equivalents"] = ["loinc:2143-6"]
    reg["cortisol.saliva"]["Equivalents"] = ["loinc:2143-6"]
    assert "loinc:2143-6" in _text(check_registry(reg))


def test_check_registry_flags_child_without_units():
    reg = _ok()
    del reg["cortisol.saliva"]["Units"]
    assert "Units" in _text(check_registry(reg))


# --- resolve_column ---------------------------------------------------------

def _reg(**parent_over):
    reg = _ok()
    reg["cortisol"].update(Aliases=["cort", "corts"], Equivalents=["loinc:2143-6"], **parent_over)
    reg["cortisol.serum"] = _child(specimen="serum")
    return reg


def test_term_parent_resolves_to_specimen_child():
    r = resolve_column(_reg(), "cort", {"Term": "cortisol"}, "saliva")
    assert r.kind == "term" and r.term["TermID"] == "prism:cortisol.saliva"


def test_term_child_specimen_mismatch():
    r = resolve_column(_reg(), "cort", {"Term": "prism:cortisol.serum"}, "saliva")
    assert r.kind == "specimen_mismatch"


def test_term_matches_exact_id_slug_and_equivalent():
    for ref in ("prism:cortisol", "cortisol", "loinc:2143-6"):
        r = resolve_column(_reg(), "x", {"Term": ref}, "saliva")
        assert r.term["TermID"] == "prism:cortisol.saliva", ref


def test_parent_without_matching_child_is_known_analyte_new_specimen():
    r = resolve_column(_reg(), "cort", {"Term": "cortisol"}, "hair")
    assert r.kind == "known_analyte_new_specimen" and r.term["TermID"] == "prism:cortisol"


def test_parent_with_no_specimen_does_not_crash():
    assert resolve_column(_reg(), "cort", {"Term": "cortisol"}, None).kind == "known_analyte_new_specimen"


def test_alias_suggests_not_applies():
    r = resolve_column(_reg(), "cort", {"Description": "d", "Units": "nmol/L"}, "saliva")
    assert r.kind == "suggestion" and r.similar == ("prism:cortisol",)


def test_alias_match_is_case_insensitive():
    for name in ("CORT", "Cort", "corts"):
        assert resolve_column(_reg(), name, {}, "saliva").kind == "suggestion"


def test_unknown_lists_similar():
    r = resolve_column(_reg(), "salivary_cortisol", {}, "saliva")
    assert r.kind == "unknown" and "prism:cortisol" in r.similar


def test_unknown_with_nothing_similar_has_empty_similar():
    r = resolve_column(_reg(), "zzz_marker", {}, "saliva")
    assert r.kind == "unknown" and r.similar == ()


def test_unresolvable_term_is_unknown():
    assert resolve_column(_reg(), "x", {"Term": "nonsense"}, "saliva").kind == "unknown"


def test_empty_registry_gives_unknown():
    assert resolve_column({}, "cort", {"Term": "cortisol"}, "saliva").kind == "unknown"


def test_deprecated_term_points_to_replacement():
    reg = _reg()
    reg["cortisol"].update(Status="deprecated", ReplacedBy="prism:hydrocortisone")
    r = resolve_column(reg, "cort", {"Term": "cortisol"}, "saliva")
    assert r.kind == "deprecated" and "prism:hydrocortisone" in r.message


# --- review fix pass -------------------------------------------------------

def test_deprecated_parent_still_resolves_to_the_child():
    reg = _reg()
    reg["cortisol"].update(Status="deprecated", ReplacedBy="prism:hydrocortisone")
    r = resolve_column(reg, "cort", {"Term": "cortisol"}, "saliva")
    assert r.kind == "deprecated" and r.term["TermID"] == "prism:cortisol.saliva"
    assert "prism:hydrocortisone" in r.message


def test_deprecated_child_still_supplies_its_definition():
    reg = _reg()
    reg["cortisol.saliva"].update(Status="deprecated", ReplacedBy="prism:cortisol.serum")
    r = resolve_column(reg, "cort", {"Term": "prism:cortisol.saliva"}, "saliva")
    assert r.kind == "deprecated" and r.term["Units"] == "nmol/L"
    assert "prism:cortisol.serum" in r.message


def test_non_string_term_is_ignored_not_a_crash():
    for ref in (5, ["prism:cortisol"], {"a": 1}):
        assert resolve_column(_reg(), "x", {"Term": ref}, "saliva").kind == "unknown"


def test_check_registry_flags_label_collisions():
    a = _parent("il6", Label="Interleukin-6")
    assert check_registry({"il6": a, "il-6": _parent("il-6", Label="interleukin-6")})
    assert check_registry({"il6": a, "other": _parent("other", Aliases=["Interleukin-6"])})
