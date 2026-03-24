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

        success, output_df, messages = converter.convert_participant_data(source, mapping)

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

        success, output_df, messages = converter.convert_participant_data(source, mapping)

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
