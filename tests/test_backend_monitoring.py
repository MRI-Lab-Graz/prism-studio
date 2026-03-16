import sys
import io
from pathlib import Path

from flask import Flask, request, session

# Ensure app package is importable as `src.*`
PROJECT_ROOT = Path(__file__).resolve().parent.parent
APP_PATH = PROJECT_ROOT / "app"
if str(APP_PATH) not in sys.path:
    sys.path.insert(0, str(APP_PATH))

from src.web.backend_monitoring import (  # noqa: E402
    _build_terminal_command,
    _build_validate_folder_terminal_command,
    emit_backend_request_action,
)


def test_build_validate_folder_terminal_command_full_flags():
    app = Flask(__name__)
    with app.test_request_context(
        "/validate_folder",
        method="POST",
        data={
            "folder_path": "/tmp/my dataset",
            "schema_version": "v0.1",
            "validation_mode": "bids",
            "bids_warnings": "true",
            "library_path": "/tmp/library path",
        },
    ):
        cmd = _build_validate_folder_terminal_command(request)

    assert cmd == (
        "python prism.py '/tmp/my dataset' --schema-version v0.1 "
        "--bids --no-prism --bids-warnings --library '/tmp/library path'"
    )


def test_emit_backend_request_action_includes_validator_command(capsys):
    app = Flask(__name__)

    def _noop_view():
        return "ok"

    app.add_url_rule(
        "/validate_folder",
        endpoint="validation.validate_folder",
        view_func=_noop_view,
        methods=["POST"],
    )

    with app.test_request_context(
        "/validate_folder",
        method="POST",
        data={
            "folder_path": "/tmp/ds",
            "schema_version": "stable",
            "validation_mode": "both",
            "bids_warnings": "false",
        },
    ):
        emit_backend_request_action(request, app_root=str(APP_PATH))

    captured = capsys.readouterr().out
    assert "[BACKEND-ACTION]" in captured
    assert "POST /validate_folder -> validate folder" in captured
    assert "cmd=python prism.py /tmp/ds --bids" in captured


def test_build_validate_folder_command_uses_session_project_path():
    app = Flask(__name__)
    app.secret_key = "test-secret"  # pragma: allowlist secret
    with app.test_request_context(
        "/validate_folder",
        method="POST",
        data={
            "folder_path": "",
            "validation_mode": "prism",
        },
    ):
        session["current_project_path"] = "/tmp/from-session"
        cmd = _build_validate_folder_terminal_command(request)

    assert cmd == "python prism.py /tmp/from-session"


def test_build_terminal_command_for_survey_convert_endpoint():
    app = Flask(__name__)

    def _noop_view():
        return "ok"

    app.add_url_rule(
        "/api/survey-convert",
        endpoint="conversion_survey.api_survey_convert",
        view_func=_noop_view,
        methods=["POST"],
    )

    with app.test_request_context(
        "/api/survey-convert",
        method="POST",
        data={
            "file": (io.BytesIO(b"x"), "T1.xlsx"),
            "id_column": "participant_id",
            "session_column": "session",
            "unknown": "ignore",
            "sheet": "0",
        },
        content_type="multipart/form-data",
    ):
        cmd = _build_terminal_command(request)

    assert cmd == (
        "python prism_tools.py survey convert --input T1.xlsx --output '<output-dir>' "
        "--id-column participant_id --session-column session --sheet 0 "
        "--unknown ignore --force"
    )


def test_emit_backend_request_action_includes_survey_convert_command(capsys):
    app = Flask(__name__)

    def _noop_view():
        return "ok"

    app.add_url_rule(
        "/api/survey-convert",
        endpoint="conversion_survey.api_survey_convert",
        view_func=_noop_view,
        methods=["POST"],
    )

    with app.test_request_context(
        "/api/survey-convert",
        method="POST",
        data={
            "file": (io.BytesIO(b"x"), "T1.xlsx"),
            "id_column": "participant_id",
        },
        content_type="multipart/form-data",
    ):
        emit_backend_request_action(request, app_root=str(APP_PATH))

    captured = capsys.readouterr().out
    assert "[BACKEND-ACTION]" in captured
    assert "POST /api/survey-convert" in captured
    assert "cmd=python prism_tools.py survey convert --input T1.xlsx" in captured


def test_survey_convert_command_uses_current_project_as_output_dir():
    app = Flask(__name__)
    app.secret_key = "test-secret"  # pragma: allowlist secret

    def _noop_view():
        return "ok"

    app.add_url_rule(
        "/api/survey-convert-preview",
        endpoint="conversion_survey.api_survey_convert_preview",
        view_func=_noop_view,
        methods=["POST"],
    )

    with app.test_request_context(
        "/api/survey-convert-preview",
        method="POST",
        data={
            "file": (io.BytesIO(b"x"), "T1.xlsx"),
            "id_column": "ID",
        },
        content_type="multipart/form-data",
    ):
        session["current_project_path"] = "/tmp/my-project"
        cmd = _build_terminal_command(request)

    assert "--output /tmp/my-project" in cmd


def test_emit_backend_request_action_includes_survey_check_templates_command(capsys):
    app = Flask(__name__)

    def _noop_view():
        return "ok"

    app.add_url_rule(
        "/api/survey-check-project-templates",
        endpoint="conversion_survey.api_survey_check_project_templates",
        view_func=_noop_view,
        methods=["POST"],
    )

    with app.test_request_context(
        "/api/survey-check-project-templates",
        method="POST",
        data={
            "excel": (io.BytesIO(b"x"), "T1.xlsx"),
            "id_column": "ID",
            "sheet": "0",
        },
        content_type="multipart/form-data",
    ):
        emit_backend_request_action(request, app_root=str(APP_PATH))

    captured = capsys.readouterr().out
    assert "POST /api/survey-check-project-templates" in captured
    assert (
        "cmd=python prism_tools.py survey convert --input T1.xlsx --output '<output-dir>' "
        "--dry-run --force --id-column ID --sheet 0"
    ) in captured


def test_emit_backend_request_action_includes_detect_columns_command(capsys):
    app = Flask(__name__)

    def _noop_view():
        return "ok"

    app.add_url_rule(
        "/api/detect-columns",
        endpoint="tools.detect_columns",
        view_func=_noop_view,
        methods=["POST"],
    )

    with app.test_request_context(
        "/api/detect-columns",
        method="POST",
        data={"file": (io.BytesIO(b"x"), "T1.xlsx")},
        content_type="multipart/form-data",
    ):
        emit_backend_request_action(request, app_root=str(APP_PATH))

    captured = capsys.readouterr().out
    assert "POST /api/detect-columns" in captured
    assert (
        "cmd=python prism_tools.py survey convert --input T1.xlsx --output '<output-dir>' "
        "--dry-run --force"
    ) in captured


def test_emit_backend_request_action_includes_participants_preview_command(capsys):
    app = Flask(__name__)

    def _noop_view():
        return "ok"

    app.add_url_rule(
        "/api/participants-preview",
        endpoint="conversion_participants.api_participants_preview",
        view_func=_noop_view,
        methods=["POST"],
    )

    with app.test_request_context(
        "/api/participants-preview",
        method="POST",
        data={
            "mode": "file",
            "sheet": "0",
            "id_column": "participant_id",
            "file": (io.BytesIO(b"x"), "participants.xlsx"),
        },
        content_type="multipart/form-data",
    ):
        emit_backend_request_action(request, app_root=str(APP_PATH))

    captured = capsys.readouterr().out
    assert "POST /api/participants-preview -> participants preview" in captured
    assert "endpoint=conversion_participants.api_participants_preview" in captured
    assert "cmd=curl -X POST" in captured
    assert "participants-preview" in captured
    assert "file=@participants.xlsx" in captured
    assert "id_column=participant_id" in captured


def test_emit_backend_request_action_includes_participants_detect_id_command(capsys):
    app = Flask(__name__)

    def _noop_view():
        return "ok"

    app.add_url_rule(
        "/api/participants-detect-id",
        endpoint="conversion_participants.api_participants_detect_id",
        view_func=_noop_view,
        methods=["POST"],
    )

    with app.test_request_context(
        "/api/participants-detect-id",
        method="POST",
        data={
            "sheet": "1",
            "file": (io.BytesIO(b"x"), "participants.tsv"),
        },
        content_type="multipart/form-data",
    ):
        emit_backend_request_action(request, app_root=str(APP_PATH))

    captured = capsys.readouterr().out
    assert "POST /api/participants-detect-id -> participants detect id" in captured
    assert "endpoint=conversion_participants.api_participants_detect_id" in captured
    assert "cmd=curl -X POST" in captured
    assert "participants-detect-id" in captured
    assert "file=@participants.tsv" in captured
    assert "sheet=1" in captured


def test_emit_backend_request_action_includes_participants_convert_command(capsys):
    app = Flask(__name__)

    def _noop_view():
        return "ok"

    app.add_url_rule(
        "/api/participants-convert",
        endpoint="conversion_participants.api_participants_convert",
        view_func=_noop_view,
        methods=["POST"],
    )

    with app.test_request_context(
        "/api/participants-convert",
        method="POST",
        data={
            "mode": "file",
            "sheet": "0",
            "id_column": "participant_id",
            "force_overwrite": "true",
            "neurobagel_schema": '{"sex": {"Description": "Biological sex"}}',
            "file": (io.BytesIO(b"x"), "participants.xlsx"),
        },
        content_type="multipart/form-data",
    ):
        emit_backend_request_action(request, app_root=str(APP_PATH))

    captured = capsys.readouterr().out
    assert "POST /api/participants-convert -> participants convert" in captured
    assert "endpoint=conversion_participants.api_participants_convert" in captured
    assert "cmd=curl -X POST" in captured
    assert "participants-convert" in captured
    assert "file=@participants.xlsx" in captured
    assert "force_overwrite=true" in captured
    assert "id_column=participant_id" in captured
    assert "neurobagel_schema=<json>" in captured


def test_emit_backend_request_action_includes_biometrics_detect_command(capsys):
    app = Flask(__name__)

    def _noop_view():
        return "ok"

    app.add_url_rule(
        "/api/biometrics-detect",
        endpoint="conversion.api_biometrics_detect",
        view_func=_noop_view,
        methods=["POST"],
    )

    with app.test_request_context(
        "/api/biometrics-detect",
        method="POST",
        data={
            "sheet": "0",
            "data": (io.BytesIO(b"x"), "bio.xlsx"),
        },
        content_type="multipart/form-data",
    ):
        emit_backend_request_action(request, app_root=str(APP_PATH))

    captured = capsys.readouterr().out
    assert "POST /api/biometrics-detect -> biometrics detect" in captured
    assert "cmd=curl -X POST" in captured
    assert "file=@bio.xlsx" not in captured
    assert "data=@bio.xlsx" in captured
    assert "sheet=0" in captured


def test_emit_backend_request_action_includes_biometrics_convert_command(capsys):
    app = Flask(__name__)

    def _noop_view():
        return "ok"

    app.add_url_rule(
        "/api/biometrics-convert",
        endpoint="conversion.api_biometrics_convert",
        view_func=_noop_view,
        methods=["POST"],
    )

    with app.test_request_context(
        "/api/biometrics-convert",
        method="POST",
        data={
            "session": "1",
            "dry_run": "true",
            "validate": "true",
            "tasks[]": ["grip", "balance"],
            "data": (io.BytesIO(b"x"), "biometrics.xlsx"),
        },
        content_type="multipart/form-data",
    ):
        emit_backend_request_action(request, app_root=str(APP_PATH))

    captured = capsys.readouterr().out
    assert "POST /api/biometrics-convert -> biometrics convert" in captured
    assert "cmd=curl -X POST" in captured
    assert "data=@biometrics.xlsx" in captured
    assert "session=1" in captured
    assert "dry_run=true" in captured
    assert "tasks[]=grip" in captured
    assert "tasks[]=balance" in captured


def test_emit_backend_request_action_includes_physio_convert_command(capsys):
    app = Flask(__name__)

    def _noop_view():
        return "ok"

    app.add_url_rule(
        "/api/physio-convert",
        endpoint="conversion.api_physio_convert",
        view_func=_noop_view,
        methods=["POST"],
    )

    with app.test_request_context(
        "/api/physio-convert",
        method="POST",
        data={
            "task": "rest",
            "sampling_rate": "256",
            "raw": (io.BytesIO(b"x"), "signal.raw"),
        },
        content_type="multipart/form-data",
    ):
        emit_backend_request_action(request, app_root=str(APP_PATH))

    captured = capsys.readouterr().out
    assert "POST /api/physio-convert -> physio convert" in captured
    assert "cmd=curl -X POST" in captured
    assert "raw=@signal.raw" in captured
    assert "task=rest" in captured
    assert "sampling_rate=256" in captured


def test_emit_backend_request_action_includes_batch_convert_start_command(capsys):
    app = Flask(__name__)

    def _noop_view():
        return "ok"

    app.add_url_rule(
        "/api/batch-convert-start",
        endpoint="conversion.api_batch_convert_start",
        view_func=_noop_view,
        methods=["POST"],
    )

    with app.test_request_context(
        "/api/batch-convert-start",
        method="POST",
        data={
            "folder_path": "C:/data/physio",
            "dataset_name": "Physio Dataset",
            "modality": "physio",
            "save_to_project": "true",
            "dest_root": "rawdata",
            "dry_run": "false",
        },
    ):
        emit_backend_request_action(request, app_root=str(APP_PATH))

    captured = capsys.readouterr().out
    assert "POST /api/batch-convert-start -> batch convert start" in captured
    assert "cmd=curl -X POST" in captured
    assert "folder_path=C:/data/physio" in captured
    assert "dataset_name=Physio Dataset" in captured
    assert "modality=physio" in captured


def test_emit_backend_request_action_includes_physio_rename_command(capsys):
    app = Flask(__name__)

    def _noop_view():
        return "ok"

    app.add_url_rule(
        "/api/physio-rename",
        endpoint="conversion.api_physio_rename",
        view_func=_noop_view,
        methods=["POST"],
    )

    with app.test_request_context(
        "/api/physio-rename",
        method="POST",
        data={
            "pattern": "(.*)",
            "replacement": "sub-01_task-rest_physio",
            "dry_run": "true",
            "organize": "true",
            "modality": "physio",
            "filenames[]": ["input1.raw"],
            "source_paths[]": ["subj1/session1/input1.raw"],
        },
    ):
        emit_backend_request_action(request, app_root=str(APP_PATH))

    captured = capsys.readouterr().out
    assert "POST /api/physio-rename -> physio rename" in captured
    assert "cmd=curl -X POST" in captured
    assert "pattern=(.*)" in captured
    assert "replacement=sub-01_task-rest_physio" in captured
    assert "filenames[]=input1.raw" in captured
    assert "source_paths[]=subj1/session1/input1.raw" in captured


def test_emit_backend_request_action_includes_save_participant_mapping_command(capsys):
    app = Flask(__name__)

    def _noop_view():
        return "ok"

    app.add_url_rule(
        "/api/save-participant-mapping",
        endpoint="conversion_participants.save_participant_mapping",
        view_func=_noop_view,
        methods=["POST"],
    )

    with app.test_request_context(
        "/api/save-participant-mapping",
        method="POST",
        json={
            "mapping": {"mappings": {"age": {"source_column": "Age"}}},
            "library_path": "C:/library",
        },
    ):
        emit_backend_request_action(request, app_root=str(APP_PATH))

    captured = capsys.readouterr().out
    assert "POST /api/save-participant-mapping -> save participant mapping" in captured
    assert "cmd=curl -X POST" in captured
    assert "Content-Type: application/json" in captured
    assert '{"mapping":"<object>","library_path":"<path>"}' in captured
