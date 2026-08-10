import json
from pathlib import Path

from flask import Response, jsonify, request, session

from src.converters.file_reader import read_tabular_file
from src.participants_backend import (
    merge_neurobagel_schema_for_columns as _merge_neurobagel_schema_for_columns,
)

from .conversion_participants_helpers import (
    _generate_neurobagel_schema,
    _load_project_participant_filter_config,
)
from .conversion_participants_io import (
    _expected_delimiter_for_suffix,
    _normalize_separator_option,
    _resolve_participants_sheet_arg,
    _save_participants_upload_to_temp,
)
from .conversion_participants_mapping import (
    _canonicalize_preview_id_column,
    _collect_preview_column_values,
    _load_existing_participants_schema,
    _parse_requested_column_list,
    _rekey_neurobagel_schema_to_output_columns,
    _resolve_excluded_output_columns,
    _resolve_web_participant_import_mapping,
)
from .conversion_utils import resolve_effective_library_path


def _build_participants_merge_schema_preview(
    *,
    project_root: Path,
    columns: list[str],
    neurobagel_schema: dict,
    mapping: dict | None,
    log_callback=None,
) -> dict:
    schema = {}
    existing_schema = _load_existing_participants_schema(project_root)

    for column_name in columns:
        existing_field = existing_schema.get(column_name)
        if isinstance(existing_field, dict):
            schema[column_name] = dict(existing_field)
        else:
            schema[column_name] = {}

    if neurobagel_schema:
        aligned_neurobagel_schema = _rekey_neurobagel_schema_to_output_columns(
            neurobagel_schema=neurobagel_schema,
            mapping=mapping,
            allowed_columns=columns,
        )
        schema, _merged_count = _merge_neurobagel_schema_for_columns(
            schema,
            aligned_neurobagel_schema,
            columns,
            log_callback=log_callback,
        )

    fallback_descriptions = {
        "participant_id": "Participant identifier (sub-<label>)",
        "age": "Age of participant",
    }
    for column_name in columns:
        field = schema.setdefault(column_name, {})
        if not isinstance(field, dict):
            schema[column_name] = {}
            field = schema[column_name]
        current_description = str(field.get("Description") or "").strip()
        if not current_description:
            field["Description"] = fallback_descriptions.get(
                column_name, f"Participant {column_name}"
            )

    return schema


def _project_relative_merge_paths(
    project_root: Path, paths: list[str] | None
) -> list[str]:
    if not isinstance(paths, list):
        return []

    rebased_paths: list[str] = []
    for path_value in paths:
        path_text = str(path_value or "").strip()
        if not path_text:
            continue
        rebased_paths.append(str(project_root / Path(path_text).name))
    return rebased_paths


def _parse_participants_merge_request(
    project_root: Path,
) -> dict[str, object]:
    upload = _save_participants_upload_to_temp(
        uploaded_file=request.files.get("file"),
        temp_prefix="prism_participants_merge_api_",
    )
    suffix = str(upload["suffix"])

    separator_option = _normalize_separator_option(request.form.get("separator"))
    preview_limit_text = str(request.form.get("preview_limit", "20") or "20").strip()
    preview_limit = int(preview_limit_text) if preview_limit_text.isdigit() else 20
    explicit_id_column = request.form.get("id_column", "").strip() or None
    extra_columns = _parse_requested_column_list(request.form.get("extra_columns"))
    excluded_columns = set(
        _parse_requested_column_list(request.form.get("excluded_columns"))
    )

    neurobagel_schema_json = request.form.get("neurobagel_schema")
    neurobagel_schema = {}
    if neurobagel_schema_json:
        try:
            neurobagel_schema = json.loads(neurobagel_schema_json)
        except json.JSONDecodeError:
            neurobagel_schema = {}

    harmonization_decisions_json = request.form.get("harmonization_decisions")
    harmonization_decisions: dict[str, object] = {}
    if harmonization_decisions_json:
        try:
            decoded = json.loads(harmonization_decisions_json)
            if isinstance(decoded, dict):
                harmonization_decisions = decoded
        except json.JSONDecodeError:
            harmonization_decisions = {}

    session_resolution_decisions_json = request.form.get(
        "session_resolution_decisions"
    )
    session_resolution_decisions: dict[str, object] = {}
    if session_resolution_decisions_json:
        try:
            decoded = json.loads(session_resolution_decisions_json)
            if isinstance(decoded, dict):
                session_resolution_decisions = decoded
        except json.JSONDecodeError:
            session_resolution_decisions = {}

    logs = []

    def log_msg(level, message):
        logs.append({"level": level, "message": message})

    tmp_dir = str(upload["tmp_dir"])
    input_path = Path(str(upload["input_path"]))

    sheet_arg = _resolve_participants_sheet_arg(
        input_path=input_path,
        suffix=suffix,
        sheet_value=request.form.get("sheet"),
    )

    context = _resolve_web_participant_import_mapping(
        project_root=project_root,
        input_path=input_path,
        suffix=suffix,
        sheet_arg=sheet_arg,
        separator_option=separator_option,
        explicit_id_column=explicit_id_column,
        excluded_columns=excluded_columns,
        extra_columns=extra_columns,
        log_callback=log_msg,
    )

    mapping = context.get("mapping")
    if not isinstance(mapping, dict):
        raise ValueError("Could not resolve participant mapping")

    return {
        "tmp_dir": tmp_dir,
        "input_path": input_path,
        "suffix": suffix,
        "sheet_arg": sheet_arg,
        "separator": _expected_delimiter_for_suffix(suffix, separator_option),
        "preview_limit": preview_limit,
        "neurobagel_schema": neurobagel_schema,
        "harmonization_decisions": harmonization_decisions,
        "session_resolution_decisions": session_resolution_decisions,
        "context": context,
        "mapping": mapping,
        "logs": logs,
        "log_callback": log_msg,
    }


def _participants_id_required_response(
    *,
    source_columns: list[str],
    suggested_id_column: object | None = None,
    logs: list[dict[str, str]] | None = None,
) -> tuple[Response, int]:
    payload: dict[str, object] = {
        "error": "id_column_required",
        "message": "Select the source ID column manually. It will be renamed to participant_id in output.",
        "columns": source_columns,
    }
    if logs is not None:
        payload["log"] = logs
    suggested_text = str(suggested_id_column or "").strip()
    if suggested_text:
        payload["suggested_id_column"] = suggested_text
        payload["participant_id_found"] = False
    return jsonify(payload), 409


def _validate_participants_merge_request_context(
    merge_request: dict[str, object],
) -> tuple[dict[str, object] | None, tuple[Response, int] | None]:
    raw_context = merge_request.get("context")
    if not isinstance(raw_context, dict):
        raise ValueError("Could not resolve participant import context")
    context = raw_context

    raw_logs = merge_request.get("logs")
    logs: list[dict[str, str]] | None = None
    if isinstance(raw_logs, list):
        logs = []
        for entry in raw_logs:
            if not isinstance(entry, dict):
                continue
            logs.append(
                {
                    "level": str(entry.get("level") or ""),
                    "message": str(entry.get("message") or ""),
                }
            )

    raw_id_resolution = context.get("id_resolution")
    id_resolution = raw_id_resolution if isinstance(raw_id_resolution, dict) else {}
    raw_source_columns = context.get("source_columns")
    source_columns = (
        [str(column) for column in raw_source_columns]
        if isinstance(raw_source_columns, list)
        else []
    )

    if bool(id_resolution.get("id_selection_required")):
        return None, _participants_id_required_response(
            source_columns=source_columns,
            logs=logs,
            suggested_id_column=id_resolution.get("suggested_id_column"),
        )

    detected_id_col = str(context.get("detected_id_column") or "").strip()
    if not detected_id_col:
        return None, _participants_id_required_response(
            source_columns=source_columns,
            logs=logs,
        )

    return {
        "context": context,
        "id_resolution": id_resolution,
        "source_columns": source_columns,
        "detected_id_col": detected_id_col,
    }, None


def _build_existing_participants_preview_payload(
    project_root: Path,
    excluded_columns: set[str] | None = None,
) -> dict[str, object]:
    from src.participants_converter import ParticipantsConverter

    participants_tsv = project_root / "participants.tsv"
    if not participants_tsv.exists() or not participants_tsv.is_file():
        raise ValueError("participants.tsv not found in the selected project")

    read_result = read_tabular_file(
        participants_tsv,
        kind="tsv",
        separator="\t",
    )
    df = read_result.df
    if df is None or df.empty:
        raise ValueError("participants.tsv is empty")

    source_columns = [str(col) for col in df.columns]
    source_id_column = (
        "participant_id"
        if "participant_id" in df.columns
        else ParticipantsConverter._find_participant_id_source_column(source_columns)
    )
    if not source_id_column:
        raise ValueError("participants.tsv has no identifiable participant ID column")

    output_df, preview_id_column = _canonicalize_preview_id_column(
        df,
        source_id_column,
        keep_session_id_columns=True,
    )
    if (
        output_df is None
        or output_df.empty
        or "participant_id" not in output_df.columns
    ):
        raise ValueError("No valid participant rows found in participants.tsv")

    resolved_excluded_columns = _resolve_excluded_output_columns(
        columns=[str(col) for col in output_df.columns],
        requested_excluded=excluded_columns,
    )
    if resolved_excluded_columns:
        output_df = output_df.drop(columns=sorted(resolved_excluded_columns))

    preview_df = output_df.head(20)
    preview_df = preview_df.astype(object).where(preview_df.notna(), None)

    library_path = resolve_effective_library_path()
    participant_filter_config = _load_project_participant_filter_config(
        session.get("current_project_path")
    )
    neurobagel_schema = _generate_neurobagel_schema(
        output_df,
        preview_id_column,
        library_path=library_path,
        participant_filter_config=participant_filter_config,
    )

    existing_schema = _load_existing_participants_schema(project_root)
    if isinstance(existing_schema, dict):
        for field_name, field_schema in existing_schema.items():
            if not field_name:
                continue
            if not isinstance(field_schema, dict):
                neurobagel_schema[field_name] = field_schema
                continue

            current_schema = neurobagel_schema.get(field_name)
            if isinstance(current_schema, dict):
                merged = dict(current_schema)
                merged.update(field_schema)
                neurobagel_schema[field_name] = merged
            else:
                neurobagel_schema[field_name] = dict(field_schema)

    return {
        "status": "success",
        "columns": [str(col) for col in output_df.columns],
        "column_values": _collect_preview_column_values(output_df),
        "source_columns": source_columns,
        "questionnaire_like_columns": [],
        "id_column": "participant_id",
        "source_id_column": str(source_id_column),
        "suggested_id_column": str(source_id_column),
        "participant_id_found": True,
        "id_selection_required": False,
        "participant_count": len(output_df),
        "preview_rows": preview_df.to_dict(orient="records"),
        "library_path": str(library_path),
        "simulation_note": "Previewing existing participants.tsv from project root.",
        "total_source_columns": len(source_columns),
        "extracted_columns": len(output_df.columns),
        "neurobagel_schema": neurobagel_schema,
        "format_warnings": [],
        "problem_columns": [],
    }


def _convert_existing_participants_files(
    *,
    project_root: Path,
    neurobagel_schema: dict,
    excluded_columns: set[str],
    log_callback,
) -> dict[str, object]:
    from src.participants_converter import ParticipantsConverter

    participants_tsv = project_root / "participants.tsv"
    participants_json = project_root / "participants.json"

    if not participants_tsv.exists() or not participants_tsv.is_file():
        raise ValueError("participants.tsv not found in the selected project")

    read_result = read_tabular_file(
        participants_tsv,
        kind="tsv",
        separator="\t",
    )
    df = read_result.df
    if df is None or df.empty:
        raise ValueError("participants.tsv is empty")

    source_columns = [str(col) for col in df.columns]
    source_id_column = (
        "participant_id"
        if "participant_id" in df.columns
        else ParticipantsConverter._find_participant_id_source_column(source_columns)
    )
    if not source_id_column:
        raise ValueError("participants.tsv has no identifiable participant ID column")

    output_df, _ = _canonicalize_preview_id_column(
        df,
        source_id_column,
        keep_session_id_columns=False,
    )
    if (
        output_df is None
        or output_df.empty
        or "participant_id" not in output_df.columns
    ):
        raise ValueError("No valid participant rows found in participants.tsv")

    resolved_excluded_columns = _resolve_excluded_output_columns(
        columns=[str(col) for col in output_df.columns],
        requested_excluded=excluded_columns,
    )
    if resolved_excluded_columns:
        output_df = output_df.drop(columns=sorted(resolved_excluded_columns))
        log_callback(
            "INFO",
            "Excluded column(s) from existing participants files: "
            + ", ".join(sorted(resolved_excluded_columns)),
        )

    output_df.to_csv(participants_tsv, sep="\t", index=False)
    log_callback(
        "INFO",
        f"Normalized and wrote {participants_tsv.name} with {len(output_df)} participant row(s)",
    )

    participants_json_data = _load_existing_participants_schema(project_root)
    if not isinstance(participants_json_data, dict):
        participants_json_data = {}

    output_columns = [str(col) for col in output_df.columns]
    output_column_set = set(output_columns)
    removed_schema_columns = [
        str(column_name)
        for column_name in participants_json_data.keys()
        if str(column_name) not in output_column_set
    ]
    if removed_schema_columns:
        participants_json_data = {
            str(column_name): column_schema
            for column_name, column_schema in participants_json_data.items()
            if str(column_name) in output_column_set
        }
        log_callback(
            "INFO",
            "Removed participants.json field(s) not present in output columns: "
            + ", ".join(sorted(removed_schema_columns)),
        )

    for col in output_columns:
        col_name = str(col)
        if col_name not in participants_json_data or not isinstance(
            participants_json_data.get(col_name), dict
        ):
            participants_json_data[col_name] = {}

    if neurobagel_schema:
        aligned_neurobagel_schema = _rekey_neurobagel_schema_to_output_columns(
            neurobagel_schema=neurobagel_schema,
            mapping=None,
            allowed_columns=list(output_df.columns),
        )
        participants_json_data, merged_count = _merge_neurobagel_schema_for_columns(
            participants_json_data,
            aligned_neurobagel_schema,
            output_columns,
            log_callback=log_callback,
        )
        log_callback(
            "INFO",
            f"Merged NeuroBagel annotations for {merged_count} participants.tsv column(s)",
        )

    fallback_descriptions = {
        "participant_id": "Participant identifier (sub-<label>)",
        "age": "Age of participant",
    }
    for col in output_columns:
        col_name = str(col)
        field = participants_json_data.setdefault(col_name, {})
        if not isinstance(field, dict):
            participants_json_data[col_name] = {}
            field = participants_json_data[col_name]

        current_description = str(field.get("Description") or "").strip()
        if not current_description:
            field["Description"] = fallback_descriptions.get(
                col_name, f"Participant {col_name}"
            )

    participants_json.write_text(
        json.dumps(participants_json_data, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )
    log_callback("INFO", f"Updated {participants_json.name}")

    return {
        "status": "success",
        "participant_count": len(output_df),
        "files_created": [str(participants_tsv), str(participants_json)],
        "output_directory": str(project_root),
    }
