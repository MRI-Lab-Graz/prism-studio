"""build_methods: one backend entry point for the methods section (CLI and GUI)."""

import json
import sys
from pathlib import Path
from unittest.mock import patch

import pytest

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))
sys.path.insert(0, str(REPO / "app"))

from src.methods_project import MethodsResult, build_methods  # noqa: E402

TEMPLATE = {
    "Study": {
        "TaskName": {"en": "Affective Distress Scale"},
        "Description": {"en": "Assesses current distress symptoms."},
    },
    "item_01": {"Levels": {"1": {"en": "No"}, "2": {"en": "Yes"}}},
}


def _project(tmp_path, project_json):
    (tmp_path / "project.json").write_text(json.dumps(project_json), encoding="utf-8")
    return tmp_path


def _no_global_library():
    return patch(
        "src.config.get_effective_template_library_path",
        return_value={"effective_external_path": "", "global_library_path": ""},
    )


def test_build_methods_returns_result(tmp_path):
    root = _project(tmp_path, {"StudyDesign": {"Type": "cross-sectional"}})
    with _no_global_library():
        result = build_methods(root)
    assert isinstance(result, MethodsResult)
    assert "cross sectional design" in result.md
    assert "StudyDesign" in result.sections_used
    assert result.warnings and "sample size" in result.warnings[0]
    assert result.template_data == {}


def test_build_methods_without_project_json_raises(tmp_path):
    with pytest.raises(FileNotFoundError, match="No project metadata"):
        build_methods(tmp_path)


def test_build_methods_finds_template_in_project_library(tmp_path):
    root = _project(tmp_path, {"TaskDefinitions": {"ads": {"modality": "survey"}}})
    lib = root / "code" / "library" / "survey"
    lib.mkdir(parents=True)
    (lib / "survey-ads.json").write_text(json.dumps(TEMPLATE), encoding="utf-8")
    with _no_global_library():
        result = build_methods(root)
    assert "Affective Distress Scale" in result.md
    assert set(result.template_data) == {"ads"}


def test_build_methods_uses_given_project_data_and_stats(tmp_path):
    root = _project(tmp_path, {})
    with _no_global_library():
        result = build_methods(
            root,
            project_data={"StudyDesign": {"Type": "longitudinal"}},
            compute_participant_stats=lambda path, lang="en": {"n": 12},
        )
    assert "*N* = 12 participants" in result.md


def test_build_methods_reports_warnings(tmp_path):
    p = _project(tmp_path, {"TaskDefinitions": {"ads": {"modality": "survey"}}})
    result = build_methods(p, app_root=str(tmp_path), compute_participant_stats=lambda *a, **k: None)
    assert any("sample size" in w for w in result.warnings)


def test_build_methods_includes_acquisition_from_sidecars(tmp_path):
    p = _project(tmp_path, {"StudyDesign": {"Type": "cross-sectional"}})
    d = p / "sub-01" / "ses-1" / "func"
    d.mkdir(parents=True)
    (d / "sub-01_ses-1_task-x_bold.json").write_text(
        json.dumps({"RepetitionTime": 2.0}), encoding="utf-8"
    )
    result = build_methods(p, app_root=str(tmp_path), compute_participant_stats=lambda *a, **k: None)
    assert "TR = 2000 ms" in result.md
    assert "DataAcquisition" in result.sections_used


def test_build_methods_includes_processing_from_recipes(tmp_path):
    p = _project(tmp_path, {"StudyDesign": {"Type": "cross-sectional"}})
    d = p / "code" / "recipes" / "survey"
    d.mkdir(parents=True)
    (d / "recipe-ads.json").write_text(
        json.dumps({"Survey": {"TaskName": "ads"}, "Scores": [{"Name": "Total"}]}), encoding="utf-8"
    )
    result = build_methods(p, app_root=str(tmp_path), compute_participant_stats=lambda *a, **k: None)
    assert "ads (Total)" in result.md and "DataProcessing" in result.sections_used


def test_build_methods_accepts_project_json_path(tmp_path):
    p = _project(tmp_path, {"StudyDesign": {"Type": "cross-sectional"}})
    result = build_methods(p / "project.json", app_root=str(tmp_path), compute_participant_stats=lambda *a, **k: None)
    assert "cross sectional design" in result.md


def test_build_methods_lists_surveys_found_in_dataset_without_task_definitions(tmp_path):
    root = _project(tmp_path, {"StudyDesign": {"Type": "cross-sectional"}})
    survey = root / "rawdata" / "sub-01" / "ses-1" / "survey"
    survey.mkdir(parents=True)
    (survey / "sub-01_ses-1_task-ads_survey.tsv").write_text("item_01\n1\n", encoding="utf-8")
    lib = root / "code" / "library" / "survey"
    lib.mkdir(parents=True)
    (lib / "survey-ads.json").write_text(json.dumps(TEMPLATE), encoding="utf-8")
    with _no_global_library():
        result = build_methods(root)
    assert "Measures" in result.sections_used
    assert "Affective Distress Scale" in result.md
    assert set(result.template_data) == {"ads"}


def test_methods_cites_prism_studio_zenodo(tmp_path):
    from src.text_export import references_bib

    root = _project(tmp_path, {"StudyDesign": {"Type": "cross-sectional"}})
    with _no_global_library():
        result = build_methods(root)
    assert "https://doi.org/10.5281/zenodo.22809100" in result.md
    assert "10.5281/zenodo.22809100" in references_bib(result.template_data)


def _survey_file(root, sub, ses, task):
    folder = root / "rawdata" / f"sub-{sub}" / (f"ses-{ses}" if ses else "") / "survey"
    folder.mkdir(parents=True, exist_ok=True)
    name = f"sub-{sub}_" + (f"ses-{ses}_" if ses else "") + f"task-{task}_survey.tsv"
    (folder / name).write_text("item_01\n1\n", encoding="utf-8")


def test_discover_sessions_groups_tasks_and_counts(tmp_path):
    from src.methods_project import discover_sessions

    for sub in ("01", "02"):
        _survey_file(tmp_path, sub, "1", "ads")
    _survey_file(tmp_path, "01", "2", "ads")
    _survey_file(tmp_path, "01", "2", "pss")
    sessions = discover_sessions(tmp_path)
    assert [s["label"] for s in sessions] == ["1", "2"]
    assert sessions[0]["id"] == "ses-1"
    assert sessions[0]["tasks"] == [{"task": "ads", "n": 2}]
    assert sessions[1]["tasks"] == [{"task": "ads", "n": 1}, {"task": "pss", "n": 1}]
    assert all(s["ordered"] for s in sessions)


def test_discover_sessions_keeps_1_and_01_distinct(tmp_path):
    from src.methods_project import discover_sessions

    _survey_file(tmp_path, "01", "1", "ads")
    _survey_file(tmp_path, "01", "01", "ads")
    assert sorted(s["label"] for s in discover_sessions(tmp_path)) == ["01", "1"]


def test_discover_sessions_non_numeric_unordered(tmp_path):
    from src.methods_project import discover_sessions

    _survey_file(tmp_path, "01", "pre", "ads")
    _survey_file(tmp_path, "01", "post", "ads")
    sessions = discover_sessions(tmp_path)
    assert [s["label"] for s in sessions] == ["post", "pre"]
    assert not any(s["ordered"] for s in sessions)


def test_discover_sessions_without_session_folders(tmp_path):
    from src.methods_project import discover_sessions

    _survey_file(tmp_path, "01", "", "ads")
    sessions = discover_sessions(tmp_path)
    assert sessions == [{"id": "", "label": "", "tasks": [{"task": "ads", "n": 1}], "ordered": True}]


def _sessions_tsv(root, sub, rows):
    folder = root / "rawdata" / f"sub-{sub}"
    folder.mkdir(parents=True, exist_ok=True)
    lines = ["session_id\tacq_time"] + [f"ses-{label}\t{when}" for label, when in rows]
    (folder / f"sub-{sub}_sessions.tsv").write_text("\n".join(lines) + "\n", encoding="utf-8")


def _two_sessions():
    return [
        {"id": "ses-1", "label": "1", "tasks": [], "ordered": True},
        {"id": "ses-2", "label": "2", "tasks": [], "ordered": True},
    ]


def test_timing_from_sessions_tsv_gives_days_after_baseline(tmp_path):
    from src.methods_project import add_session_timing

    _sessions_tsv(tmp_path, "01", [("1", "2025-01-01T09:00:00"), ("2", "2025-01-15T09:00:00")])
    _sessions_tsv(tmp_path, "02", [("1", "2025-01-03T09:00:00"), ("2", "2025-01-17T09:00:00")])
    sessions = _two_sessions()
    add_session_timing(tmp_path, sessions)
    assert "timingRelativeToBaseline" not in sessions[0]
    assert sessions[1]["timingRelativeToBaseline"] == {"Value": 14, "Unit": "days"}


def test_timing_ignores_na_and_empty_acq_time(tmp_path):
    from src.methods_project import add_session_timing

    _sessions_tsv(tmp_path, "01", [("1", "n/a"), ("2", "")])
    sessions = _two_sessions()
    add_session_timing(tmp_path, sessions)
    assert not any("timingRelativeToBaseline" in s for s in sessions)


def test_timing_absent_without_tsv(tmp_path):
    from src.methods_project import add_session_timing

    sessions = _two_sessions()
    add_session_timing(tmp_path, sessions)
    assert not any("timingRelativeToBaseline" in s for s in sessions)


def _build_two_session_project(tmp_path, labels=("1", "2"), project=None):
    root = _project(tmp_path, project or {"StudyDesign": {"Type": "longitudinal"}})
    for sub in ("01", "02"):
        _survey_file(root, sub, labels[0], "ads")
    _survey_file(root, "01", labels[1], "ads")
    lib = root / "code" / "library" / "survey"
    lib.mkdir(parents=True)
    (lib / "survey-ads.json").write_text(json.dumps(TEMPLATE), encoding="utf-8")
    return root


def test_build_methods_procedure_lists_surveys_per_session(tmp_path):
    root = _build_two_session_project(tmp_path)
    with _no_global_library():
        result = build_methods(root)
    assert "Procedure" in result.sections_used
    assert 'In the first session ("1")' not in result.md  # inferred sessions: no enrollment claim
    assert '"1"' in result.md and '"2"' in result.md
    assert "ADS" in result.md or "Affective Distress Scale" in result.md


def test_methods_states_participant_count_per_instrument(tmp_path):
    root = _build_two_session_project(tmp_path)
    with _no_global_library():
        result = build_methods(root)
    assert "*n* = 2" in result.md and "*n* = 1" in result.md


def test_methods_unordered_sessions_make_no_ordinal_claim(tmp_path):
    root = _build_two_session_project(tmp_path, labels=("pre", "post"))
    with _no_global_library():
        result = build_methods(root)
    assert "first session" not in result.md.lower()
    assert "session 2" not in result.md.lower()
    assert any("order" in w for w in result.warnings)


def test_methods_placeholder_for_unknown_timing(tmp_path):
    root = _build_two_session_project(tmp_path)
    with _no_global_library():
        result = build_methods(root)
    assert "[please add: time between sessions]" in result.md


def test_methods_no_timing_placeholder_when_timing_known(tmp_path):
    root = _build_two_session_project(tmp_path)
    _sessions_tsv(root, "01", [("1", "2025-01-01T09:00:00"), ("2", "2025-01-15T09:00:00")])
    with _no_global_library():
        result = build_methods(root)
    assert "[please add: time between sessions]" not in result.md
    assert "14 days after baseline" in result.md


def test_methods_placeholder_for_missing_reference(tmp_path):
    root = _build_two_session_project(tmp_path)
    (root / "code" / "library" / "survey" / "survey-ads.json").unlink()
    with _no_global_library():
        result = build_methods(root)
    assert "[please add: reference for" in result.md


def test_declared_sessions_override_inference(tmp_path):
    root = _build_two_session_project(
        tmp_path,
        project={"Sessions": [{"id": "ses-A", "label": "Baseline", "tasks": [{"task": "ads"}]}]},
    )
    with _no_global_library():
        result = build_methods(root)
    assert "Baseline" in result.md
    assert '"2"' not in result.md


def test_timing_falls_back_to_scans_tsv(tmp_path):
    from src.methods_project import add_session_timing

    for ses, when in (("1", "2025-02-01T10:00:00"), ("2", "2025-02-08T10:00:00")):
        folder = tmp_path / "rawdata" / "sub-01" / f"ses-{ses}"
        folder.mkdir(parents=True)
        (folder / f"sub-01_ses-{ses}_scans.tsv").write_text(
            f"filename\tacq_time\nfunc/x.nii.gz\t{when}\n", encoding="utf-8"
        )
    sessions = _two_sessions()
    add_session_timing(tmp_path, sessions)
    assert sessions[1]["timingRelativeToBaseline"] == {"Value": 7, "Unit": "days"}


def _dated_survey(root, sub, ses, date):
    folder = root / "rawdata" / f"sub-{sub}" / f"ses-{ses}" / "survey"
    folder.mkdir(parents=True, exist_ok=True)
    (folder / f"sub-{sub}_ses-{ses}_task-ads_survey.tsv").write_text(
        f"SurveyStartDate\titem_01\n{date}\t1\n", encoding="utf-8"
    )


def test_timing_from_survey_start_date_is_per_subject(tmp_path):
    from src.methods_project import add_session_timing

    _dated_survey(tmp_path, "01", "1", "2025-01-01")
    _dated_survey(tmp_path, "01", "2", "2025-01-15")
    _dated_survey(tmp_path, "02", "1", "2025-01-10")
    _dated_survey(tmp_path, "02", "2", "2025-01-24")
    _dated_survey(tmp_path, "03", "2", "2025-03-01")  # one dated session only: no interval
    sessions = _two_sessions()
    add_session_timing(tmp_path, sessions)
    assert sessions[1]["timingRelativeToBaseline"] == {"Value": 14, "Unit": "days"}


def test_timing_survey_date_beats_sessions_tsv(tmp_path):
    from src.methods_project import add_session_timing

    _dated_survey(tmp_path, "01", "1", "2025-01-01")
    _dated_survey(tmp_path, "01", "2", "2025-01-15")
    _sessions_tsv(tmp_path, "01", [("1", "2025-01-01T09:00:00"), ("2", "2025-04-11T09:00:00")])
    sessions = _two_sessions()
    add_session_timing(tmp_path, sessions)
    assert sessions[1]["timingRelativeToBaseline"]["Value"] == 14


def test_timing_survey_dates_with_empty_cells_are_skipped(tmp_path):
    from src.methods_project import add_session_timing

    _dated_survey(tmp_path, "01", "1", "")
    _dated_survey(tmp_path, "01", "2", "2025-01-15")
    sessions = _two_sessions()
    add_session_timing(tmp_path, sessions)
    assert not any("timingRelativeToBaseline" in s for s in sessions)
