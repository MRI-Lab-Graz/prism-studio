from __future__ import annotations

import importlib
import os
import sys
from pathlib import Path

from flask import Flask, session


def _build_app() -> Flask:
    app_root = Path(__file__).resolve().parents[1] / "app"
    if str(app_root) not in sys.path:
        sys.path.insert(0, str(app_root))

    app = Flask(__name__, root_path=str(app_root))
    app.secret_key = os.urandom(32)
    return app


def _extract_template_info(path: str, filename: str, source: str | None = None):
    return {
        "path": path,
        "filename": filename,
        "source": source,
        "detected_languages": ["en"],
    }


def test_list_library_files_merged_can_target_explicit_project_path(tmp_path):
    app = _build_app()
    handlers = importlib.import_module("src.web.blueprints.tools_library_handlers")

    primary_project = tmp_path / "primary"
    target_project = tmp_path / "target"
    (primary_project / "code" / "library" / "survey").mkdir(parents=True)
    (target_project / "code" / "library" / "survey").mkdir(parents=True)
    (
        primary_project / "code" / "library" / "survey" / "survey-primary.json"
    ).write_text("{}", encoding="utf-8")
    (target_project / "code" / "library" / "survey" / "survey-target.json").write_text(
        "{}", encoding="utf-8"
    )

    with app.test_request_context(
        f"/api/list-library-files-merged?project_path={target_project}"
    ):
        session["current_project_path"] = str(primary_project)
        response = handlers.handle_list_library_files_merged(
            extract_template_info=_extract_template_info,
            global_survey_library_root=lambda: None,
        )

    assert response.status_code == 200
    payload = response.get_json()
    assert [item["filename"] for item in payload["survey"]] == ["survey-target.json"]
    assert payload["sources"]["project_library_path"] == str(
        target_project / "code" / "library"
    )
    assert payload["sources"]["project_library_exists"] is True


def test_list_library_files_merged_normalizes_project_json_session_path(tmp_path):
    app = _build_app()
    handlers = importlib.import_module("src.web.blueprints.tools_library_handlers")

    project_root = tmp_path / "demo-project"
    (project_root / "code" / "library" / "survey").mkdir(parents=True)
    (project_root / "code" / "library" / "survey" / "survey-demo.json").write_text(
        "{}", encoding="utf-8"
    )
    (project_root / "project.json").write_text("{}", encoding="utf-8")

    with app.test_request_context("/api/list-library-files-merged"):
        session["current_project_path"] = str(project_root / "project.json")
        response = handlers.handle_list_library_files_merged(
            extract_template_info=_extract_template_info,
            global_survey_library_root=lambda: None,
        )

    assert response.status_code == 200
    payload = response.get_json()
    assert payload["sources"]["project_library_path"] == str(
        project_root / "code" / "library"
    )
    assert payload["sources"]["project_library_exists"] is True
    assert [item["filename"] for item in payload["survey"]] == ["survey-demo.json"]


def test_list_library_files_merged_empty_explicit_project_path_skips_session_fallback(
    tmp_path,
):
    app = _build_app()
    handlers = importlib.import_module("src.web.blueprints.tools_library_handlers")

    primary_project = tmp_path / "primary"
    (primary_project / "code" / "library" / "survey").mkdir(parents=True)
    (
        primary_project / "code" / "library" / "survey" / "survey-primary.json"
    ).write_text("{}", encoding="utf-8")

    with app.test_request_context("/api/list-library-files-merged?project_path="):
        session["current_project_path"] = str(primary_project)
        response = handlers.handle_list_library_files_merged(
            extract_template_info=_extract_template_info,
            global_survey_library_root=lambda: None,
        )

    assert response.status_code == 200
    payload = response.get_json()
    assert payload["survey"] == []
    assert payload["sources"]["project_library_path"] is None
    assert payload["sources"]["project_library_exists"] is False
