"""Helpers for writing per-subject survey response TSV files."""

from __future__ import annotations

import csv


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
