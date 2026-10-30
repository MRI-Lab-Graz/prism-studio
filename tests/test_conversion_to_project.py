"""What happens after a conversion, for `survey convert` and Studio's Save to project: one function."""

import json
from types import SimpleNamespace

import pytest

from src import conversion_to_project as ctp
from src.conversion_to_project import (
    cleanup_stale_tool_limesurvey_sidecars,
    extract_tasks_from_output,
    iter_session_registration_values,
    save_conversion_to_project,
)


@pytest.fixture
def world(tmp_path):
    project = tmp_path / "proj"
    project.mkdir()
    (project / "project.json").write_text(json.dumps({"Sessions": []}), encoding="utf-8")
    staged = tmp_path / "staged"
    (staged / "sub-001" / "ses-1" / "survey").mkdir(parents=True)
    (staged / "sub-001" / "ses-1" / "survey" / "sub-001_ses-1_task-pss_survey.tsv").write_text("PSS1\n1\n", encoding="utf-8")
    (staged / "task-pss_survey.json").write_text("{}", encoding="utf-8")
    (staged / ".DS_Store").write_text("junk", encoding="utf-8")
    source = tmp_path / "answers.csv"
    source.write_text("ID,PSS1\n1,1\n", encoding="utf-8")
    return project, staged, source


def _save(world, **overrides):
    project, staged, source = world
    kwargs = dict(
        project_root=project, staged_root=staged, convert_result=SimpleNamespace(tasks_included=["pss"], detected_sessions=[]),
        source_path=source, source_name="answers.csv", session_override=None, template_version_overrides=None,
        archive_sourcedata=False, modality="survey", run_message="PRISM: Copy converted survey files into project",
    )
    kwargs.update(overrides)
    return save_conversion_to_project(**kwargs)


def test_every_converted_file_is_copied_into_the_project_but_no_system_files(world):
    project, _staged, _source = world
    result = _save(world)

    assert (project / "sub-001" / "ses-1" / "survey" / "sub-001_ses-1_task-pss_survey.tsv").read_text(encoding="utf-8") == "PSS1\n1\n"
    assert (project / "task-pss_survey.json").exists()
    assert not (project / ".DS_Store").exists()
    assert "task-pss_survey.json" in result.copied_paths


def test_the_source_file_is_archived_in_sourcedata_when_asked(world):
    project, _staged, _source = world
    _save(world)
    assert not (project / "sourcedata").exists()
    _save(world, archive_sourcedata=True)
    assert (project / "sourcedata" / "answers.csv").read_text(encoding="utf-8") == "ID,PSS1\n1,1\n"


def test_the_copy_goes_through_the_datalad_aware_function_with_studios_message(world, monkeypatch):
    seen = {}

    def fake_copy(*, dataset_root, copy_pairs, run_message):
        seen.update(root=dataset_root, pairs=list(copy_pairs), message=run_message)
        return {"copied_paths": [], "datalad": {"tracked": True}}

    monkeypatch.setattr(ctp, "copy_files_into_project", fake_copy)
    result = _save(world)

    assert seen["message"] == "PRISM: Copy converted survey files into project"
    assert len(seen["pairs"]) == 2  # the two real files, not .DS_Store
    assert result.datalad == {"tracked": True}


def test_template_versions_are_registered_in_project_json_only_for_a_given_session(world):
    project, _staged, _source = world
    _save(world, template_version_overrides={"pss": "10-likert"})  # no session: nothing registered, as in Studio
    assert "TemplateVersionSelections" not in json.loads((project / "project.json").read_text(encoding="utf-8"))

    result = _save(world, session_override="ses-1", template_version_overrides={"pss": "10-likert"})

    assert result.registered_sessions == ["ses-1"]
    selections = json.loads((project / "project.json").read_text(encoding="utf-8"))["TemplateVersionSelections"]
    assert selections == [{"task": "pss", "version": "10-likert", "session": "ses-1"}]


def test_session_all_registers_every_detected_session():
    assert iter_session_registration_values(session_override="all", detected_sessions=["1", "2", "all", "2", ""]) == ["1", "2"]
    assert iter_session_registration_values(session_override="ses-3", detected_sessions=["1"]) == ["ses-3"]
    assert iter_session_registration_values(session_override=None, detected_sessions=["1"]) == []


def test_stale_limesurvey_sidecars_go_for_other_sources_but_not_for_limesurvey(tmp_path):
    survey = tmp_path / "sub-1" / "survey"
    survey.mkdir(parents=True)
    stale = survey / "sub-1_task-x_tool-limesurvey_survey.tsv"
    stale.write_text("old", encoding="utf-8")
    fresh = survey / "sub-1_task-x_survey.tsv"
    fresh.write_text("new", encoding="utf-8")

    assert cleanup_stale_tool_limesurvey_sidecars(copied_output_paths=[fresh], source_suffix=".lsa") == []
    assert stale.exists()
    assert cleanup_stale_tool_limesurvey_sidecars(copied_output_paths=[fresh], source_suffix=".csv") == [stale]
    assert not stale.exists() and fresh.exists()


def test_applied_value_offsets_are_synced_into_the_recipes(world, monkeypatch):
    project, _staged, _source = world
    seen = {}
    monkeypatch.setattr(
        "src.converters.survey.sync_project_survey_recipe_offsets",
        lambda **kw: seen.update(kw) or {"updated_tasks": ["pss"], "missing_tasks": [], "errors": []},
    )
    result = _save(world, convert_result=SimpleNamespace(
        tasks_included=["pss"], detected_sessions=[], applied_value_offsets={"pss": -1.0}, value_offset_application_counts={"pss": 3},
    ))

    assert seen["project_root"] == project and seen["task_value_offsets"] == {"pss": -1.0}
    assert result.recipe_offset_summary["updated_tasks"] == ["pss"]


def test_tasks_are_read_from_the_file_names_of_the_output(tmp_path):
    (tmp_path / "sub-1").mkdir()
    (tmp_path / "sub-1" / "sub-1_task-pss_survey.tsv").write_text("", encoding="utf-8")
    (tmp_path / "sub-1" / "sub-1_task-gad7_survey.tsv").write_text("", encoding="utf-8")
    assert extract_tasks_from_output(tmp_path) == ["gad7", "pss"]
