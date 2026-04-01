import re
import shutil
import tempfile
from pathlib import Path

from flask import Blueprint, jsonify, request, session
from werkzeug.utils import secure_filename
from src.converters.file_reader import read_tabular_file
from src.participants_backend import (
    convert_dataset_participants,
    preview_dataset_participants,
    save_participant_mapping as save_participant_mapping_backend,
)
from src.participants_paths import participants_mapping_candidates

from .conversion_participants_helpers import (
    _detect_repeated_questionnaire_prefixes,
    _filter_participant_relevant_columns,
    _generate_neurobagel_schema,
    _is_likely_questionnaire_column,
    _load_project_participant_filter_config,
    _load_survey_template_item_ids,
    _normalize_column_name,
)
from .conversion_utils import resolve_effective_library_path
from .projects_helpers import _resolve_project_root_path

conversion_participants_bp = Blueprint("conversion_participants", __name__)

_SEPARATOR_MAP: dict[str, str] = {
    "comma": ",",
    "semicolon": ";",
    "tab": "\t",
    "pipe": "|",
}


def _normalize_separator_option(value: str | None) -> str:
    normalized = str(value or "auto").strip().lower()
    if normalized in {"", "auto", "default"}:
        return "auto"
    if normalized in _SEPARATOR_MAP:
        return normalized
    raise ValueError(
        "Invalid separator option. Use one of: auto, comma, semicolon, tab, pipe"
    )


def _expected_delimiter_for_suffix(suffix: str, separator_option: str) -> str | None:
    if separator_option != "auto":
        return _SEPARATOR_MAP[separator_option]
    if suffix == ".tsv":
        return "\t"
    if suffix == ".csv":
        return ","
    return None


def _read_participants_input_table(
    *,
    input_path: Path,
    suffix: str,
    sheet_arg: str | int,
    separator_option: str,
):
    if suffix in {".xlsx", ".csv", ".tsv"}:
        kind = "xlsx" if suffix == ".xlsx" else suffix.lstrip(".")
        result = read_tabular_file(
            input_path,
            kind=kind,
            sheet=sheet_arg,
            separator=_expected_delimiter_for_suffix(suffix, separator_option),
        )
        return result.df

    if suffix == ".lsa":
        from src.converters.survey import _read_lsa_as_dataframe

        return _read_lsa_as_dataframe(input_path)

    raise ValueError("Supported formats: .xlsx, .csv, .tsv, .lsa")


def _get_excel_sheet_names(input_path: Path) -> list[str]:
    try:
        import pandas as pd

        with pd.ExcelFile(input_path) as workbook:
            return [str(name) for name in workbook.sheet_names]
    except Exception:
        return []


_TIME_STYLE_PATTERNS: tuple[tuple[str, re.Pattern[str]], ...] = (
    ("clock", re.compile(r"^\d{1,2}:\d{2}(?::\d{2})?$")),
    ("hours", re.compile(r"^\d+(?:\.\d+)?\s*h(?:ours?)?$", re.IGNORECASE)),
    (
        "minutes",
        re.compile(r"^\d+(?:\.\d+)?\s*m(?:in(?:ute)?s?)?$", re.IGNORECASE),
    ),
    ("seconds", re.compile(r"^\d+(?:\.\d+)?\s*s(?:ec(?:ond)?s?)?$", re.IGNORECASE)),
    ("numeric", re.compile(r"^\d+(?:\.\d+)?$")),
)


def _classify_time_style(value: str) -> str | None:
    text = str(value or "").strip()
    if not text:
        return None

    for style_name, pattern in _TIME_STYLE_PATTERNS:
        if pattern.match(text):
            return style_name

    return None


def _detect_mixed_time_style_columns(
    df, max_examples: int = 4, max_scanned_values: int = 250
) -> list[dict[str, object]]:
    """Find columns that mix multiple time-like formats, e.g. HH:MM and 2h."""
    issues: list[dict[str, object]] = []

    for col in df.columns:
        col_values = [
            str(v).strip()
            for v in df[col].dropna().astype(str).head(max_scanned_values)
            if str(v).strip()
        ]
        if len(col_values) < 2:
            continue

        style_set: set[str] = set()
        example_values: list[str] = []

        for value in col_values:
            style = _classify_time_style(value)
            if not style:
                continue
            style_set.add(style)
            if value not in example_values:
                example_values.append(value)

        if len(style_set) < 2:
            continue

        has_clock_like = "clock" in style_set
        has_unit_or_numeric = any(
            style in style_set for style in {"hours", "minutes", "seconds", "numeric"}
        )
        if not (has_clock_like and has_unit_or_numeric):
            continue

        issues.append(
            {
                "column": str(col),
                "detected_formats": sorted(style_set),
                "examples": example_values[:max_examples],
            }
        )

    return issues


def _format_mixed_time_style_message(
    mixed_columns: list[dict[str, object]],
) -> str:
    if not mixed_columns:
        return ""

    details: list[str] = []
    for issue in mixed_columns:
        column = str(issue.get("column") or "")
        examples_raw = issue.get("examples") or []
        examples = list(examples_raw) if isinstance(examples_raw, (list, tuple)) else []
        examples_text = ", ".join(f"'{str(v)}'" for v in examples[:4])
        if examples_text:
            details.append(f"{column} ({examples_text})")
        else:
            details.append(column)

    joined = "; ".join(details)
    return (
        "Detected mixed time formats in participant data: "
        f"{joined}. Please fix this manually in the source file before import. "
        "PRISM does not auto-convert mixed formats. Use exactly one format per "
        "affected column (recommended: all HH:MM or all numeric minutes) and "
        "avoid ranges/ambiguous values (for example '4-6h' or '10 30')."
    )


def _get_session_project_root() -> Path | None:
    """Resolve current project root from session path (folder or project.json path)."""
    current_project_path = session.get("current_project_path")
    if not isinstance(current_project_path, str) or not current_project_path.strip():
        return None
    return _resolve_project_root_path(current_project_path)


def _merge_neurobagel_schema_for_columns(
    base_schema: dict,
    neurobagel_schema: dict,
    allowed_columns: list[str],
    log_callback=None,
) -> tuple[dict, int]:
    """Merge NeuroBagel schema into participants metadata, limited to TSV columns only."""
    if not isinstance(base_schema, dict):
        base_schema = {}
    if not isinstance(neurobagel_schema, dict):
        return base_schema, 0

    allowed = {str(col) for col in allowed_columns}
    merged_count = 0

    for col, schema_def in neurobagel_schema.items():
        if col not in allowed:
            if log_callback:
                log_callback(
                    "INFO",
                    f"Skipped annotation-only field '{col}' (not present in participants.tsv)",
                )
            continue

        if col not in base_schema:
            base_schema[col] = {}

        if isinstance(schema_def, dict) and "Annotations" in schema_def:
            if "Annotations" not in base_schema[col]:
                base_schema[col]["Annotations"] = {}
            annotations = schema_def["Annotations"]
            if isinstance(annotations, dict):
                base_schema[col]["Annotations"].update(annotations)

        if isinstance(schema_def, dict):
            for key, value in schema_def.items():
                if key == "Annotations":
                    continue
                if key not in base_schema[col]:
                    base_schema[col][key] = value

        merged_count += 1

    return base_schema, merged_count


def _normalize_column_token(value: str | None) -> str:
    return re.sub(r"[^a-z0-9]+", "", str(value or "").strip().lower())


def _rekey_neurobagel_schema_to_output_columns(
    neurobagel_schema: dict,
    mapping: dict | None,
    allowed_columns: list[str],
) -> dict:
    """Align frontend schema keys with converted participants.tsv column names."""
    if not isinstance(neurobagel_schema, dict):
        return {}

    allowed = [str(col) for col in (allowed_columns or [])]
    allowed_set = set(allowed)
    allowed_by_norm = {
        _normalize_column_token(col): col
        for col in allowed
        if _normalize_column_token(col)
    }

    source_to_target_exact: dict[str, str] = {}
    source_to_target_norm: dict[str, str] = {}

    mapping_block = mapping.get("mappings") if isinstance(mapping, dict) else None
    if isinstance(mapping_block, dict):
        for spec in mapping_block.values():
            if not isinstance(spec, dict):
                continue

            source_name = str(spec.get("source_column") or "").strip()
            target_name = str(spec.get("standard_variable") or "").strip()
            if not source_name or not target_name:
                continue

            resolved_target = allowed_by_norm.get(
                _normalize_column_token(target_name), target_name
            )
            source_to_target_exact[source_name] = resolved_target

            source_norm = _normalize_column_token(source_name)
            if source_norm:
                source_to_target_norm[source_norm] = resolved_target

    remapped: dict = {}

    for raw_key, schema_def in neurobagel_schema.items():
        key = str(raw_key or "").strip()
        if not key:
            continue

        target_key = key if key in allowed_set else ""

        if not target_key:
            mapped_target = source_to_target_exact.get(key)
            if mapped_target in allowed_set:
                target_key = mapped_target

        if not target_key:
            key_norm = _normalize_column_token(key)
            mapped_target = source_to_target_norm.get(key_norm) if key_norm else None
            if mapped_target in allowed_set:
                target_key = mapped_target
            elif key_norm and key_norm in allowed_by_norm:
                target_key = allowed_by_norm[key_norm]

        if not target_key:
            # Keep unmatched keys untouched so merge can still log skipped fields.
            target_key = key

        existing = remapped.get(target_key)
        if not isinstance(existing, dict) or not isinstance(schema_def, dict):
            remapped[target_key] = schema_def
            continue

        merged = dict(existing)
        for field_key, field_value in schema_def.items():
            if field_key == "Annotations":
                prev_annotations = merged.get("Annotations")
                if isinstance(prev_annotations, dict) and isinstance(field_value, dict):
                    next_annotations = dict(prev_annotations)
                    next_annotations.update(field_value)
                    merged["Annotations"] = next_annotations
                else:
                    merged["Annotations"] = field_value
            else:
                merged[field_key] = field_value
        remapped[target_key] = merged

    return remapped


def _canonicalize_preview_id_column(output_df, id_column: str | None):
    """Mirror final participants.tsv naming in preview payloads."""
    if output_df is None:
        return output_df, str(id_column or "").strip()

    source_id_column = str(id_column or "").strip()
    if not source_id_column:
        if "participant_id" in getattr(output_df, "columns", []):
            return output_df, "participant_id"
        return output_df, source_id_column

    if source_id_column == "participant_id":
        return output_df, "participant_id"

    if source_id_column not in output_df.columns:
        return output_df, source_id_column

    preview_df = output_df.copy()
    if "participant_id" in preview_df.columns:
        preview_df = preview_df.drop(columns=["participant_id"])

    preview_df = preview_df.rename(columns={source_id_column: "participant_id"})
    ordered_columns = ["participant_id"] + [
        col for col in preview_df.columns if col != "participant_id"
    ]
    preview_df = preview_df[ordered_columns]
    return preview_df, "participant_id"


def _parse_requested_column_list(raw_value: str | None) -> list[str]:
    payload = str(raw_value or "").strip()
    if not payload:
        return []

    try:
        import json as _json

        parsed = _json.loads(payload)
    except Exception:
        return []

    if not isinstance(parsed, list):
        return []

    result: list[str] = []
    seen: set[str] = set()
    for value in parsed:
        column_name = str(value or "").strip()
        if not column_name or column_name in seen:
            continue
        seen.add(column_name)
        result.append(column_name)
    return result


@conversion_participants_bp.route("/api/save-participant-mapping", methods=["POST"])
def save_participant_mapping():
    """Save additional-variables mapping JSON file to the project library directory."""
    try:
        data = request.get_json()
        if not data:
            return jsonify({"error": "No JSON data provided"}), 400

        mapping = data.get("mapping")
        library_path = data.get("library_path")
        project_root = _get_session_project_root()
        result = save_participant_mapping_backend(
            mapping,
            project_root=project_root,
            library_path=library_path,
        )
        mapping_file = Path(result["mapping_file"])

        return jsonify(
            {
                "status": "success",
                "file_path": str(mapping_file),
                "library_source": result["library_source"],
                "message": (
                    f"Saved {mapping_file.name}. "
                    "This mapping is applied when you run Extract & Convert."
                ),
            }
        )
    except ValueError as e:
        return jsonify({"error": str(e)}), 400
    except Exception as e:
        import traceback

        traceback.print_exc()
        return jsonify({"error": f"Error saving mapping: {str(e)}"}), 500


@conversion_participants_bp.route("/api/participants-check", methods=["GET"])
def api_participants_check():
    """Check if participants.tsv and participants.json exist in the project/dataset."""
    project_root = _get_session_project_root()
    if not project_root:
        return jsonify({"error": "No project selected"}), 400

    participants_tsv = project_root / "participants.tsv"
    participants_json = project_root / "participants.json"
    exists_root = participants_tsv.exists() or participants_json.exists()

    return jsonify(
        {
            "exists": exists_root,
            "location": ("root" if exists_root else None),
            "files": {
                "participants_tsv": (
                    str(participants_tsv) if participants_tsv.exists() else None
                ),
                "participants_json": (
                    str(participants_json) if participants_json.exists() else None
                ),
            },
        }
    )


@conversion_participants_bp.route("/api/participants-detect-id", methods=["POST"])
def api_participants_detect_id():
    """Detect participant ID column for an uploaded participant file."""
    uploaded_file = request.files.get("file")
    if not uploaded_file or not uploaded_file.filename:
        return jsonify({"error": "Missing input file"}), 400

    filename = secure_filename(uploaded_file.filename)
    suffix = Path(filename).suffix.lower()
    try:
        separator_option = _normalize_separator_option(request.form.get("separator"))
    except ValueError as error:
        return jsonify({"error": str(error)}), 400

    if suffix not in {".xlsx", ".csv", ".tsv", ".lsa"}:
        return jsonify({"error": "Supported formats: .xlsx, .csv, .tsv, .lsa"}), 400

    tmp_dir = tempfile.mkdtemp(prefix="prism_participants_detect_id_")
    try:
        tmp_path = Path(tmp_dir)
        input_path = tmp_path / filename
        uploaded_file.save(str(input_path))

        sheet = request.form.get("sheet", "0").strip() or "0"
        try:
            sheet_arg = int(sheet) if sheet.isdigit() else sheet
        except (ValueError, TypeError):
            sheet_arg = 0

        df = _read_participants_input_table(
            input_path=input_path,
            suffix=suffix,
            sheet_arg=sheet_arg,
            separator_option=separator_option,
        )
        sheet_names = _get_excel_sheet_names(input_path) if suffix == ".xlsx" else []

        from src.converters.id_detection import (
            detect_id_column as _detect_id,
            has_prismmeta_columns as _has_pm_cols,
        )

        source_fmt = "lsa" if suffix == ".lsa" else "xlsx"
        detected_id = _detect_id(
            list(df.columns),
            source_fmt,
            explicit_id_column=None,
            has_prismmeta=_has_pm_cols(list(df.columns)),
        )

        return jsonify(
            {
                "status": "success",
                "id_found": bool(detected_id),
                "id_column": detected_id,
                "columns": [str(c) for c in df.columns],
                "sheet_count": len(sheet_names) if suffix == ".xlsx" else None,
                "sheet_names": sheet_names,
                "show_sheet_selector": suffix == ".xlsx" and len(sheet_names) > 1,
            }
        )
    except Exception as e:
        return jsonify({"error": str(e)}), 500
    finally:
        shutil.rmtree(tmp_dir, ignore_errors=True)


@conversion_participants_bp.route("/api/participants-preview", methods=["POST"])
def api_participants_preview():
    """Preview participant data extraction from uploaded file."""
    mode = request.form.get("mode", "file")

    if mode == "file":
        uploaded_file = request.files.get("file")
        if not uploaded_file or not uploaded_file.filename:
            return jsonify({"error": "Missing input file"}), 400

        filename = secure_filename(uploaded_file.filename)
        suffix = Path(filename).suffix.lower()
        try:
            separator_option = _normalize_separator_option(
                request.form.get("separator")
            )
        except ValueError as error:
            return jsonify({"error": str(error)}), 400

        if suffix not in {".xlsx", ".csv", ".tsv", ".lsa"}:
            return jsonify({"error": "Supported formats: .xlsx, .csv, .tsv, .lsa"}), 400

        tmp_dir = tempfile.mkdtemp(prefix="prism_participants_preview_")
        try:
            preview_stage = "initializing preview"
            tmp_path = Path(tmp_dir)
            input_path = tmp_path / filename
            uploaded_file.save(str(input_path))

            sheet = request.form.get("sheet", "0").strip() or "0"
            try:
                sheet_arg = int(sheet) if sheet.isdigit() else sheet
            except (ValueError, TypeError):
                sheet_arg = 0

            preview_stage = "reading input file"
            try:
                df = _read_participants_input_table(
                    input_path=input_path,
                    suffix=suffix,
                    sheet_arg=sheet_arg,
                    separator_option=separator_option,
                )
            except ImportError:
                return jsonify({"error": "LimeSurvey support not available"}), 500

            from src.converters.id_detection import (
                detect_id_column as _detect_id,
                has_prismmeta_columns as _has_pm_cols,
            )

            id_column = request.form.get("id_column", "").strip() or None
            source_fmt = "lsa" if suffix == ".lsa" else "xlsx"
            _has_pm = _has_pm_cols(list(df.columns))
            preview_stage = "detecting participant ID column"
            id_column = _detect_id(
                list(df.columns),
                source_fmt,
                explicit_id_column=id_column,
                has_prismmeta=_has_pm,
            )

            if not id_column:
                return (
                    jsonify(
                        {
                            "error": "id_column_required",
                            "message": f"Could not auto-detect ID column. Available columns: {', '.join(df.columns)}",
                            "columns": list(df.columns),
                        }
                    ),
                    409,
                )

            mixed_time_style_columns = _detect_mixed_time_style_columns(df)
            mixed_time_warning = _format_mixed_time_style_message(
                mixed_time_style_columns
            )

            preview_stage = "resolving template library"
            library_path = resolve_effective_library_path()
            participant_filter_config = _load_project_participant_filter_config(
                session.get("current_project_path")
            )

            preview_stage = "loading survey template IDs"
            template_item_ids = _load_survey_template_item_ids(library_path)
            repeated_prefixes = _detect_repeated_questionnaire_prefixes(
                [str(c) for c in df.columns],
                participant_filter_config=participant_filter_config,
            )
            questionnaire_like_columns = [
                str(col)
                for col in df.columns
                if str(col) != id_column
                and _is_likely_questionnaire_column(
                    str(col),
                    _normalize_column_name(str(col)),
                    template_item_ids,
                    repeated_prefixes,
                )
            ]

            output_columns = _filter_participant_relevant_columns(
                df,
                id_column=id_column,
                library_path=library_path,
                participant_filter_config=participant_filter_config,
                include_template_columns=False,
                allow_nonrelevant_fallback=False,
            )
            excluded_columns = set(
                col
                for col in _parse_requested_column_list(
                    request.form.get("excluded_columns")
                )
                if col != id_column
            )

            additional_columns = []
            project_root = _get_session_project_root()
            if project_root:
                import json

                mapping_candidates = participants_mapping_candidates(project_root)

                loaded_mapping = None
                for candidate in mapping_candidates:
                    if candidate.exists() and candidate.is_file():
                        try:
                            with open(candidate, "r", encoding="utf-8") as mapping_file:
                                loaded_mapping = json.load(mapping_file)
                            break
                        except Exception:
                            loaded_mapping = None

                if isinstance(loaded_mapping, dict):
                    if isinstance(loaded_mapping.get("mappings"), dict):
                        for map_spec in loaded_mapping["mappings"].values():
                            if not isinstance(map_spec, dict):
                                continue
                            source_col = str(
                                map_spec.get("source_column") or ""
                            ).strip()
                            if (
                                source_col
                                and source_col in df.columns
                                and source_col not in excluded_columns
                            ):
                                additional_columns.append(source_col)
                    elif loaded_mapping:
                        for source_col in loaded_mapping.keys():
                            source_name = str(source_col or "").strip()
                            if (
                                source_name
                                and source_name in df.columns
                                and source_name not in excluded_columns
                            ):
                                additional_columns.append(source_name)

                # Keep preview column membership driven by the current source file
                # plus the explicit additional-variable selection. Saved
                # participants.json metadata is merged separately in the UI and
                # must not force removed variables back into the preview.

            for column_name in additional_columns:
                if column_name not in output_columns:
                    output_columns.append(column_name)

            # Also honour any columns explicitly requested by the frontend
            # (user-added via "Additional Variables" modal, sent as extra_columns JSON).
            extra_columns_json = request.form.get("extra_columns", "")
            if extra_columns_json:
                try:
                    import json as _json

                    for col in _json.loads(extra_columns_json):
                        col = str(col or "").strip()
                        if (
                            col
                            and col in df.columns
                            and col not in excluded_columns
                            and col not in output_columns
                        ):
                            output_columns.append(col)
                except Exception:
                    pass

            if excluded_columns:
                output_columns = [
                    col
                    for col in output_columns
                    if col == id_column or col not in excluded_columns
                ]

            if len(output_columns) <= 1:
                if id_column in df.columns:
                    output_df = df[[id_column]]
                    simulation_note = "Detected participant ID only. Additional variables can be added via Add Additional Variables."
                else:
                    output_df = df[list(df.columns)]
                    simulation_note = "Could not detect a participant ID column. Showing raw file structure."
            else:
                output_df = df[output_columns]
                if additional_columns:
                    simulation_note = (
                        f"Simulated output with {len(output_columns)} participant columns "
                        f"(including {len(set(additional_columns))} selected additional variable(s))."
                    )
                else:
                    simulation_note = f"Simulated output with {len(output_columns)} default participant columns."

            output_df, preview_id_column = _canonicalize_preview_id_column(
                output_df, id_column
            )

            preview_df = output_df.head(20)
            # Ensure strict JSON payload: replace pandas NaN/NA with None,
            # otherwise browsers can fail parsing response.json() on NaN literals.
            preview_df = preview_df.astype(object).where(preview_df.notna(), None)

            preview_stage = "generating participants schema"
            neurobagel_schema = _generate_neurobagel_schema(
                output_df,
                preview_id_column,
                library_path=library_path,
                participant_filter_config=participant_filter_config,
            )

            return jsonify(
                {
                    "status": "success",
                    "columns": list(output_df.columns),
                    "source_columns": list(df.columns),
                    "questionnaire_like_columns": questionnaire_like_columns,
                    "id_column": preview_id_column,
                    "source_id_column": id_column,
                    "participant_count": len(df),
                    "preview_rows": preview_df.to_dict(orient="records"),
                    "library_path": str(library_path),
                    "simulation_note": simulation_note,
                    "total_source_columns": len(df.columns),
                    "extracted_columns": len(output_df.columns),
                    "neurobagel_schema": neurobagel_schema,
                    "format_warnings": (
                        [mixed_time_warning] if mixed_time_warning else []
                    ),
                    "problem_columns": mixed_time_style_columns,
                }
            )

        except Exception as e:
            diagnostic_columns: list[dict[str, object]] = []

            try:
                if "df" in locals():
                    diagnostic_columns = _detect_mixed_time_style_columns(df)
            except Exception:
                diagnostic_columns = []

            if not diagnostic_columns:
                try:
                    diagnostic_df = (
                        _read_participants_input_table(
                            input_path=input_path,
                            suffix=suffix,
                            sheet_arg=sheet_arg,
                            separator_option=separator_option,
                        )
                        if suffix in {".xlsx", ".csv", ".tsv", ".lsa"}
                        else None
                    )

                    if diagnostic_df is not None:
                        diagnostic_columns = _detect_mixed_time_style_columns(
                            diagnostic_df
                        )
                except Exception:
                    diagnostic_columns = []

            if diagnostic_columns:
                mixed_time_message = _format_mixed_time_style_message(
                    diagnostic_columns
                )
                return (
                    jsonify(
                        {
                            "error": mixed_time_message,
                            "error_code": "mixed_time_formats",
                            "problem_columns": diagnostic_columns,
                        }
                    ),
                    400,
                )

            error_text = str(e) or "Preview failed"
            error_type = e.__class__.__name__
            stage_text = (
                preview_stage
                if "preview_stage" in locals() and preview_stage
                else "unknown stage"
            )

            if (
                error_text.strip().lower()
                == "the string did not match the expected pattern."
            ):
                error_text = (
                    "Preview failed due to an invalid value pattern in the uploaded data "
                    f"(stage: {stage_text}). Please check columns with timing/duration values "
                    "for mixed formats and ambiguous tokens, then retry."
                )

            return (
                jsonify(
                    {
                        "error": error_text,
                        "error_type": error_type,
                        "error_stage": stage_text,
                    }
                ),
                500,
            )

        finally:
            shutil.rmtree(tmp_dir, ignore_errors=True)

    elif mode == "dataset":
        project_root = _get_session_project_root()
        if not project_root:
            return jsonify({"error": "No project selected"}), 400
        extract_from_survey = (
            request.form.get("extract_from_survey", "true").lower() == "true"
        )
        extract_from_biometrics = (
            request.form.get("extract_from_biometrics", "true").lower() == "true"
        )
        try:
            return jsonify(
                preview_dataset_participants(
                    project_root,
                    extract_from_survey=extract_from_survey,
                    extract_from_biometrics=extract_from_biometrics,
                )
            )
        except ValueError as e:
            return jsonify({"error": str(e)}), 400

    else:
        return jsonify({"error": f"Unknown mode: {mode}"}), 400


@conversion_participants_bp.route("/api/participants-convert", methods=["POST"])
def api_participants_convert():
    """Convert/extract participant data and create participants.tsv and participants.json."""
    try:
        from src.participants_converter import ParticipantsConverter
        import pandas as pd
        import json
    except ImportError as e:
        return jsonify({"error": f"Required module not available: {str(e)}"}), 500

    mode = request.form.get("mode", "file")
    force_overwrite = request.form.get("force_overwrite", "false").lower() == "true"
    neurobagel_schema_json = request.form.get("neurobagel_schema")
    try:
        separator_option = _normalize_separator_option(request.form.get("separator"))
    except ValueError as error:
        return jsonify({"error": str(error)}), 400

    neurobagel_schema = {}
    if neurobagel_schema_json:
        try:
            neurobagel_schema = json.loads(neurobagel_schema_json)
        except json.JSONDecodeError:
            pass
    excluded_columns = set(
        _parse_requested_column_list(request.form.get("excluded_columns"))
    )

    project_root = _get_session_project_root()
    if not project_root:
        return jsonify({"error": "No project selected"}), 400

    participants_tsv = project_root / "participants.tsv"
    participants_json = project_root / "participants.json"

    existing_files = []
    if participants_tsv.exists():
        existing_files.append(str(participants_tsv))
    if participants_json.exists():
        existing_files.append(str(participants_json))

    if existing_files and not force_overwrite:
        return (
            jsonify(
                {
                    "error": "Participant files already exist. Enable 'force overwrite' to replace them.",
                    "existing_files": existing_files,
                }
            ),
            409,
        )

    logs = []

    def log_msg(level, message):
        logs.append({"level": level, "message": message})

    try:
        if mode == "file":
            uploaded_file = request.files.get("file")
            if not uploaded_file or not uploaded_file.filename:
                return jsonify({"error": "Missing input file"}), 400

            filename = secure_filename(uploaded_file.filename)
            suffix = Path(filename).suffix.lower()

            tmp_dir = tempfile.mkdtemp(prefix="prism_participants_convert_")
            try:
                tmp_path = Path(tmp_dir)
                input_path = tmp_path / filename
                uploaded_file.save(str(input_path))

                log_msg("INFO", f"Processing {filename}...")

                converter = ParticipantsConverter(project_root, log_callback=log_msg)

                mapping = None
                mapping_candidates = participants_mapping_candidates(project_root)
                for candidate in mapping_candidates:
                    if candidate.exists() and candidate.is_file():
                        mapping = converter.load_mapping_from_file(candidate)
                        if mapping:
                            log_msg(
                                "INFO",
                                f"Using participants_mapping.json from {candidate}",
                            )
                            break

                if isinstance(mapping, dict) and "mappings" not in mapping:
                    legacy_mappings = {}
                    for source_column, standard_variable in mapping.items():
                        src = str(source_column).strip()
                        if not src:
                            continue
                        std_raw = str(standard_variable).strip() or src
                        std = re.sub(r"[^a-zA-Z0-9_]+", "_", std_raw).strip("_").lower()
                        if not std:
                            std = re.sub(r"[^a-zA-Z0-9_]+", "_", src).strip("_").lower()
                        if not std:
                            continue
                        legacy_mappings[std] = {
                            "source_column": src,
                            "standard_variable": std,
                            "type": "string",
                        }
                    mapping = {
                        "version": "1.0",
                        "description": "Normalized legacy participant mapping",
                        "mappings": legacy_mappings,
                    }
                    log_msg(
                        "INFO", "Normalized legacy participants_mapping.json format"
                    )

                if not mapping:
                    try:
                        test_df = _read_participants_input_table(
                            input_path=input_path,
                            suffix=suffix,
                            sheet_arg=0,
                            separator_option=separator_option,
                        )
                        columns = list(test_df.columns)
                        log_msg("INFO", f"Auto-detected columns: {', '.join(columns)}")

                        mapping = {"version": "1.0", "mappings": {}}

                        for col in columns:
                            col_lower = col.lower()
                            if col_lower in ["participant_id", "sub", "subject", "id"]:
                                mapping["mappings"]["participant_id"] = {
                                    "source_column": col,
                                    "standard_variable": "participant_id",
                                }
                            elif col_lower in ["age"]:
                                mapping["mappings"]["age"] = {
                                    "source_column": col,
                                    "standard_variable": "age",
                                }
                            elif col_lower in [
                                "sex",
                                "biological_sex",
                                "biologicalsex",
                            ]:
                                mapping["mappings"]["sex"] = {
                                    "source_column": col,
                                    "standard_variable": "sex",
                                }
                            elif col_lower in [
                                "gender",
                                "gender_identity",
                                "genderidentity",
                            ]:
                                mapping["mappings"]["gender"] = {
                                    "source_column": col,
                                    "standard_variable": "gender",
                                }
                            elif col_lower in ["handedness"]:
                                mapping["mappings"]["handedness"] = {
                                    "source_column": col,
                                    "standard_variable": "handedness",
                                }
                            elif col_lower in [
                                "education",
                                "education_level",
                                "educationlevel",
                            ]:
                                mapping["mappings"]["education"] = {
                                    "source_column": col,
                                    "standard_variable": "education",
                                }

                        if mapping["mappings"]:
                            log_msg(
                                "INFO",
                                f"Auto-created mapping for {len(mapping['mappings'])} columns",
                            )
                    except Exception as e:
                        log_msg("WARNING", f"Could not auto-detect columns: {e}")
                        mapping = {"version": "1.0", "mappings": {}}
                else:
                    if mapping.get("mappings"):
                        log_msg(
                            "INFO",
                            f"Using explicit participant mapping for {len(mapping.get('mappings', {}))} columns",
                        )

                try:
                    from src.converters.id_detection import (
                        detect_id_column as _detect_id,
                        has_prismmeta_columns as _has_pm_cols,
                    )

                    suffix = input_path.suffix.lower()
                    if suffix in {".xlsx", ".csv", ".tsv", ".lsa"}:
                        sheet = request.form.get("sheet", "0").strip() or "0"
                        try:
                            sheet_arg = int(sheet) if sheet.isdigit() else sheet
                        except (ValueError, TypeError):
                            sheet_arg = 0
                        df_for_merge = _read_participants_input_table(
                            input_path=input_path,
                            suffix=suffix,
                            sheet_arg=sheet_arg,
                            separator_option=separator_option,
                        )
                    else:
                        df_for_merge = read_tabular_file(input_path).df

                    explicit_id_col = request.form.get("id_column", "").strip() or None
                    source_fmt = "lsa" if suffix == ".lsa" else "xlsx"
                    detected_id_col = _detect_id(
                        list(df_for_merge.columns),
                        source_fmt,
                        explicit_id_column=explicit_id_col,
                        has_prismmeta=_has_pm_cols(list(df_for_merge.columns)),
                    )
                    if not detected_id_col and explicit_id_col in df_for_merge.columns:
                        detected_id_col = explicit_id_col
                    if not detected_id_col and len(df_for_merge.columns) > 0:
                        detected_id_col = str(df_for_merge.columns[0])

                    library_path = resolve_effective_library_path()
                    participant_filter_config = _load_project_participant_filter_config(
                        session.get("current_project_path")
                    )

                    auto_columns = _filter_participant_relevant_columns(
                        df_for_merge,
                        id_column=detected_id_col,
                        library_path=library_path,
                        participant_filter_config=participant_filter_config,
                        include_template_columns=False,
                        allow_nonrelevant_fallback=False,
                    )

                    if not isinstance(mapping, dict):
                        mapping = {"version": "1.0", "mappings": {}}
                    mapping.setdefault("version", "1.0")
                    mapping_block = mapping.setdefault("mappings", {})

                    used_sources = {
                        str(spec.get("source_column")).strip()
                        for spec in mapping_block.values()
                        if isinstance(spec, dict) and spec.get("source_column")
                    }
                    used_targets = {
                        str(spec.get("standard_variable")).strip()
                        for spec in mapping_block.values()
                        if isinstance(spec, dict) and spec.get("standard_variable")
                    }

                    mapping_block_keys = list(mapping_block.keys())
                    removed_explicit = 0
                    for mapping_key in mapping_block_keys:
                        spec = mapping_block.get(mapping_key)
                        if not isinstance(spec, dict):
                            continue
                        source_col = str(spec.get("source_column") or "").strip()
                        standard_var = str(spec.get("standard_variable") or "").strip()
                        if (
                            source_col == detected_id_col
                            or standard_var == "participant_id"
                        ):
                            continue
                        if (
                            source_col in excluded_columns
                            or standard_var in excluded_columns
                        ):
                            del mapping_block[mapping_key]
                            removed_explicit += 1
                    if removed_explicit:
                        log_msg(
                            "INFO",
                            f"Removed {removed_explicit} excluded participant columns from mapping",
                        )

                    added_auto = 0
                    for col in auto_columns:
                        source_col = str(col).strip()
                        if not source_col:
                            continue
                        if source_col in excluded_columns:
                            continue

                        standard_var = (
                            "participant_id"
                            if detected_id_col and source_col == detected_id_col
                            else source_col
                        )

                        if source_col in used_sources or standard_var in used_targets:
                            continue

                        mapping_block[standard_var] = {
                            "source_column": source_col,
                            "standard_variable": standard_var,
                            "type": "string",
                        }
                        used_sources.add(source_col)
                        used_targets.add(standard_var)
                        added_auto += 1

                    if added_auto:
                        log_msg(
                            "INFO",
                            f"Added {added_auto} auto-detected participant columns to mapping (additive merge)",
                        )
                except Exception as merge_error:
                    log_msg(
                        "WARNING",
                        f"Could not merge auto-detected participant columns into mapping: {merge_error}",
                    )

                success, df, messages = converter.convert_participant_data(
                    source_file=str(input_path),
                    mapping=mapping,
                    output_file=str(participants_tsv),
                    separator=separator_option,
                )

                for msg in messages:
                    log_msg("INFO", msg)

                if not success or df is None:
                    return jsonify({"error": "Conversion failed", "log": logs}), 400

                df.to_csv(participants_tsv, sep="\t", index=False)
                log_msg("INFO", f"✓ Created {participants_tsv.name}")

                import json as json_module

                participants_json_data = {str(col): {} for col in df.columns}

                if neurobagel_schema:
                    try:
                        aligned_neurobagel_schema = (
                            _rekey_neurobagel_schema_to_output_columns(
                                neurobagel_schema=neurobagel_schema,
                                mapping=mapping if isinstance(mapping, dict) else None,
                                allowed_columns=list(df.columns),
                            )
                        )
                        participants_json_data, merged_count = (
                            _merge_neurobagel_schema_for_columns(
                                participants_json_data,
                                aligned_neurobagel_schema,
                                list(df.columns),
                                log_callback=log_msg,
                            )
                        )
                        log_msg(
                            "INFO",
                            f"Merged NeuroBagel annotations for {merged_count} participants.tsv column(s)",
                        )
                    except Exception as e:
                        log_msg(
                            "WARNING", f"Could not merge NeuroBagel schema: {str(e)}"
                        )

                fallback_descriptions = {
                    "participant_id": "Participant identifier (sub-<label>)",
                    "age": "Age of participant",
                }
                for col in df.columns:
                    col_name = str(col)
                    field = participants_json_data.setdefault(col_name, {})
                    current_description = str(field.get("Description") or "").strip()
                    if current_description:
                        continue
                    field["Description"] = fallback_descriptions.get(
                        col_name, f"Participant {col_name}"
                    )

                with open(participants_json, "w") as f:
                    json_module.dump(participants_json_data, f, indent=2)

                log_msg("INFO", f"✓ Created {participants_json.name}")

                log_msg("INFO", f"✓ Created {participants_tsv.name}")
                log_msg("INFO", f"✓ Created {participants_json.name}")

                return jsonify(
                    {
                        "status": "success",
                        "log": logs,
                        "files_created": [
                            str(participants_tsv),
                            str(participants_json),
                        ],
                    }
                )

            finally:
                shutil.rmtree(tmp_dir, ignore_errors=True)

        elif mode == "dataset":
            extract_from_survey = (
                request.form.get("extract_from_survey", "true").lower() == "true"
            )
            extract_from_biometrics = (
                request.form.get("extract_from_biometrics", "true").lower() == "true"
            )

            log_msg("INFO", "Extracting participant data from dataset...")
            try:
                result = convert_dataset_participants(
                    project_root,
                    neurobagel_schema=neurobagel_schema,
                    extract_from_survey=extract_from_survey,
                    extract_from_biometrics=extract_from_biometrics,
                    log_callback=log_msg,
                )
            except ValueError as e:
                return jsonify({"error": str(e), "log": logs}), 400

            return jsonify({**result, "log": logs})

        else:
            return jsonify({"error": f"Unknown mode: {mode}", "log": logs}), 400

    except Exception as e:
        import traceback

        log_msg("ERROR", f"Error: {str(e)}")
        log_msg("ERROR", traceback.format_exc())
        return jsonify({"error": str(e), "log": logs}), 500
