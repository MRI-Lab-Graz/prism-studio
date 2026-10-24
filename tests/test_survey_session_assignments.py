"""Survey conversion: sessions mode uses completed responses and the project's decisions."""

import pytest

from src.converters.survey import convert_survey_lsa_to_prism_dataset
from src.session_assignments import set_assignment
from src.session_map import save_session_map
from tests.lsa_fixtures import make_library, make_lsa


def _convert(tmp_path, project=None, **kwargs):
    return convert_survey_lsa_to_prism_dataset(
        input_path=make_lsa(tmp_path),
        library_dir=make_library(tmp_path),
        output_root=tmp_path / "out",
        id_column="token",
        duplicate_handling="sessions",
        project_path=project,
        **kwargs,
    )


def _sessions(tmp_path, participant):
    return sorted(p.name for p in (tmp_path / "out" / participant).glob("ses-*"))


def test_only_completed_responses_become_sessions(tmp_path):
    _convert(tmp_path)

    assert _sessions(tmp_path, "sub-a") == ["ses-1", "ses-2"]
    assert _sessions(tmp_path, "sub-c") == ["ses-1"]
    assert _sessions(tmp_path, "sub-b") == []  # only abandoned starts


def test_single_incomplete_response_is_left_out_in_sessions_mode(tmp_path):
    rows = [["1", "a", "2026-03-01 09:00:00", "", "2", "4", "3", "5"],
            ["2", "c", "2026-03-03 10:00:00", "2026-03-03 10:10:00", "5", "5", "5", "5"]]
    convert_survey_lsa_to_prism_dataset(
        input_path=make_lsa(tmp_path, rows), library_dir=make_library(tmp_path),
        output_root=tmp_path / "out", id_column="token", duplicate_handling="sessions",
    )

    assert _sessions(tmp_path, "sub-a") == []
    assert _sessions(tmp_path, "sub-c") == ["ses-1"]


def test_project_decisions_are_applied(tmp_path):
    project = tmp_path / "proj"
    project.mkdir()
    (project / "project.json").write_text('{"StudyDesign": {"Timepoints": "single"}}')
    set_assignment(project, "2", survey_id="999999", skip=True)

    _convert(tmp_path, project=project)

    assert _sessions(tmp_path, "sub-a") == ["ses-1"]  # response 3 is now its first completed one


def test_decisions_saved_for_another_survey_drop_nothing(tmp_path):
    project = tmp_path / "proj"
    project.mkdir()
    (project / "project.json").write_text('{"StudyDesign": {"Timepoints": "multiple"}}')
    save_session_map(project, {"1": "1", "2": "2"})
    set_assignment(project, "2", survey_id="123", skip=True)

    _convert(tmp_path, project=project)

    assert _sessions(tmp_path, "sub-a") == ["ses-1", "ses-2"]


def test_sessions_mode_never_reports_the_internal_session_column(tmp_path):
    result = _convert(tmp_path, dry_run=True)

    assert result.session_column is None
    assert result.dry_run_preview["summary"].get("session_column") is None
    paths = str(result.dry_run_preview)
    assert "ses-1" in paths and "ses-2" in paths and "_dup_session_num" not in paths


def test_an_archive_without_completed_responses_fails_and_writes_nothing(tmp_path):
    rows = [["1", "a", "2026-03-01 09:00:00", "", "2", "4", "3", "5"],
            ["2", "b", "2026-03-02 09:00:00", "", "1", "4", "3", "5"]]
    with pytest.raises(ValueError, match="No response gets a session"):
        convert_survey_lsa_to_prism_dataset(
            input_path=make_lsa(tmp_path, rows), library_dir=make_library(tmp_path),
            output_root=tmp_path / "out", id_column="token", duplicate_handling="sessions",
        )

    assert not (tmp_path / "out").exists() or not list((tmp_path / "out").iterdir())
