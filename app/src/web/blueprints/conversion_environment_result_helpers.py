from __future__ import annotations

from pathlib import Path


def handle_persist_environment_outputs(
    *,
    input_path: Path,
    rows_out: list[dict],
    project_root_path: Path,
    write_environment_tsv,
    write_environment_sidecar,
    environment_conversion_cancelled_error_cls,
    check_and_update_bidsignore,
    log_callback,
    raise_if_cancelled,
) -> tuple[list[str], Path | None]:
    output_root = input_path.parent / "environment"
    output_root.mkdir()
    output_path = output_root / "recording-weather_environment.tsv"
    write_environment_tsv(rows_out, output_path)

    log_callback(
        f"Wrote {len(rows_out)} rows → recording-weather_environment.tsv", "success"
    )

    grouped_rows: dict[tuple[str, str], list[dict]] = {}
    for row in rows_out:
        subject_id = str(row.get("subject_id") or "").strip() or "sub-unknown"
        session_id = str(row.get("session_id") or "").strip() or "ses-01"
        grouped_rows.setdefault((subject_id, session_id), []).append(row)

    written_project_paths: list[str] = []
    written_project_paths_for_cleanup: list[Path] = []
    inherited_sidecar_path: Path | None = None
    try:
        for (subject_id, session_id), grouped in grouped_rows.items():
            raise_if_cancelled()
            env_dir = project_root_path / subject_id / session_id / "environment"
            filename = f"{subject_id}_{session_id}_recording-weather_environment.tsv"
            target_path = env_dir / filename
            write_environment_tsv(grouped, target_path)
            written_project_paths.append(str(target_path))
            written_project_paths_for_cleanup.append(target_path)

        raise_if_cancelled()
        inherited_sidecar_path = (
            project_root_path / "recording-weather_environment.json"
        )
        write_environment_sidecar(inherited_sidecar_path)
    except environment_conversion_cancelled_error_cls:
        for path in written_project_paths_for_cleanup:
            path.unlink(missing_ok=True)
        if inherited_sidecar_path is not None:
            inherited_sidecar_path.unlink(missing_ok=True)
        raise

    log_callback(
        "Saved inherited root sidecar: recording-weather_environment.json", "success"
    )

    added_bidsignore_rules = check_and_update_bidsignore(
        str(project_root_path), ["environment"]
    )
    if added_bidsignore_rules:
        log_callback(
            f"Updated .bidsignore for environment outputs ({len(added_bidsignore_rules)} rule(s) added)",
            "info",
        )

    log_callback(
        f"Saved to project: {len(written_project_paths)} environment file(s) under sub-*/ses-*/environment/",
        "success",
    )

    return written_project_paths, inherited_sidecar_path