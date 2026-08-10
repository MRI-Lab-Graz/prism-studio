import json
import shutil
from pathlib import Path
from typing import Any

from flask import Response, jsonify

from src.participants_backend import convert_dataset_participants
from src.participants_backend import (
    merge_neurobagel_schema_for_columns as _merge_neurobagel_schema_for_columns,
)

from .conversion_job_store import ConversionJobStore
from .conversion_participants_mapping import _rekey_neurobagel_schema_to_output_columns
from .conversion_participants_merge import _convert_existing_participants_files

_participants_job_store = ConversionJobStore(log_level_key="level")


def _check_existing_participants_files(
    project_root: Path, mode: str, force_overwrite: bool
) -> tuple[Path, Path, list[str], "tuple[Response, int] | None"]:
    """Return (participants_tsv, participants_json, existing_files, error_response).

    error_response is None when the request may proceed; otherwise it's the
    (response, status_code) tuple the caller should return immediately.
    Only blocks on real participant data (participants.tsv). A schema-only
    participants.json saved earlier from the annotation widget has no rows
    to lose, so it doesn't require force_overwrite confirmation.
    """
    participants_tsv = project_root / "participants.tsv"
    participants_json = project_root / "participants.json"

    existing_files = []
    if participants_tsv.exists():
        existing_files.append(str(participants_tsv))
    if participants_json.exists():
        existing_files.append(str(participants_json))

    if participants_tsv.exists() and not force_overwrite and mode != "existing":
        error_response = (
            jsonify(
                {
                    "error": "Participant files already exist. Enable 'force overwrite' to replace them.",
                    "existing_files": existing_files,
                }
            ),
            409,
        )
        return participants_tsv, participants_json, existing_files, error_response

    return participants_tsv, participants_json, existing_files, None


def _run_participants_convert_job(job_id: str, config: dict[str, Any]) -> None:
    """Worker thread body for an async participants conversion job."""

    def log_msg(level, message):
        _participants_job_store.append_log(job_id, message, level)

    mode = config["mode"]
    project_root = config["project_root"]
    existing_files = config["existing_files"]
    neurobagel_schema = config["neurobagel_schema"]

    try:
        if mode == "file":
            tmp_dir = config["tmp_dir"]
            try:
                from src.participants_converter import ParticipantsConverter

                input_path = config["input_path"]
                participants_tsv = config["participants_tsv"]
                participants_json = config["participants_json"]
                mapping = config["mapping"]

                converter = ParticipantsConverter(project_root, log_callback=log_msg)
                success, df, messages = converter.convert_participant_data(
                    source_file=str(input_path),
                    mapping=mapping,
                    output_file=str(participants_tsv),
                    separator=config["converter_separator"],
                    sheet=config["sheet_arg"],
                )

                for msg in messages:
                    log_msg("INFO", msg)

                if not success or df is None:
                    _participants_job_store.failure(job_id, "Conversion failed")
                    return

                df.to_csv(participants_tsv, sep="\t", index=False)
                log_msg("INFO", f"✓ Created {participants_tsv.name}")

                participants_json_data: dict[str, Any] = {str(col): {} for col in df.columns}

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

                with open(participants_json, "w", encoding="utf-8") as f:
                    json.dump(
                        participants_json_data,
                        f,
                        indent=2,
                        ensure_ascii=False,
                    )

                log_msg("INFO", f"✓ Created {participants_json.name}")

                _participants_job_store.success(
                    job_id,
                    {
                        "status": "success",
                        "files_created": [
                            str(participants_tsv),
                            str(participants_json),
                        ],
                        "output_directory": str(project_root),
                        "overwrote_existing": bool(existing_files),
                        "overwritten_files": existing_files if existing_files else [],
                    },
                )
            finally:
                shutil.rmtree(tmp_dir, ignore_errors=True)

        elif mode == "existing":
            log_msg("INFO", "Updating existing participants.tsv/participants.json...")
            try:
                result = _convert_existing_participants_files(
                    project_root=project_root,
                    neurobagel_schema=neurobagel_schema,
                    excluded_columns=config["excluded_columns"],
                    log_callback=log_msg,
                )
            except ValueError as e:
                _participants_job_store.failure(job_id, str(e))
                return

            _participants_job_store.success(
                job_id,
                {
                    **result,
                    "overwrote_existing": bool(existing_files),
                    "overwritten_files": existing_files if existing_files else [],
                },
            )

        elif mode == "dataset":
            log_msg("INFO", "Extracting participant data from dataset...")
            try:
                result = convert_dataset_participants(
                    project_root,
                    neurobagel_schema=neurobagel_schema,
                    extract_from_survey=config["extract_from_survey"],
                    extract_from_biometrics=config["extract_from_biometrics"],
                    log_callback=log_msg,
                )
            except ValueError as e:
                _participants_job_store.failure(job_id, str(e))
                return

            _participants_job_store.success(job_id, dict(result))

    except Exception as e:
        _participants_job_store.failure(job_id, str(e))
