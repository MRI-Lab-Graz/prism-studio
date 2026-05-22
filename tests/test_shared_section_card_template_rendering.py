from __future__ import annotations

import os
import sys
from pathlib import Path

from flask import Blueprint, Flask, render_template


APP_ROOT = Path(__file__).resolve().parents[1] / "app"
if str(APP_ROOT) not in sys.path:
    sys.path.insert(0, str(APP_ROOT))

from src.web.utils import endpoint_exists


def _build_template_app() -> Flask:
    app = Flask(
        __name__,
        root_path=str(APP_ROOT),
        template_folder="templates",
        static_folder="static",
    )
    app.secret_key = os.urandom(32)

    projects_bp = Blueprint("projects", __name__)
    validation_bp = Blueprint("validation", __name__)
    template_editor_bp = Blueprint("tools_template_editor", __name__)
    json_editor_bp = Blueprint("json_editor", __name__)

    @app.context_processor
    def inject_template_context():
        return {
            "endpoint_exists": endpoint_exists,
            "current_project": {"path": None, "name": None, "icon": None},
            "prism_static_asset_token": "test-token",
            "prism_studio_version": "test",
            "latest_prism_studio_version": "test",
            "latest_prism_studio_release_url": "https://example.invalid/releases/latest",
            "prism_studio_update_available": False,
        }

    @app.route("/")
    def index():
        return render_template("home.html")

    @app.route("/specifications")
    def specifications():
        return render_template("specifications.html")

    @app.route("/assets/prism-logo")
    def prism_logo():
        return "logo"

    @projects_bp.route("/projects")
    def projects_page():
        return render_template(
            "projects.html",
            current_project={"path": None, "name": None, "icon": None},
            modalities=[],
            schema_versions=["stable"],
            default_schema_version="stable",
        )

    @validation_bp.route("/validate")
    def validate_dataset():
        return render_template(
            "index.html",
            current_project={"path": None, "name": None, "icon": None},
            schema_versions=["stable"],
            default_library_path="",
        )

    @validation_bp.route("/upload", methods=["POST"])
    def upload_dataset():
        return "ok"

    @validation_bp.route("/validate_folder", methods=["POST"])
    def validate_folder():
        return "ok"

    @template_editor_bp.route("/template-editor")
    def template_editor():
        return "template-editor"

    @json_editor_bp.route("/editor")
    def editor_index():
        return "editor"

    app.register_blueprint(projects_bp)
    app.register_blueprint(validation_bp)
    app.register_blueprint(template_editor_bp)
    app.register_blueprint(json_editor_bp)
    return app


def test_home_page_renders_shared_section_cards() -> None:
    app = _build_template_app()

    with app.test_client() as client:
        response = client.get("/")

    assert response.status_code == 200
    assert b"Why Researchers Use PRISM Studio" in response.data
    assert b"A Concrete Before And After" in response.data
    assert b"One Structure For Multimodal Studies" in response.data


def test_validator_page_renders_shared_section_card_shell() -> None:
    app = _build_template_app()

    with app.test_client() as client:
        response = client.get("/validate")

    assert response.status_code == 200
    assert b"Dataset Validation" in response.data
    assert b"Start Validation" in response.data
    assert b"validationProgressPanel" in response.data


def test_projects_page_renders_shared_path_pickers() -> None:
    app = _build_template_app()

    with app.test_client() as client:
        response = client.get("/projects")

    assert response.status_code == 200
    assert b"Project Manager" in response.data
    assert b'id="projectPath"' in response.data
    assert b'id="initBidsPath"' in response.data
    assert b'id="initBidsRemoteUrl"' in response.data
    assert b'id="initBidsClonePath"' in response.data
    assert b'id="existingPath"' in response.data