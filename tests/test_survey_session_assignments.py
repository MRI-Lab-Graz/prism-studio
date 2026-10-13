"""Survey conversion: sessions mode uses completed responses and the project's decisions."""

from src.converters.survey import convert_survey_lsa_to_prism_dataset
from src.session_assignments import set_assignment
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
    set_assignment(project, "2", skip=True)

    _convert(tmp_path, project=project)

    assert _sessions(tmp_path, "sub-a") == ["ses-1"]  # response 3 is now its first completed one
