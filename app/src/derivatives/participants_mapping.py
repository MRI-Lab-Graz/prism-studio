"""Derivative helper flows for participants preprocessing.

This logic is orchestration-level and intentionally separated from core
validation.
"""

import importlib
from pathlib import Path
from typing import Callable, Optional


def apply_participants_mapping(
    dataset_path: str, progress_callback: Optional[Callable] = None
) -> dict:
    """Auto-detect and apply participants mapping if present.

    If participants_mapping.json exists in code/library/ or sourcedata/, it is
    applied to generate/update participants.tsv before validation.

    Returns a dict describing what happened so callers can surface this
    dataset-mutating side effect to the user instead of it being silent:
    {"applied": bool, "mapping_file": str|None, "rows": int|None, "reason": str|None}
    """
    result: dict = {
        "applied": False,
        "mapping_file": None,
        "rows": None,
        "reason": None,
    }

    mapping_file = None
    search_paths = [
        Path(dataset_path).parent / "code" / "library" / "participants_mapping.json",
        Path(dataset_path).parent / "sourcedata" / "participants_mapping.json",
        Path(dataset_path).parent.parent
        / "code"
        / "library"
        / "participants_mapping.json",
    ]

    for candidate in search_paths:
        if candidate.exists():
            mapping_file = candidate
            break

    if not mapping_file:
        return result

    result["mapping_file"] = str(mapping_file)

    try:
        if progress_callback:
            progress_callback(
                0, "Detected participants_mapping.json - applying transformations..."
            )

        try:
            participants_converter_module = importlib.import_module(
                "src.participants_converter"
            )
        except ImportError:
            participants_converter_module = importlib.import_module(
                "participants_converter"
            )

        converter = participants_converter_module.ParticipantsConverter(dataset_path)
        mapping = converter.load_mapping_from_file(mapping_file)

        if not mapping:
            result["reason"] = "Could not load participants mapping"
            if progress_callback:
                progress_callback(5, f"⚠ {result['reason']}")
            return result

        is_valid, errors = converter.validate_mapping(mapping)
        if not is_valid:
            result["reason"] = f"Mapping validation failed: {'; '.join(errors[:3])}"
            if progress_callback:
                progress_callback(5, f"⚠ {result['reason']}")
            return result

        source_file = None
        raw_data_dir = Path(dataset_path).parent / "raw_data"

        if not raw_data_dir.exists():
            raw_data_dir = Path(dataset_path).parent.parent / "raw_data"

        if not raw_data_dir.exists():
            raw_data_dir = Path(dataset_path).parent / "sourcedata"

        if raw_data_dir.exists():
            for tsv_file in raw_data_dir.glob("**/*.tsv"):
                if not tsv_file.name.startswith("."):
                    source_file = tsv_file
                    break

        if not source_file:
            result["reason"] = "No source participant data file found - skipping mapping"
            if progress_callback:
                progress_callback(5, f"ℹ {result['reason']}")
            return result

        success, df, _messages = converter.convert_participant_data(
            source_file, mapping, output_file=Path(dataset_path) / "participants.tsv"
        )

        if success and df is not None:
            result["applied"] = True
            result["rows"] = len(df)
            if progress_callback:
                progress_callback(
                    15, f"✓ Applied participants mapping ({len(df)} rows transformed)"
                )
        else:
            result["reason"] = "Participants mapping partially failed"
            if progress_callback:
                progress_callback(10, f"⚠ {result['reason']}")

    except Exception as e:
        result["reason"] = f"Participants mapping skipped: {str(e)[:50]}"
        if progress_callback:
            progress_callback(5, f"ℹ {result['reason']}")

    return result
