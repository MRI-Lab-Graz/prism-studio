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


def test_build_terminal_command_for_survey_convert_includes_template_versions():
    app = Flask(__name__)

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
            "template_versions": '{"wellbeing":"7-likert","pss":"short"}',
        },
        content_type="multipart/form-data",
    ):
        cmd = _build_terminal_command(request)

    assert cmd == (
        "python prism_tools.py survey convert --input T1.xlsx --output '<output-dir>' "
        "--template-version pss=short --template-version wellbeing=7-likert --dry-run --force"
    )


def test_build_terminal_command_for_survey_convert_includes_run_specific_template_versions():
    app = Flask(__name__)

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
            "template_versions": '[{"task":"wellbeing","run":2,"version":"10-vas"}]',
        },
        content_type="multipart/form-data",
    ):
        cmd = _build_terminal_command(request)

    assert cmd == (
        "python prism_tools.py survey convert --input T1.xlsx --output '<output-dir>' "
        "--template-version 'wellbeing;run=2=10-vas' --dry-run --force"
    )


def test_build_terminal_command_for_survey_convert_coerces_language_map_versions():
    app = Flask(__name__)

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
            "template_versions": '[{"task":"wellbeing","session":"ses-pre","run":1,"version":{"en":"10-likert","de":"10-likert"}}]',
        },
        content_type="multipart/form-data",
    ):
        cmd = _build_terminal_command(request)

    assert cmd == (
        "python prism_tools.py survey convert --input T1.xlsx --output '<output-dir>' "
        "--template-version 'wellbeing;session=ses-pre;run=1=10-likert' --dry-run --force"
    )


def test_build_terminal_command_for_survey_convert_accepts_alphanumeric_run_entities():
    app = Flask(__name__)

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
            "template_versions": '[{"task":"wellbeing","session":"ses-pre","run":"run-A","version":"10-vas"}]',
        },
        content_type="multipart/form-data",
    ):
        cmd = _build_terminal_command(request)

    assert cmd == (
        "python prism_tools.py survey convert --input T1.xlsx --output '<output-dir>' "
        "--template-version 'wellbeing;session=ses-pre;run=A=10-vas' --dry-run --force"
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


def test_wide_to_long_preview_command_uses_prism_cli():
    app = Flask(__name__)

    def _noop_view():
        return "ok"

    app.add_url_rule(
        "/api/file-management/wide-to-long-preview",
        endpoint="tools.api_file_management_wide_to_long_preview",
        view_func=_noop_view,
        methods=["POST"],
    )

    with app.test_request_context(
        "/api/file-management/wide-to-long-preview",
        method="POST",
        data={
            "data": (io.BytesIO(b"x"), "survey.xlsx"),
            "session_column": "session",
            "session_indicators": "T1_,T2_,T3_",
            "session_value_map": "T1_:pre,T2_:post",
        },
        content_type="multipart/form-data",
    ):
        cmd = _build_terminal_command(request)

    assert cmd == (
        "python prism.py wide-to-long --input survey.xlsx --session-column session "
        "--session-indicators T1_,T2_,T3_ --session-map T1_:pre,T2_:post --inspect-only"
    )


def test_wide_to_long_convert_command_uses_prism_cli():
    app = Flask(__name__)

    def _noop_view():
        return "ok"

    app.add_url_rule(
        "/api/file-management/wide-to-long",
        endpoint="tools.api_file_management_wide_to_long",
        view_func=_noop_view,
        methods=["POST"],
    )

    with app.test_request_context(
        "/api/file-management/wide-to-long",
        method="POST",
        data={
            "data": (io.BytesIO(b"x"), "survey.xlsx"),
            "session_column": "session",
            "session_indicators": "T1_,T2_,T3_",
        },
        content_type="multipart/form-data",
    ):
        cmd = _build_terminal_command(request)

    assert cmd == (
        "python prism.py wide-to-long --input survey.xlsx --session-column session "
        "--session-indicators T1_,T2_,T3_ --output '<output-file>'"
    )


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
    expected_input = str(Path("participants.xlsx").resolve())
    assert "POST /api/participants-preview -> participants preview" in captured
    assert "endpoint=conversion_participants.api_participants_preview" in captured
    assert "cmd=python prism_tools.py participants preview" in captured
    assert f"--input {expected_input}" in captured
    assert "--sheet 0" in captured
    assert "--id-column participant_id" in captured
    assert "--json" in captured


def test_participants_preview_command_includes_session_project_path(capsys):
    app = Flask(__name__)
    app.secret_key = "test_secret"  # pragma: allowlist secret

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
            "file": (io.BytesIO(b"x"), "participants.xlsx"),
        },
        content_type="multipart/form-data",
    ):
        session["current_project_path"] = "/tmp/demo-project/project.json"
        emit_backend_request_action(request, app_root=str(APP_PATH))

    captured = capsys.readouterr().out
    assert "--project /tmp/demo-project/project.json" in captured


def test_emit_backend_request_action_includes_environment_preview_command(capsys):
    app = Flask(__name__)
    app.secret_key = "test_secret"  # pragma: allowlist secret

    def _noop_view():
        return "ok"

    app.add_url_rule(
        "/api/environment-preview",
        endpoint="conversion.api_environment_preview",
        view_func=_noop_view,
        methods=["POST"],
    )

    with app.test_request_context(
        "/api/environment-preview",
        method="POST",
        data={
            "separator": "auto",
            "file": (
                io.BytesIO(
                    b"timestamp,participant_id,session\n2026-03-24 10:00:00,sub-01,ses-01\n"
                ),
                "environment.csv",
            ),
        },
        content_type="multipart/form-data",
    ):
        session["current_project_path"] = "/tmp/demo-project"
        emit_backend_request_action(request, app_root=str(APP_PATH))

    captured = capsys.readouterr().out
    expected_input = str((Path("/tmp/demo-project") / "environment.csv").resolve())
    assert "POST /api/environment-preview -> environment preview" in captured
    assert "endpoint=conversion.api_environment_preview" in captured
    assert "cmd=python prism_tools.py environment preview" in captured
    assert f"--input {expected_input}" in captured
    assert "--project /tmp/demo-project" in captured
    assert "--separator auto" in captured
    assert "--json" in captured


def test_emit_backend_request_action_includes_environment_convert_command(capsys):
    app = Flask(__name__)
    app.secret_key = "test_secret"  # pragma: allowlist secret

    def _noop_view():
        return "ok"

    app.add_url_rule(
        "/api/environment-convert",
        endpoint="conversion.api_environment_convert",
        view_func=_noop_view,
        methods=["POST"],
    )

    with app.test_request_context(
        "/api/environment-convert",
        method="POST",
        data={
            "separator": "auto",
            "timestamp_col": "timestamp",
            "participant_col": "participant_id",
            "session_col": "session",
            "lat": "47.0667",
            "lon": "15.45",
            "pilot_random_subject": "true",
            "file": (
                io.BytesIO(
                    b"timestamp,participant_id,session\n2026-03-24 10:00:00,sub-01,ses-01\n"
                ),
                "environment.csv",
            ),
        },
        content_type="multipart/form-data",
    ):
        session["current_project_path"] = "/tmp/demo-project"
        emit_backend_request_action(request, app_root=str(APP_PATH))

    captured = capsys.readouterr().out
    expected_input = str((Path("/tmp/demo-project") / "environment.csv").resolve())
    assert "POST /api/environment-convert -> environment convert" in captured
    assert "endpoint=conversion.api_environment_convert" in captured
    assert "cmd=python prism_tools.py environment convert" in captured
    assert f"--input {expected_input}" in captured
    assert "--project /tmp/demo-project" in captured
    assert "--timestamp-col timestamp" in captured
    assert "--participant-col participant_id" in captured
    assert "--session-col session" in captured
    assert "--lat 47.0667" in captured
    assert "--lon 15.45" in captured
    assert "--pilot-random-subject" in captured
    assert "--json" in captured


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
    expected_input = str(Path("participants.tsv").resolve())
    assert "POST /api/participants-detect-id -> participants detect id" in captured
    assert "endpoint=conversion_participants.api_participants_detect_id" in captured
    assert "cmd=python prism_tools.py participants detect-id" in captured
    assert f"--input {expected_input}" in captured
    assert "--sheet 1" in captured
    assert "--json" in captured


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
    expected_input = str(Path("participants.xlsx").resolve())
    assert "POST /api/participants-convert -> participants convert" in captured
    assert "endpoint=conversion_participants.api_participants_convert" in captured
    assert "cmd=python prism_tools.py participants convert" in captured
    assert f"--input {expected_input}" in captured
    assert "--sheet 0" in captured
    assert "--id-column participant_id" in captured
    assert "--project '<project-path>'" in captured
    assert "--force" in captured
    assert "--json" in captured


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
    assert "cmd=python prism_tools.py biometrics detect" in captured
    assert "bio.xlsx" in captured
    assert "--library" in captured


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
    assert "cmd=python prism_tools.py biometrics convert" in captured
    assert "biometrics.xlsx" in captured
    assert "--session" in captured
    assert "--tasks" in captured
    assert "grip" in captured
    assert "balance" in captured


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
    assert "cmd=python prism_tools.py convert physio" in captured
    assert "signal.raw" in captured
    assert "--task" in captured
    assert "rest" in captured
    assert "--sampling-rate" in captured
    assert "256" in captured
    assert "--output" in captured


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
    assert "cmd=python prism_tools.py physio batch-convert" in captured
    assert "C:/data/physio" in captured
    assert "--modality" in captured
    assert "physio" in captured


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
    assert "cmd=python prism_tools.py participants save-mapping" in captured
    assert "--mapping-json" in captured
    assert "--library-path C:/library" in captured
    assert "--json" in captured


def test_emit_backend_request_action_includes_participants_dataset_preview_command(
    capsys,
):
    app = Flask(__name__)
    app.secret_key = "test_secret"  # pragma: allowlist secret

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
            "mode": "dataset",
            "extract_from_survey": "false",
            "extract_from_biometrics": "true",
        },
    ):
        session["current_project_path"] = "/tmp/demo-project/project.json"
        emit_backend_request_action(request, app_root=str(APP_PATH))

    captured = capsys.readouterr().out
    assert "POST /api/participants-preview -> participants preview" in captured
    assert "cmd=python prism_tools.py participants preview --mode dataset" in captured
    assert "--project /tmp/demo-project/project.json" in captured
    assert "--no-extract-from-survey" in captured
    assert "--json" in captured


def test_emit_backend_request_action_includes_participants_dataset_convert_command(
    capsys,
):
    app = Flask(__name__)
    app.secret_key = "test_secret"  # pragma: allowlist secret

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
            "mode": "dataset",
            "force_overwrite": "true",
            "extract_from_survey": "true",
            "extract_from_biometrics": "false",
            "neurobagel_schema": '{"participant_id": {"Description": "Participant"}}',
        },
    ):
        session["current_project_path"] = "/tmp/demo-project"
        emit_backend_request_action(request, app_root=str(APP_PATH))

    captured = capsys.readouterr().out
    assert "POST /api/participants-convert -> participants convert" in captured
    assert "cmd=python prism_tools.py participants convert --mode dataset" in captured
    assert "--project /tmp/demo-project" in captured
    assert "--force" in captured
    assert "--no-extract-from-biometrics" in captured
    assert "--neurobagel-schema" in captured
    assert "--json" in captured


def test_emit_backend_request_action_includes_environment_convert_start_command(capsys):
    app = Flask(__name__)
    app.secret_key = "test_secret"  # pragma: allowlist secret

    def _noop_view():
        return "ok"

    app.add_url_rule(
        "/api/environment-convert-start",
        endpoint="conversion.api_environment_convert_start",
        view_func=_noop_view,
        methods=["POST"],
    )

    with app.test_request_context(
        "/api/environment-convert-start",
        method="POST",
        data={
            "separator": "auto",
            "timestamp_col": "timestamp",
            "participant_col": "participant_id",
            "session_col": "session",
            "lat": "47.0667",
            "lon": "15.45",
            "convert_in_background": "true",
            "file": (
                io.BytesIO(
                    b"timestamp,participant_id,session\n2026-03-24 10:00:00,sub-01,ses-01\n"
                ),
                "environment.csv",
            ),
        },
        content_type="multipart/form-data",
    ):
        session["current_project_path"] = "/tmp/demo-project"
        emit_backend_request_action(request, app_root=str(APP_PATH))

    captured = capsys.readouterr().out
    expected_input = str((Path("/tmp/demo-project") / "environment.csv").resolve())
    assert (
        "POST /api/environment-convert-start -> environment convert start" in captured
    )
    assert "endpoint=conversion.api_environment_convert_start" in captured
    assert "cmd=python prism_tools.py environment convert" in captured
    assert f"--input {expected_input}" in captured
    assert "--project /tmp/demo-project" in captured
    assert "--timestamp-col timestamp" in captured
    assert "--participant-col participant_id" in captured
    assert "--session-col session" in captured
    assert "--lat 47.0667" in captured
    assert "--lon 15.45" in captured
    assert "--json" in captured
