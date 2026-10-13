from flask import Flask, session

from src.web.blueprints import projects as projects_module


def _app():
    app = Flask(__name__)
    app.secret_key = "test"  # pragma: allowlist secret
    return app


def test_a_current_project_whose_folder_is_gone_is_cleared(tmp_path):
    with _app().test_request_context():
        session["current_project_path"] = str(tmp_path / "gone")
        session["current_project_name"] = "gone"

        current = projects_module.get_current_project()

        assert not current["path"]
        assert "current_project_path" not in session


def test_an_existing_current_project_is_kept(tmp_path):
    with _app().test_request_context():
        session["current_project_path"] = str(tmp_path)

        assert projects_module.get_current_project()["path"] == str(tmp_path)
