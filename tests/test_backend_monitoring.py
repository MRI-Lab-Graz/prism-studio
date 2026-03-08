import sys
from pathlib import Path

from flask import Flask, request, session


# Ensure app package is importable as `src.*`
PROJECT_ROOT = Path(__file__).resolve().parent.parent
APP_PATH = PROJECT_ROOT / "app"
if str(APP_PATH) not in sys.path:
    sys.path.insert(0, str(APP_PATH))

from src.web.backend_monitoring import (  # noqa: E402
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
    assert "POST /validate_folder -> validation.validate folder" in captured
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
