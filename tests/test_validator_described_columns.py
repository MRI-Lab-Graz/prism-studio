"""A modality added by data gets column-value and strict file-name checks only if it sets describedColumns."""

import dataclasses
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "app"))
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "app" / "src"))

from src.entity_rules import ModalityRule, load_entity_rules
from src.schema_manager import DEFAULT_SCHEMA_DIR, load_all_schemas
from src.specification import load_specification, use_specification
from validator import DatasetValidator


def _spec(described_columns):
    rules = load_entity_rules()
    rule = ModalityRule.from_json(
        "bloodwork",
        {
            "kind": "prism",
            "description": "Blood draws",
            "suffixes": ["bloodchem"],
            "extensions": ["tsv", "json"],
            "describedColumns": described_columns,
        },
    )
    rules = dataclasses.replace(rules, modalities={**rules.modalities, "bloodwork": rule})
    schemas = {
        **load_all_schemas(DEFAULT_SCHEMA_DIR),
        "bloodwork": {"type": "object", "properties": {}},
    }
    return load_specification(rules=rules, schemas=schemas)


def _content_issues(tmp_path, described_columns):
    folder = tmp_path / "sub-01" / "bloodwork"
    folder.mkdir(parents=True)
    data = folder / "sub-01_bloodchem.tsv"
    data.write_text("fasting\nmaybe\n")
    (folder / "sub-01_bloodchem.json").write_text(
        json.dumps({"fasting": {"Description": "Fasted", "AllowedValues": ["yes", "no"]}})
    )
    with use_specification(_spec(described_columns)):
        return DatasetValidator().validate_data_content(str(data), "bloodwork", str(tmp_path))


def _filename_errors(tmp_path, name, described_columns):
    with use_specification(_spec(described_columns)):
        issues = DatasetValidator().validate_filename(name, "bloodwork", subject_id="sub-01")
    return [m for level, m in issues if level == "ERROR" and "expected pattern" in m]


def test_a_modality_added_by_data_gets_its_column_values_checked(tmp_path):
    issues = _content_issues(tmp_path, described_columns=True)
    assert any("maybe" in msg for level, msg in issues if level == "ERROR")


def test_without_described_columns_the_values_are_not_checked(tmp_path):
    assert _content_issues(tmp_path, described_columns=False) == []


def test_the_strict_file_name_check_follows_described_columns(tmp_path):
    bad = "sub-01_bloodchemX.tsv"
    assert _filename_errors(tmp_path, bad, described_columns=True)
    assert not _filename_errors(tmp_path, bad, described_columns=False)
