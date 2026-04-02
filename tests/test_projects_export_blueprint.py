import os
import sys
import importlib
from pathlib import Path
from unittest.mock import patch

from flask import Flask

current_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.dirname(current_dir)
app_path = os.path.join(project_root, "app")
if app_path not in sys.path:
    sys.path.insert(0, app_path)

projects_export_bp = importlib.import_module(
    "src.web.blueprints.projects_export_blueprint"
).projects_export_bp


def test_projects_export_uses_fixed_internal_anonymization_settings(tmp_path):
    app = Flask(__name__)
    app.register_blueprint(projects_export_bp)

    project_dir = tmp_path / "study"
    project_dir.mkdir(parents=True, exist_ok=True)
    (project_dir / "project.json").write_text("{}", encoding="utf-8")

    called = {}

    def fake_export_project(**kwargs):
        called.update(kwargs)
        output_zip = kwargs["output_zip"]
        Path(output_zip).write_bytes(b"PK\x03\x04")
        return {"files_processed": 0, "files_anonymized": 0, "participant_count": 0}

    with patch("src.web.export_project.export_project", side_effect=fake_export_project):
        with app.test_client() as client:
            response = client.post(
                "/api/projects/export",
                json={
                    "project_path": str(project_dir),
                    "anonymize": True,
                    "mask_questions": False,
                    "include_derivatives": True,
                    "include_code": False,
                    "include_analysis": False,
                },
            )

    assert response.status_code == 200
    assert called["anonymize"] is True
    assert called["mask_questions"] is False
    assert called["id_length"] == 8
    assert called["deterministic"] is False
