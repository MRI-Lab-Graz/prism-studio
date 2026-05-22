"""Backend action monitoring helpers for PRISM Studio web requests."""

from __future__ import annotations

import json
import os
import shlex
import sys
import time
from datetime import datetime
from pathlib import Path
from pathlib import PureWindowsPath

from flask import session

from src.config import load_app_settings
from src.cross_platform import normalize_path
from src.project_manager import ProjectManager
from src.project_session_logging import record_project_session_command

_MUTATING_METHODS = {"POST", "PUT", "PATCH", "DELETE"}
_ANSI_GREEN = "\033[32m"
_ANSI_RESET = "\033[0m"
_DUPLICATE_SUPPRESS_SECONDS = 1.5
_DUPLICATE_SUPPRESS_ENDPOINTS = {
    "projects.set_current",
    "projects_export.export_project_structure",
}
_RECENT_ACTIONS: dict[str, float] = {}
_SUPPRESSED_ENDPOINTS = {
    # Frequent UI probe used for recent-project availability checks.
    "projects.project_path_status",
    # Frequent sync from localStorage cache updates; low diagnostic value.
    "projects.set_recent_projects",
    # Draft validation can fire repeatedly while editing forms.
    "projects.validate_dataset_description_draft",
}
_PATH_ENDPOINT_FALLBACKS = {
    "/api/survey-prepare-workflow": "conversion_survey.api_survey_prepare_workflow",
    "/api/survey-workflow-command": "conversion_survey.api_survey_workflow_command",
    "/api/survey-detect-version-contexts": "conversion_survey.api_survey_detect_version_context",
    "/api/survey-convert-preview": "conversion_survey.api_survey_convert_preview",
    "/api/survey-convert": "conversion_survey.api_survey_convert",
    "/api/survey-convert-validate": "conversion_survey.api_survey_convert_validate",
    "/api/survey-check-project-templates": "conversion_survey.api_survey_check_project_templates",
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
    "conversion_survey.api_survey_prepare_workflow": "survey prepare workflow",
    "conversion_survey.api_survey_workflow_command": "survey workflow command",
    "conversion_survey.api_survey_detect_version_context": "survey detect version contexts",
    "conversion_survey.api_survey_check_project_templates": "survey check project templates",
    "tools.detect_columns": "detect columns",
    "tools.api_recipes_surveys": "recipes survey output",
    "tools.api_file_management_wide_to_long_preview": "wide-to-long preview",
    "tools.api_file_management_wide_to_long": "wide-to-long convert",
    "projects.project_path_status": "check project path availability",
    "projects.set_current": "set current project",
    "projects.create_project": "create project",
    "projects.init_on_bids": "init PRISM on existing BIDS dataset",
    "projects.open_project": "open project",
    "projects.validate_project": "validate project",
    "projects.fix_project": "apply project fixes",
    "projects.save_datalad_snapshot": "save DataLad snapshot",
    "projects.enable_datalad_for_project": "repair DataLad structure",
    "projects_export.export_project_structure": "export project structure",
    "projects_export.export_project_folder": "folder export project",
    "projects_export.template_export_project": "template export project",
    "projects_library.set_backend_monitoring_setting": "update backend monitoring setting",
    "projects_library.set_global_library_settings": "save global library settings",
    "conversion_participants.save_participant_mapping": "save participant mapping",
    "conversion_participants.api_participants_detect_id": "participants detect id",
    "conversion_participants.api_participants_preview": "participants preview",
    "conversion_participants.api_participants_convert": "participants convert",
    "conversion_participants.api_participants_merge": "participants merge",
    "conversion_participants.api_participants_merge_conflicts": "participants merge conflicts",
}


def _coerce_template_version_value(raw_value: object) -> str:
    """Collapse template version payloads to a concrete version string."""
    if isinstance(raw_value, str):
        return raw_value.strip()
    if isinstance(raw_value, dict):
        if "version" in raw_value:
            nested_value = _coerce_template_version_value(raw_value.get("version"))
            if nested_value:
                return nested_value
        for lang in ("en", "de"):
            candidate = raw_value.get(lang)
            if isinstance(candidate, str) and candidate.strip():
                return candidate.strip()
        for candidate in raw_value.values():
            if isinstance(candidate, str) and candidate.strip():
                return candidate.strip()
    return ""


def _normalize_template_version_run(run_value: object) -> str | None:
    text = str(run_value or "").strip()
    if not text:
        return None
    label = text[4:] if text[:4].lower() == "run-" else text
    label = "".join(ch for ch in label if ch.isalnum())
    if not label:
        return None
    return f"run-{label}"


def _format_template_version_run(run_value: object) -> str | None:
    normalized = _normalize_template_version_run(run_value)
    if not normalized:
        return None
    return normalized[4:]


def _compact_path(path_value: str | None) -> str:
    """Return a short, human-friendly path preview for terminal logs."""
    path_text = str(path_value or "").strip()
    if not path_text:
        return ""

    backslash = chr(92)
    normalized_text = normalize_path(path_text)
    normalized = str(normalized_text or path_text).replace(backslash, "/")
    parts = [part for part in normalized.split("/") if part]
    if len(parts) <= 3:
        return normalized
    return f".../{'/'.join(parts[-3:])}"


def _absolute_path_value(path_value: str | None) -> str:
    """Return an absolute path string for log previews when possible."""
    path_text = str(path_value or "").strip()
    if not path_text:
        return ""

    if path_text.startswith("<") and path_text.endswith(">"):
        return path_text

    if "://" in path_text:
        return path_text

    # Preserve Windows absolute path semantics even when running on POSIX.
    if len(path_text) >= 3 and path_text[1] == ":" and path_text[2] in {"/", "\\"}:
        return str(PureWindowsPath(path_text))

    try:
        return str(Path(path_text).expanduser().resolve(strict=False))
    except Exception:
        return path_text


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
            details.append(f"{key}={_absolute_path_value(value)}")

    for key in ("name", "project_name", "modality", "survey", "format", "layout"):
        value = payload.get(key)
        if isinstance(value, str) and value.strip():
            details.append(f"{key}={value.strip()}")

    if "backend_monitoring" in payload:
        details.append(f"backend_monitoring={bool(payload.get('backend_monitoring'))}")
    if "backend_monitoring_verbose" in payload:
        details.append(
            "backend_monitoring_verbose="
            f"{bool(payload.get('backend_monitoring_verbose'))}"
        )

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

    if project_path.name == "project.json":
        return project_path.parent

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


def _resolve_request_endpoint(req) -> str:
    """Resolve Flask endpoint and fall back to known path-based mappings."""
    endpoint = str(getattr(req, "endpoint", "") or "").strip()
    if endpoint:
        return endpoint

    path = str(getattr(req, "path", "") or "").strip()
    if not path:
        return "unknown"

    return _PATH_ENDPOINT_FALLBACKS.get(path, "unknown")


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


def _build_projects_set_current_terminal_command(req) -> str:
    """Build command preview for setting current project endpoint."""
    payload = req.get_json(silent=True) or {}
    if not isinstance(payload, dict):
        payload = {}

    project_path = _absolute_path_value(payload.get("path"))
    endpoint_url = _get_request_url(req, "/api/projects/current")

    if not project_path:
        return " ".join(
            shlex.quote(part)
            for part in [
                "curl",
                "-X",
                "POST",
                endpoint_url,
                "-H",
                "Content-Type: application/json",
                "-d",
                json.dumps({"path": ""}),
            ]
        )

    return " ".join(
        shlex.quote(part)
        for part in [
            "curl",
            "-X",
            "POST",
            endpoint_url,
            "-H",
            "Content-Type: application/json",
            "-d",
            json.dumps({"path": project_path}),
        ]
    )


def _build_projects_export_structure_terminal_command(req) -> str:
    """Build command preview for project export structure endpoint."""
    payload = req.get_json(silent=True) or {}
    if not isinstance(payload, dict):
        payload = {}

    project_path = _absolute_path_value(payload.get("project_path"))
    endpoint_url = _get_request_url(req, "/api/projects/export/structure")
    body = {"project_path": project_path or "<project-path>"}

    return " ".join(
        shlex.quote(part)
        for part in [
            "curl",
            "-X",
            "POST",
            endpoint_url,
            "-H",
            "Content-Type: application/json",
            "-d",
            json.dumps(body),
        ]
    )


def _build_projects_folder_export_terminal_command(req) -> str:
    """Build backend command preview for plain folder export endpoint."""
    payload = req.get_json(silent=True) or {}
    if not isinstance(payload, dict):
        payload = {}

    project_path = _absolute_path_value(payload.get("project_path")) or "<project-path>"
    output_folder = _absolute_path_value(payload.get("output_folder"))

    cmd_parts = [
        "python",
        "prism.py",
        "projects",
        "export-folder",
        "--project",
        project_path,
    ]

    if output_folder:
        cmd_parts.extend(["--output", output_folder])

    if bool(payload.get("materialize_annex_content", False)):
        cmd_parts.append("--materialize-annex-content")

    if bool(payload.get("include_derivatives", True)) is False:
        cmd_parts.append("--exclude-derivatives")
    if bool(payload.get("include_code", True)) is False:
        cmd_parts.append("--exclude-code")
    if bool(payload.get("include_analysis", True)) is False:
        cmd_parts.append("--exclude-analysis")

    exclude_subjects = payload.get("exclude_subjects") or []
    if isinstance(exclude_subjects, (list, tuple, set)):
        normalized_subjects = [
            str(value).strip() for value in exclude_subjects if str(value).strip()
        ]
        if normalized_subjects:
            cmd_parts.extend(["--exclude-subjects", ",".join(normalized_subjects)])

    exclude_sessions = payload.get("exclude_sessions") or []
    if isinstance(exclude_sessions, (list, tuple, set)):
        normalized_sessions = [
            str(value).strip() for value in exclude_sessions if str(value).strip()
        ]
        if normalized_sessions:
            cmd_parts.extend(["--exclude-sessions", ",".join(normalized_sessions)])

    exclude_modalities = payload.get("exclude_modalities") or []
    if isinstance(exclude_modalities, (list, tuple, set)):
        normalized_modalities = [
            str(value).strip() for value in exclude_modalities if str(value).strip()
        ]
        if normalized_modalities:
            cmd_parts.extend(
                ["--exclude-modalities", ",".join(normalized_modalities)]
            )

    return " ".join(shlex.quote(part) for part in cmd_parts)


def _build_projects_datalad_save_terminal_command(req) -> str:
    """Build exact datalad save command for project snapshot endpoint."""
    payload = req.get_json(silent=True) or {}
    if not isinstance(payload, dict):
        payload = {}

    project_root = _session_project_root()
    if project_root is None:
        return ""

    message = str(payload.get("message") or "").strip() or "Save PRISM project changes"
    cmd_parts = ["datalad", "-C", str(project_root), "save", "-r", "-m", message]
    return " ".join(shlex.quote(part) for part in cmd_parts)


def _build_projects_datalad_enable_terminal_command(req) -> str:
    """Build exact datalad init/repair command for DataLad enable endpoint."""
    def _render_shell_segments(segments: list[list[str]]) -> str:
        rendered_segments = []
        for segment in segments:
            rendered_segments.append(" ".join(shlex.quote(part) for part in segment))
        return " && ".join(rendered_segments)

    payload = req.get_json(silent=True) or {}
    if not isinstance(payload, dict):
        payload = {}

    project_root = _session_project_root()
    if project_root is None:
        return ""

    message = str(payload.get("message") or "").strip() or "Enable DataLad for PRISM project"
    status = ProjectManager().get_datalad_status(project_root)

    if not status.get("enabled"):
        return _render_shell_segments(
            [
                ["datalad", "-C", str(project_root), "create", "--force"],
                ["datalad", "-C", str(project_root), "save", "-m", message],
            ]
        )

    next_missing = str(status.get("next_missing_subdataset") or "").strip()
    if not next_missing:
        return ""

    nested_root = project_root / Path(next_missing)
    nested_name = nested_root.name
    requires_parent_untrack = ProjectManager()._parent_tracks_nested_dataset_path(
        project_root,
        nested_root,
    )
    if requires_parent_untrack:
        return _render_shell_segments(
            [
                ["git", "-C", str(project_root), "rm", "--cached", "-r", "--", next_missing],
                [
                    "datalad",
                    "-C",
                    str(project_root),
                    "save",
                    "--updated",
                    "-m",
                    (
                        "PRISM: Converting data into nested PRISM-structure "
                        f'(prepare parent untracking "{next_missing}")'
                    ),
                ],
                ["datalad", "-C", str(project_root), "create", "-d", ".", "--force", next_missing],
                [
                    "datalad",
                    "-C",
                    str(nested_root),
                    "save",
                    "-m",
                    (
                        "PRISM: Nested structure conversion "
                        f'(initialize "{nested_name}")'
                    ),
                ],
                ["datalad", "-C", str(project_root), "save", "-m", message],
            ]
        )

    return _render_shell_segments(
        [
            ["datalad", "-C", str(project_root), "create", "-d", ".", "--force", next_missing],
            [
                "datalad",
                "-C",
                str(nested_root),
                "save",
                "-m",
                (
                    "PRISM: Nested structure conversion "
                    f'(initialize "{nested_name}")'
                ),
            ],
            ["datalad", "-C", str(project_root), "save", "-m", message],
        ]
    )


def _build_tools_recipes_surveys_terminal_command(req) -> str:
    """Build command preview for recipes survey export endpoint."""
    payload = req.get_json(silent=True) or {}
    if not isinstance(payload, dict):
        payload = {}

    dataset_path = _absolute_path_value(payload.get("dataset_path"))
    modality = str(payload.get("modality") or "survey").strip().lower() or "survey"
    out_format = str(payload.get("format") or "sav").strip().lower() or "sav"
    layout = str(payload.get("layout") or "long").strip().lower() or "long"
    lang = str(payload.get("lang") or "en").strip().lower() or "en"

    cmd_parts: list[str] = [
        "python",
        "prism_tools.py",
        "recipes",
        modality,
        "--prism",
        dataset_path or "<dataset-path>",
        "--format",
        out_format,
        "--layout",
        layout,
        "--lang",
        lang,
    ]

    survey_filter = str(payload.get("survey") or "").strip()
    if survey_filter:
        cmd_parts.extend(["--survey", survey_filter])

    sessions_filter = str(payload.get("sessions") or "").strip()
    if sessions_filter:
        cmd_parts.extend(["--sessions", sessions_filter])

    recipe_dir = _absolute_path_value(payload.get("recipe_dir"))
    if recipe_dir:
        cmd_parts.extend(["--recipes", recipe_dir])

    if bool(payload.get("include_raw", False)):
        cmd_parts.append("--include-raw")
    if bool(payload.get("merge_all", False)):
        cmd_parts.append("--merge-all")
    if not bool(payload.get("include_recipe_prefix", True)):
        cmd_parts.append("--no-recipe-prefix")

    return " ".join(shlex.quote(part) for part in cmd_parts)


def _build_projects_template_export_terminal_command(req) -> str:
    """Build command preview for project template export endpoint."""
    payload = req.get_json(silent=True) or {}
    if not isinstance(payload, dict):
        payload = {}

    project_path = _absolute_path_value(payload.get("project_path"))
    output_folder = _absolute_path_value(payload.get("output_folder"))
    validation_mode = str(payload.get("validation_mode") or "").strip()

    body: dict[str, str] = {"project_path": project_path or "<project-path>"}
    if validation_mode:
        body["validation_mode"] = validation_mode
    if output_folder:
        body["output_folder"] = output_folder

    endpoint_url = _get_request_url(req, "/api/projects/template-export")
    return " ".join(
        shlex.quote(part)
        for part in [
            "curl",
            "-X",
            "POST",
            endpoint_url,
            "-H",
            "Content-Type: application/json",
            "-d",
            json.dumps(body),
        ]
    )


def _build_survey_convert_terminal_command(req, *, dry_run: bool = False) -> str:
    """Build CLI-equivalent survey convert command for survey conversion endpoints."""
    form = req.form
    files = req.files

    uploaded = files.get("excel") or files.get("file")
    filename = ""
    if uploaded is not None:
        filename = str(getattr(uploaded, "filename", "") or "").strip()
    if not filename:
        filename = str(form.get("source_file_path", "") or "").strip()
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
                version_name = _coerce_template_version_value(version)
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
                version_name = _coerce_template_version_value(entry.get("version"))
                session_name = str(entry.get("session") or "").strip()
                run_value = entry.get("run")
                if not task_name or not version_name:
                    continue
                parsed_run: str | None = None
                if run_value not in {None, ""}:
                    parsed_run = _format_template_version_run(run_value)
                    if not parsed_run:
                        continue
                selector_suffix = ""
                if session_name:
                    selector_suffix += f";session={session_name}"
                if parsed_run is not None:
                    selector_suffix += f";run={parsed_run}"
                normalized_entries.append(
                    (
                        task_name,
                        session_name,
                        parsed_run or "",
                        selector_suffix,
                        version_name,
                    )
                )
            for (
                task_name,
                _session_name,
                _run_value,
                selector_suffix,
                version_name,
            ) in sorted(normalized_entries):
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
        filename = str(req.form.get("source_file_path", "") or "").strip()
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

    id_column = str(form.get("id_column", "") or "").strip()
    if id_column:
        cmd_parts.extend(["--id-column", id_column])

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
        filename = str(form.get("source_file_path", "") or "").strip()
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
            else str(project_root) if project_root is not None else "<output-dir>"
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
        "subject_rewrite_mode",
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
        "subject_rewrite_mode",
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


def _build_participants_merge_terminal_command(
    req, *, conflicts_csv: bool = False
) -> str:
    """Build a real backend CLI command for participants merge."""
    form = req.form
    files = req.files

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
        "merge",
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

    neurobagel_schema = str(form.get("neurobagel_schema", "") or "").strip()
    if neurobagel_schema:
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

    if conflicts_csv:
        cmd_parts.append("--conflicts-csv")
    elif _truthy_form_value(form.get("apply")):
        cmd_parts.append("--apply")

    if not conflicts_csv:
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
    endpoint = _resolve_request_endpoint(req)
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
    if endpoint == "conversion_survey.api_survey_workflow_command":
        workflow_command = str(
            req.form.get("workflow_command")
            or req.form.get("command")
            or req.form.get("mode")
            or ""
        ).strip().lower()
        return _build_survey_convert_terminal_command(
            req,
            dry_run=workflow_command != "convert",
        )
    if endpoint in {
        "conversion_survey.api_survey_convert_preview",
        "conversion_survey.api_survey_convert_validate",
    }:
        return _build_survey_convert_terminal_command(req, dry_run=True)
    if endpoint in {
        "conversion_survey.api_survey_prepare_workflow",
        "conversion_survey.api_survey_detect_version_context",
    }:
        return _build_survey_convert_terminal_command(req, dry_run=True)
    if endpoint == "conversion_survey.api_survey_check_project_templates":
        return _build_survey_check_templates_terminal_command(req)
    if endpoint == "tools.detect_columns":
        return _build_detect_columns_terminal_command(req)
    if endpoint == "tools.api_recipes_surveys":
        return _build_tools_recipes_surveys_terminal_command(req)
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
    if endpoint == "conversion_participants.api_participants_merge":
        return _build_participants_merge_terminal_command(req)
    if endpoint == "conversion_participants.api_participants_merge_conflicts":
        return _build_participants_merge_terminal_command(req, conflicts_csv=True)
    if endpoint == "conversion_participants.save_participant_mapping":
        return _build_save_participant_mapping_terminal_command(req)
    if endpoint == "projects.set_current":
        return _build_projects_set_current_terminal_command(req)
    if endpoint == "projects.save_datalad_snapshot":
        return _build_projects_datalad_save_terminal_command(req)
    if endpoint == "projects.enable_datalad_for_project":
        return _build_projects_datalad_enable_terminal_command(req)
    if endpoint == "projects_export.export_project_structure":
        return _build_projects_export_structure_terminal_command(req)
    if endpoint == "projects_export.export_project_folder":
        return _build_projects_folder_export_terminal_command(req)
    if endpoint == "projects_export.template_export_project":
        return _build_projects_template_export_terminal_command(req)
    return ""


def _build_generic_request_terminal_command(req) -> str:
    """Build a generic curl command preview for endpoints without explicit mapping."""
    method = str(getattr(req, "method", "GET") or "GET").upper()
    endpoint_url = _get_request_url(req, req.path or "/")
    cmd_parts: list[str] = ["curl", "-X", method, endpoint_url]

    payload = req.get_json(silent=True)
    if isinstance(payload, dict) and payload:
        cmd_parts.extend(["-H", "Content-Type: application/json", "-d", json.dumps(payload)])
        return " ".join(shlex.quote(part) for part in cmd_parts)

    if getattr(req, "form", None):
        for key in sorted(req.form.keys()):
            values = req.form.getlist(key) or [req.form.get(key)]
            for value in values:
                _append_curl_form_field(cmd_parts, key, value)

    if getattr(req, "files", None):
        for key in sorted(req.files.keys()):
            uploads = req.files.getlist(key)
            for upload in uploads:
                filename = str(getattr(upload, "filename", "") or "").strip()
                _append_curl_form_file(cmd_parts, key, filename)

    return " ".join(shlex.quote(part) for part in cmd_parts)


def _get_backend_monitoring_state(app_root: str) -> tuple[bool, bool]:
    """Return (enabled, verbose_enabled) backend monitoring state."""
    settings = load_app_settings(app_root=app_root)
    enabled = bool(settings.backend_monitoring)
    verbose_enabled = bool(getattr(settings, "backend_monitoring_verbose", False))
    return enabled, verbose_enabled


def _should_suppress_duplicate_action(
    *, dedupe_key: str, endpoint: str, verbose_enabled: bool
) -> bool:
    """Suppress immediate duplicate startup logs in non-verbose mode."""
    if verbose_enabled or endpoint not in _DUPLICATE_SUPPRESS_ENDPOINTS:
        return False

    now = time.monotonic()
    previous = _RECENT_ACTIONS.get(dedupe_key)
    _RECENT_ACTIONS[dedupe_key] = now

    if len(_RECENT_ACTIONS) > 128:
        stale_keys = [
            cached_key
            for cached_key, timestamp in _RECENT_ACTIONS.items()
            if now - timestamp > (_DUPLICATE_SUPPRESS_SECONDS * 4)
        ]
        for stale_key in stale_keys:
            _RECENT_ACTIONS.pop(stale_key, None)

    return previous is not None and (now - previous) <= _DUPLICATE_SUPPRESS_SECONDS


def _build_duplicate_suppression_key(req, endpoint: str, action: str) -> str:
    """Build endpoint-aware duplicate key to suppress startup spam safely."""
    payload = req.get_json(silent=True)
    if not isinstance(payload, dict):
        payload = {}

    if endpoint == "projects.set_current":
        return f"{endpoint}:{_absolute_path_value(payload.get('path'))}"

    if endpoint == "projects_export.export_project_structure":
        return f"{endpoint}:{_absolute_path_value(payload.get('project_path'))}"

    return f"{endpoint}:{action}"


def is_backend_monitoring_enabled(app_root: str) -> bool:
    """Return whether backend monitoring is enabled in app settings."""
    enabled, _verbose_enabled = _get_backend_monitoring_state(app_root)
    return enabled


def is_backend_monitoring_verbose_enabled(app_root: str) -> bool:
    """Return whether verbose backend monitoring is enabled."""
    _enabled, verbose_enabled = _get_backend_monitoring_state(app_root)
    return verbose_enabled


def _is_backend_terminal_command(command: str) -> bool:
    """Return True for CLI commands that execute backend-owned workflows."""
    command_text = str(command or "").strip()
    if not command_text:
        return False

    try:
        tokens = shlex.split(command_text)
    except ValueError:
        tokens = command_text.split()

    if not tokens:
        return False

    if str(tokens[0]).strip().lower() == "datalad":
        return True

    if len(tokens) < 2:
        return False

    python_token = str(tokens[0]).strip().lower()
    script_token = str(tokens[1]).strip().lower()
    return python_token in {"python", "python3"} and script_token in {
        "prism.py",
        "prism_tools.py",
    }


def _build_structured_terminal_lines(message: str, prefix: str) -> list[str]:
    """Render terminal output using date/time/action columns."""
    text = str(message or "").strip()
    if not text:
        return []

    action_text = text
    command_text = ""
    if "\ncmd=" in text:
        action_text, command_payload = text.split("\ncmd=", 1)
        command_text = f"cmd={command_payload.strip()}"

    timestamp = datetime.now().astimezone()
    date_text = timestamp.strftime("%Y-%m-%d")
    time_text = timestamp.strftime("%H:%M:%S")

    lines = [f"[{prefix}] {date_text}\t{time_text}\tACTION\t{action_text.strip()}"]
    if command_text:
        rendered_command = command_text
        if _supports_ansi_color():
            rendered_command = f"{_ANSI_GREEN}{command_text}{_ANSI_RESET}"
        lines.append(
            f"[{prefix}] {date_text}\t{time_text}\tCOMMAND\t{rendered_command}"
        )

    return lines


def emit_backend_action(
    message: str,
    app_root: str,
    *,
    prefix: str = "ANALYSIS_OUTPUT",
    force_emit: bool = False,
) -> None:
    """Print a backend action line to terminal when monitoring is enabled."""
    if not force_emit and not is_backend_monitoring_enabled(app_root):
        return

    text = str(message or "").strip()
    if not text:
        return

    lines = _build_structured_terminal_lines(text, prefix)
    if not lines:
        return

    rendered_lines = "\n".join(lines)
    print(f"\n{rendered_lines}\n", flush=True)


def emit_backend_request_action(req, app_root: str) -> None:
    """Print backend action line for mutating HTTP requests when enabled."""
    method = (req.method or "").upper()
    path = req.path or "/"
    endpoint = _resolve_request_endpoint(req)

    mapped_terminal_command = _build_terminal_command(req)
    backend_terminal_command = (
        mapped_terminal_command
        if _is_backend_terminal_command(mapped_terminal_command)
        else ""
    )

    if backend_terminal_command and method in _MUTATING_METHODS:
        try:
            record_project_session_command(
                backend_terminal_command,
                method=method,
                endpoint=endpoint,
            )
        except Exception:
            # Session logging must never block web request handling.
            pass

    monitoring_enabled, verbose_enabled = _get_backend_monitoring_state(app_root)
    if not monitoring_enabled:
        return

    if method not in _MUTATING_METHODS and not verbose_enabled:
        return

    if method in _MUTATING_METHODS and not verbose_enabled and not backend_terminal_command:
        return

    if endpoint in _SUPPRESSED_ENDPOINTS and not verbose_enabled:
        return

    label = _ENDPOINT_LABELS.get(endpoint, endpoint.replace("_", " "))
    payload_summary = _summarize_payload(req)
    prefix = "ANALYSIS_OUTPUT"
    if endpoint.startswith(("projects.", "projects_export.", "projects_library.")):
        prefix = "PROJECT"

    action = f"{method} {path} -> {label} (endpoint={endpoint})"
    if payload_summary:
        action = f"{action} | {payload_summary}"

    if verbose_enabled:
        terminal_command = mapped_terminal_command
        if not terminal_command:
            terminal_command = _build_generic_request_terminal_command(req)
    else:
        terminal_command = backend_terminal_command

    if terminal_command:
        action = f"{action}\ncmd={terminal_command}"

    dedupe_key = _build_duplicate_suppression_key(req, endpoint, action)
    if _should_suppress_duplicate_action(
        dedupe_key=dedupe_key,
        endpoint=endpoint,
        verbose_enabled=verbose_enabled,
    ):
        return

    emit_backend_action(action, app_root=app_root, prefix=prefix, force_emit=True)


def get_app_root_from_current_app(current_app_obj) -> str:
    """Resolve absolute app root path as string from current_app."""
    return str(Path(current_app_obj.root_path))
