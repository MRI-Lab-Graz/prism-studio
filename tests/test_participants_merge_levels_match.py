"""Levels and Annotations.Levels of one column must describe the same codes."""

import json

from src.participants_backend import (
    merge_neurobagel_schema_for_columns,
    merge_survey_selected_participants_schema,
)
from src.participants_levels import check_participants_levels


def test_new_labels_replace_old_ones_together_with_annotations():
    base = {"gender": {"Levels": {"1": "Male", "2": "Female", "9": "Unknown"}}}
    new = {
        "gender": {
            "Levels": {"1": "Female", "2": "Male"},
            "Annotations": {"Levels": {"1": {"Label": "Female"}}},
        }
    }

    merged, _ = merge_neurobagel_schema_for_columns(base, new, ["gender"])

    assert merged["gender"]["Levels"] == {"1": "Female", "2": "Male", "9": "Unknown"}


def test_unlabelled_code_does_not_replace_a_real_label():
    base = {"gender": {"Levels": {"1": "Male"}}}
    new = {"gender": {"Levels": {"1": "1", "2": "2"}}}

    merged, _ = merge_neurobagel_schema_for_columns(base, new, ["gender"])

    assert merged["gender"]["Levels"] == {"1": "Male", "2": "2"}


def _check(tmp_path, levels, annotation_labels):
    (tmp_path / "participants.tsv").write_text("participant_id\tgender\nsub-1\t1\n")
    spec = {
        "Levels": levels,
        "Annotations": {
            "Levels": {c: {"Label": v} for c, v in annotation_labels.items()}
        },
    }
    (tmp_path / "participants.json").write_text(json.dumps({"gender": spec}))
    return check_participants_levels(str(tmp_path))


def test_validator_reports_swapped_annotation_labels(tmp_path):
    issues = _check(
        tmp_path, {"1": "Male", "2": "Female"}, {"1": "Female", "2": "Male"}
    )

    assert [i[0] for i in issues] == ["ERROR"]
    assert "gender" in issues[0][1] and "1, 2" in issues[0][1]


def test_validator_accepts_different_wording_for_the_same_code(tmp_path):
    assert not _check(
        tmp_path, {"1": "männlich", "2": "weiblich"}, {"1": "Male", "2": "Female"}
    )


def test_survey_selected_keeps_curated_levels_with_their_annotations():
    curated = {
        "Levels": {"1": "Female", "2": "Male"},
        "Annotations": {"Levels": {"1": {"Label": "Female"}}},
    }
    generic = {"Description": "Sex", "Levels": {"M": "Male", "F": "Female"}}

    merged = merge_survey_selected_participants_schema(
        {"sex": curated}, {"sex": generic}
    )

    assert merged["sex"] == {**curated, "Description": "Sex"}


def test_new_levels_without_annotations_drop_the_contradicted_ones():
    base = {
        "gender": {
            "Levels": {"1": "Male", "2": "Female"},
            "Annotations": {
                "Levels": {"1": {"Label": "Male"}, "2": {"Label": "Female"}}
            },
        }
    }
    new = {"gender": {"Levels": {"1": "Female", "2": "Male"}, "Annotations": {}}}
    log = []

    merged, _ = merge_neurobagel_schema_for_columns(
        base, new, ["gender"], log_callback=lambda *a: log.append(a)
    )

    assert merged["gender"]["Annotations"]["Levels"] == {}
    assert [level for level, _ in log] == ["WARNING", "WARNING"]
    assert "1, 2" in log[0][1]


def test_non_object_levels_do_not_crash():
    base = {"gender": {"Levels": {"1": "Male"}}}

    merged, _ = merge_neurobagel_schema_for_columns(
        base, {"gender": {"Levels": None}}, ["gender"]
    )

    assert merged["gender"]["Levels"] == {"1": "Male"}


def test_validator_accepts_two_codes_mapped_to_one_term(tmp_path):
    assert not _check(
        tmp_path, {"1": "Right", "2": "Mostly right"}, {"1": "Right", "2": "Right"}
    )


def test_validator_reads_object_levels(tmp_path):
    levels = {"1": {"Description": "Male"}, "2": {"Description": "Female"}}

    assert _check(tmp_path, levels, {"1": "Female"})


def test_survey_selected_fills_unlabelled_curated_levels():
    merged = merge_survey_selected_participants_schema(
        {"sex": {"Levels": {"M": "M", "F": "Woman"}}},
        {"sex": {"Levels": {"M": "Male", "F": "Female", "O": "Other"}}},
    )

    assert merged["sex"]["Levels"] == {"M": "Male", "F": "Woman"}
