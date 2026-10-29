"""A project template that changed after the data was converted: the root sidecar is stale."""

import json

from src.issues import infer_code_from_message
from src.survey_template_drift import check_survey_template_drift

TEMPLATE = {
    "Technical": {"StimulusType": "Questionnaire", "FileFormat": "tsv", "Language": "de"},
    "Study": {"TaskName": "ads", "OriginalName": "ads", "LicenseID": "Other", "License": ""},
    "Metadata": {"SchemaVersion": "1.1.1", "CreationDate": "2026-10-01", "Creator": "t"},
    "ADS1": {"Description": {"de": "Frage"}, "Levels": {"ADS0": {"de": "selten"}, "ADS1": {"de": "oft"}}},
    "ADS2": {"Description": {"de": "Frage 2"}, "Levels": {"ADS0": {"de": "selten"}, "ADS1": {"de": "oft"}}},
}


def _project(tmp_path, template=TEMPLATE):
    library = tmp_path / "code" / "library" / "survey"
    library.mkdir(parents=True)
    (library / "survey-ads.json").write_text(json.dumps(template), encoding="utf-8")
    return tmp_path


def _convert(tmp_path):
    """Write the root sidecar the way the converter does, from the current template."""
    from src.converters.survey_core import _inject_missing_token, load_survey_library
    from src.survey_localize import _localize_survey_template

    template = load_survey_library(str(tmp_path / "code" / "library" / "survey"))["ads"]
    sidecar = _inject_missing_token(_localize_survey_template(template, None), token="n/a")
    (tmp_path / "task-ads_survey.json").write_text(json.dumps(sidecar), encoding="utf-8")


def _edit_template(tmp_path, edit):
    path = tmp_path / "code" / "library" / "survey" / "survey-ads.json"
    template = json.loads(path.read_text(encoding="utf-8"))
    edit(template)
    path.write_text(json.dumps(template), encoding="utf-8")


def test_unchanged_template_gives_no_warning(tmp_path):
    _project(tmp_path)
    _convert(tmp_path)
    assert check_survey_template_drift(str(tmp_path), project_path=str(tmp_path)) == []


def test_changed_levels_are_reported_per_survey(tmp_path):
    _project(tmp_path)
    _convert(tmp_path)
    _edit_template(
        tmp_path,
        lambda t: [t[k].__setitem__("Levels", {"0": {"de": "selten"}, "1": {"de": "oft"}}) for k in ("ADS1", "ADS2")],
    )

    issues = check_survey_template_drift(str(tmp_path), project_path=str(tmp_path))

    assert len(issues) == 1
    level, message, path = issues[0]
    assert level == "WARNING"
    assert "'ads'" in message and "ADS1" in message and "ADS2" in message
    assert "survey convert --force" in message
    assert path.endswith("task-ads_survey.json")
    assert infer_code_from_message(message) == "PRISM710"


def test_edits_to_technical_study_and_metadata_are_not_drift(tmp_path):
    _project(tmp_path)
    _convert(tmp_path)
    sidecar_path = tmp_path / "task-ads_survey.json"
    sidecar = json.loads(sidecar_path.read_text(encoding="utf-8"))
    sidecar["Technical"]["SoftwarePlatform"] = "LimeSurvey"
    sidecar["Study"]["License"] = "CC0"
    sidecar["Metadata"]["Creator"] = "someone else"
    sidecar_path.write_text(json.dumps(sidecar), encoding="utf-8")

    assert check_survey_template_drift(str(tmp_path), project_path=str(tmp_path)) == []


def test_sidecar_without_project_template_is_ignored(tmp_path):
    (tmp_path / "task-ads_survey.json").write_text(json.dumps(TEMPLATE), encoding="utf-8")
    assert check_survey_template_drift(str(tmp_path), project_path=str(tmp_path)) == []


def test_bounds_implied_by_the_levels_are_not_a_change_either_way(tmp_path):
    """Whether the converter wrote MinValue/MaxValue into the sidecar or not, the template did not change."""
    template = {**TEMPLATE, "ADS1": {"Description": {"de": "Frage"}, "Levels": {"0": {"de": "a"}, "1": {"de": "b"}}}}
    template.pop("ADS2")
    _project(tmp_path, template)
    _convert(tmp_path)
    sidecar_path = tmp_path / "task-ads_survey.json"

    for with_bounds in (False, True):
        sidecar = json.loads(sidecar_path.read_text(encoding="utf-8"))
        for name in ("MinValue", "MaxValue"):
            sidecar["ADS1"].pop(name, None)
        if with_bounds:
            sidecar["ADS1"].update(MinValue=0, MaxValue=1)
        sidecar_path.write_text(json.dumps(sidecar), encoding="utf-8")
        assert check_survey_template_drift(str(tmp_path), project_path=str(tmp_path)) == [], with_bounds
