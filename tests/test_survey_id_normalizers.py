from src.converters.survey_core import build_survey_id_normalizers


def test_normalize_sub_adds_sub_prefix_and_strips_non_alnum():
    normalizers = build_survey_id_normalizers(project_path=None)
    assert normalizers.normalize_sub("A-01!") == "sub-A01"


def test_normalize_sub_treats_nan_string_as_empty():
    normalizers = build_survey_id_normalizers(project_path=None)
    assert normalizers.normalize_sub("nan") == ""


def test_normalize_sub_matches_existing_project_participant_by_numeric_id(tmp_path):
    (tmp_path / "participants.tsv").write_text("participant_id\nsub-001\n")

    normalizers = build_survey_id_normalizers(project_path=tmp_path)

    # A bare "1" in source data should resolve to the existing "sub-001"
    # folder rather than creating a duplicate "sub-1".
    assert normalizers.normalize_sub("1") == "sub-001"


def test_normalize_ses_defaults_to_ses_1_for_missing_value():
    normalizers = build_survey_id_normalizers(project_path=None)
    assert normalizers.normalize_ses("") == "ses-1"
    assert normalizers.normalize_ses("nan") == "ses-1"


def test_normalize_ses_adds_ses_prefix():
    normalizers = build_survey_id_normalizers(project_path=None)
    assert normalizers.normalize_ses("baseline") == "ses-baseline"


def test_normalize_run_returns_none_for_missing_value():
    normalizers = build_survey_id_normalizers(project_path=None)
    assert normalizers.normalize_run("") is None
    assert normalizers.normalize_run("nan") is None


def test_normalize_run_adds_run_prefix():
    normalizers = build_survey_id_normalizers(project_path=None)
    assert normalizers.normalize_run("2") == "run-2"


def test_is_missing_detects_nan_and_blank_string():
    import pandas as pd

    normalizers = build_survey_id_normalizers(project_path=None)
    assert normalizers.is_missing(float("nan")) is True
    assert normalizers.is_missing("   ") is True
    assert normalizers.is_missing("value") is False
    assert normalizers.is_missing(pd.NA) is True
