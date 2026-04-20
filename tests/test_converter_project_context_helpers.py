import json
import sys
from pathlib import Path

from flask import Flask


APP_ROOT = Path(__file__).resolve().parents[1] / "app"
if str(APP_ROOT) not in sys.path:
    sys.path.insert(0, str(APP_ROOT))

from src.web.blueprints.conversion_survey_handlers import api_survey_check_project_templates
from src.web.blueprints.projects_sessions_handlers import (
    handle_get_sessions_declared,
    handle_register_session,
)
from src.web.blueprints.projects_participants_handlers import (
    handle_get_participants_schema,
    handle_save_participants_schema,
)
from src.web.blueprints.projects_sourcedata_handlers import (
    handle_get_sourcedata_file,
    handle_get_sourcedata_files,
)


def _write_project_json(project_root: Path, payload: dict) -> None:
    project_root.mkdir(parents=True, exist_ok=True)
    (project_root / "project.json").write_text(json.dumps(payload), encoding="utf-8")


def _read_project_json(project_root: Path):
    project_json_path = project_root / "project.json"
    if not project_json_path.exists():
        return None
    return json.loads(project_json_path.read_text(encoding="utf-8"))


def _build_app(current_project_path: str) -> Flask:
    app = Flask(__name__, root_path=str(APP_ROOT))
    app.secret_key = "test-secret"

    def get_current_project():
        return {"path": current_project_path, "name": "Current Project"}

    @app.get("/api/projects/sessions/declared")
    def sessions_declared_route():
        return handle_get_sessions_declared(
            get_current_project=get_current_project,
            read_project_json=_read_project_json,
        )

    @app.post("/api/projects/sessions/register")
    def register_session_route():
        return handle_register_session(
            get_current_project=get_current_project,
            read_project_json=_read_project_json,
            write_project_json=_write_project_json,
        )

    @app.get("/api/projects/sourcedata-files")
    def sourcedata_files_route():
        return handle_get_sourcedata_files(get_current_project=get_current_project)

    @app.get("/api/projects/sourcedata-file")
    def sourcedata_file_route():
        return handle_get_sourcedata_file(get_current_project=get_current_project)

    @app.get("/api/projects/participants")
    def participants_schema_route():
        return handle_get_participants_schema(
            get_current_project=get_current_project,
            get_bids_file_path=lambda project_root, filename: project_root / filename,
        )

    @app.post("/api/projects/participants")
    def participants_schema_save_route():
        return handle_save_participants_schema(
            get_current_project=get_current_project,
            get_bids_file_path=lambda project_root, filename: project_root / filename,
        )

    app.add_url_rule(
        "/api/survey-check-project-templates",
        view_func=api_survey_check_project_templates,
        methods=["POST"],
    )

    return app


def test_sessions_declared_prefers_explicit_project_path(tmp_path):
    current_project = tmp_path / "project-current"
    other_project = tmp_path / "project-other"
    _write_project_json(current_project, {"Sessions": [{"id": "ses-01", "label": "Current"}]})
    _write_project_json(other_project, {"Sessions": [{"id": "ses-02", "label": "Other"}]})

    app = _build_app(str(current_project))

    with app.test_client() as client:
        response = client.get(
            "/api/projects/sessions/declared",
            query_string={"project_path": str(other_project)},
        )

    assert response.status_code == 200
    assert response.get_json() == {
        "sessions": [{"id": "ses-02", "label": "Other"}]
    }


def test_register_session_prefers_explicit_project_path(tmp_path):
    current_project = tmp_path / "project-current"
    other_project = tmp_path / "project-other"
    _write_project_json(current_project, {"Sessions": [], "TaskDefinitions": {}})
    _write_project_json(other_project, {"Sessions": [], "TaskDefinitions": {}})

    app = _build_app(str(current_project))

    with app.test_client() as client:
        response = client.post(
            "/api/projects/sessions/register",
            json={
                "project_path": str(other_project),
                "session_id": "1",
                "tasks": ["demo"],
                "modality": "survey",
                "source_file": "input.xlsx",
                "converter": "survey-xlsx",
            },
        )

    assert response.status_code == 200
    current_payload = _read_project_json(current_project)
    other_payload = _read_project_json(other_project)
    assert current_payload["Sessions"] == []
    assert other_payload["Sessions"][0]["id"] == "ses-01"
    assert other_payload["TaskDefinitions"]["demo"]["modality"] == "survey"


def test_sourcedata_helpers_prefer_explicit_project_path(tmp_path):
    current_project = tmp_path / "project-current"
    other_project = tmp_path / "project-other"
    _write_project_json(current_project, {})
    _write_project_json(other_project, {})

    current_sourcedata = current_project / "sourcedata"
    other_sourcedata = other_project / "sourcedata"
    current_sourcedata.mkdir()
    other_sourcedata.mkdir()
    (current_sourcedata / "current.tsv").write_text("current", encoding="utf-8")
    (other_sourcedata / "other.tsv").write_text("other", encoding="utf-8")

    app = _build_app(str(current_project))

    with app.test_client() as client:
        list_response = client.get(
            "/api/projects/sourcedata-files",
            query_string={"project_path": str(other_project)},
        )
        file_response = client.get(
            "/api/projects/sourcedata-file",
            query_string={"project_path": str(other_project), "name": "other.tsv"},
        )

    assert list_response.status_code == 200
    list_payload = list_response.get_json()
    assert list_payload["sourcedata_exists"] is True
    assert [item["name"] for item in list_payload["files"]] == ["other.tsv"]
    assert file_response.status_code == 200
    assert file_response.get_data(as_text=True) == "other"


def test_survey_check_project_templates_prefers_explicit_project_path(tmp_path):
    current_project = tmp_path / "project-current"
    other_project = tmp_path / "project-other"
    _write_project_json(current_project, {})
    _write_project_json(other_project, {})

    app = _build_app(str(current_project))

    with app.test_client() as client:
        with client.session_transaction() as sess:
            sess["current_project_path"] = str(current_project)

        response = client.post(
            "/api/survey-check-project-templates",
            data={"project_path": str(other_project)},
        )

    assert response.status_code == 200
    payload = response.get_json()
    assert payload["ok"] is True
    assert payload["template_dir"] == str(other_project / "code" / "library" / "survey")


def test_participants_schema_helpers_prefer_explicit_project_path(tmp_path):
    current_project = tmp_path / "project-current"
    other_project = tmp_path / "project-other"
    _write_project_json(current_project, {})
    _write_project_json(other_project, {})
    (current_project / "participants.json").write_text(
        json.dumps({"current_only": {"Description": "current"}}),
        encoding="utf-8",
    )
    (other_project / "participants.json").write_text(
        json.dumps({"other_only": {"Description": "other"}}),
        encoding="utf-8",
    )

    app = _build_app(str(current_project))

    with app.test_client() as client:
        get_response = client.get(
            "/api/projects/participants",
            query_string={"project_path": str(other_project)},
        )
        save_response = client.post(
            "/api/projects/participants",
            json={
                "project_path": str(other_project),
                "schema": {"age": {"Description": "Age in years"}},
            },
        )

    assert get_response.status_code == 200
    get_payload = get_response.get_json()
    assert get_payload["schema"] == {"other_only": {"Description": "other"}}
    assert save_response.status_code == 200

    current_schema = json.loads((current_project / "participants.json").read_text(encoding="utf-8"))
    other_schema = json.loads((other_project / "participants.json").read_text(encoding="utf-8"))
    assert current_schema == {"current_only": {"Description": "current"}}
    assert "participant_id" in other_schema
    assert other_schema["age"]["Description"] == "Age in years"