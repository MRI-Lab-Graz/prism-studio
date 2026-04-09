"""Backend action monitoring helpers for PRISM Studio web requests."""

from __future__ import annotations

import json
import os
import shlex
import sys
from pathlib import Path

from flask import session

from src.config import load_app_settings

_MUTATING_METHODS = {"POST", "PUT", "PATCH", "DELETE"}
_ANSI_GREEN = "\033[32m"
_ANSI_RESET = "\033[0m"
_SUPPRESSED_ENDPOINTS = {
    # Frequent UI probe used for recent-project availability checks.
    "projects.project_path_status",
    # Frequent sync from localStorage cache updates; low diagnostic value.
    "projects.set_recent_projects",
    # Draft validation can fire repeatedly while editing forms.
    "projects.validate_dataset_description_draft",
}
_ENDPOINT_LABELS = {
    "conversion.api_biometrics_detect": "biometrics detect",
    "conversion.api_biometrics_convert": "biometrics convert",
    "conversion.api_physio_convert": "physio convert",
    "conversion.api_batch_convert": "batch convert",
    "conversion.api_batch_convert_start": "batch convert start",
    "conversion.api_physio_rename": "physio rename",
    "conversion.api_environment_preview": "environment preview",
    "conversion.api_environment_convert": "environment convert",
    "conversion.api_environment_convert_start": "environment convert start",
    "validation.validate_folder": "validate folder",
    "conversion_survey.api_survey_convert": "survey convert",
    "conversion_survey.api_survey_convert_preview": "survey convert preview",
    "conversion_survey.api_survey_convert_validate": "survey convert validate",
    "conversion_survey.api_survey_check_project_templates": "survey check project templates",
    "tools.detect_columns": "detect columns",
    "tools.api_file_management_wide_to_long_preview": "wide-to-long preview",
    "tools.api_file_management_wide_to_long": "wide-to-long convert",
    "projects.project_path_status": "check project path availability",
    "projects.create_project": "create project",
    "projects.open_project": "open project",
    "projects.validate_project": "validate project",
    "projects.fix_project": "apply project fixes",
    "projects_library.set_backend_monitoring_setting": "update backend monitoring setting",
    "projects_library.set_global_library_settings": "save global library settings",
    "conversion_participants.save_participant_mapping": "save participant mapping",
    "conversion_participants.api_participants_detect_id": "participants detect id",
    "conversion_participants.api_participants_preview": "participants preview",
    "conversion_participants.api_participants_convert": "participants convert",
}


def _compact_path(path_value: str | None) -> str:
    """Return a short, human-friendly path preview for terminal logs."""
    path_text = str(path_value or "").strip()
    if not path_text:
        return ""

    backslash = chr(92)
    normalized = path_text.replace(backslash, "/")
    parts = [part for part in normalized.split("/") if part]
    if len(parts) <= 3:
        return normalized
    return f".../{'/'.join(parts[-3:])}"


def _summarize_payload(req) -> str:
    """Extract small, useful request details without dumping full payloads."""
    try:
        payload = req.get_json(silent=True) or {}
    except Exception:
        payload = {}

    if not isinstance(payload, dict):
        payload = {}

    details: list[str] = []

    for key in ("path", "project_path", "dataset_path", "existing_path"):
        value = payload.get(key)
        if isinstance(value, str) and value.strip():
            details.append(f"{key}={_compact_path(value)}")

    for key in ("name", "project_name", "modality", "survey", "format", "layout"):
        value = payload.get(key)
        if isinstance(value, str) and value.strip():
            details.append(f"{key}={value.strip()}")

    if "backend_monitoring" in payload:
        details.append(f"backend_monitoring={bool(payload.get('backend_monitoring'))}")

    # Add a concise key count if no common fields are present.
    if not details and payload:
        keys = sorted(str(key) for key in payload.keys())
        preview = ", ".join(keys[:4])
        if len(keys) > 4:
            preview += ", ..."
        details.append(f"json_keys=[{preview}]")

    return ", ".join(details)


def _truthy_form_value(value: str | None) -> bool:
    """Interpret common form truthy values used by the frontend."""
    return str(value or "").strip().lower() in {"1", "true", "yes", "on"}


def _session_project_root() -> Path | None:
    """Return current project root from session, normalizing project.json paths."""
    project_path_text = str(session.get("current_project_path", "") or "").strip()
    if not project_path_text:
        return None

    try:
        project_path = Path(project_path_text).expanduser().resolve()
    except Exception:
        return None

    if project_path.is_file():
        return project_path.parent
    return project_path


def _absolute_input_path(filename: str) -> str:
    """Return absolute input path for CLI previews.

    Uploaded browser files expose only a file name; we anchor relative names to
    the current project root when available, otherwise current working directory.
    """
    file_text = str(filename or "").strip()
    if not file_text or file_text.startswith("<"):
        return file_text

    try:
        candidate = Path(file_text).expanduser()
        if candidate.is_absolute():
            return str(candidate)

        project_root = _session_project_root()
        base_dir = project_root if project_root is not None else Path.cwd()
        return str((base_dir / candidate).resolve())
    except Exception:
        return file_text


def _supports_ansi_color() -> bool:
    """Return True when ANSI coloring is likely supported by current terminal."""
    if os.environ.get("NO_COLOR") is not None:
        return False

    if not getattr(sys.stdout, "isatty", lambda: False)():
        return False

    if os.name != "nt":
        return True

    # Common Windows terminals with ANSI support.
    if os.environ.get("WT_SESSION"):
        return True
    if os.environ.get("ANSICON"):
        return True
    if str(os.environ.get("ConEmuANSI", "")).upper() == "ON":
        return True

    term = str(os.environ.get("TERM", "")).lower()
    return "xterm" in term or "ansi" in term


def _resolve_survey_output_dir(req) -> str:
    """Resolve an output directory for survey CLI command previews."""
    form = req.form

    explicit_output = str(form.get("output", "") or form.get("output_root", "")).strip()
    if explicit_output:
        return explicit_output

    current_project_path = str(session.get("current_project_path", "")).strip()
    if current_project_path:
        return current_project_path

    return "<output-dir>"


def _build_validate_folder_terminal_command(req) -> str:
    """Build the exact validator CLI equivalent for /validate_folder requests."""
    form = req.form
    folder_path = str(form.get("folder_path", "")).strip()
    if not folder_path:
        folder_path = str(session.get("current_project_path", "")).strip()
    if not folder_path:
        return ""

    # Mirror prism.py CLI invocation so users can copy-paste from logs.
    cmd_parts: list[str] = ["python", "prism.py", folder_path]

    schema_version = str(form.get("schema_version", "")).strip()
    if schema_version and schema_version != "stable":
        cmd_parts.extend(["--schema-version", schema_version])

    validation_mode = str(form.get("validation_mode", "both")).strip().lower()
    if validation_mode in {"both", "bids"}:
        cmd_parts.append("--bids")
    if validation_mode == "bids":
        cmd_parts.append("--no-prism")

    if _truthy_form_value(form.get("bids_warnings")):
        cmd_parts.append("--bids-warnings")

    library_path = str(form.get("library_path", "")).strip()
    if library_path:
        cmd_parts.extend(["--library", library_path])

    return " ".join(shlex.quote(part) for part in cmd_parts)


def _build_survey_convert_terminal_command(req, *, dry_run: bool = False) -> str:
    """Build CLI-equivalent survey convert command for survey conversion endpoints."""
    form = req.form
    files = req.files

    uploaded = files.get("excel") or files.get("file")
    filename = ""
    if uploaded is not None:
        filename = str(getattr(uploaded, "filename", "") or "").strip()
    if not filename:
        filename = "<input-file>"

    output_dir = _resolve_survey_output_dir(req)

    cmd_parts: list[str] = [
        "python",
        "prism_tools.py",
        "survey",
        "convert",
        "--input",
        filename,
        "--output",
        output_dir,
    ]

    survey = str(form.get("survey", "")).strip()
    if survey:
        cmd_parts.extend(["--survey", survey])

    template_versions_raw = str(form.get("template_versions", "")).strip()
    if template_versions_raw:
        try:
            template_versions = json.loads(template_versions_raw)
        except json.JSONDecodeError:
            template_versions = []
        if isinstance(template_versions, dict):
            for task, version in sorted(template_versions.items()):
                task_name = str(task or "").strip().lower()
                version_name = str(version or "").strip()
                if task_name and version_name:
                    cmd_parts.extend(
                        ["--template-version", f"{task_name}={version_name}"]
                    )
        elif isinstance(template_versions, list):
            normalized_entries = []
            for entry in template_versions:
                if not isinstance(entry, dict):
                    continue
                task_name = str(entry.get("task") or "").strip().lower()
                version_name = str(entry.get("version") or "").strip()
                session_name = str(entry.get("session") or "").strip()
                run_value = entry.get("run")
                if not task_name or not version_name:
                    continue
                selector_suffix = ""
                if session_name:
                    selector_suffix += f";session={session_name}"
                if run_value not in {None, ""}:
                    selector_suffix += f";run={int(run_value)}"
                normalized_entries.append(
                    (
                        task_name,
                        session_name,
                        int(run_value) if run_value not in {None, ""} else -1,
                        selector_suffix,
                        version_name,
                    )
                )
            for task_name, _session_name, _run_value, selector_suffix, version_name in sorted(normalized_entries):
                cmd_parts.extend(
                    [
                        "--template-version",
                        f"{task_name}{selector_suffix}={version_name}",
                    ]
                )

    id_column = str(form.get("id_column", "")).strip()
    if id_column:
        cmd_parts.extend(["--id-column", id_column])

    session_column = str(form.get("session_column", "")).strip()
    if session_column:
        cmd_parts.extend(["--session-column", session_column])

    run_column = str(form.get("run_column", "")).strip()
    if run_column:
        cmd_parts.extend(["--run-column", run_column])

    sheet = str(form.get("sheet", "")).strip()
    if sheet:
        cmd_parts.extend(["--sheet", sheet])

    unknown = str(form.get("unknown", "")).strip().lower()
    if unknown and unknown != "warn":
        cmd_parts.extend(["--unknown", unknown])

    language = str(form.get("language", "")).strip()
    if language:
        cmd_parts.extend(["--lang", language])

    if dry_run:
        cmd_parts.append("--dry-run")

    cmd_parts.append("--force")
    return " ".join(shlex.quote(part) for part in cmd_parts)


def _build_detect_columns_terminal_command(req) -> str:
    """Build CLI-equivalent command preview for detect-columns uploads."""
    files = req.files
    uploaded = files.get("file")
    filename = ""
    if uploaded is not None:
        filename = str(getattr(uploaded, "filename", "") or "").strip()
    if not filename:
        filename = "<input-file>"

    output_dir = _resolve_survey_output_dir(req)

    # Closest equivalent: run survey conversion as dry-run to trigger
    # parser loading and ID/session auto-detection without writing files.
    cmd_parts: list[str] = [
        "python",
        "prism_tools.py",
        "survey",
        "convert",
        "--input",
        filename,
        "--output",
        output_dir,
        "--dry-run",
        "--force",
    ]
    return " ".join(shlex.quote(part) for part in cmd_parts)


def _build_wide_to_long_terminal_command(req, *, inspect_only: bool) -> str:
    """Build CLI-equivalent command preview for wide-to-long endpoints."""
    files = req.files
    form = req.form
    uploaded = files.get("data") or files.get("file")
    filename = str(getattr(uploaded, "filename", "") or "").strip() or "<input-file>"

    cmd_parts: list[str] = [
        "python",
        "prism.py",
        "wide-to-long",
        "--input",
        filename,
        "--session-column",
        str(form.get("session_column", "session") or "session").strip() or "session",
    ]

    session_indicators = str(
        form.get("session_indicators", "") or form.get("session_prefixes", "")
    ).strip()
    if session_indicators:
        cmd_parts.extend(["--session-indicators", session_indicators])

    session_map = str(form.get("session_value_map", "") or "").strip()
    if session_map:
        cmd_parts.extend(["--session-map", session_map])

    if inspect_only:
        cmd_parts.append("--inspect-only")
    else:
        cmd_parts.extend(["--output", "<output-file>"])

    return " ".join(shlex.quote(part) for part in cmd_parts)


def _build_survey_check_templates_terminal_command(req) -> str:
    """Build command preview for survey template pre-check endpoint."""
    form = req.form
    files = req.files

    uploaded = files.get("excel") or files.get("file")
    filename = ""
    if uploaded is not None:
        filename = str(getattr(uploaded, "filename", "") or "").strip()
    if not filename:
        filename = "<input-file>"

    output_dir = _resolve_survey_output_dir(req)

    cmd_parts: list[str] = [
        "python",
        "prism_tools.py",
        "survey",
        "convert",
        "--input",
        filename,
        "--output",
        output_dir,
        "--dry-run",
        "--force",
    ]

    id_column = str(form.get("id_column", "")).strip()
    if id_column:
        cmd_parts.extend(["--id-column", id_column])

    session_column = str(form.get("session_column", "")).strip()
    if session_column:
        cmd_parts.extend(["--session-column", session_column])

    sheet = str(form.get("sheet", "")).strip()
    if sheet:
        cmd_parts.extend(["--sheet", sheet])

    return " ".join(shlex.quote(part) for part in cmd_parts)


def _get_request_url(req, fallback_path: str) -> str:
    """Return absolute request URL for curl command previews."""
    base_url = str(getattr(req, "host_url", "") or "http://localhost").rstrip("/")
    return f"{base_url}{req.path or fallback_path}"


def _append_curl_form_field(cmd_parts: list[str], key: str, value: str | None) -> None:
    """Append a curl multipart form field when a value is present."""
    text = str(value or "").strip()
    if not text:
        return
    cmd_parts.extend(["-F", f"{key}={text}"])


def _append_curl_form_file(
    cmd_parts: list[str], key: str, filename: str | None
) -> None:
    """Append a curl multipart file field using a filename placeholder."""
    name = str(filename or "").strip() or "<input-file>"
    cmd_parts.extend(["-F", f"{key}=@{name}"])


def _json_command_argument(value, placeholder: str) -> str:
    """Render short JSON payloads inline, otherwise fall back to a placeholder."""
    if value in (None, ""):
        return placeholder
    try:
        rendered = json.dumps(value, separators=(",", ":"), ensure_ascii=False)
    except (TypeError, ValueError):
        return placeholder
    if len(rendered) > 240:
        return placeholder
    return rendered


def _build_biometrics_detect_terminal_command(req) -> str:
    """Build a CLI command for biometrics task detection."""
    files = req.files
    form = req.form

    uploaded = files.get("data") or files.get("file")
    filename = str(getattr(uploaded, "filename", "") or "").strip()
    input_path = _absolute_input_path(filename) if filename else "<input-file>"

    project_root = _session_project_root()
    library_dir = (
        str(project_root / "code" / "library" / "biometrics")
        if project_root is not None
        else "<library-dir>"
    )

    cmd_parts = [
        "python",
        "prism_tools.py",
        "biometrics",
        "detect",
        "--input",
        input_path,
        "--library",
        library_dir,
    ]

    sheet = str(form.get("sheet", "") or "").strip()
    if sheet and sheet != "0":
        cmd_parts.extend(["--sheet", sheet])

    return " ".join(shlex.quote(p) for p in cmd_parts)


def _build_biometrics_convert_terminal_command(req) -> str:
    """Build a CLI command for biometrics table conversion."""
    files = req.files
    form = req.form

    uploaded = files.get("data") or files.get("file")
    filename = str(getattr(uploaded, "filename", "") or "").strip()
    input_path = _absolute_input_path(filename) if filename else "<input-file>"

    project_root = _session_project_root()
    library_dir = (
        str(project_root / "code" / "library" / "biometrics")
        if project_root is not None
        else "<library-dir>"
    )
    output_dir = str(project_root) if project_root is not None else "<output-dir>"

    cmd_parts = [
        "python",
        "prism_tools.py",
        "biometrics",
        "convert",
        "--input",
        input_path,
        "--library",
        library_dir,
        "--output",
        output_dir,
    ]

    id_column = str(form.get("id_column", "") or "").strip()
    if id_column:
        cmd_parts.extend(["--id-column", id_column])

    session_column = str(form.get("session_column", "") or "").strip()
    if session_column:
        cmd_parts.extend(["--session-column", session_column])

    session = str(form.get("session", "") or "").strip()
    if session:
        cmd_parts.extend(["--session", session])

    sheet = str(form.get("sheet", "") or "").strip()
    if sheet and sheet != "0":
        cmd_parts.extend(["--sheet", sheet])

    unknown = str(form.get("unknown", "warn") or "warn").strip()
    if unknown and unknown != "warn":
        cmd_parts.extend(["--unknown", unknown])

    tasks = req.form.getlist("tasks[]")
    if tasks:
        cmd_parts.extend(["--tasks", ",".join(tasks)])

    dataset_name = str(form.get("dataset_name", "") or "").strip()
    if dataset_name:
        cmd_parts.extend(["--name", dataset_name])

    return " ".join(shlex.quote(p) for p in cmd_parts)


def _build_physio_convert_terminal_command(req) -> str:
    """Build a CLI command for single-file physio (Varioport) conversion."""
    files = req.files
    form = req.form

    uploaded = files.get("raw") or files.get("file")
    filename = str(getattr(uploaded, "filename", "") or "").strip()
    input_path = _absolute_input_path(filename) if filename else "<input-file>"

    project_root = _session_project_root()
    output_dir = str(project_root) if project_root is not None else "<output-dir>"

    cmd_parts = [
        "python",
        "prism_tools.py",
        "convert",
        "physio",
        "--input",
        input_path,
        "--output",
        output_dir,
    ]

    task = str(form.get("task", "rest") or "rest").strip() or "rest"
    cmd_parts.extend(["--task", task])

    sampling_rate = str(form.get("sampling_rate", "") or "").strip()
    if sampling_rate:
        cmd_parts.extend(["--sampling-rate", sampling_rate])

    return " ".join(shlex.quote(p) for p in cmd_parts)


def _build_batch_convert_terminal_command(req, *, start_async: bool) -> str:
    """Build a CLI command for batch physio/eyetracking conversion.

    When a server-side folder_path is present, emit a real prism_tools command.
    Fall back to curl when files were uploaded without a local folder reference.
    """
    form = req.form

    folder_path = str(form.get("folder_path", "") or "").strip()
    if folder_path:
        project_root = _session_project_root()
        dest_root = str(form.get("dest_root", "") or "").strip()
        output_dir = (
            str(project_root / dest_root)
            if dest_root and project_root is not None
            else str(project_root)
            if project_root is not None
            else "<output-dir>"
        )

        cmd_parts = [
            "python",
            "prism_tools.py",
            "physio",
            "batch-convert",
            "--input",
            folder_path,
            "--output",
            output_dir,
        ]

        modality = str(form.get("modality", "all") or "all").strip()
        if modality and modality != "all":
            cmd_parts.extend(["--modality", modality])

        sampling_rate = str(form.get("sampling_rate", "") or "").strip()
        if sampling_rate:
            cmd_parts.extend(["--sampling-rate", sampling_rate])

        if _truthy_form_value(form.get("dry_run")):
            cmd_parts.append("--dry-run")

        return " ".join(shlex.quote(p) for p in cmd_parts)

    # Fallback to curl when only uploaded files are available (no local path).
    endpoint_url = _get_request_url(
        req, "/api/batch-convert-start" if start_async else "/api/batch-convert"
    )
    cmd_parts = ["curl", "-X", "POST", endpoint_url]
    uploaded_files = req.files.getlist("files[]") or req.files.getlist("files")
    for uploaded in uploaded_files:
        filename = str(getattr(uploaded, "filename", "") or "").strip()
        _append_curl_form_file(cmd_parts, "files", filename)

    for key in (
        "dataset_name",
        "modality",
        "save_to_project",
        "dest_root",
        "generate_physio_reports",
        "sampling_rate",
        "dry_run",
        "flat_structure",
    ):
        _append_curl_form_field(cmd_parts, key, form.get(key))

    return " ".join(shlex.quote(p) for p in cmd_parts)


def _build_physio_rename_terminal_command(req) -> str:
    """Build a reproducible request command for physio rename requests."""
    endpoint_url = _get_request_url(req, "/api/physio-rename")
    cmd_parts = ["curl", "-X", "POST", endpoint_url]

    for key in (
        "pattern",
        "replacement",
        "dry_run",
        "organize",
        "modality",
        "save_to_project",
        "skip_zip",
        "dest_root",
        "flat_structure",
        "id_source",
        "folder_subject_level",
        "folder_session_level",
        "folder_subject_value",
        "folder_session_value",
        "folder_example_path",
    ):
        _append_curl_form_field(cmd_parts, key, req.form.get(key))

    for name in req.form.getlist("filenames[]") or req.form.getlist("filenames"):
        _append_curl_form_field(cmd_parts, "filenames[]", name)
    for source_path in req.form.getlist("source_paths[]") or req.form.getlist(
        "source_paths"
    ):
        _append_curl_form_field(cmd_parts, "source_paths[]", source_path)

    uploaded_files = req.files.getlist("files[]") or req.files.getlist("files")
    for uploaded in uploaded_files:
        filename = str(getattr(uploaded, "filename", "") or "").strip()
        _append_curl_form_file(cmd_parts, "files", filename)

    return " ".join(shlex.quote(part) for part in cmd_parts)


def _build_save_participant_mapping_terminal_command(req) -> str:
    """Build a real backend CLI command for participant mapping saves."""
    payload = req.get_json(silent=True) or {}
    if not isinstance(payload, dict):
        payload = {}

    project_path = str(session.get("current_project_path", "") or "").strip()
    library_path = str(payload.get("library_path", "") or "").strip()
    mapping_json = _json_command_argument(payload.get("mapping"), "<mapping-json>")

    cmd_parts = [
        "python",
        "prism_tools.py",
        "participants",
        "save-mapping",
        "--mapping-json",
        mapping_json,
    ]
    if project_path:
        cmd_parts.extend(["--project", project_path])
    elif library_path:
        cmd_parts.extend(["--library-path", library_path])
    else:
        cmd_parts.extend(["--project", "<project-path>"])
    cmd_parts.append("--json")
    return " ".join(shlex.quote(part) for part in cmd_parts)


def _build_participants_preview_terminal_command(req) -> str:
    """Build a real backend CLI command for participants preview."""
    form = req.form
    files = req.files

    mode = str(form.get("mode", "file") or "file").strip().lower() or "file"
    cmd_parts: list[str] = ["python", "prism_tools.py", "participants", "preview"]

    if mode == "file":
        uploaded = files.get("file")
        filename = ""
        if uploaded is not None:
            filename = str(getattr(uploaded, "filename", "") or "").strip()
        if not filename:
            filename = "<input-file>"
        input_path = _absolute_input_path(filename)

        sheet = str(form.get("sheet", "0") or "0").strip() or "0"
        cmd_parts.extend(["--input", input_path, "--sheet", sheet])

        separator = str(form.get("separator", "") or "").strip().lower()
        if separator:
            cmd_parts.extend(["--separator", separator])

        id_column = str(form.get("id_column", "") or "").strip()
        if id_column:
            cmd_parts.extend(["--id-column", id_column])

        project_path = str(session.get("current_project_path", "") or "").strip()
        if project_path:
            cmd_parts.extend(["--project", project_path])

        cmd_parts.append("--json")

    elif mode == "dataset":
        project_path = str(session.get("current_project_path", "") or "").strip()
        if not project_path:
            project_path = "<project-path>"
        cmd_parts = [
            "python",
            "prism_tools.py",
            "participants",
            "preview",
            "--mode",
            "dataset",
            "--project",
            project_path,
        ]
        extract_from_survey = str(form.get("extract_from_survey", "true") or "true")
        extract_from_biometrics = str(
            form.get("extract_from_biometrics", "true") or "true"
        )
        if extract_from_survey.lower() not in {"1", "true", "yes", "on"}:
            cmd_parts.append("--no-extract-from-survey")
        if extract_from_biometrics.lower() not in {"1", "true", "yes", "on"}:
            cmd_parts.append("--no-extract-from-biometrics")
        cmd_parts.append("--json")

    return " ".join(shlex.quote(part) for part in cmd_parts)


def _build_participants_detect_id_terminal_command(req) -> str:
    """Build a real backend CLI command for participants ID detection."""
    files = req.files
    form = req.form

    uploaded = files.get("file")
    filename = ""
    if uploaded is not None:
        filename = str(getattr(uploaded, "filename", "") or "").strip()
    if not filename:
        filename = "<input-file>"
    input_path = _absolute_input_path(filename)

    sheet = str(form.get("sheet", "0") or "0").strip() or "0"

    cmd_parts = [
        "python",
        "prism_tools.py",
        "participants",
        "detect-id",
        "--input",
        input_path,
        "--sheet",
        sheet,
    ]

    separator = str(form.get("separator", "") or "").strip().lower()
    if separator:
        cmd_parts.extend(["--separator", separator])

    cmd_parts.append("--json")
    return " ".join(shlex.quote(part) for part in cmd_parts)


def _build_participants_convert_terminal_command(req) -> str:
    """Build a real backend CLI command for participants conversion."""
    form = req.form
    files = req.files

    mode = str(form.get("mode", "file") or "file").strip().lower() or "file"
    force_overwrite = str(form.get("force_overwrite", "false") or "false").strip()

    if mode == "file":
        uploaded = files.get("file")
        filename = ""
        if uploaded is not None:
            filename = str(getattr(uploaded, "filename", "") or "").strip()
        if not filename:
            filename = "<input-file>"
        input_path = _absolute_input_path(filename)

        cmd_parts: list[str] = [
            "python",
            "prism_tools.py",
            "participants",
            "convert",
            "--input",
            input_path,
        ]

        sheet = str(form.get("sheet", "0") or "0").strip() or "0"
        cmd_parts.extend(["--sheet", sheet])

        separator = str(form.get("separator", "") or "").strip().lower()
        if separator:
            cmd_parts.extend(["--separator", separator])

        id_column = str(form.get("id_column", "") or "").strip()
        if id_column:
            cmd_parts.extend(["--id-column", id_column])

        project_path = str(session.get("current_project_path", "") or "").strip()
        if project_path:
            cmd_parts.extend(["--project", project_path])
        else:
            cmd_parts.extend(["--project", "<project-path>"])

        if force_overwrite.lower() in {"1", "true", "yes", "on"}:
            cmd_parts.append("--force")

    elif mode == "dataset":
        project_path = str(session.get("current_project_path", "") or "").strip()
        if not project_path:
            project_path = "<project-path>"
        cmd_parts = [
            "python",
            "prism_tools.py",
            "participants",
            "convert",
            "--mode",
            "dataset",
            "--project",
            project_path,
        ]
        extract_from_survey = str(form.get("extract_from_survey", "true") or "true")
        extract_from_biometrics = str(
            form.get("extract_from_biometrics", "true") or "true"
        )
        if force_overwrite.lower() in {"1", "true", "yes", "on"}:
            cmd_parts.append("--force")
        if extract_from_survey.lower() not in {"1", "true", "yes", "on"}:
            cmd_parts.append("--no-extract-from-survey")
        if extract_from_biometrics.lower() not in {"1", "true", "yes", "on"}:
            cmd_parts.append("--no-extract-from-biometrics")
    else:
        endpoint_url = _get_request_url(req, "/api/participants-convert")
        cmd_parts = [
            "curl",
            "-X",
            "POST",
            endpoint_url,
            "-F",
            f"mode={mode}",
            "-F",
            f"force_overwrite={force_overwrite}",
        ]

    neurobagel_schema = str(form.get("neurobagel_schema", "") or "").strip()
    if neurobagel_schema:
        if mode in {"file", "dataset"}:
            try:
                schema_value = json.loads(neurobagel_schema)
            except (TypeError, ValueError):
                schema_value = "<json>"
            cmd_parts.extend(
                [
                    "--neurobagel-schema",
                    _json_command_argument(schema_value, "<json>"),
                ]
            )
        else:
            cmd_parts.extend(["-F", "neurobagel_schema=<json>"])

    if mode in {"file", "dataset"}:
        cmd_parts.append("--json")

    return " ".join(shlex.quote(part) for part in cmd_parts)


def _build_environment_preview_terminal_command(req) -> str:
    """Build a real backend CLI command for environment preview."""
    uploaded = req.files.get("file")
    filename = ""
    if uploaded is not None:
        filename = str(getattr(uploaded, "filename", "") or "").strip()
    if not filename:
        filename = "<input-file>"
    input_path = _absolute_input_path(filename)

    separator = str(req.form.get("separator", "auto") or "auto").strip().lower()
    if not separator:
        separator = "auto"

    project_path = str(session.get("current_project_path", "") or "").strip()
    if not project_path:
        project_path = "<project-path>"

    cmd_parts = [
        "python",
        "prism_tools.py",
        "environment",
        "preview",
        "--input",
        input_path,
        "--project",
        project_path,
        "--separator",
        separator,
        "--json",
    ]
    return " ".join(shlex.quote(part) for part in cmd_parts)


def _build_environment_convert_terminal_command(req) -> str:
    """Build a real backend CLI command for environment conversion."""
    uploaded = req.files.get("file")
    filename = ""
    if uploaded is not None:
        filename = str(getattr(uploaded, "filename", "") or "").strip()
    if not filename:
        filename = "<input-file>"
    input_path = _absolute_input_path(filename)

    separator = str(req.form.get("separator", "auto") or "auto").strip().lower()
    if not separator:
        separator = "auto"

    project_path = str(session.get("current_project_path", "") or "").strip()
    if not project_path:
        project_path = "<project-path>"

    cmd_parts = [
        "python",
        "prism_tools.py",
        "environment",
        "convert",
        "--input",
        input_path,
        "--project",
        project_path,
        "--separator",
        separator,
    ]

    for form_key, arg_name in [
        ("timestamp_col", "--timestamp-col"),
        ("participant_col", "--participant-col"),
        ("participant_override", "--participant-override"),
        ("session_col", "--session-col"),
        ("session_override", "--session-override"),
        ("location_col", "--location-col"),
        ("lat_col", "--lat-col"),
        ("lon_col", "--lon-col"),
        ("location_label", "--location-label"),
        ("lat", "--lat"),
        ("lon", "--lon"),
    ]:
        value = str(req.form.get(form_key, "") or "").strip()
        if value:
            cmd_parts.extend([arg_name, value])

    if str(req.form.get("pilot_random_subject", "") or "").strip().lower() in {
        "1",
        "true",
        "yes",
        "on",
    }:
        cmd_parts.append("--pilot-random-subject")

    cmd_parts.append("--json")
    return " ".join(shlex.quote(part) for part in cmd_parts)


def _build_terminal_command(req) -> str:
    """Return an exact terminal command preview for supported actions."""
    endpoint = req.endpoint or ""
    if endpoint == "validation.validate_folder":
        return _build_validate_folder_terminal_command(req)
    if endpoint == "conversion.api_biometrics_detect":
        return _build_biometrics_detect_terminal_command(req)
    if endpoint == "conversion.api_biometrics_convert":
        return _build_biometrics_convert_terminal_command(req)
    if endpoint == "conversion.api_physio_convert":
        return _build_physio_convert_terminal_command(req)
    if endpoint == "conversion.api_batch_convert":
        return _build_batch_convert_terminal_command(req, start_async=False)
    if endpoint == "conversion.api_batch_convert_start":
        return _build_batch_convert_terminal_command(req, start_async=True)
    if endpoint == "conversion.api_physio_rename":
        return _build_physio_rename_terminal_command(req)
    if endpoint == "conversion_survey.api_survey_convert":
        return _build_survey_convert_terminal_command(req, dry_run=False)
    if endpoint in {
        "conversion_survey.api_survey_convert_preview",
        "conversion_survey.api_survey_convert_validate",
    }:
        return _build_survey_convert_terminal_command(req, dry_run=True)
    if endpoint == "conversion_survey.api_survey_check_project_templates":
        return _build_survey_check_templates_terminal_command(req)
    if endpoint == "tools.detect_columns":
        return _build_detect_columns_terminal_command(req)
    if endpoint == "tools.api_file_management_wide_to_long_preview":
        return _build_wide_to_long_terminal_command(req, inspect_only=True)
    if endpoint == "tools.api_file_management_wide_to_long":
        return _build_wide_to_long_terminal_command(req, inspect_only=False)
    if endpoint == "conversion.api_environment_preview":
        return _build_environment_preview_terminal_command(req)
    if endpoint == "conversion.api_environment_convert":
        return _build_environment_convert_terminal_command(req)
    if endpoint == "conversion.api_environment_convert_start":
        return _build_environment_convert_terminal_command(req)
    if endpoint == "conversion_participants.api_participants_detect_id":
        return _build_participants_detect_id_terminal_command(req)
    if endpoint == "conversion_participants.api_participants_preview":
        return _build_participants_preview_terminal_command(req)
    if endpoint == "conversion_participants.api_participants_convert":
        return _build_participants_convert_terminal_command(req)
    if endpoint == "conversion_participants.save_participant_mapping":
        return _build_save_participant_mapping_terminal_command(req)
    return ""


def is_backend_monitoring_enabled(app_root: str) -> bool:
    """Return whether backend monitoring is enabled in app settings."""
    settings = load_app_settings(app_root=app_root)
    return bool(settings.backend_monitoring)


def emit_backend_action(message: str, app_root: str) -> None:
    """Print a backend action line to terminal when monitoring is enabled."""
    if not is_backend_monitoring_enabled(app_root):
        return

    text = str(message or "").strip()
    if not text:
        return

    cmd_idx = text.find("cmd=")
    if cmd_idx >= 0 and _supports_ansi_color():
        head = text[:cmd_idx]
        command_segment = text[cmd_idx:]
        text = f"{head}{_ANSI_GREEN}{command_segment}{_ANSI_RESET}"

    print(f"\n[BACKEND-ACTION] {text}\n")


def emit_backend_request_action(req, app_root: str) -> None:
    """Print backend action line for mutating HTTP requests when enabled."""
    method = (req.method or "").upper()
    if method not in _MUTATING_METHODS:
        return

    path = req.path or "/"
    endpoint = req.endpoint or "unknown"
    if endpoint in _SUPPRESSED_ENDPOINTS:
        return

    label = _ENDPOINT_LABELS.get(endpoint, endpoint.replace("_", " "))
    payload_summary = _summarize_payload(req)

    action = f"{method} {path} -> {label} (endpoint={endpoint})"
    if payload_summary:
        action = f"{action} | {payload_summary}"

    terminal_command = _build_terminal_command(req)
    if terminal_command:
        action = f"{action} | cmd={terminal_command}"

    emit_backend_action(action, app_root=app_root)


def get_app_root_from_current_app(current_app_obj) -> str:
    """Resolve absolute app root path as string from current_app."""
    return str(Path(current_app_obj.root_path))
