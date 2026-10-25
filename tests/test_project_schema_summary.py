import json

from src.modality_versions import current_version, project_schema_summary


def _project(tmp_path, pins=None):
    (tmp_path / "project.json").write_text(json.dumps({"SchemaVersions": pins or {}}), encoding="utf-8")
    (tmp_path / "sub-01" / "survey").mkdir(parents=True)
    (tmp_path / "sub-01" / "survey" / "sub-01_task-x_survey.tsv").write_text("a\n", encoding="utf-8")
    return tmp_path


def test_lists_the_modalities_present_with_the_version_that_applies(tmp_path):
    summary = project_schema_summary(_project(tmp_path))

    assert summary["schemas"] == [{"name": "survey", "version": current_version("survey"), "pinned": False}]
    assert summary["local_additions"] == 0


def test_a_pinned_version_wins_and_is_marked(tmp_path):
    summary = project_schema_summary(_project(tmp_path, {"survey": "1.0.0"}))

    assert summary["schemas"] == [{"name": "survey", "version": "1.0.0", "pinned": True}]



def test_invalid_overlay_files_are_not_counted_as_local_additions(tmp_path):
    project = _project(tmp_path)
    terms = project / "code" / "specification" / "terms" / "biosample"
    terms.mkdir(parents=True)
    (terms / "broken.json").write_text("{not json", encoding="utf-8")

    assert project_schema_summary(project)["local_additions"] == 0
