"""The Template Editor picks its import file with the in-app picker (a server path);
this route hands the picked file's bytes back so the page can import it exactly like an upload."""

import importlib
import os
import sys
from pathlib import Path

import pytest
from flask import Flask

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "app"))


@pytest.fixture
def client():
    module = importlib.import_module("src.web.blueprints.tools_template_editor_blueprint")
    app = Flask(__name__, root_path=str(Path(__file__).resolve().parents[1] / "app"))
    app.secret_key = os.urandom(32)
    app.register_blueprint(module.tools_template_editor_bp)
    return app.test_client()


def test_returns_the_bytes_of_a_picked_import_file(client, tmp_path):
    source = tmp_path / "survey.lss"
    source.write_bytes(b"<document/>")

    response = client.get("/api/template-editor/read-source", query_string={"path": str(source)})

    assert response.status_code == 200
    assert response.data == b"<document/>"


@pytest.mark.parametrize("name", ["secrets.txt", "key.pem", "run.py"])
def test_refuses_files_the_import_cannot_read(client, tmp_path, name):
    source = tmp_path / name
    source.write_text("x")

    response = client.get("/api/template-editor/read-source", query_string={"path": str(source)})

    assert response.status_code == 400
    assert "error" in response.get_json()


def test_a_missing_file_says_so(client, tmp_path):
    response = client.get("/api/template-editor/read-source", query_string={"path": str(tmp_path / "gone.lss")})

    assert response.status_code == 404
