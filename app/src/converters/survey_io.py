"""IO helpers for survey conversion: writing responses, sidecars, and previews.

This module consolidates file writing and preview generation logic including:
- Response TSV writing (per subject/session)
- Task Sidecar JSON writing
- Participants TSV preview generation
- Dry-run preview generation
"""

from __future__ import annotations

import csv
import re
from collections import Counter
from datetime import datetime
from pathlib import Path


# -----------------------------------------------------------------------------
# Response Writing
# -----------------------------------------------------------------------------


def _process_and_write_responses(
    *,
    df,
    res_id_col: str,
    res_ses_col: str | None,
    session: str | None,
    output_root,
    task_run_columns: dict[tuple[str, int | None], list[str]],
    selected_tasks: set[str] | None,
    templates: dict,
    col_to_mapping: dict,
    strict_levels: bool,
    task_runs: dict[str, int | None],
    ls_system_cols: list[str],
    non_item_toplevel_keys,
    normalize_sub_fn,
    normalize_ses_fn,
    normalize_item_fn,
    is_missing_fn,
    ensure_dir_fn,
    write_limesurvey_data_fn,
    process_survey_row_with_run_fn,
    build_bids_survey_filename_fn,
) -> tuple[dict[str, int], dict[str, set[str]]]:
    """Process all response rows and write survey TSV files."""
    missing_cells_by_subject: dict[str, int] = {}
    items_using_tolerance: dict[str, set[str]] = {}

    for _, row in df.iterrows():
        sub_id = normalize_sub_fn(row[res_id_col])
        ses_id = (
            normalize_ses_fn(session)
            if session and session != "all"
            else (normalize_ses_fn(row[res_ses_col]) if res_ses_col else "ses-1")
        )
        modality_dir = ensure_dir_fn(output_root / sub_id / ses_id / "survey")

        if ls_system_cols:
            write_limesurvey_data_fn(
                row=row,
                ls_columns=ls_system_cols,
                sub_id=sub_id,
                ses_id=ses_id,
                modality_dir=modality_dir,
                normalize_val_fn=normalize_item_fn,
            )

        for (task, run), columns in sorted(
            task_run_columns.items(), key=lambda x: (x[0][0], x[0][1] or 0)
        ):
            if selected_tasks is not None and task not in selected_tasks:
                continue

            schema = templates[task]["json"]
            run_col_mapping = {col_to_mapping[c].base_item: c for c in columns}

            out_row, missing_count = process_survey_row_with_run_fn(
                row=row,
                df_cols=df.columns,
                task=task,
                run=run,
                schema=schema,
                run_col_mapping=run_col_mapping,
                sub_id=sub_id,
                strict_levels=strict_levels,
                items_using_tolerance=items_using_tolerance,
                is_missing_fn=is_missing_fn,
                normalize_val_fn=normalize_item_fn,
            )
            missing_cells_by_subject[sub_id] = (
                missing_cells_by_subject.get(sub_id, 0) + missing_count
            )

            expected_cols = [
                k
                for k in schema.keys()
                if k not in non_item_toplevel_keys and k not in schema.get("_aliases", {})
            ]

            include_run = task_runs.get(task) is not None
            effective_run = run if include_run else None

            filename = build_bids_survey_filename_fn(
                sub_id, ses_id, task, effective_run, "tsv"
            )
            res_file = modality_dir / filename

            with open(res_file, "w", encoding="utf-8", newline="") as f:
                writer = csv.DictWriter(
                    f, fieldnames=expected_cols, delimiter="\t", lineterminator="\n"
                )
                writer.writeheader()
                writer.writerow(out_row)

    return missing_cells_by_subject, items_using_tolerance


def _build_tolerance_warnings(
    *,
    items_using_tolerance: dict[str, set[str]],
) -> list[str]:
    """Build summary warnings for items accepted via numeric range tolerance."""
    warnings: list[str] = []
    if items_using_tolerance:
        for task, item_ids in sorted(items_using_tolerance.items()):
            sorted_items = sorted(list(item_ids))
            shown = ", ".join(sorted_items[:10])
            more = "" if len(sorted_items) <= 10 else f" (+{len(sorted_items) - 10} more)"
            warnings.append(
                f"Task '{task}': Numeric values for items [{shown}{more}] were accepted via range tolerance."
            )
    return warnings


# -----------------------------------------------------------------------------
# Sidecar Writing
# -----------------------------------------------------------------------------


def _write_task_sidecars(
    *,
    tasks_with_data: set[str],
    dataset_root,
    templates: dict,
    language: str | None,
    force: bool,
    technical_overrides: dict | None,
    missing_token: str,
    localize_survey_template_fn,
    inject_missing_token_fn,
    apply_technical_overrides_fn,
    strip_internal_keys_fn,
    write_json_fn,
) -> None:
    """Write task-level survey sidecars with required PRISM fields."""
    for task in sorted(tasks_with_data):
        sidecar_path = dataset_root / f"task-{task}_survey.json"
        if not sidecar_path.exists() or force:
            localized = localize_survey_template_fn(
                templates[task]["json"], language=language
            )
            localized = inject_missing_token_fn(localized, token=missing_token)
            if technical_overrides:
                localized = apply_technical_overrides_fn(localized, technical_overrides)

            if "Metadata" not in localized:
                localized["Metadata"] = {
                    "SchemaVersion": "1.1.1",
                    "CreationDate": datetime.utcnow().strftime("%Y-%m-%d"),
                    "Creator": "prism-studio",
                }

            if "Technical" not in localized or not isinstance(
                localized.get("Technical"), dict
            ):
                localized["Technical"] = {}
            tech = localized["Technical"]
            if "StimulusType" not in tech:
                tech["StimulusType"] = "Questionnaire"
            if "FileFormat" not in tech:
                tech["FileFormat"] = "tsv"
            if "Language" not in tech:
                tech["Language"] = language or ""
            if "Respondent" not in tech:
                tech["Respondent"] = "self"

            if "Study" not in localized or not isinstance(localized.get("Study"), dict):
                localized["Study"] = {}
            study = localized["Study"]
            if "TaskName" not in study:
                study["TaskName"] = task
            if "OriginalName" not in study:
                study["OriginalName"] = study.get("TaskName", task)
            if "LicenseID" not in study:
                study["LicenseID"] = "Other"
            if "License" not in study:
                study["License"] = ""

            cleaned = strip_internal_keys_fn(localized)
            write_json_fn(sidecar_path, cleaned)


# -----------------------------------------------------------------------------
# Preview Generation
# -----------------------------------------------------------------------------


def _generate_participants_preview(
    *,
    df,
    res_id_col: str,
    res_ses_col: str | None,
    session: str | None,
    normalize_sub_fn,
    normalize_ses_fn,
    is_missing_fn,
    participant_template: dict | None,
    output_root: Path,
    survey_columns: set[str] | None = None,
    ls_system_columns: list[str] | None = None,
    lsa_questions_map: dict | None = None,
    missing_token: str = "n/a",
) -> dict:
    """Generate a preview of what will be written to participants.tsv."""
    from .survey_participants_logic import (
        _load_participants_mapping,
        _get_mapped_columns,
        _normalize_participant_template_dict,
    )

    preview = {
        "columns": [],
        "sample_rows": [],
        "mappings": {},
        "total_rows": 0,
        "unused_columns": [],
        "notes": [],
    }

    participants_mapping = _load_participants_mapping(output_root)
    mapped_cols, col_renames, value_mappings = _get_mapped_columns(participants_mapping)

    lower_to_col = {str(c).strip().lower(): str(c).strip() for c in df.columns}
    template_norm = _normalize_participant_template_dict(participant_template)
    template_cols = set(template_norm.keys()) if template_norm else set()
    non_column_keys = {
        "@context",
        "Technical",
        "I18n",
        "Study",
        "Metadata",
        "_aliases",
        "_reverse_aliases",
    }
    template_cols = template_cols - non_column_keys

    extra_cols: list[str] = []
    col_output_names: dict[str, str] = {}

    if participants_mapping and mapped_cols:
        for source_col_lower in mapped_cols:
            if source_col_lower in lower_to_col:
                actual_col = lower_to_col[source_col_lower]
                if actual_col not in {res_id_col, res_ses_col}:
                    extra_cols.append(actual_col)
                    output_name = col_renames.get(source_col_lower, source_col_lower)
                    col_output_names[actual_col] = output_name

        preview["notes"].append(
            f"Using participants_mapping.json with {len(mapped_cols)} explicit column mappings"
        )
    else:
        for col in template_cols:
            if col in lower_to_col:
                actual_col = lower_to_col[col]
                if actual_col not in {res_id_col, res_ses_col}:
                    extra_cols.append(actual_col)
                    col_output_names[actual_col] = col

        if not extra_cols:
            preview["notes"].append(
                "No participants_mapping.json found. Using template columns only (or none available in data)."
            )
        else:
            preview["notes"].append(
                f"No participants_mapping.json found. Using {len(extra_cols)} columns from participant template."
            )

    output_columns = ["participant_id"] + [
        col_output_names.get(c, c) for c in extra_cols
    ]
    preview["columns"] = output_columns

    extra_cols = list(dict.fromkeys(extra_cols))
    sample_rows = []

    for idx, row in df.iterrows():
        if len(sample_rows) >= 10:
            break

        sub_id_raw = row[res_id_col]
        sub_id = normalize_sub_fn(sub_id_raw)

        row_data = {"participant_id": sub_id}

        for col in extra_cols:
            output_name = col_output_names.get(col, col)
            val = row.get(col)

            if output_name in value_mappings:
                val_map = value_mappings[output_name]
                display_val = (
                    val_map.get(str(val), str(val))
                    if val not in ("nan", "None", "")
                    else missing_token
                )
            else:
                if is_missing_fn(val):
                    display_val = missing_token
                else:
                    display_val = str(val)

            row_data[output_name] = display_val

        sample_rows.append(row_data)

    preview["sample_rows"] = sample_rows
    preview["total_rows"] = len(df[res_id_col].unique())

    if extra_cols:
        for col in extra_cols:
            output_name = col_output_names.get(col, col)
            preview["mappings"][output_name] = {
                "source_column": col,
                "has_value_mapping": output_name in value_mappings,
                "value_mapping": value_mappings.get(output_name, {}),
            }

    used_in_participants = (
        set(extra_cols) | {res_id_col, res_ses_col}
        if res_ses_col
        else set(extra_cols) | {res_id_col}
    )
    survey_cols = survey_columns or set()
    ls_sys_cols = set(ls_system_columns) if ls_system_columns else set()

    unused_cols = []

    for col in df.columns:
        if (
            col not in used_in_participants
            and col not in survey_cols
            and col not in ls_sys_cols
        ):
            has_data = df[col].notna().any()
            has_non_empty = (df[col].astype(str).str.strip() != "").any()

            if has_data and has_non_empty:
                unused_cols.append(col)

    unused_cols_with_descriptions = []
    if lsa_questions_map:
        field_descriptions = {}
        for qid, q_info in lsa_questions_map.items():
            title = q_info.get("title", "")
            question = q_info.get("question", "")
            description = title if title else question
            field_descriptions[qid] = description

        for col in sorted(unused_cols):
            qid_match = re.search(r"^_\d+X\d+X(\d+)", col)
            qid = qid_match.group(1) if qid_match else col

            description = field_descriptions.get(qid, "")
            if description:
                unused_cols_with_descriptions.append(
                    {"field_code": col, "description": description}
                )
            else:
                unused_cols_with_descriptions.append(
                    {"field_code": col, "description": ""}
                )

        preview["unused_columns"] = unused_cols_with_descriptions
    else:
        preview["unused_columns"] = sorted(unused_cols)

    return preview


def _generate_dry_run_preview(
    *,
    df,
    tasks_with_data: set[str],
    task_run_columns: dict[tuple[str, int | None], list[str]],
    col_to_mapping: dict,
    templates: dict,
    res_id_col: str,
    res_ses_col: str | None,
    session: str | None,
    selected_tasks: set[str] | None,
    normalize_sub_fn,
    normalize_ses_fn,
    is_missing_fn,
    ls_system_cols: list[str],
    participant_template: dict | None,
    skip_participants: bool = True,
    output_root: Path,
    dataset_root: Path,
    lsa_questions_map: dict | None = None,
    missing_token: str = "n/a",
) -> dict:
    """Generate a detailed preview of what will be created during conversion."""

    preview = {
        "summary": {},
        "participants": [],
        "files_to_create": [],
        "data_issues": [],
        "column_mapping": {},
    }

    preview["summary"] = {
        "total_participants": len(df),
        "unique_participants": df[res_id_col].nunique(),
        "tasks": sorted(tasks_with_data),
        "output_root": str(output_root),
        "dataset_root": str(dataset_root),
    }

    issues = []
    participants_info = []
    sub_ids_normalized = []

    for idx, row in df.iterrows():
        sub_id_raw = row[res_id_col]
        sub_id = normalize_sub_fn(sub_id_raw)
        sub_ids_normalized.append(sub_id)

        ses_id = (
            normalize_ses_fn(session)
            if session
            else (normalize_ses_fn(row[res_ses_col]) if res_ses_col else "ses-1")
        )

        missing_count = 0
        total_items = 0

        for (task, run), columns in task_run_columns.items():
            if selected_tasks is not None and task not in selected_tasks:
                continue

            for col in columns:
                val = row.get(col)
                total_items += 1
                if is_missing_fn(val):
                    missing_count += 1

        participants_info.append(
            {
                "participant_id": sub_id,
                "session_id": ses_id,
                "raw_id": str(sub_id_raw),
                "missing_values": missing_count,
                "total_items": total_items,
                "completeness_percent": (
                    round((total_items - missing_count) / total_items * 100, 1)
                    if total_items > 0
                    else 100
                ),
            }
        )

    preview["participants"] = participants_info

    id_counts = Counter(sub_ids_normalized)
    duplicates = {sub_id: count for sub_id, count in id_counts.items() if count > 1}
    if duplicates:
        issues.append(
            {
                "type": "duplicate_ids",
                "severity": "error",
                "message": f"Found {len(duplicates)} duplicate participant IDs after normalization",
                "details": {k: v for k, v in list(duplicates.items())[:10]},
            }
        )

    col_mapping_details = {}
    for col, mapping in col_to_mapping.items():
        task = mapping.task
        run = mapping.run
        base_item = mapping.base_item

        schema = templates[task]["json"]
        item_def = schema.get(base_item, {})

        # We can add more details here if needed

    return preview
