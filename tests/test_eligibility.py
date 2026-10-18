import json

from src.eligibility import check_eligibility


def _make(tmp_path, criteria, sidecar, rows, header=("participant_id", "age")):
    if criteria is not None:
        (tmp_path / "project.json").write_text(
            json.dumps({"Eligibility": {"Criteria": criteria}}), encoding="utf-8"
        )
    (tmp_path / "participants.json").write_text(json.dumps(sidecar), encoding="utf-8")
    lines = ["\t".join(header)] + ["\t".join(r) for r in rows]
    (tmp_path / "participants.tsv").write_text("\n".join(lines) + "\n", encoding="utf-8")
    return str(tmp_path)


AGE = {"id": "age", "label": "Age", "term": "nb:Age", "type": "numeric",
       "mode": "include", "min": 18, "max": 35, "unit": "years"}
LINK_AGE = {"age": {"EligibilityCriterion": "age"}}


def _codes(issues, code):
    return [i for i in issues if code in i[1]]


def test_include_range_flags_outside_values(tmp_path):
    root = _make(tmp_path, [AGE], LINK_AGE,
                 [("sub-P01", "17"), ("sub-P02", "18"), ("sub-P03", "35"), ("sub-P04", "36")])
    warnings = [i for i in check_eligibility(root) if "sub-P0" in i[1]]
    assert len(warnings) == 2
    assert all(i[0] == "WARNING" and "PRISM602" in i[1] for i in warnings)
    assert "sub-P01" in warnings[0][1] and "17" in warnings[0][1] and "18-35" in warnings[0][1]
    assert "sub-P04" in warnings[1][1]


def test_summary_line_counts_violations(tmp_path):
    root = _make(tmp_path, [AGE], LINK_AGE, [("sub-P01", "17"), ("sub-P02", "40")])
    assert "2 participant(s)" in check_eligibility(root)[0][1]


def test_exclude_range_flags_inside_values(tmp_path):
    crit = {"id": "iq", "label": "IQ", "term": None, "type": "numeric",
            "mode": "exclude", "max": 69}
    root = _make(tmp_path, [crit], {"iq": {"EligibilityCriterion": "iq"}},
                 [("sub-P01", "69"), ("sub-P02", "70")], header=("participant_id", "iq"))
    warnings = [i for i in check_eligibility(root) if "sub-P0" in i[1]]
    assert len(warnings) == 1 and "sub-P01" in warnings[0][1]


def test_open_ended_bounds(tmp_path):
    crit = {"id": "iq", "label": "IQ", "term": None, "type": "numeric",
            "mode": "include", "min": 85}
    root = _make(tmp_path, [crit], {"iq": {"EligibilityCriterion": "iq"}},
                 [("sub-P01", "84"), ("sub-P02", "200")], header=("participant_id", "iq"))
    warnings = [i for i in check_eligibility(root) if "sub-P0" in i[1]]
    assert len(warnings) == 1 and "sub-P01" in warnings[0][1]


def test_empty_na_and_non_numeric_skipped(tmp_path):
    root = _make(tmp_path, [AGE], LINK_AGE,
                 [("sub-P01", ""), ("sub-P02", "n/a"), ("sub-P03", "abc")])
    assert check_eligibility(root) == []


def test_decimal_comma(tmp_path):
    root = _make(tmp_path, [AGE], LINK_AGE, [("sub-P01", "17,5")])
    assert _codes(check_eligibility(root), "sub-P01")


def test_unlinked_criterion_silent(tmp_path):
    root = _make(tmp_path, [AGE], {}, [("sub-P01", "10")])
    assert check_eligibility(root) == []


def test_missing_project_json_or_criteria_silent(tmp_path):
    root = _make(tmp_path, None, LINK_AGE, [("sub-P01", "10")])
    assert check_eligibility(root) == []
    (tmp_path / "project.json").write_text(json.dumps({"Eligibility": {}}))
    assert check_eligibility(root) == []


def test_invalid_project_json_silent(tmp_path):
    root = _make(tmp_path, None, LINK_AGE, [("sub-P01", "10")])
    (tmp_path / "project.json").write_text("{nope")
    assert check_eligibility(root) == []


def test_limit_change_applies_without_touching_participants_json(tmp_path):
    root = _make(tmp_path, [AGE], LINK_AGE, [("sub-P01", "40")])
    assert _codes(check_eligibility(root), "sub-P01")
    wider = dict(AGE, max=50)
    (tmp_path / "project.json").write_text(json.dumps({"Eligibility": {"Criteria": [wider]}}))
    assert check_eligibility(root) == []


def test_min_greater_than_max_warns_once_and_skips(tmp_path):
    bad = dict(AGE, min=40, max=20)
    root = _make(tmp_path, [bad], LINK_AGE, [("sub-P01", "30"), ("sub-P02", "5")])
    issues = check_eligibility(root)
    assert len(issues) == 1 and "PRISM603" in issues[0][1]


def test_unknown_criterion_id_warns_once(tmp_path):
    root = _make(tmp_path, [AGE], {"age": {"EligibilityCriterion": "gone"}},
                 [("sub-P01", "10"), ("sub-P02", "11")])
    issues = check_eligibility(root)
    assert len(issues) == 1 and "PRISM603" in issues[0][1] and "gone" in issues[0][1]


def test_duplicate_ids_warn_and_first_wins(tmp_path):
    second = dict(AGE, min=0, max=99)
    root = _make(tmp_path, [AGE, second], LINK_AGE, [("sub-P01", "40")])
    issues = check_eligibility(root)
    assert _codes(issues, "PRISM603") and _codes(issues, "sub-P01")


def test_linked_column_missing_from_tsv_warns_once(tmp_path):
    root = _make(tmp_path, [AGE], {"age": {"EligibilityCriterion": "age"}},
                 [("sub-P01", "x")], header=("participant_id", "years"))
    issues = check_eligibility(root)
    assert len(issues) == 1 and "PRISM603" in issues[0][1] and "age" in issues[0][1]


SEX_LINK = {"EligibilityCriterion": "sex"}
LEVELS = {"1": "Female", "2": "Male", "3": "Other"}


def _sex(tmp_path, mode, values, levels=LEVELS, extra=None):
    crit = {"id": "sex", "label": "Sex", "term": "nb:Sex", "type": "categorical",
            "mode": mode, "values": values}
    spec = dict(SEX_LINK, **({"Levels": levels} if levels else {}), **(extra or {}))
    return _make(tmp_path, [crit], {"sex": spec},
                 [("sub-P01", "1"), ("sub-P02", "2"), ("sub-P03", "3"), ("sub-P04", "2")],
                 header=("participant_id", "sex"))


def _flagged(issues):
    return sorted(i[1].split()[1].rstrip(":") for i in issues if "sub-P0" in i[1])


def test_exclude_label_flags_every_participant_with_that_code(tmp_path):
    root = _sex(tmp_path, "exclude", ["Male"])
    issues = check_eligibility(root)
    assert _flagged(issues) == ["sub-P02", "sub-P04"]
    assert "Male" in issues[1][1]


def test_include_labels_flag_everyone_else(tmp_path):
    root = _sex(tmp_path, "include", ["Female", "Male"])
    assert _flagged(check_eligibility(root)) == ["sub-P03"]


def test_label_compare_is_exact_and_a_total_mismatch_is_reported_once(tmp_path):
    root = _sex(tmp_path, "exclude", ["Male"], levels={"1": "female", "2": "male", "3": "other"})
    issues = check_eligibility(root)
    assert not _codes(issues, "PRISM602")
    assert len(issues) == 1 and "PRISM603" in issues[0][1] and "Male" in issues[0][1]


def test_linked_categorical_without_levels_warns_once(tmp_path):
    root = _sex(tmp_path, "exclude", ["Male"], levels=None)
    issues = check_eligibility(root)
    assert len(issues) == 1 and "PRISM603" in issues[0][1] and "Levels" in issues[0][1]


def test_levels_from_annotations_are_used_when_no_plain_levels(tmp_path):
    ann = {"Annotations": {"Levels": {"2": {"TermURL": "snomed:248153007", "Label": "Male"}}}}
    root = _sex(tmp_path, "exclude", ["Male"], levels=None, extra=ann)
    assert _flagged(check_eligibility(root)) == ["sub-P02", "sub-P04"]


def test_code_without_label_is_outside_an_include_criterion(tmp_path):
    root = _sex(tmp_path, "include", ["Female", "Male"], levels={"1": "Female", "2": "Male"})
    assert _flagged(check_eligibility(root)) == ["sub-P03"]


# ---- final review: malformed criteria must never crash the validator ----

def _run(tmp_path, criterion, link="age"):
    root = _make(tmp_path, [criterion], {"age": {"EligibilityCriterion": link}},
                 [("sub-P01", "17")])
    return check_eligibility(root)


import pytest


@pytest.mark.parametrize("bad", [
    {"id": "age", "type": "numeric", "mode": "include"},                         # no bounds
    {"id": "age", "type": "numeric", "mode": "include", "min": "18"},            # string bound
    {"id": "age", "type": "numeric", "mode": "include", "min": "18", "max": "35"},
    {"id": "age", "type": "numeric", "mode": "include", "min": True},            # bool is no number
    {"id": "age", "type": "categorical", "mode": "include", "values": "Male"},   # not a list
    {"id": "age", "type": "categorical", "mode": "include", "values": []},
    {"id": "age", "type": "other", "mode": "include", "min": 1},
    {"id": "age", "type": "numeric", "mode": "sometimes", "min": 1},
    {"id": ["age"], "type": "numeric", "mode": "include", "min": 1},
    None,
    "text",
])
def test_malformed_criterion_is_reported_not_fatal(tmp_path, bad):
    issues = _run(tmp_path, bad)
    assert all(i[0] == "WARNING" for i in issues)
    assert not _codes(issues, "PRISM602")


def test_malformed_criterion_with_a_link_gets_one_warning(tmp_path):
    issues = _run(tmp_path, {"id": "age", "type": "numeric", "mode": "include"})
    assert len(issues) == 1 and "PRISM603" in issues[0][1] and "malformed" in issues[0][1]


@pytest.mark.parametrize("link", [["age"], {"a": 1}, 5])
def test_non_string_link_is_ignored(tmp_path, link):
    assert _run(tmp_path, AGE, link=link) == []


def test_load_criteria_only_returns_usable_criteria(tmp_path):
    from src.eligibility import load_criteria

    (tmp_path / "project.json").write_text(json.dumps({"Eligibility": {"Criteria": [
        None, "x", {"id": "a", "type": "numeric", "mode": "include"}, AGE]}}))
    assert load_criteria(str(tmp_path)) == [AGE]


def test_neurobagel_label_in_annotations_counts_next_to_free_text_levels(tmp_path):
    levels = {"1": "weiblich", "2": "maennlich", "3": "anderes"}
    ann = {"Annotations": {"Levels": {"2": {"TermURL": "snomed:248153007", "Label": "Male"}}}}
    root = _sex(tmp_path, "exclude", ["Male"], levels=levels, extra=ann)
    issues = check_eligibility(root)
    assert _flagged(issues) == ["sub-P02", "sub-P04"]
    assert not _codes(issues, "PRISM603")


def test_levels_given_as_dicts_without_label_fall_back_to_annotations(tmp_path):
    levels = {"1": {"Description": ""}, "2": {"Description": ""}}
    ann = {"Annotations": {"Levels": {"2": {"Label": "Male"}}}}
    root = _sex(tmp_path, "exclude", ["Male"], levels=levels, extra=ann)
    assert _flagged(check_eligibility(root)) == ["sub-P02", "sub-P04"]


# ---- deferred minors ----

def test_duplicate_id_warning_is_reported_once_even_with_two_linked_columns(tmp_path):
    second = dict(AGE, min=0, max=99)
    root = _make(tmp_path, [AGE, second],
                 {"age": {"EligibilityCriterion": "age"}, "age2": {"EligibilityCriterion": "age"}},
                 [("sub-P01", "40", "40")], header=("participant_id", "age", "age2"))
    assert len([i for i in check_eligibility(root) if "more than once" in i[1]]) == 1


def test_summary_counts_distinct_participants_not_violations(tmp_path):
    iq = {"id": "iq", "label": "IQ", "term": None, "type": "numeric", "mode": "include", "min": 85}
    root = _make(tmp_path, [AGE, iq],
                 {"age": {"EligibilityCriterion": "age"}, "iq": {"EligibilityCriterion": "iq"}},
                 [("sub-P01", "17", "70"), ("sub-P02", "20", "100")], header=("participant_id", "age", "iq"))
    issues = check_eligibility(root)
    assert "1 participant(s)" in issues[0][1]
    assert len([i for i in issues if "sub-P01" in i[1]]) == 2


def test_nan_is_not_a_number_and_is_skipped(tmp_path):
    root = _make(tmp_path, [AGE], LINK_AGE, [("sub-P01", "nan"), ("sub-P02", "NaN")])
    assert check_eligibility(root) == []


def test_large_bounds_are_not_printed_in_scientific_notation(tmp_path):
    big = {"id": "n", "label": "N", "term": None, "type": "numeric", "mode": "include",
           "min": 1234567, "max": 2500000.5}
    root = _make(tmp_path, [big], {"n": {"EligibilityCriterion": "n"}}, [("sub-P01", "5")],
                 header=("participant_id", "n"))
    assert "1234567-2500000.5" in check_eligibility(root)[1][1]


def test_non_utf8_participants_tsv_is_left_to_other_checks(tmp_path):
    root = _make(tmp_path, [AGE], LINK_AGE, [("sub-P01", "17")])
    (tmp_path / "participants.tsv").write_bytes("participant_id\tage\nsub-Müller\t17\n".encode("latin-1"))
    assert check_eligibility(root) == []


def test_numeric_criterion_on_a_column_with_value_labels_warns_once_instead_of_flagging_codes(tmp_path):
    sidecar = {"age": {"EligibilityCriterion": "age", "Levels": {"1": "Female", "2": "Male"}}}
    root = _make(tmp_path, [AGE], sidecar, [("sub-P01", "1"), ("sub-P02", "2")])
    issues = check_eligibility(root)
    assert len(issues) == 1 and "PRISM603" in issues[0][1] and "numeric" in issues[0][1]
