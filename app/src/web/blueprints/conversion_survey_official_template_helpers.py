"""Studio's side of the official-template check: save the upload, ask the backend (src.survey_input_checks)."""

import shutil
import tempfile
from pathlib import Path
from typing import Any

from flask import current_app, has_app_context
from werkzeug.utils import secure_filename

from src import survey_input_checks as _checks


def app_root() -> Path:
    return Path(current_app.root_path).parent if has_app_context() else Path(__file__).resolve().parents[4]


def resolve_official_survey_dir(project_path: str | None) -> Path | None:
    return _checks.resolve_official_survey_dir(project_path, app_root())


def infer_tasks_against_official_templates(
    *,
    uploaded_file,
    filename: str,
    project_path: str | None,
    id_column: str | None,
    session_column: str | None,
    sheet: str | int,
    duplicate_handling: str,
    separator_option: str,
) -> dict[str, Any]:
    tmp_dir = tempfile.mkdtemp(prefix="prism_survey_upload_")
    try:
        input_path = Path(tmp_dir) / secure_filename(filename)
        uploaded_file.save(str(input_path))
        return _checks.infer_tasks_against_official_templates(
            input_path=input_path,
            project_path=project_path,
            id_column=id_column,
            session_column=session_column,
            sheet=sheet,
            duplicate_handling=duplicate_handling,
            separator_option=separator_option,
            app_root=app_root(),
        )
    finally:
        shutil.rmtree(tmp_dir, ignore_errors=True)
