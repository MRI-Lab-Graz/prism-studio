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
from typing import Any


def _lookup_task_context_value(mapping, *, task: str, session: str | None, run: int | None):
    """Resolve the most specific task/session/run value with graceful fallbacks."""
    if not mapping:
        return None

    lookup_order = [
        (task, session, run),
        (task, session, None) if session is not None else None,
        (task, None, run) if run is not None else None,
        (task, None, None),
    ]
    seen = set()
    for key in lookup_order:
        if key is None or key in seen:
            continue
        seen.add(key)
        if key in mapping:
            return mapping[key]

    for key, value in mapping.items():
        if isinstance(key, tuple) and len(key) == 3 and key[0] == task:
            return value
    return None

# -----------------------------------------------------------------------------
# Response Writing
# -----------------------------------------------------------------------------


def _process_and_write_responses(
    *,
    df,
    res_id_col: str,
    res_ses_col: str | None,
    res_run_col: str | None = None,
    session: str | None,
    output_root,
    task_run_columns: dict[tuple[str, int | None], list[str]],
    selected_tasks: set[str] | None,
    templates: dict,
    task_context_templates: dict[tuple[str, str | None, int | None], dict],
    col_to_mapping: dict,
    strict_levels: bool,
    task_runs: dict[str, int | None],
    task_context_acq_map: dict[tuple[str, str | None, int | None], str | None],
    non_item_toplevel_keys,
    normalize_sub_fn,
    normalize_ses_fn,
    normalize_item_fn,
    is_missing_fn,
    ensure_dir_fn,
    process_survey_row_with_run_fn,
    build_bids_survey_filename_fn,
) -> tuple[dict[str, int], dict[str, set[str]]]:
    """Process all response rows and write survey TSV files."""
    missing_cells_by_subject: dict[str, int] = {}
    items_using_tolerance: dict[str, set[str]] = {}

    # Sort rows by (session, run, participant) so files are created in a stable order.
    sort_cols = [
        c for c in [res_ses_col, res_run_col, res_id_col] if c and c in df.columns
    ]
    if sort_cols:
        df = df.sort_values(sort_cols, kind="stable").reset_index(drop=True)

    for _, row in df.iterrows():
        sub_id = normalize_sub_fn(row[res_id_col])
        ses_id = (
            normalize_ses_fn(session)
            if session and session != "all"
            else (normalize_ses_fn(row[res_ses_col]) if res_ses_col else "ses-1")
        )

        # Determine row-level run number (from a dedicated run column in the data)
        row_run: int | None = None
        if res_run_col and res_run_col in df.columns:
            try:
                row_run = int(str(row[res_run_col]).strip())
            except (ValueError, TypeError):
                row_run = None

        modality_dir = ensure_dir_fn(output_root / sub_id / ses_id / "survey")

        for (task, run), columns in sorted(
            task_run_columns.items(), key=lambda x: (x[0][0], x[0][1] or 0)
        ):
            if selected_tasks is not None and task not in selected_tasks:
                continue

            include_run = task_runs.get(task) is not None
            # Row-level run (from a dedicated run column) takes priority over
            # column-level run detection; use it when present and valid.
            effective_run: int | None
            if row_run is not None:
                effective_run = row_run
            else:
                effective_run = run if include_run else None

            schema = _lookup_task_context_value(
                task_context_templates,
                task=task,
                session=ses_id,
                run=effective_run,
            )
            if schema is None:
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
                if k not in non_item_toplevel_keys
                and k not in schema.get("_aliases", {})
            ]

            acq_value = _lookup_task_context_value(
                task_context_acq_map,
                task=task,
                session=ses_id,
                run=effective_run,
            )

            filename = build_bids_survey_filename_fn(
                sub_id,
                ses_id,
                task,
                effective_run,
                "tsv",
                acq_value,
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
            more = (
                "" if len(sorted_items) <= 10 else f" (+{len(sorted_items) - 10} more)"
            )
            warnings.append(
                f"Task '{task}': Numeric values for items [{shown}{more}] were accepted via range tolerance."
            )
    return warnings


# -----------------------------------------------------------------------------
# Sidecar Writing
# -----------------------------------------------------------------------------


def _write_task_sidecars(
    *,
    dataset_root,
    task_context_templates: dict[tuple[str, str | None, int | None], dict] | None = None,
    task_context_acq_map: dict[tuple[str, str | None, int | None], str | None] | None = None,
    tasks_with_data: set[str] | None = None,
    templates: dict | None = None,
    task_acq_map: dict[str, str | None] | None = None,
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
    if task_context_templates is None:
        task_context_templates = {}
        for task in sorted(tasks_with_data or set()):
            template_json = ((templates or {}).get(task) or {}).get("json")
            if isinstance(template_json, dict):
                task_context_templates[(task, None, None)] = template_json

    if task_context_acq_map is None:
        task_context_acq_map = {
            (task, None, None): value for task, value in (task_acq_map or {}).items()
        }

    written_sidecars: set[tuple[str, str | None]] = set()
    for (task, context_session, context_run), template_json in sorted(
        task_context_templates.items(),
        key=lambda item: (item[0][0], item[0][1] or "", item[0][2] or 0),
    ):
        acq_value = _lookup_task_context_value(
            task_context_acq_map,
            task=task,
            session=context_session,
            run=context_run,
        )
        sidecar_key = (task, acq_value)
        if sidecar_key in written_sidecars:
            continue
        written_sidecars.add(sidecar_key)
        if acq_value:
            sidecar_name = f"task-{task}_acq-{acq_value}_survey.json"
        else:
            sidecar_name = f"task-{task}_survey.json"
        sidecar_path = dataset_root / sidecar_name
        if not sidecar_path.exists() or force:
            localized = localize_survey_template_fn(template_json, language=language)
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
            if "SoftwarePlatform" not in tech:
                # Keep key present for schema compliance; projects can fill this later.
                tech["SoftwarePlatform"] = ""
            if "AdministrationMethod" not in tech:
                tech["AdministrationMethod"] = ""
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

    preview: dict[str, Any] = {
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
    sample_rows: list[dict[str, str]] = []

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

    unused_cols: list[str] = []

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

    unused_cols_with_descriptions: list[dict[str, str]] = []
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


_LS_SYSTEM_FIELD_DESCRIPTIONS: dict[str, dict[str, Any]] = {
    # Core default columns (always present)
    "id": {
        "Description": "LimeSurvey response ID (auto-increment)",
        "DataType": "integer",
    },
    "submitdate": {
        "Description": "Timestamp when participant submitted the survey (NULL if incomplete)",
        "DataType": "string",
        "Format": "ISO8601",
    },
    "lastpage": {
        "Description": "Last survey page viewed by participant",
        "DataType": "integer",
    },
    "startlanguage": {
        "Description": "Language selected at survey start",
        "DataType": "string",
    },
    "completed": {
        "Description": "LimeSurvey internal completion status flag",
        "DataType": "string",
    },
    "seed": {
        "Description": "Randomization seed for question/answer order",
        "DataType": "string",
    },
    "token": {
        "Description": "Participant access token (if token-based access was enabled)",
        "DataType": "string",
        "Sensitive": True,
    },
    # Optional columns (enabled via survey settings)
    "startdate": {
        "Description": "Timestamp when participant started the survey",
        "DataType": "string",
        "Format": "ISO8601",
    },
    "datestamp": {
        "Description": "Timestamp of last respondent action on the survey",
        "DataType": "string",
        "Format": "ISO8601",
    },
    "ipaddr": {
        "Description": "IP address of participant (if Save IP Address was enabled)",
        "DataType": "string",
        "Sensitive": True,
    },
    "refurl": {
        "Description": "Referrer URL when participant entered the survey (if Save Referrer URL was enabled)",
        "DataType": "string",
    },
    # Timing
    "interviewtime": {
        "Description": "Total time spent on the survey",
        "DataType": "float",
        "Unit": "seconds",
    },
    # Participant management
    "optout": {
        "Description": "Participant opt-out status from token management",
        "DataType": "string",
    },
    "emailstatus": {
        "Description": "Email delivery status for token-based surveys",
        "DataType": "string",
    },
}


def _write_tool_limesurvey_files(
    *,
    df,
    ls_system_cols: list[str],
    res_id_col: str,
    res_ses_col: str | None,
    session: str | None,
    output_root: Path,
    normalize_sub_fn,
    normalize_ses_fn,
    ensure_dir_fn,
    build_bids_survey_filename_fn,
    ls_metadata: dict | None = None,
) -> int:
    """Write tool-limesurvey TSV + JSON sidecar files.

    For each participant/session, writes:
    - A TSV file with the system columns (startdate, submitdate, seed, etc.)
    - A JSON sidecar describing the columns and their semantics

    The JSON sidecar is written once per modality directory (shared across
    subjects in the same session).

    Args:
        ls_metadata: Optional dict with keys like 'survey_id', 'survey_title',
            'tool_version' extracted from the .lss structure during import.

    Returns the number of TSV files written.
    """
    import json as _json

    if not ls_system_cols:
        return 0

    available_cols = [c for c in ls_system_cols if c in df.columns]
    if not available_cols:
        return 0

    meta = ls_metadata or {}
    files_written = 0
    sidecar_dirs_written: set[str] = set()

    for _, row in df.iterrows():
        sub_id = normalize_sub_fn(row[res_id_col])
        ses_id = (
            normalize_ses_fn(session)
            if session and session != "all"
            else (normalize_ses_fn(row[res_ses_col]) if res_ses_col else "ses-1")
        )
        modality_dir = ensure_dir_fn(output_root / sub_id / ses_id / "survey")

        # ── TSV file ─────────────────────────────────────────────
        tsv_filename = f"{sub_id}_{ses_id}_tool-limesurvey_survey.tsv"
        tsv_path = modality_dir / tsv_filename

        out_row = {}
        for col in available_cols:
            val = row.get(col)
            if val is None or (isinstance(val, float) and str(val) == "nan"):
                out_row[col] = "n/a"
            else:
                out_row[col] = str(val)

        # Derived fields
        try:
            import pandas as pd

            start = pd.to_datetime(row.get("startdate"), errors="coerce")
            submit = pd.to_datetime(row.get("submitdate"), errors="coerce")
            if pd.notna(start) and pd.notna(submit):
                duration_min = round((submit - start).total_seconds() / 60, 2)
                out_row["SurveyDuration_minutes"] = str(duration_min)
            if pd.notna(submit):
                out_row["CompletionStatus"] = "complete"
            else:
                out_row["CompletionStatus"] = "incomplete"
        except Exception:
            pass

        fieldnames = list(out_row.keys())
        with open(tsv_path, "w", encoding="utf-8", newline="") as f:
            writer = csv.DictWriter(
                f, fieldnames=fieldnames, delimiter="\t", lineterminator="\n"
            )
            writer.writeheader()
            writer.writerow(out_row)

        files_written += 1

        # ── JSON sidecar (once per directory) ────────────────────
        dir_key = str(modality_dir)
        if dir_key not in sidecar_dirs_written:
            sidecar_dirs_written.add(dir_key)
            json_filename = f"{sub_id}_{ses_id}_tool-limesurvey_survey.json"
            json_path = modality_dir / json_filename

            sidecar = _build_tool_limesurvey_sidecar(
                available_cols=available_cols,
                has_duration="SurveyDuration_minutes" in out_row,
                has_completion="CompletionStatus" in out_row,
                ls_metadata=meta,
            )
            with open(json_path, "w", encoding="utf-8") as f:
                _json.dump(sidecar, f, indent=2, ensure_ascii=False)
                f.write("\n")

    return files_written


def _build_tool_limesurvey_sidecar(
    *,
    available_cols: list[str],
    has_duration: bool,
    has_completion: bool,
    ls_metadata: dict,
) -> dict:
    """Build the JSON sidecar for a tool-limesurvey_survey.tsv file."""
    sidecar: dict = {
        "Metadata": {
            "SchemaVersion": "1.0.0",
            "Tool": "LimeSurvey",
            "CreationDate": datetime.now().strftime("%Y-%m-%d"),
        },
        "SystemFields": {},
    }

    # Add optional metadata from .lss import
    if ls_metadata.get("tool_version"):
        sidecar["Metadata"]["ToolVersion"] = ls_metadata["tool_version"]
    if ls_metadata.get("survey_id"):
        sidecar["Metadata"]["SurveyId"] = ls_metadata["survey_id"]
    if ls_metadata.get("survey_title"):
        sidecar["Metadata"]["SurveyTitle"] = ls_metadata["survey_title"]

    # Document system fields that are present in the TSV
    timing_cols = []
    for col in available_cols:
        col_lower = col.strip().lower()
        if col_lower in _LS_SYSTEM_FIELD_DESCRIPTIONS:
            sidecar["SystemFields"][col] = _LS_SYSTEM_FIELD_DESCRIPTIONS[
                col_lower
            ].copy()
        elif col_lower.startswith("grouptime"):
            timing_cols.append(("group", col))
        elif col_lower.startswith("questiontime"):
            timing_cols.append(("question", col))
        elif col_lower.startswith("duration_"):
            timing_cols.append(("duration", col))
        elif re.match(r"^attribute_\d+$", col_lower):
            sidecar["SystemFields"][col] = {
                "Description": f"Custom participant attribute '{col}'",
                "DataType": "string",
            }
        else:
            sidecar["SystemFields"][col] = {
                "Description": f"LimeSurvey system column '{col}'",
                "DataType": "string",
            }

    # Timing fields (group timing, question timing, duration columns)
    if timing_cols:
        sidecar["Timings"] = {}
        for kind, col in timing_cols:
            if kind == "group":
                desc = f"Time spent on question group (column '{col}')"
            elif kind == "question":
                desc = f"Time spent on individual question (column '{col}')"
            else:
                desc = f"Duration measurement (column '{col}')"
            sidecar["Timings"][col] = {
                "Description": desc,
                "Unit": "seconds",
                "DataType": "float",
            }

    # Derived fields
    derived: dict[str, Any] = {}
    if has_duration:
        derived["SurveyDuration_minutes"] = {
            "Description": "Total survey duration calculated from submitdate - startdate",
            "Unit": "minutes",
            "DataType": "float",
        }
    if has_completion:
        derived["CompletionStatus"] = {
            "Description": "Whether the survey was completed and submitted",
            "Levels": {
                "complete": "Survey was submitted (submitdate present)",
                "incomplete": "Survey was not submitted (submitdate missing)",
            },
        }
    if derived:
        sidecar["DerivedFields"] = derived

    return sidecar


def _generate_dry_run_preview(
    *,
    df,
    tasks_with_data: set[str],
    task_run_columns: dict[tuple[str, int | None], list[str]],
    col_to_mapping: dict,
    templates: dict,
    task_context_templates: dict[tuple[str, str | None, int | None], dict] | None = None,
    res_id_col: str,
    res_ses_col: str | None,
    res_run_col: str | None = None,
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
    task_runs: dict[str, int | None] | None = None,
    task_context_acq_map: dict[tuple[str, str | None, int | None], str | None] | None = None,
    task_acq_map: dict[str, str | None] | None = None,
) -> dict:
    """Generate a detailed preview of what will be created during conversion."""

    if task_context_templates is None:
        task_context_templates = {
            (task, None, None): template_data["json"]
            for task, template_data in templates.items()
            if isinstance(template_data, dict)
            and isinstance(template_data.get("json"), dict)
        }
    if task_context_acq_map is None:
        task_context_acq_map = {
            (task, None, None): value for task, value in (task_acq_map or {}).items()
        }

    preview: dict[str, Any] = {
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
        "session_column": res_ses_col,
        "run_column": res_run_col,
    }

    issues: list[dict[str, Any]] = []
    participants_info: list[dict[str, Any]] = []
    composite_keys: list[tuple] = []  # (sub_id, ses_id, run_id) for duplicate detection
    planned_file_paths: set[str] = set()

    # Sort rows by (session, run, participant) so the preview reflects a stable order.
    sort_cols = [
        c for c in [res_ses_col, res_run_col, res_id_col] if c and c in df.columns
    ]
    if sort_cols:
        df = df.sort_values(sort_cols, kind="stable").reset_index(drop=True)

    for idx, row in df.iterrows():
        sub_id_raw = row[res_id_col]
        sub_id = normalize_sub_fn(sub_id_raw)

        ses_id = (
            normalize_ses_fn(session)
            if session and session != "all"
            else (normalize_ses_fn(row[res_ses_col]) if res_ses_col else "ses-1")
        )

        run_id: int | None = None
        if res_run_col and res_run_col in df.columns:
            try:
                run_id = int(str(row[res_run_col]).strip())
            except (ValueError, TypeError):
                run_id = None

        composite_keys.append((sub_id, ses_id, run_id))

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

            # Build BIDS filename for this row × task combination
            include_run = (task_runs or {}).get(task) is not None
            if run_id is not None:
                effective_run: int | None = run_id
            else:
                effective_run = run if include_run else None

            acq = _lookup_task_context_value(
                task_context_acq_map,
                task=task,
                session=ses_id,
                run=effective_run,
            )
            parts = [sub_id, ses_id, f"task-{task}"]
            if acq:
                parts.append(f"acq-{acq}")
            if effective_run is not None:
                parts.append(f"run-{effective_run:02d}")
            parts.append("survey")
            fname = "_".join(parts) + ".tsv"
            fpath = str(output_root / sub_id / ses_id / "survey" / fname)
            if fpath not in planned_file_paths:
                description_parts = [f"Survey data for task {task}"]
                if acq:
                    description_parts.append(f"acq {acq}")
                if effective_run is not None:
                    description_parts.append(f"run {effective_run:02d}")

                preview["files_to_create"].append(
                    {
                        "type": "data",
                        "path": fpath,
                        "description": ", ".join(description_parts),
                    }
                )
                planned_file_paths.add(fpath)

        participants_info.append(
            {
                "participant_id": sub_id,
                "session_id": ses_id,
                "run_id": run_id,
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

    key_counts = Counter(composite_keys)
    # A true duplicate is a row where (sub_id, ses_id, run_id) repeats
    dup_keys = {key: count for key, count in key_counts.items() if count > 1}
    if dup_keys:
        # Collect just the sub_ids for readable display
        dup_sub_ids = sorted({key[0] for key in dup_keys})
        issues.append(
            {
                "type": "duplicate_ids",
                "severity": "error",
                "message": f"Found {len(dup_sub_ids)} duplicate participant IDs after normalization",
                "details": {
                    sub_id: key_counts[key]
                    for key, sub_id in [(k, k[0]) for k in list(dup_keys.keys())[:10]]
                },
            }
        )

    col_mapping_details: dict[str, Any] = {}
    for col, mapping in col_to_mapping.items():
        task = mapping.task
        run = mapping.run
        base_item = mapping.base_item

        schema = _lookup_task_context_value(
            task_context_templates,
            task=task,
            session=None,
            run=run,
        )
        if schema is None:
            schema = templates[task]["json"]
        item_def = schema.get(base_item, {})
        missing_count = sum(1 for value in df[col] if is_missing_fn(value))
        total_values = len(df.index)
        expected_levels = item_def.get("Levels") if isinstance(item_def, dict) else None

        col_mapping_details[col] = {
            "task": task,
            "run": run,
            "base_item": base_item,
            "missing_count": missing_count,
            "missing_percent": (
                round((missing_count / total_values) * 100, 1) if total_values else 0.0
            ),
            "has_unexpected_values": False,
            "expected_levels": (
                sorted(expected_levels.keys())
                if isinstance(expected_levels, dict)
                else []
            ),
        }

    preview["column_mapping"] = col_mapping_details
    preview["data_issues"] = issues
    preview["summary"]["total_files"] = len(preview["files_to_create"])
    preview["summary"]["total_files_to_create"] = len(preview["files_to_create"])

    return preview
