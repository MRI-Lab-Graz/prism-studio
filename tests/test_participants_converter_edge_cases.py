import tempfile
from pathlib import Path

import pandas as pd

from src.participants_converter import ParticipantsConverter


def _write_csv(path: Path, rows: list[dict[str, object]]) -> None:
    pd.DataFrame(rows).to_csv(path, index=False)


def test_convert_recovers_id_and_drops_invalid_rows():
    with tempfile.TemporaryDirectory() as tmp:
        dataset_root = Path(tmp)
        source = dataset_root / "participants_source.csv"
        _write_csv(
            source,
            [
                {"ID": "001", "age": "21"},
                {"ID": "  ", "age": "22"},
                {"ID": "003", "age": "23"},
            ],
        )

        converter = ParticipantsConverter(dataset_root)
        mapping = {
            "version": "1.0",
            "mappings": {
                "age": {
                    "source_column": "age",
                    "standard_variable": "age",
                    "type": "string",
                }
            },
        }

        success, output_df, messages = converter.convert_participant_data(
            source, mapping
        )

        assert success is True
        assert output_df is not None
        assert list(output_df.columns)[0] == "participant_id"
        assert list(output_df["participant_id"]) == ["sub-001", "sub-003"]
        assert any("Dropped 1 rows without valid participant_id" in m for m in messages)


def test_convert_fails_without_recoverable_participant_id():
    with tempfile.TemporaryDirectory() as tmp:
        dataset_root = Path(tmp)
        source = dataset_root / "participants_source.csv"
        _write_csv(
            source,
            [
                {"age": "21"},
                {"age": "22"},
            ],
        )

        converter = ParticipantsConverter(dataset_root)
        mapping = {
            "version": "1.0",
            "mappings": {
                "age": {
                    "source_column": "age",
                    "standard_variable": "age",
                    "type": "string",
                }
            },
        }

        success, output_df, messages = converter.convert_participant_data(
            source, mapping
        )

        assert success is False
        assert output_df is None
        assert any("Could not determine participant_id values" in m for m in messages)


def test_convert_preserves_mixed_time_formats_in_source_values():
    with tempfile.TemporaryDirectory() as tmp:
        dataset_root = Path(tmp)
        source = dataset_root / "participants_source.csv"
        _write_csv(
            source,
            [
                {"participant_id": "001", "fitness_time": "04:00"},
                {"participant_id": "002", "fitness_time": "2h"},
            ],
        )

        converter = ParticipantsConverter(dataset_root)
        mapping = {
            "version": "1.0",
            "mappings": {
                "participant_id": {
                    "source_column": "participant_id",
                    "standard_variable": "participant_id",
                    "type": "string",
                },
                "fitness_time": {
                    "source_column": "fitness_time",
                    "standard_variable": "fitness_time",
                    "type": "string",
                },
            },
        }

        success, output_df, _ = converter.convert_participant_data(source, mapping)

        assert success is True
        assert output_df is not None
        assert list(output_df["fitness_time"]) == ["04:00", "2h"]


def test_convert_preserves_existing_prefixed_ids_exactly():
    with tempfile.TemporaryDirectory() as tmp:
        dataset_root = Path(tmp)
        source = dataset_root / "participants_source.csv"
        _write_csv(
            source,
            [
                {"participant_id": "sub-1", "age": "21"},
                {"participant_id": "sub-001", "age": "22"},
            ],
        )

        converter = ParticipantsConverter(dataset_root)
        mapping = {
            "version": "1.0",
            "mappings": {
                "participant_id": {
                    "source_column": "participant_id",
                    "standard_variable": "participant_id",
                    "type": "string",
                },
                "age": {
                    "source_column": "age",
                    "standard_variable": "age",
                    "type": "string",
                },
            },
        }

        success, output_df, messages = converter.convert_participant_data(
            source, mapping
        )

        assert success is True
        assert output_df is not None
        assert list(output_df["participant_id"]) == ["sub-1", "sub-001"]
        assert any(
            "Preserved participant_id values without renumbering" in message
            for message in messages
        )


def test_convert_sanitizes_invalid_participant_characters_without_padding():
    with tempfile.TemporaryDirectory() as tmp:
        dataset_root = Path(tmp)
        source = dataset_root / "participants_source.csv"
        _write_csv(
            source,
            [
                {"participant_id": "011_S_0002", "age": "21"},
            ],
        )

        converter = ParticipantsConverter(dataset_root)
        mapping = {
            "version": "1.0",
            "mappings": {
                "participant_id": {
                    "source_column": "participant_id",
                    "standard_variable": "participant_id",
                    "type": "string",
                },
                "age": {
                    "source_column": "age",
                    "standard_variable": "age",
                    "type": "string",
                },
            },
        }

        success, output_df, _messages = converter.convert_participant_data(
            source, mapping
        )

        assert success is True
        assert output_df is not None
        assert list(output_df["participant_id"]) == ["sub-011S0002"]


def test_convert_drops_session_and_run_and_collapses_to_unique_participants():
    with tempfile.TemporaryDirectory() as tmp:
        dataset_root = Path(tmp)
        source = dataset_root / "participants_source.csv"
        _write_csv(
            source,
            [
                {
                    "Code": "1",
                    "session": "pre",
                    "run": "1",
                    "Geschlecht": "2",
                    "Alter": "20",
                    "Händigkeit": "0",
                },
                {
                    "Code": "1",
                    "session": "post",
                    "run": "2",
                    "Geschlecht": "2",
                    "Alter": "20",
                    "Händigkeit": "0",
                },
                {
                    "Code": "2",
                    "session": "pre",
                    "run": "1",
                    "Geschlecht": "1",
                    "Alter": "25",
                    "Händigkeit": "1",
                },
            ],
        )

        converter = ParticipantsConverter(dataset_root)
        mapping = {
            "version": "1.0",
            "mappings": {
                "participant_id": {
                    "source_column": "Code",
                    "standard_variable": "participant_id",
                    "type": "string",
                },
                "session": {
                    "source_column": "session",
                    "standard_variable": "session",
                    "type": "string",
                },
                "run": {
                    "source_column": "run",
                    "standard_variable": "run",
                    "type": "string",
                },
                "geschlecht": {
                    "source_column": "Geschlecht",
                    "standard_variable": "geschlecht",
                    "type": "string",
                },
                "alter": {
                    "source_column": "Alter",
                    "standard_variable": "alter",
                    "type": "string",
                },
                "haendigkeit": {
                    "source_column": "Händigkeit",
                    "standard_variable": "haendigkeit",
                    "type": "string",
                },
            },
        }

        success, output_df, messages = converter.convert_participant_data(
            source, mapping
        )

        assert success is True
        assert output_df is not None
        assert list(output_df.columns) == [
            "participant_id",
            "geschlecht",
            "alter",
            "haendigkeit",
        ]
        assert list(output_df["participant_id"]) == ["sub-1", "sub-2"]
        assert any(
            "Dropped non-BIDS participants.tsv columns: session, run" in m
            for m in messages
        )
        assert any(
            "Collapsed repeated rows to one row per participant_id" in m
            for m in messages
        )
