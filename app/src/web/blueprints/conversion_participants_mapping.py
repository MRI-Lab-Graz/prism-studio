import json
import re
from pathlib import Path

from flask import session

from src.participants_id_selection import resolve_participants_id_selection
from src.participants_paths import participants_mapping_candidates

from .conversion_participants_helpers import (
    _detect_repeated_questionnaire_prefixes,
    _filter_participant_relevant_columns,
    _is_likely_questionnaire_column,
    _load_project_participant_filter_config,
    _load_survey_template_item_ids,
    _normalize_column_name,
)
from .conversion_participants_io import _read_participants_input_table
from .conversion_utils import resolve_effective_library_path


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


def _canonicalize_preview_id_column(
    output_df, id_column: str | None, *, keep_session_id_columns: bool = False
):
    """Mirror final participants.tsv naming in preview payloads."""
    if output_df is None:
        return output_df, str(id_column or "").strip()

    from src.participants_converter import ParticipantsConverter

    source_id_column = str(id_column or "").strip()
    if not source_id_column:
        if "participant_id" in getattr(output_df, "columns", []):
            preview_df = output_df.copy()
        else:
            return output_df, source_id_column
    elif source_id_column == "participant_id":
        preview_df = output_df.copy()
    elif source_id_column not in output_df.columns:
        return output_df, source_id_column
    else:
        preview_df = output_df.copy()
        if "participant_id" in preview_df.columns:
            preview_df = preview_df.drop(columns=["participant_id"])

        preview_df = preview_df.rename(columns={source_id_column: "participant_id"})
        ordered_columns = ["participant_id"] + [
            col for col in preview_df.columns if col != "participant_id"
        ]
        preview_df = preview_df[ordered_columns]

    if "participant_id" not in preview_df.columns:
        return preview_df, source_id_column

    preview_df = preview_df.copy()
    preview_df["participant_id"] = preview_df["participant_id"].map(
        ParticipantsConverter._normalize_participant_id
    )
    preview_df = preview_df.loc[preview_df["participant_id"].notna()].copy()

    pre_collapse_df = preview_df.copy()

    preview_df, _, _ = ParticipantsConverter._collapse_to_bids_participants_table(
        preview_df
    )

    if keep_session_id_columns and "participant_id" in preview_df.columns:
        def _normalized_alias(value: object) -> str:
            return re.sub(r"[^a-z0-9]+", "", str(value or "").strip().lower())

        session_id_columns = [
            str(column)
            for column in pre_collapse_df.columns
            if str(column) != "participant_id"
            and _normalized_alias(column) == "sessionid"
        ]

        if not session_id_columns:
            return preview_df, "participant_id"

        import pandas as pd

        for column_name in session_id_columns:
            if column_name in preview_df.columns:
                continue

            values_by_participant: dict[object, object] = {}
            for participant_id, raw_value in pre_collapse_df[
                ["participant_id", column_name]
            ].itertuples(index=False, name=None):
                if pd.isna(participant_id):
                    continue
                if participant_id in values_by_participant:
                    continue
                if pd.isna(raw_value):
                    continue
                if isinstance(raw_value, str):
                    raw_value = raw_value.strip()
                    if not raw_value:
                        continue
                values_by_participant[participant_id] = raw_value

            if values_by_participant:
                preview_df[column_name] = preview_df["participant_id"].map(
                    values_by_participant
                )

        ordered_columns = [
            str(column)
            for column in pre_collapse_df.columns
            if str(column) in preview_df.columns
        ]
        ordered_columns.extend(
            str(column)
            for column in preview_df.columns
            if str(column) not in ordered_columns
        )
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


def _resolve_excluded_output_columns(
    *, columns: list[str], requested_excluded: set[str] | None
) -> set[str]:
    if not requested_excluded:
        return set()

    column_lookup: dict[str, str] = {}
    for column_name in columns:
        cleaned_name = str(column_name or "").strip()
        if not cleaned_name:
            continue
        column_lookup.setdefault(cleaned_name.lower(), cleaned_name)

    resolved: set[str] = set()
    for raw_value in requested_excluded:
        requested_name = str(raw_value or "").strip()
        if not requested_name:
            continue

        requested_lower = requested_name.lower()
        if requested_lower in {"participant_id", "participantid"}:
            continue

        matched_name = column_lookup.get(requested_lower)
        if matched_name:
            resolved.add(matched_name)

    return resolved


def _collect_preview_column_values(
    df, *, max_values: int = 50
) -> dict[str, list[str]]:
    if df is None or getattr(df, "empty", True):
        return {}

    import pandas as pd

    column_values: dict[str, list[str]] = {}
    limit = max(int(max_values or 50), 1)

    for column in df.columns:
        unique_values: list[str] = []
        seen_values: set[str] = set()
        for raw_value in df[column].tolist():
            if pd.isna(raw_value):
                continue
            text_value = str(raw_value).strip()
            if not text_value or text_value in seen_values:
                continue
            seen_values.add(text_value)
            unique_values.append(text_value)
            if len(unique_values) >= limit:
                break

        column_values[str(column)] = unique_values

    return column_values


def _load_existing_participants_schema(project_root: Path) -> dict:
    participants_json = project_root / "participants.json"
    if not participants_json.exists() or not participants_json.is_file():
        return {}

    try:
        with open(participants_json, "r", encoding="utf-8") as schema_file:
            loaded = json.load(schema_file)
        return loaded if isinstance(loaded, dict) else {}
    except Exception:
        return {}


def _load_saved_participants_mapping(project_root: Path, converter, log_callback=None):
    mapping = None
    for candidate in participants_mapping_candidates(project_root):
        if candidate.exists() and candidate.is_file():
            mapping = converter.load_mapping_from_file(candidate)
            if mapping:
                if log_callback:
                    log_callback(
                        "INFO",
                        f"Using participants_mapping.json from {candidate}",
                    )
                break
    return mapping


def _normalize_legacy_participants_mapping(mapping: dict, log_callback=None) -> dict:
    if not isinstance(mapping, dict) or "mappings" in mapping:
        return mapping

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

    normalized = {
        "version": "1.0",
        "description": "Normalized legacy participant mapping",
        "mappings": legacy_mappings,
    }
    if log_callback:
        log_callback("INFO", "Normalized legacy participants_mapping.json format")
    return normalized


def _resolve_web_participant_import_mapping(
    *,
    project_root: Path,
    input_path: Path,
    suffix: str,
    sheet_arg: str | int,
    separator_option: str,
    explicit_id_column: str | None,
    excluded_columns: set[str],
    extra_columns: list[str],
    log_callback=None,
) -> dict[str, object]:
    from src.converters.id_detection import (
        detect_id_column as _detect_id,
        has_prismmeta_columns as _has_pm_cols,
    )
    from src.participants_converter import ParticipantsConverter

    converter = ParticipantsConverter(project_root, log_callback=log_callback)
    mapping = _load_saved_participants_mapping(project_root, converter, log_callback)
    if isinstance(mapping, dict):
        mapping = _normalize_legacy_participants_mapping(mapping, log_callback)

    df_for_import = _read_participants_input_table(
        input_path=input_path,
        suffix=suffix,
        sheet_arg=sheet_arg,
        separator_option=separator_option,
    )
    source_columns = [str(col) for col in df_for_import.columns]
    source_fmt = suffix.lstrip(".")
    has_prismmeta = _has_pm_cols(source_columns)
    id_resolution = resolve_participants_id_selection(
        columns=source_columns,
        source_format=source_fmt,
        detect_id_fn=_detect_id,
        has_prismmeta=has_prismmeta,
        explicit_id_column=explicit_id_column,
    )
    detected_id_col = str(id_resolution.get("resolved_id_column") or "").strip()

    library_path = resolve_effective_library_path()
    participant_filter_config = _load_project_participant_filter_config(
        session.get("current_project_path")
    )
    template_item_ids = _load_survey_template_item_ids(library_path)
    repeated_prefixes = _detect_repeated_questionnaire_prefixes(
        source_columns,
        participant_filter_config=participant_filter_config,
    )
    questionnaire_like_columns = [
        str(col)
        for col in df_for_import.columns
        if str(col) != detected_id_col
        and _is_likely_questionnaire_column(
            str(col),
            _normalize_column_name(str(col)),
            template_item_ids,
            repeated_prefixes,
        )
    ]

    if not detected_id_col or bool(id_resolution.get("id_selection_required")):
        return {
            "mapping": mapping,
            "df": df_for_import,
            "id_resolution": id_resolution,
            "detected_id_column": detected_id_col,
            "source_columns": source_columns,
            "questionnaire_like_columns": questionnaire_like_columns,
            "library_path": library_path,
        }

    auto_columns = _filter_participant_relevant_columns(
        df_for_import,
        id_column=detected_id_col,
        library_path=library_path,
        participant_filter_config=participant_filter_config,
        include_template_columns=False,
        allow_nonrelevant_fallback=False,
    )

    requested_extra_columns: list[str] = []
    seen_extra: set[str] = set()
    for raw_col in extra_columns:
        source_col = str(raw_col or "").strip()
        if (
            not source_col
            or source_col in seen_extra
            or source_col not in df_for_import.columns
            or source_col in excluded_columns
        ):
            continue
        seen_extra.add(source_col)
        requested_extra_columns.append(source_col)

    if not isinstance(mapping, dict):
        mapping = {"version": "1.0", "mappings": {}}

    mapping.setdefault("version", "1.0")
    mapping_block = mapping.get("mappings")
    if not isinstance(mapping_block, dict):
        mapping_block = {}
        mapping["mappings"] = mapping_block

    if mapping_block:
        if log_callback:
            log_callback(
                "INFO",
                f"Using explicit participant mapping for {len(mapping_block)} columns",
            )

    removed_conflicting_id_mappings = 0
    for mapping_key in list(mapping_block.keys()):
        spec = mapping_block.get(mapping_key)
        if not isinstance(spec, dict):
            continue

        source_col = str(spec.get("source_column") or "").strip()
        standard_var = str(spec.get("standard_variable") or "").strip()

        if source_col == detected_id_col and standard_var != "participant_id":
            del mapping_block[mapping_key]
            removed_conflicting_id_mappings += 1
            continue

        if (
            standard_var == "participant_id"
            and source_col
            and source_col != detected_id_col
        ):
            del mapping_block[mapping_key]
            removed_conflicting_id_mappings += 1

    if removed_conflicting_id_mappings and log_callback:
        log_callback(
            "INFO",
            (
                "Removed "
                f"{removed_conflicting_id_mappings} conflicting ID mapping entry(ies) "
                "to enforce participant_id from selected source column"
            ),
        )

    previous_pid_spec = mapping_block.get("participant_id")
    participant_id_spec = {
        "source_column": detected_id_col,
        "standard_variable": "participant_id",
        "type": "string",
    }
    if isinstance(previous_pid_spec, dict):
        for keep_key in ["description", "value_mapping"]:
            if keep_key in previous_pid_spec:
                participant_id_spec[keep_key] = previous_pid_spec[keep_key]
    mapping_block["participant_id"] = participant_id_spec
    if log_callback:
        log_callback(
            "INFO",
            f"Using '{detected_id_col}' as source for required participant_id mapping",
        )

    removed_explicit = 0
    for mapping_key in list(mapping_block.keys()):
        spec = mapping_block.get(mapping_key)
        if not isinstance(spec, dict):
            continue
        source_col = str(spec.get("source_column") or "").strip()
        standard_var = str(spec.get("standard_variable") or "").strip()
        if source_col == detected_id_col or standard_var == "participant_id":
            continue
        if source_col in excluded_columns or standard_var in excluded_columns:
            del mapping_block[mapping_key]
            removed_explicit += 1
    if removed_explicit and log_callback:
        log_callback(
            "INFO",
            f"Removed {removed_explicit} excluded participant columns from mapping",
        )

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

    candidate_columns = list(auto_columns)
    for source_col in requested_extra_columns:
        if source_col not in candidate_columns:
            candidate_columns.append(source_col)

    added_auto = 0
    for col in candidate_columns:
        source_col = str(col).strip()
        if not source_col or source_col in excluded_columns:
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

    if added_auto and log_callback:
        log_callback(
            "INFO",
            f"Added {added_auto} auto-detected participant columns to mapping (additive merge)",
        )

    return {
        "mapping": mapping,
        "df": df_for_import,
        "id_resolution": id_resolution,
        "detected_id_column": detected_id_col,
        "source_columns": source_columns,
        "questionnaire_like_columns": questionnaire_like_columns,
        "library_path": library_path,
    }
