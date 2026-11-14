"""Term registry: loader, registry check, column resolution (docs/superpowers/specs/2026-10-22-biosample-term-registry-design.md (removed after v1.24.0; in git history))."""

import json
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(__file__)), "app", "src"))

from src.term_registry import load_registry, resolve_column  # noqa: E402


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


# --- polish batch ---------------------------------------------------------------

def test_short_probes_do_not_list_similar_terms():
    for probe in ("a", "co"):
        assert resolve_column(_reg(), probe, {}, "saliva").similar == (), probe


def test_a_name_match_on_a_deprecated_term_only_suggests():
    reg = _reg()
    reg["cortisol"].update(Status="deprecated", ReplacedBy="prism:hydrocortisone")
    r = resolve_column(reg, "cort", {}, "saliva")
    assert r.kind == "suggestion" and "prism:hydrocortisone" in r.message and r.similar == ("prism:hydrocortisone",)


# --- term_columns: which sidecar columns the term checks look at -----------

def test_term_columns_skips_blocks_sample_columns_and_non_numeric_columns():
    from src.term_registry import term_columns

    sidecar = {
        "Technical": {"SpecimenType": "saliva"}, "Study": {}, "Metadata": {},
        "sample_id": {"Units": "n/a"}, "collection_time": {"Units": "n/a"}, "fasting": {"Units": "n/a"},
        "visit": {"Description": "d", "Units": "n/a"},  # any column with Units n/a
        "text": "not a column definition",
        "cort": {"Description": "d", "Units": "nmol/L"}, "dhea_s": {"Term": "prism:dhea-s"},
    }
    assert [name for name, _ in term_columns(sidecar, "biosample")] == ["cort", "dhea_s"]


def test_term_columns_biosample_unchanged():
    from src.term_registry import term_columns

    sidecar = {"Technical": {}, "sample_id": {"Units": "n/a"}, "cort": {"Units": "nmol/L"}, "dhea_s": {"Term": "prism:dhea-s"}}
    assert [n for n, _ in term_columns(sidecar, "biosample")] == ["cort", "dhea_s"]


def test_term_columns_environment_skips_ids():
    from src.term_registry import term_columns

    sidecar = {
        "Technical": {"X": 1}, "Study": {}, "Metadata": {},
        "subject_id": {"Description": "d"}, "session_id": {"Description": "d"},
        "temp_c": {"Units": "degC"},
    }
    assert [n for n, _ in term_columns(sidecar, "environment")] == ["temp_c"]


def test_context_value():
    from src.term_registry import context_value

    sidecar = {"Technical": {"SpecimenType": "saliva"}}
    assert context_value(sidecar, "biosample") == "saliva"
    assert context_value({"Technical": "bad"}, "biosample") is None
    assert context_value(sidecar, "environment") is None


_AIR = {"TermID": "prism:air-temperature", "Status": "official", "Level": "variable", "Label": "air temperature",
        "Aliases": ["temp_c"], "Units": "degC"}


def test_variable_term_resolves_without_specimen():
    r = resolve_column({"air-temperature": _AIR}, "temp_c", {"Term": "prism:air-temperature"}, None)
    assert r.kind == "term" and r.term["TermID"] == "prism:air-temperature"


def test_alias_suggests_variable():
    r = resolve_column({"air-temperature": _AIR}, "temp_c", {}, None)
    assert r.kind == "suggestion" and "prism:air-temperature" in r.message


def test_similar_returns_variable_terms():
    r = resolve_column({"air-temperature": _AIR}, "temp_c_mean", {}, None)
    assert r.kind == "unknown" and r.similar == ("prism:air-temperature",)


def test_term_columns_keeps_upper_case_analyte_columns():
    from src.term_registry import term_columns

    sidecar = {"Technical": {}, "Study": {}, "Metadata": {}, "CRP": {"Units": "mg/L"}, "IL6": {"Term": "prism:il-6"}}
    assert [n for n, _ in term_columns(sidecar, "biosample")] == ["CRP", "IL6"]


def test_find_term_prefers_the_slug_in_any_case_over_a_label():
    from src.term_registry import find_term
    reg = {
        "dass.dass21": {"TermID": "prism:dass.dass21", "Label": "DASS21"},
        "dass21": {"TermID": "prism:dass21", "Label": "DASS-21"},
    }
    assert find_term(reg, "DASS21")[1]["TermID"] == "prism:dass21"
    assert find_term(reg, "dass21")[1]["TermID"] == "prism:dass21"


# --- term_links: the links of a term come from mappings/, its parent's included ---

def _map(root, modality, family, content):
    folder = root / modality
    folder.mkdir(parents=True, exist_ok=True)
    (folder / f"{family}.json").write_text(content if isinstance(content, str) else json.dumps(content), encoding="utf-8")


def test_term_links_of_a_child_come_from_its_parent(tmp_path):
    from src.term_registry import load_mappings, term_links
    _map(tmp_path, "biosample", "a", {"prism:a": {"SameAs": {"snomed": "https://example.org/a"}}})
    reg = {"a": {"TermID": "prism:a"}, "a.serum": {"TermID": "prism:a.serum", "Parent": "prism:a"}}
    maps = load_mappings("biosample", root=tmp_path)
    expected = {"snomed": {"url": "https://example.org/a", "from": "prism:a"}}
    assert term_links(reg, reg["a.serum"], mappings=maps) == expected
    assert term_links(reg, reg["a"], mappings=maps) == expected


def test_term_links_own_entry_wins_and_others_are_added(tmp_path):
    from src.term_registry import load_mappings, term_links
    _map(tmp_path, "biosample", "a", {
        "prism:a": {"SameAs": {"snomed": "https://example.org/1", "chebi": "https://example.org/c"}},
        "prism:a.serum": {"SameAs": {"snomed": "https://example.org/2"}},
    })
    reg = {"a": {"TermID": "prism:a"}, "a.serum": {"TermID": "prism:a.serum", "Parent": "prism:a"}}
    links = term_links(reg, reg["a.serum"], mappings=load_mappings("biosample", root=tmp_path))
    assert links["snomed"] == {"url": "https://example.org/2", "from": "prism:a.serum"}
    assert links["chebi"] == {"url": "https://example.org/c", "from": "prism:a"}


def test_term_links_survive_missing_parent_and_bad_types(tmp_path):
    from src.term_registry import load_mappings, term_links
    assert term_links({}, {"TermID": "prism:x", "Parent": "prism:gone"}, mappings={}) == {}
    _map(tmp_path, "biosample", "x", {"prism:x": {"SameAs": ["not", "an", "object"]}})
    _map(tmp_path, "biosample", "y", {"prism:y": {"SameAs": {"snomed": 5}}})
    _map(tmp_path, "biosample", "z", "[1, 2]")
    _map(tmp_path, "biosample", "w", "{")
    _map(tmp_path, "biosample", "v", {"prism:v": "text"})
    maps = load_mappings("biosample", root=tmp_path)
    assert term_links({}, {"TermID": "prism:x"}, mappings=maps) == {}
    assert term_links({}, {"TermID": "prism:y"}, mappings=maps) == {}
    assert term_links({}, {"TermID": "prism:v"}, mappings=maps) == {}


def test_term_without_mappings_has_no_links():
    from src.term_registry import term_links
    assert term_links({}, {"TermID": "prism:none"}, mappings={}) == {}


def test_load_mappings_missing_folder_is_empty(tmp_path):
    from src.term_registry import load_mappings
    assert load_mappings("biosample", root=tmp_path / "nope") == {}


# The eight analytes that carried TermURL before the links moved to mappings/ (values from the old term files).
_OLD_LINKS = {
    "estradiol": "https://snomed.info/id/126172005",
    "progesterone": "https://snomed.info/id/16683002",
    "testosterone": "https://snomed.info/id/43688007",
    "free-testosterone": "https://snomed.info/id/259355006",
    "lh": "https://snomed.info/id/64182005",
    "fsh": "https://snomed.info/id/25217009",
    "prolactin": "https://snomed.info/id/70454002",
    "shbg": "https://snomed.info/id/55503002",
}


def test_term_links_of_the_eight_moved_analytes_are_unchanged():
    from src.term_registry import term_links
    reg = load_registry("biosample")
    for name, url in _OLD_LINKS.items():
        expected = {"snomed": {"url": url, "from": f"prism:{name}"}}
        assert term_links(reg, reg[name]) == expected, name
        children = [t for t in reg.values() if t.get("Parent") == f"prism:{name}"]
        for child in children:
            assert term_links(reg, child) == expected, child["TermID"]
