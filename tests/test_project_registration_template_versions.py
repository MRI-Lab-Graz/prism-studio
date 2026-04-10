import json
from pathlib import Path

from src.web.services.project_registration import register_session_in_project


def _write_project_json(project_root: Path, payload: dict) -> None:
    (project_root / "project.json").write_text(
        json.dumps(payload, indent=2), encoding="utf-8"
    )


def _read_project_json(project_root: Path) -> dict:
    return json.loads((project_root / "project.json").read_text(encoding="utf-8"))


def test_register_session_persists_template_versions_with_task_session_run(tmp_path: Path):
    _write_project_json(tmp_path, {"Sessions": [], "TaskDefinitions": {}})

    register_session_in_project(
        project_path=tmp_path,
        session_id="1",
        tasks=["wellbeing"],
        modality="survey",
        source_file="responses.xlsx",
        converter="survey-xlsx",
        template_version_overrides=[
            {
                "task": "wellbeing",
                "session": "pre",
                "run": "2",
                "version": "10-vas",
            },
            {
                "task": "wellbeing",
                "version": {"en": "10-likert", "de": "10-likert"},
            },
        ],
    )

    project_data = _read_project_json(tmp_path)

    assert project_data["Sessions"][0]["id"] == "ses-01"
    assert project_data["TaskDefinitions"]["wellbeing"]["modality"] == "survey"

    selections = project_data.get("TemplateVersionSelections")
    assert isinstance(selections, list)

    selection_map = {
        (entry.get("task"), entry.get("session"), entry.get("run")): entry.get(
            "version"
        )
        for entry in selections
    }
    assert selection_map[("wellbeing", "ses-pre", "run-2")] == "10-vas"
    assert selection_map[("wellbeing", "ses-01", None)] == "10-likert"


def test_register_session_merges_template_versions_by_task_session_run(tmp_path: Path):
    _write_project_json(
        tmp_path,
        {
            "Sessions": [{"id": "ses-01", "label": "ses-01", "tasks": []}],
            "TaskDefinitions": {"wellbeing": {"modality": "survey"}},
            "TemplateVersionSelections": [
                {
                    "task": "wellbeing",
                    "session": "ses-01",
                    "version": "old-version",
                },
                {
                    "task": "wellbeing",
                    "session": "ses-pre",
                    "run": "run-1",
                    "version": "v1",
                },
            ],
        },
    )

    register_session_in_project(
        project_path=tmp_path,
        session_id="ses-01",
        tasks=["wellbeing"],
        modality="survey",
        source_file="responses.xlsx",
        converter="survey-xlsx",
        template_version_overrides=[
            {"task": "wellbeing", "version": "new-version"},
            {
                "task": "wellbeing",
                "session": "ses-pre",
                "run": "1",
                "version": "v2",
            },
        ],
    )

    project_data = _read_project_json(tmp_path)
    selections = project_data.get("TemplateVersionSelections")

    assert isinstance(selections, list)
    selection_map = {
        (entry.get("task"), entry.get("session"), entry.get("run")): entry.get(
            "version"
        )
        for entry in selections
    }
    assert selection_map[("wellbeing", "ses-01", None)] == "new-version"
    assert selection_map[("wellbeing", "ses-pre", "run-1")] == "v2"
    assert len(selection_map) == 2


def test_register_session_preserves_alphanumeric_run_entities(tmp_path: Path):
    _write_project_json(tmp_path, {"Sessions": [], "TaskDefinitions": {}})

    register_session_in_project(
        project_path=tmp_path,
        session_id="pre",
        tasks=["wellbeing"],
        modality="survey",
        source_file="responses.xlsx",
        converter="survey-xlsx",
        template_version_overrides=[
            {
                "task": "wellbeing",
                "session": "pre",
                "run": "A",
                "version": "10-vas",
            }
        ],
    )

    project_data = _read_project_json(tmp_path)
    selections = project_data.get("TemplateVersionSelections") or []
    assert any(
        entry.get("task") == "wellbeing"
        and entry.get("session") == "ses-pre"
        and entry.get("run") == "run-A"
        and entry.get("version") == "10-vas"
        for entry in selections
    )
