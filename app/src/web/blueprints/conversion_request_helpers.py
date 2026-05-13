from pathlib import Path

from flask import request, session
from src.survey_workflow_service import SurveyWorkflowStageService

from .conversion_utils import require_existing_project_root, resolve_existing_project_root


class LocalPathUpload:
    """Minimal upload-like wrapper backed by a local filesystem path."""

    def __init__(self, source_path: Path):
        self._source_path = source_path
        self.filename = source_path.name

    def save(self, destination: str):
        import shutil

        shutil.copy2(self._source_path, destination)


def resolve_uploaded_or_source_file(
    *,
    field_names: tuple[str, ...],
    missing_input_message: str = "Missing input file",
):
    for field_name in field_names:
        upload = request.files.get(field_name)
        if upload is not None and upload.filename:
            return upload, None

    source_file_path = (
        (request.form.get("source_file_path") or "").strip()
        or (request.args.get("source_file_path") or "").strip()
    )
    if not source_file_path:
        return None, missing_input_message

    source_path = Path(source_file_path).expanduser().resolve()
    if not source_path.exists() or not source_path.is_file():
        return None, f"File not found: {source_file_path}"

    return LocalPathUpload(source_path), None


def resolve_requested_project_root(
    *,
    require_project: bool,
    missing_message: str,
    missing_path_message: str,
) -> Path | None:
    requested_project_path = (
        (request.form.get("project_path") or request.args.get("project_path") or "")
        .strip()
        or None
    )

    if requested_project_path:
        return require_existing_project_root(
            requested_project_path,
            missing_message=missing_message,
            missing_path_message=missing_path_message,
        )

    session_project_path = session.get("current_project_path")
    if require_project:
        return require_existing_project_root(
            session_project_path,
            missing_message=missing_message,
            missing_path_message=missing_path_message,
        )

    return resolve_existing_project_root(session_project_path)


def format_workflow_preparation_stale_response(
    payload: dict[str, object],
    *,
    log_messages: list[dict[str, str]] | None = None,
) -> dict[str, object]:
    return SurveyWorkflowStageService.format_workflow_preparation_stale_response(
        payload=payload,
        prepared_workflow=SurveyWorkflowStageService.parse_prepared_workflow_flag(
            request.form.get("prepared_workflow")
        ),
        log_messages=log_messages,
    )