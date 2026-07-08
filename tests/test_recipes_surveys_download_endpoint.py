import os
import sys
from pathlib import Path

from flask import Flask

APP_ROOT = Path(__file__).resolve().parents[1] / "app"
if str(APP_ROOT) not in sys.path:
    sys.path.insert(0, str(APP_ROOT))

from src.web.blueprints.tools_recipes_surveys_handlers import (  # noqa: E402
    handle_download_recipes_output_file,
)


def _build_app() -> Flask:
    app = Flask(__name__, root_path=str(APP_ROOT))
    app.secret_key = os.urandom(32)

    @app.get("/api/recipes-surveys/download")
    def download_route():
        return handle_download_recipes_output_file()

    return app


def test_downloads_file_inside_derivatives(tmp_path):
    project = tmp_path / "proj"
    out_dir = project / "derivatives" / "survey" / "long_en"
    out_dir.mkdir(parents=True)
    out_file = out_dir / "scores.sav"
    out_file.write_bytes(b"fake-sav-bytes")

    app = _build_app()
    with app.test_client() as client:
        response = client.get(
            "/api/recipes-surveys/download",
            query_string={"dataset_path": str(project), "path": str(out_file)},
        )

    assert response.status_code == 200
    assert response.data == b"fake-sav-bytes"


def test_rejects_path_outside_derivatives(tmp_path):
    project = tmp_path / "proj"
    (project / "sourcedata").mkdir(parents=True)
    escaped_file = project / "sourcedata" / "secret.sav"
    escaped_file.write_bytes(b"should-not-be-servable")

    app = _build_app()
    with app.test_client() as client:
        response = client.get(
            "/api/recipes-surveys/download",
            query_string={"dataset_path": str(project), "path": str(escaped_file)},
        )

    assert response.status_code == 400


def test_rejects_traversal_outside_project(tmp_path):
    project = tmp_path / "proj"
    (project / "derivatives").mkdir(parents=True)
    outside_file = tmp_path / "outside.sav"
    outside_file.write_bytes(b"should-not-be-servable")

    app = _build_app()
    with app.test_client() as client:
        response = client.get(
            "/api/recipes-surveys/download",
            query_string={
                "dataset_path": str(project),
                "path": str(project / "derivatives" / ".." / ".." / "outside.sav"),
            },
        )

    assert response.status_code == 400


def test_missing_file_returns_404(tmp_path):
    project = tmp_path / "proj"
    (project / "derivatives").mkdir(parents=True)

    app = _build_app()
    with app.test_client() as client:
        response = client.get(
            "/api/recipes-surveys/download",
            query_string={
                "dataset_path": str(project),
                "path": str(project / "derivatives" / "missing.sav"),
            },
        )

    assert response.status_code == 404


def test_invalid_dataset_path_returns_400(tmp_path):
    app = _build_app()
    with app.test_client() as client:
        response = client.get(
            "/api/recipes-surveys/download",
            query_string={
                "dataset_path": str(tmp_path / "does-not-exist"),
                "path": str(tmp_path / "does-not-exist" / "derivatives" / "x.sav"),
            },
        )

    assert response.status_code == 400
