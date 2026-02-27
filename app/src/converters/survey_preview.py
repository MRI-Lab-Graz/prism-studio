"""Preview-generation helpers for survey conversion dry-run mode."""

from __future__ import annotations

from pathlib import Path
import re

from .survey_participants import (
    _load_participants_mapping,
    _get_mapped_columns,
    _normalize_participant_template_dict,
)


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

    from collections import Counter

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

        col_values = df[col]
        missing = col_values.apply(is_missing_fn).sum()
        total = len(col_values)
        unique_vals = col_values.dropna().unique()

        col_info = {
            "task": task,
            "run": run,
            "base_item": base_item,
            "missing_count": int(missing),
            "missing_percent": round(missing / total * 100, 1) if total > 0 else 0,
            "unique_values": len(unique_vals),
            "data_type": item_def.get("DataType", "unknown"),
        }

        has_numeric_range = "MinValue" in item_def or "MaxValue" in item_def

        if (
            "Levels" in item_def
            and isinstance(item_def["Levels"], dict)
            and not has_numeric_range
        ):
            expected_levels = set(str(k) for k in item_def["Levels"].keys())
            actual_values = set(str(v) for v in unique_vals if not is_missing_fn(v))
            unexpected = actual_values - expected_levels

            if unexpected:
                issues.append(
                    {
                        "type": "unexpected_values",
                        "severity": "warning",
                        "column": col,
                        "task": task,
                        "item": base_item,
                        "message": f"Column '{col}' has {len(unexpected)} unexpected value(s)",
                        "expected": sorted(expected_levels),
                        "unexpected": sorted(list(unexpected)[:20]),
                    }
                )
                col_info["has_unexpected_values"] = True

        if "MinValue" in item_def or "MaxValue" in item_def:
            try:
                import pandas as pd

                numeric_vals = pd.to_numeric(col_values, errors="coerce").dropna()
                if len(numeric_vals) > 0:
                    min_val = item_def.get("MinValue")
                    max_val = item_def.get("MaxValue")

                    out_of_range = []
                    if min_val is not None:
                        out_of_range.extend(numeric_vals[numeric_vals < min_val])
                    if max_val is not None:
                        out_of_range.extend(numeric_vals[numeric_vals > max_val])

                    if len(out_of_range) > 0:
                        issues.append(
                            {
                                "type": "out_of_range",
                                "severity": "warning",
                                "column": col,
                                "task": task,
                                "item": base_item,
                                "message": f"Column '{col}' has {len(out_of_range)} value(s) outside expected range",
                                "range": f"[{min_val}, {max_val}]",
                                "out_of_range_count": len(out_of_range),
                            }
                        )
            except Exception:
                pass

        col_mapping_details[col] = col_info

    preview["column_mapping"] = col_mapping_details
    preview["data_issues"] = issues

    files_to_create = []
    files_to_create.append(
        {
            "path": "dataset_description.json",
            "type": "metadata",
            "description": "Dataset description (BIDS required)",
        }
    )

    if not skip_participants:
        files_to_create.append(
            {
                "path": "participants.tsv",
                "type": "metadata",
                "description": f"Participant list ({len(participants_info)} participants)",
            }
        )

        files_to_create.append(
            {
                "path": "participants.json",
                "type": "metadata",
                "description": "Participant column definitions",
            }
        )

    for task in sorted(tasks_with_data):
        files_to_create.append(
            {
                "path": f"task-{task}_survey.json",
                "type": "sidecar",
                "description": f"Survey template for {task}",
            }
        )

    if ls_system_cols:
        files_to_create.append(
            {
                "path": "tool-limesurvey.json",
                "type": "sidecar",
                "description": f"LimeSurvey system metadata ({len(ls_system_cols)} columns)",
            }
        )

    for p_info in participants_info:
        sub_id = p_info["participant_id"]
        ses_id = p_info["session_id"]

        if ls_system_cols:
            files_to_create.append(
                {
                    "path": f"{sub_id}/{ses_id}/survey/{sub_id}_{ses_id}_tool-limesurvey.tsv",
                    "type": "data",
                    "description": "LimeSurvey system data",
                }
            )

        for task in sorted(tasks_with_data):
            max_run = max(
                (r for t, r in task_run_columns.keys() if t == task and r is not None),
                default=None,
            )

            if max_run is not None:
                for run_num in range(1, max_run + 1):
                    files_to_create.append(
                        {
                            "path": f"{sub_id}/{ses_id}/survey/{sub_id}_{ses_id}_task-{task}_run-{run_num:02d}_survey.tsv",
                            "type": "data",
                            "description": f"Survey responses for {task} (run {run_num})",
                        }
                    )
            else:
                files_to_create.append(
                    {
                        "path": f"{sub_id}/{ses_id}/survey/{sub_id}_{ses_id}_task-{task}_survey.tsv",
                        "type": "data",
                        "description": f"Survey responses for {task}",
                    }
                )

    preview["files_to_create"] = files_to_create
    preview["summary"]["total_files"] = len(files_to_create)

    if not skip_participants:
        participants_tsv_preview = _generate_participants_preview(
            df=df,
            res_id_col=res_id_col,
            res_ses_col=res_ses_col,
            session=session,
            normalize_sub_fn=normalize_sub_fn,
            normalize_ses_fn=normalize_ses_fn,
            is_missing_fn=is_missing_fn,
            participant_template=participant_template,
            output_root=output_root,
            survey_columns=set(col_to_mapping.keys()),
            ls_system_columns=ls_system_cols,
            lsa_questions_map=lsa_questions_map,
            missing_token=missing_token,
        )
        preview["participants_tsv"] = participants_tsv_preview

    return preview
