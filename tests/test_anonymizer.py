"""Tests for src/anonymizer.py — participant ID and question text anonymization."""

import csv
import json
import sys
import os
import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from src.anonymizer import (
    generate_random_id,
    create_participant_mapping,
    create_question_mask_mapping,
    anonymize_tsv_file,
    replace_participant_ids_in_text,
    update_intendedfor_paths,
    anonymize_dataset,
    check_survey_copyright,
    _is_copyright_restricted,
    _pick_preferred_text,
    _iter_survey_template_items,
    _get_survey_license_info,
)


# ---------------------------------------------------------------------------
# generate_random_id
# ---------------------------------------------------------------------------

class TestGenerateRandomId:
    def test_default_prefix(self):
        rid = generate_random_id()
        assert rid.startswith("sub-")

    def test_custom_prefix(self):
        rid = generate_random_id(prefix="ses")
        assert rid.startswith("ses-")

    def test_length(self):
        rid = generate_random_id(length=8)
        assert len(rid.split("-")[1]) == 8

    def test_deterministic_with_seed(self):
        a = generate_random_id(seed="participant-001")
        b = generate_random_id(seed="participant-001")
        assert a == b

    def test_different_seeds_differ(self):
        a = generate_random_id(seed="alpha")
        b = generate_random_id(seed="beta")
        assert a != b


# ---------------------------------------------------------------------------
# create_participant_mapping
# ---------------------------------------------------------------------------

class TestCreateParticipantMapping:
    def test_creates_mapping_for_all_ids(self, tmp_path):
        ids = ["sub-001", "sub-002", "sub-003"]
        out = tmp_path / "mapping.json"
        mapping = create_participant_mapping(ids, out)
        assert set(mapping.keys()) == set(ids)

    def test_all_values_unique(self, tmp_path):
        ids = [f"sub-{i:03d}" for i in range(20)]
        out = tmp_path / "mapping.json"
        mapping = create_participant_mapping(ids, out)
        assert len(set(mapping.values())) == 20

    def test_file_saved(self, tmp_path):
        out = tmp_path / "subdir" / "mapping.json"
        create_participant_mapping(["sub-001"], out)
        assert out.exists()
        data = json.loads(out.read_text())
        assert "mapping" in data
        assert "reverse_mapping" in data

    def test_deterministic(self, tmp_path):
        ids = ["sub-001", "sub-002"]
        m1 = create_participant_mapping(ids, tmp_path / "m1.json", deterministic=True)
        m2 = create_participant_mapping(ids, tmp_path / "m2.json", deterministic=True)
        assert m1 == m2

    def test_prefix_preserved(self, tmp_path):
        ids = ["sub-001"]
        mapping = create_participant_mapping(ids, tmp_path / "m.json")
        assert mapping["sub-001"].startswith("sub-")

    def test_id_without_dash_uses_sub_prefix(self, tmp_path):
        """Line 71: ID without '-' → prefix defaults to 'sub'."""
        ids = ["participant001"]  # No dash
        mapping = create_participant_mapping(ids, tmp_path / "m.json")
        assert mapping["participant001"].startswith("sub-")


# ---------------------------------------------------------------------------
# replace_participant_ids_in_text
# ---------------------------------------------------------------------------

class TestReplaceParticipantIdsInText:
    def test_simple_replacement(self):
        result = replace_participant_ids_in_text("Found sub-001", {"sub-001": "sub-XYZ"})
        assert result == "Found sub-XYZ"

    def test_no_match_unchanged(self):
        result = replace_participant_ids_in_text("No IDs here", {"sub-001": "sub-XYZ"})
        assert result == "No IDs here"

    def test_empty_mapping(self):
        result = replace_participant_ids_in_text("sub-001", {})
        assert result == "sub-001"

    def test_empty_text(self):
        result = replace_participant_ids_in_text("", {"sub-001": "sub-XYZ"})
        assert result == ""

    def test_no_partial_match(self):
        # sub-01 should not match inside sub-010
        result = replace_participant_ids_in_text("sub-010", {"sub-01": "sub-NEW"})
        assert result == "sub-010"

    def test_multiple_replacements(self):
        result = replace_participant_ids_in_text(
            "sub-001 and sub-002",
            {"sub-001": "sub-A", "sub-002": "sub-B"}
        )
        assert "sub-A" in result
        assert "sub-B" in result


# ---------------------------------------------------------------------------
# update_intendedfor_paths
# ---------------------------------------------------------------------------

class TestUpdateIntendedforPaths:
    def test_string_value_replaced(self):
        result = update_intendedfor_paths("sub-001/eeg/file.eeg", {"sub-001": "sub-XYZ"})
        assert result == "sub-XYZ/eeg/file.eeg"

    def test_list_values_replaced(self):
        result = update_intendedfor_paths(
            ["bids::sub-001/eeg/f.eeg", "bids::sub-002/eeg/f.eeg"],
            {"sub-001": "sub-A", "sub-002": "sub-B"}
        )
        assert result[0] == "bids::sub-A/eeg/f.eeg"
        assert result[1] == "bids::sub-B/eeg/f.eeg"

    def test_dict_values_replaced(self):
        result = update_intendedfor_paths(
            {"IntendedFor": "sub-001/fmap/file.nii"},
            {"sub-001": "sub-XYZ"}
        )
        assert result["IntendedFor"] == "sub-XYZ/fmap/file.nii"

    def test_empty_mapping_passthrough(self):
        data = {"IntendedFor": "sub-001/file.nii"}
        result = update_intendedfor_paths(data, {})
        assert result == data

    def test_non_string_scalars_unchanged(self):
        result = update_intendedfor_paths(42, {"sub-001": "sub-X"})
        assert result == 42


# ---------------------------------------------------------------------------
# anonymize_tsv_file
# ---------------------------------------------------------------------------

class TestAnonymizeTsvFile:
    def _write_tsv(self, path, rows):
        with open(path, "w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=list(rows[0].keys()), delimiter="\t")
            writer.writeheader()
            writer.writerows(rows)

    def test_participant_id_replaced(self, tmp_path):
        src = tmp_path / "input.tsv"
        dst = tmp_path / "output.tsv"
        self._write_tsv(src, [{"participant_id": "sub-001", "score": "5"}])
        anonymize_tsv_file(src, dst, {"sub-001": "sub-XYZ"})
        with open(dst) as f:
            content = f.read()
        assert "sub-XYZ" in content
        assert "sub-001" not in content

    def test_question_mapping_renames_column(self, tmp_path):
        src = tmp_path / "input.tsv"
        dst = tmp_path / "output.tsv"
        self._write_tsv(src, [{"participant_id": "sub-001", "ADS_01": "3"}])
        anonymize_tsv_file(src, dst, {"sub-001": "sub-XYZ"}, {"ADS_01": "ADS Question 1"})
        with open(dst) as f:
            content = f.read()
        assert "ADS Question 1" in content

    def test_no_participant_id_column_safe(self, tmp_path):
        src = tmp_path / "input.tsv"
        dst = tmp_path / "output.tsv"
        self._write_tsv(src, [{"score": "5", "item": "a"}])
        # should not raise
        anonymize_tsv_file(src, dst, {"sub-001": "sub-XYZ"})
        assert dst.exists()


# ---------------------------------------------------------------------------
# anonymize_dataset
# ---------------------------------------------------------------------------

class TestAnonymizeDataset:
    def test_creates_mapping_file(self, tmp_path):
        ds = tmp_path / "dataset"
        sub = ds / "sub-001"
        sub.mkdir(parents=True)
        ptable = ds / "participants.tsv"
        with open(ptable, "w") as f:
            f.write("participant_id\nsub-001\n")
        mapping_path = tmp_path / "mapping.json"
        result = anonymize_dataset(ds, tmp_path / "out", mapping_path=mapping_path)
        assert result == mapping_path
        assert mapping_path.exists()

    def test_empty_dataset_no_error(self, tmp_path):
        ds = tmp_path / "empty"
        ds.mkdir()
        result = anonymize_dataset(ds, tmp_path / "out")
        assert result.exists()


# ---------------------------------------------------------------------------
# check_survey_copyright
# ---------------------------------------------------------------------------

class TestCheckSurveyCopyright:
    def test_cc0_not_restricted(self):
        template = {"Study": {"License": "CC0"}}
        assert check_survey_copyright(template) is False

    def test_no_license_restricted(self):
        template = {"Study": {}}
        assert check_survey_copyright(template) is True

    def test_proprietary_restricted(self):
        template = {"Study": {"License": "All rights reserved"}}
        assert check_survey_copyright(template) is True

    def test_cc_by_not_restricted(self):
        template = {"License": "CC-BY 4.0"}
        assert check_survey_copyright(template) is False


# ---------------------------------------------------------------------------
# _is_copyright_restricted
# ---------------------------------------------------------------------------

class TestIsCopyrightRestricted:
    def test_free_text(self):
        assert _is_copyright_restricted("free to use") is False

    def test_cc0(self):
        assert _is_copyright_restricted("CC0") is False

    def test_empty_string_restricted(self):
        assert _is_copyright_restricted("") is True

    def test_dict_with_free(self):
        assert _is_copyright_restricted({"en": "Free license"}) is False

    def test_non_string_non_dict_restricted(self):
        assert _is_copyright_restricted(None) is True


# ---------------------------------------------------------------------------
# _pick_preferred_text
# ---------------------------------------------------------------------------

class TestPickPreferredText:
    def test_plain_string(self):
        assert _pick_preferred_text("Hello", fallback="fb") == "Hello"

    def test_empty_string_uses_fallback(self):
        assert _pick_preferred_text("", fallback="fb") == "fb"

    def test_dict_en_preferred(self):
        assert _pick_preferred_text({"en": "English", "de": "German"}, fallback="fb") == "English"

    def test_dict_de_fallback(self):
        assert _pick_preferred_text({"de": "German"}, fallback="fb") == "German"

    def test_none_uses_fallback(self):
        assert _pick_preferred_text(None, fallback="fb") == "fb"


# ---------------------------------------------------------------------------
# _iter_survey_template_items
# ---------------------------------------------------------------------------

class TestIterSurveyTemplateItems:
    def test_questions_dict(self):
        template = {"Questions": {"q1": {"Description": "Q1"}, "q2": {"Description": "Q2"}}}
        items = list(_iter_survey_template_items(template))
        assert len(items) == 2

    def test_items_list(self):
        template = {"Items": [{"ItemID": "q1", "Description": "Q1"}, {"ItemID": "q2"}]}
        items = list(_iter_survey_template_items(template))
        ids = [i[0] for i in items]
        assert "q1" in ids

    def test_top_level_keys_skipped(self):
        template = {"Technical": {}, "q1": {"Description": "Q1"}}
        items = list(_iter_survey_template_items(template))
        ids = [i[0] for i in items]
        assert "Technical" not in ids
        assert "q1" in ids

    def test_non_dict_returns_empty(self):
        items = list(_iter_survey_template_items("not a dict"))
        assert items == []


# ---------------------------------------------------------------------------
# create_question_mask_mapping
# ---------------------------------------------------------------------------

class TestCreateQuestionMaskMapping:
    def test_copyrighted_questions_masked(self):
        template = {
            "Study": {"License": "All rights reserved"},
            "Questions": {
                "q1": {"Description": "Do you feel anxious?"},
                "q2": {"Description": "Do you sleep well?"},
            },
        }
        mapping = create_question_mask_mapping(template, "ADS")
        assert mapping["q1"] == "ADS Question 1"
        assert mapping["q2"] == "ADS Question 2"

    def test_free_license_keeps_description(self):
        template = {
            "Study": {"License": "CC0"},
            "Questions": {
                "q1": {"Description": "How are you?"},
            },
        }
        mapping = create_question_mask_mapping(template, "DEMO")
        assert mapping["q1"] == "How are you?"

    def test_output_file_saved(self, tmp_path):
        template = {
            "Study": {"License": "CC0"},
            "Questions": {"q1": {"Description": "test"}},
        }
        out = tmp_path / "mask.json"
        create_question_mask_mapping(template, "X", output_file=out)
        assert out.exists()
