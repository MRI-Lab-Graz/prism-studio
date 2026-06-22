"""Derivative helper flows for participants preprocessing.

This logic is orchestration-level and intentionally separated from core
validation.
"""

import importlib
from pathlib import Path
from typing import Callable, Optional


def apply_participants_mapping(
    dataset_path: str, progress_callback: Optional[Callable] = None
) -> None:
    """Auto-detect and apply participants mapping if present.

    If participants_mapping.json exists in code/library/ or sourcedata/, it is
    applied to generate/update participants.tsv before validation.
    """
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
        return

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
            if progress_callback:
                progress_callback(5, "⚠ Could not load participants mapping")
            return

        is_valid, errors = converter.validate_mapping(mapping)
        if not is_valid:
            if progress_callback:
                progress_callback(
                    5, f"⚠ Mapping validation failed: {'; '.join(errors[:3])}"
                )
            return

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
            if progress_callback:
                progress_callback(
                    5, "ℹ No source participant data file found - skipping mapping"
                )
            return

        success, df, _messages = converter.convert_participant_data(
            source_file, mapping, output_file=Path(dataset_path) / "participants.tsv"
        )

        if success and df is not None:
            if progress_callback:
                progress_callback(
                    15, f"✓ Applied participants mapping ({len(df)} rows transformed)"
                )
        else:
            if progress_callback:
                progress_callback(10, "⚠ Participants mapping partially failed")

    except Exception as e:
        if progress_callback:
            progress_callback(5, f"ℹ Participants mapping skipped: {str(e)[:50]}")
