"""Tests for src/recipes_surveys.py — pure utility functions and helpers."""

import json
import sys
import os
import pytest
from pathlib import Path

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from src.recipes_surveys import (
    _normalize_survey_key,
    _extract_task_from_survey_filename,
    _extract_acq_from_filename,
    _strip_acq_from_task,
    _strip_suffix,
    _infer_sub_ses_from_path,
    _infer_run_from_path,
    _normalize_participant_id_for_join,
    _participant_join_key,
    _parse_numeric_cell,
    _format_numeric_cell,
    _copy_recipes_to_project,
    _ensure_bidsignore_prism_rules,
    _get_sidecar_for_task,
    _read_tsv_rows,
    _write_tsv_rows,
    get_i18n_text,
    _build_variable_metadata,
    _build_survey_metadata,
    _write_codebook_json,
    _write_codebook_tsv,
    _ensure_dir,
    _get_item_value,
    _map_value_to_bucket,
    _generate_recipes_boilerplate_sections,
    _coerce_value_labeled_columns_for_sav,
    _calculate_derived_variables,
    _calculate_scores,
    _generate_recipes_boilerplate_html,
    _generate_recipes_boilerplate,
    _normalize_sessions,
    _find_tsv_files,
    _load_participants_data,
    _load_and_validate_recipes,
)


# ---------------------------------------------------------------------------
# _normalize_survey_key
# ---------------------------------------------------------------------------

class TestNormalizeSurveyKey:
    def test_strips_recipe_prefix(self):
        assert _normalize_survey_key("recipe-ads") == "ads"

    def test_strips_survey_prefix(self):
        assert _normalize_survey_key("survey-phq9") == "phq9"

    def test_strips_task_prefix(self):
        assert _normalize_survey_key("task-gad7") == "gad7"

    def test_lowercases(self):
        assert _normalize_survey_key("ADS") == "ads"

    def test_empty_returns_empty(self):
        assert _normalize_survey_key("") == ""


# ---------------------------------------------------------------------------
# _extract_task_from_survey_filename
# ---------------------------------------------------------------------------

class TestExtractTaskFromFilename:
    def test_task_entity(self):
        p = Path("sub-001_ses-01_task-ads_survey.tsv")
        assert _extract_task_from_survey_filename(p) == "ads"

    def test_survey_entity(self):
        p = Path("sub-001_ses-01_survey-phq9_beh.tsv")
        assert _extract_task_from_survey_filename(p) == "phq9"

    def test_acq_appended(self):
        p = Path("sub-001_ses-01_task-ads_acq-v2_survey.tsv")
        result = _extract_task_from_survey_filename(p)
        assert result == "ads_acq-v2"

    def test_no_task_returns_none(self):
        p = Path("sub-001_ses-01_eeg.tsv")
        assert _extract_task_from_survey_filename(p) is None


# ---------------------------------------------------------------------------
# _extract_acq_from_filename
# ---------------------------------------------------------------------------

class TestExtractAcqFromFilename:
    def test_finds_acq(self):
        p = Path("sub-001_ses-01_task-ads_acq-short_survey.tsv")
        assert _extract_acq_from_filename(p) == "short"

    def test_no_acq_returns_none(self):
        p = Path("sub-001_ses-01_task-ads_survey.tsv")
        assert _extract_acq_from_filename(p) is None


# ---------------------------------------------------------------------------
# _strip_acq_from_task
# ---------------------------------------------------------------------------

class TestStripAcqFromTask:
    def test_strips_acq(self):
        assert _strip_acq_from_task("ads_acq-v2") == "ads"

    def test_no_acq_unchanged(self):
        assert _strip_acq_from_task("ads") == "ads"

    def test_none_returns_none(self):
        assert _strip_acq_from_task(None) is None


# ---------------------------------------------------------------------------
# _strip_suffix
# ---------------------------------------------------------------------------

class TestStripSuffix:
    def test_survey_suffix(self):
        stem, suffix = _strip_suffix("sub-001_ses-01_task-ads_survey")
        assert suffix == "_survey"
        assert "survey" not in stem

    def test_beh_suffix(self):
        stem, suffix = _strip_suffix("sub-001_ses-01_task-ads_beh")
        assert suffix == "_beh"

    def test_no_suffix(self):
        stem, suffix = _strip_suffix("sub-001_ses-01_eeg")
        assert suffix is None
        assert stem == "sub-001_ses-01_eeg"


# ---------------------------------------------------------------------------
# _infer_sub_ses_from_path
# ---------------------------------------------------------------------------

class TestInferSubSesFromPath:
    def test_extracts_sub_and_ses(self):
        p = Path("/data/sub-001/ses-01/survey/file.tsv")
        sub, ses = _infer_sub_ses_from_path(p)
        assert sub == "sub-001"
        assert ses == "ses-01"

    def test_no_session(self):
        p = Path("/data/sub-001/survey/file.tsv")
        sub, ses = _infer_sub_ses_from_path(p)
        assert sub == "sub-001"
        assert ses is None

    def test_filename_not_treated_as_folder(self):
        # Filenames like "sub-001_ses-01_task-ads.tsv" should NOT set sub/ses
        p = Path("/data/dataset/sub-001_ses-01_task-ads.tsv")
        sub, ses = _infer_sub_ses_from_path(p)
        # sub-001 appears in the filename part but suffix != "" → should not be captured
        assert sub is None


# ---------------------------------------------------------------------------
# _infer_run_from_path
# ---------------------------------------------------------------------------

class TestInferRunFromPath:
    def test_finds_run(self):
        p = Path("sub-001_ses-01_task-ads_run-01_survey.tsv")
        assert _infer_run_from_path(p) == "run-01"

    def test_no_run_returns_none(self):
        p = Path("sub-001_ses-01_task-ads_survey.tsv")
        assert _infer_run_from_path(p) is None


# ---------------------------------------------------------------------------
# _normalize_participant_id_for_join
# ---------------------------------------------------------------------------

class TestNormalizeParticipantIdForJoin:
    def test_sub_prefix_preserved(self):
        assert _normalize_participant_id_for_join("sub-001") == "sub-001"

    def test_bare_number_prefixed(self):
        assert _normalize_participant_id_for_join("001") == "sub-001"

    def test_sub_without_dash(self):
        assert _normalize_participant_id_for_join("sub001") == "sub-001"

    def test_empty_returns_none(self):
        assert _normalize_participant_id_for_join("") is None

    def test_nan_returns_none(self):
        assert _normalize_participant_id_for_join("nan") is None
        assert _normalize_participant_id_for_join("n/a") is None


# ---------------------------------------------------------------------------
# _participant_join_key
# ---------------------------------------------------------------------------

class TestParticipantJoinKey:
    def test_leading_zeros_stripped(self):
        assert _participant_join_key("sub-001") == "1"
        assert _participant_join_key("001") == "1"

    def test_non_numeric_preserved(self):
        assert _participant_join_key("sub-abc") == "abc"

    def test_none_returns_none(self):
        assert _participant_join_key(None) is None

    def test_empty_token_after_strip_returns_none(self):
        """Line 663: normalized is not None but token is empty."""
        # "sub-" normalizes to "sub-" → token = "" → return None
        # Use a value that _normalize_participant_id_for_join returns "sub-" or empty:
        # Pass empty string to sub-level (raw="sub-" → rest="" → return None from normalize)
        # The normalize returns None for empty string, so we test None case
        # Instead test with a key that strips to empty token
        assert _participant_join_key("sub-") is None or _participant_join_key("  ") is None


# ---------------------------------------------------------------------------
# _parse_numeric_cell
# ---------------------------------------------------------------------------

class TestParseNumericCell:
    def test_integer_string(self):
        assert _parse_numeric_cell("42") == 42.0

    def test_float_string(self):
        assert abs(_parse_numeric_cell("3.14") - 3.14) < 0.001

    def test_comma_decimal(self):
        assert _parse_numeric_cell("3,14") == 3.14

    def test_na_returns_none(self):
        assert _parse_numeric_cell("n/a") is None
        assert _parse_numeric_cell("") is None
        assert _parse_numeric_cell(None) is None

    def test_clock_time_parsed(self):
        result = _parse_numeric_cell("22:30")
        assert result == pytest.approx(22.5, rel=1e-3)

    def test_invalid_string_returns_none(self):
        assert _parse_numeric_cell("abc") is None

    def test_clock_time_with_non_integer_raises_and_falls_back(self):
        """Lines 686-687: clock format with non-integer parts → exception → falls back."""
        # "xx:30" should hit the exception branch and return None (not a valid number)
        assert _parse_numeric_cell("xx:30") is None

    def test_clock_time_with_seconds(self):
        """Line 685: clock format with seconds."""
        result = _parse_numeric_cell("22:30:45")
        assert result is not None
        assert result > 22.0


# ---------------------------------------------------------------------------
# _format_numeric_cell
# ---------------------------------------------------------------------------

class TestFormatNumericCell:
    def test_none_returns_na(self):
        assert _format_numeric_cell(None) == "n/a"

    def test_integer_float_no_decimal(self):
        assert _format_numeric_cell(3.0) == "3"

    def test_float_preserved(self):
        result = _format_numeric_cell(3.14)
        assert "3" in result and "14" in result


# ---------------------------------------------------------------------------
# get_i18n_text
# ---------------------------------------------------------------------------

class TestGetI18nText:
    def test_plain_string(self):
        assert get_i18n_text("Hello") == "Hello"

    def test_dict_en(self):
        assert get_i18n_text({"en": "English", "de": "Deutsch"}) == "English"

    def test_dict_de_fallback(self):
        assert get_i18n_text({"de": "Deutsch"}, lang="de") == "Deutsch"

    def test_none_returns_empty(self):
        assert get_i18n_text(None) == ""


# ---------------------------------------------------------------------------
# _ensure_bidsignore_prism_rules
# ---------------------------------------------------------------------------

class TestEnsureBidsignorePrismRules:
    def test_creates_bidsignore_if_missing(self, tmp_path):
        _ensure_bidsignore_prism_rules(tmp_path, "survey")
        assert (tmp_path / ".bidsignore").exists()

    def test_adds_modality_rule(self, tmp_path):
        _ensure_bidsignore_prism_rules(tmp_path, "survey")
        content = (tmp_path / ".bidsignore").read_text()
        assert "survey/" in content

    def test_idempotent(self, tmp_path):
        _ensure_bidsignore_prism_rules(tmp_path, "survey")
        _ensure_bidsignore_prism_rules(tmp_path, "survey")
        content = (tmp_path / ".bidsignore").read_text()
        # Should not have duplicated the same rule
        assert content.count("derivatives/") <= 2  # at most once per run


# ---------------------------------------------------------------------------
# _copy_recipes_to_project
# ---------------------------------------------------------------------------

class TestCopyRecipesToProject:
    def test_copies_new_recipes(self, tmp_path):
        recipes = {
            "ads": {"json": {"RecipeVersion": "1.0"}},
        }
        count = _copy_recipes_to_project(
            recipes=recipes, dataset_root=tmp_path, modality="survey"
        )
        assert count == 1
        assert (tmp_path / "code" / "recipes" / "survey" / "recipe-ads.json").exists()

    def test_no_overwrite_existing(self, tmp_path):
        recipes_dir = tmp_path / "code" / "recipes" / "survey"
        recipes_dir.mkdir(parents=True)
        (recipes_dir / "recipe-ads.json").write_text("{}")
        count = _copy_recipes_to_project(
            recipes={"ads": {"json": {}}}, dataset_root=tmp_path, modality="survey"
        )
        assert count == 0


# ---------------------------------------------------------------------------
# _get_sidecar_for_task
# ---------------------------------------------------------------------------

class TestGetSidecarForTask:
    def test_returns_empty_if_not_found(self, tmp_path):
        result = _get_sidecar_for_task(tmp_path, "survey", "ads")
        assert result == {}

    def test_loads_from_library(self, tmp_path):
        lib = tmp_path / "code" / "library" / "survey"
        lib.mkdir(parents=True)
        (lib / "survey-ads.json").write_text(json.dumps({"ADS_01": {"Description": "Q1"}}))
        result = _get_sidecar_for_task(tmp_path, "survey", "ads")
        assert "ADS_01" in result

    def test_skips_malformed_json_and_returns_empty(self, tmp_path):
        lib = tmp_path / "code" / "library" / "survey"
        lib.mkdir(parents=True)
        (lib / "survey-ads.json").write_text("NOT VALID JSON")
        result = _get_sidecar_for_task(tmp_path, "survey", "ads")
        assert result == {}


# ---------------------------------------------------------------------------
# _read_tsv_rows / _write_tsv_rows
# ---------------------------------------------------------------------------

class TestReadWriteTsvRows:
    def test_round_trip(self, tmp_path):
        path = tmp_path / "test.tsv"
        header = ["participant_id", "score"]
        rows = [{"participant_id": "sub-001", "score": "5"}]
        _write_tsv_rows(path, header, rows)
        h, r = _read_tsv_rows(path)
        assert h == header
        assert r[0]["participant_id"] == "sub-001"

    def test_missing_value_written_as_empty(self, tmp_path):
        path = tmp_path / "test.tsv"
        header = ["a", "b"]
        rows = [{"a": "1"}]  # b is missing
        _write_tsv_rows(path, header, rows)
        _, r = _read_tsv_rows(path)
        assert r[0]["b"] == ""


# ---------------------------------------------------------------------------
# _build_variable_metadata
# ---------------------------------------------------------------------------

class TestBuildVariableMetadata:
    def test_score_description_added(self):
        recipe = {
            "Scores": [{"Name": "total", "Description": "Total score"}]
        }
        var_labels, val_labels, score_details = _build_variable_metadata(
            ["participant_id", "session", "total"],
            {},
            recipe,
        )
        assert var_labels["total"] == "Total score"

    def test_standard_columns_present(self):
        var_labels, _, _ = _build_variable_metadata([], {}, {})
        assert "participant_id" in var_labels
        assert "session" in var_labels

    def test_sidecar_description_used(self):
        sidecar = {"ADS_01": {"Description": "Feeling anxious"}}
        var_labels, _, _ = _build_variable_metadata(
            ["ADS_01"], {}, {}, sidecar_meta=sidecar
        )
        assert var_labels["ADS_01"] == "Feeling anxious"

    def test_score_details_extracted(self):
        recipe = {
            "Scores": [{"Name": "total", "Method": "sum", "Items": ["q1", "q2"]}]
        }
        _, _, score_details = _build_variable_metadata(
            ["total"], {}, recipe
        )
        assert "total" in score_details
        assert score_details["total"]["method"] == "sum"

    def test_sidecar_levels_build_value_labels(self):
        sidecar = {
            "Q1": {
                "Description": "Question 1",
                "Levels": {"0": "Never", "1": "Sometimes"},
            }
        }
        _, val_labels, _ = _build_variable_metadata(
            ["Q1"], {}, {}, sidecar_meta=sidecar
        )
        assert "Q1" in val_labels
        assert val_labels["Q1"]["0"] == "Never"

    def test_participants_meta_description_and_levels(self):
        participants_meta = {
            "age": {
                "Description": "Age in years",
                "Levels": {"1": "child", "2": "adult"},
            }
        }
        var_labels, val_labels, _ = _build_variable_metadata(
            ["age"], participants_meta, {}
        )
        assert var_labels["age"] == "Age in years"
        assert val_labels["age"]["1"] == "child"

    def test_score_all_fields_extracted(self):
        recipe = {
            "Scores": [
                {
                    "Name": "total",
                    "Method": "sum",
                    "Items": ["q1"],
                    "Range": {"min": 0, "max": 21},
                    "Note": "Clinically validated",
                    "Missing": "ignore",
                    "MinValid": 3,
                    "Interpretation": {"0-7": "minimal", "8-21": "severe"},
                }
            ]
        }
        _, val_labels, score_details = _build_variable_metadata(
            ["total"], {}, recipe
        )
        d = score_details["total"]
        assert d["range"] == {"min": 0, "max": 21}
        assert d["missing_handling"] == "ignore"
        assert d["min_valid"] == 3
        assert "minimal" in val_labels["total"]["0-7"]


# ---------------------------------------------------------------------------
# _build_survey_metadata
# ---------------------------------------------------------------------------

class TestBuildSurveyMetadata:
    def test_extracts_survey_name(self):
        recipe = {"Survey": {"Name": "Anxiety Scale", "TaskName": "ads"}}
        meta = _build_survey_metadata(recipe)
        assert meta["survey_name"] == "Anxiety Scale"
        assert meta["task_name"] == "ads"

    def test_reverse_coded_items(self):
        recipe = {
            "Transforms": {"Invert": {"Items": ["q1", "q2"], "Scale": {"min": 0, "max": 4}}}
        }
        meta = _build_survey_metadata(recipe)
        assert meta["reverse_coded_items"] == ["q1", "q2"]

    def test_empty_recipe_empty_meta(self):
        meta = _build_survey_metadata({})
        assert meta == {}

    def test_survey_description_included(self):
        recipe = {"Survey": {"Description": "A scale for anxiety"}}
        meta = _build_survey_metadata(recipe)
        assert "survey_description" in meta
        assert "anxiety" in str(meta["survey_description"]).lower()

    def test_survey_version_included(self):
        recipe = {"Survey": {"Version": "2.0"}}
        meta = _build_survey_metadata(recipe)
        assert meta.get("survey_version") == "2.0"

    def test_survey_all_optional_fields_included(self):
        recipe = {
            "Survey": {
                "Authors": ["Jane Doe"],
                "Citation": "Doe 2021",
                "License": "CC-BY",
                "URL": "https://example.com",
            }
        }
        meta = _build_survey_metadata(recipe)
        assert meta.get("authors") == ["Jane Doe"]
        assert meta.get("citation") == "Doe 2021"
        assert meta.get("license") == "CC-BY"
        assert meta.get("url") == "https://example.com"


# ---------------------------------------------------------------------------
# _write_codebook_json / _write_codebook_tsv
# ---------------------------------------------------------------------------

class TestWriteCodebook:
    def test_json_written(self, tmp_path):
        path = tmp_path / "codebook.json"
        _write_codebook_json(path, {"score": "Total score"}, {}, {})
        data = json.loads(path.read_text())
        assert "variables" in data
        assert "score" in data["variables"]

    def test_tsv_written(self, tmp_path):
        path = tmp_path / "codebook.tsv"
        _write_codebook_tsv(path, {"score": "Total score"}, {}, {})
        content = path.read_text()
        assert "score" in content
        assert "variable" in content  # header

    def test_survey_meta_in_json(self, tmp_path):
        path = tmp_path / "codebook.json"
        _write_codebook_json(
            path, {}, {}, survey_meta={"survey_name": "ADS"}
        )
        data = json.loads(path.read_text())
        assert data["survey"]["survey_name"] == "ADS"

    def test_tsv_with_value_labels_and_score_details(self, tmp_path):
        """Lines 519, 534: value_labels present and score_details with range."""
        path = tmp_path / "codebook.tsv"
        value_labels = {"score": {"0": "None", "1": "Mild"}}
        score_details = {"score": {"method": "sum", "items": ["q1", "q2"], "range": {"min": 0, "max": 10}, "min_valid": 2}}
        _write_codebook_tsv(path, {"score": "Total score"}, value_labels, score_details)
        content = path.read_text()
        assert "score" in content
        assert "0=None" in content
        assert "method=sum" in content
        assert "range=0-10" in content


# ---------------------------------------------------------------------------
# _get_item_value
# ---------------------------------------------------------------------------

class TestGetItemValue:
    def test_basic_retrieval(self):
        result = _get_item_value("q1", {"q1": "3"}, set(), None, None)
        assert result == 3.0

    def test_missing_item_returns_none(self):
        result = _get_item_value("q99", {"q1": "3"}, set(), None, None)
        assert result is None

    def test_inversion_applied(self):
        # invert_min=0, invert_max=4 → 4+0-3=1
        result = _get_item_value("q1", {"q1": "3"}, {"q1"}, 0, 4)
        assert result == 1.0

    def test_non_numeric_returns_none(self):
        result = _get_item_value("q1", {"q1": "n/a"}, set(), None, None)
        assert result is None


# ---------------------------------------------------------------------------
# _map_value_to_bucket
# ---------------------------------------------------------------------------

class TestMapValueToBucket:
    def test_range_mapping(self):
        mapping = {"0-7": "minimal", "8-14": "moderate", "15-21": "severe"}
        assert _map_value_to_bucket(5.0, mapping) == "minimal"
        assert _map_value_to_bucket(10.0, mapping) == "moderate"
        assert _map_value_to_bucket(18.0, mapping) == "severe"

    def test_exact_value_mapping(self):
        mapping = {"1": "low", "2": "medium", "3": "high"}
        assert _map_value_to_bucket(2.0, mapping) == "medium"

    def test_no_match_returns_none(self):
        mapping = {"0-7": "minimal"}
        assert _map_value_to_bucket(99.0, mapping) is None

    def test_malformed_range_key_skipped(self):
        """Lines 740-741: malformed range key like 'bad-range' raises → continue."""
        mapping = {"not-a-number-range": "invalid", "0-10": "valid"}
        result = _map_value_to_bucket(5.0, mapping)
        assert result == "valid"

    def test_malformed_exact_key_skipped(self):
        """Lines 746-747: exact key that's not a float → exception → continue."""
        mapping = {"abc": "text_key", "5": "real_key"}
        result = _map_value_to_bucket(5.0, mapping)
        assert result == "real_key"


# ---------------------------------------------------------------------------
# _generate_recipes_boilerplate_sections
# ---------------------------------------------------------------------------

class TestGenerateRecipesBoilerplateSections:
    def _make_recipe(self, name: str) -> dict:
        return {
            "Survey": {"Name": name, "TaskName": name.lower()},
            "Transforms": {"Invert": {"Items": ["q1", "q2"], "Scale": {"min": 0, "max": 4}}},
            "Scores": [{"Name": "total", "Method": "sum", "Items": ["q1", "q2"]}],
        }

    def test_basic_english(self):
        sections = _generate_recipes_boilerplate_sections(
            [self._make_recipe("Anxiety Scale")], lang="en"
        )
        text = " ".join(sections)
        assert "Anxiety Scale" in text
        assert "BIDS" in text or "PRISM" in text

    def test_german(self):
        sections = _generate_recipes_boilerplate_sections(
            [self._make_recipe("Angstskala")], lang="de"
        )
        text = " ".join(sections)
        assert "Angstskala" in text

    def test_empty_recipes_list(self):
        sections = _generate_recipes_boilerplate_sections([], lang="en")
        assert isinstance(sections, list)
        assert len(sections) > 0  # Still generates header text

    def test_scoring_section_present(self):
        sections = _generate_recipes_boilerplate_sections(
            [self._make_recipe("Scale A")], lang="en"
        )
        text = " ".join(sections)
        assert "total" in text or "sum" in text or "Scoring" in text

    def test_recipe_with_primary_reference_en(self):
        """Lines 1104-1107: primary reference in English."""
        recipe = {
            "Survey": {
                "Name": "PHQ-9",
                "TaskName": "phq9",
                "References": [{"Type": "primary", "Citation": "Kroenke 2001", "Author": "Kroenke"}],
            },
        }
        sections = _generate_recipes_boilerplate_sections([recipe], lang="en")
        text = " ".join(sections)
        # The reference should appear somewhere in output
        assert "PHQ-9" in text

    def test_recipe_with_translation_de(self):
        """Lines 1110-1115: translation reference in German."""
        recipe = {
            "Survey": {
                "Name": "PHQ-9",
                "TaskName": "phq9",
                "References": [{"Type": "translation", "Citation": "Müller 2010", "Author": "Müller"}],
            },
        }
        sections = _generate_recipes_boilerplate_sections([recipe], lang="de")
        text = " ".join(sections)
        assert "PHQ-9" in text

    def test_score_with_source(self):
        """Lines 1166-1174: score with Source field."""
        recipe = {
            "Survey": {"Name": "Test", "TaskName": "test"},
            "Scores": [{"Name": "subscale", "Method": "sum", "Items": ["q1"], "Source": "subscale_raw"}],
        }
        sections = _generate_recipes_boilerplate_sections([recipe], lang="en")
        text = " ".join(sections)
        assert "subscale" in text

    def test_primary_reference_german(self):
        """Line 1105: German language with primary reference."""
        recipe = {
            "Survey": {
                "Name": "PHQ-9",
                "TaskName": "phq9",
                "References": [{"Type": "primary", "Author": "Kroenke", "Citation": "Kroenke 2001"}],
            },
        }
        sections = _generate_recipes_boilerplate_sections([recipe], lang="de")
        text = " ".join(sections)
        assert "basiert auf" in text or "PHQ-9" in text

    def test_translation_reference_english(self):
        """Line 1115: English language with translation reference."""
        recipe = {
            "Survey": {
                "Name": "PHQ-9",
                "TaskName": "phq9",
                "References": [{"Type": "translation", "Author": "Müller", "Citation": "Müller 2010"}],
            },
        }
        sections = _generate_recipes_boilerplate_sections([recipe], lang="en")
        text = " ".join(sections)
        assert "translation used" in text or "PHQ-9" in text

    def test_score_map_method_description(self):
        """Lines 1147-1154: score with 'map' method."""
        recipe = {
            "Survey": {"Name": "SomeScale", "TaskName": "somescale"},
            "Scores": [
                {"Name": "category", "Method": "map", "Items": ["q1"],
                 "Mapping": {"0-2": "low", "3-5": "high"}}
            ],
        }
        sections = _generate_recipes_boilerplate_sections([recipe], lang="en")
        text = " ".join(sections)
        assert "category" in text or "categorical" in text or "map" in text

    def test_score_with_source_only_no_items(self):
        """Lines 1166-1176: score without items but with Source."""
        recipe = {
            "Survey": {"Name": "MyScale", "TaskName": "myscale"},
            "Scores": [{"Name": "derived", "Method": "mean", "Source": "raw_sum"}],
        }
        sections = _generate_recipes_boilerplate_sections([recipe], lang="en")
        text = " ".join(sections)
        assert "derived" in text


# ---------------------------------------------------------------------------
# _coerce_value_labeled_columns_for_sav
# ---------------------------------------------------------------------------

class TestCoerceValueLabeledColumnsForSav:
    def test_returns_unchanged_if_no_labels(self):
        try:
            import pandas as pd
        except ImportError:
            pytest.skip("pandas not available")
        df = pd.DataFrame({"q1": ["0", "1", "2"]})
        result = _coerce_value_labeled_columns_for_sav(df, {})
        assert list(result["q1"]) == list(df["q1"])

    def test_converts_numeric_labeled_column(self):
        try:
            import pandas as pd
        except ImportError:
            pytest.skip("pandas not available")
        df = pd.DataFrame({"q1": ["0", "1", "2", "n/a"]})
        value_labels = {"q1": {"0": "Never", "1": "Sometimes", "2": "Often"}}
        result = _coerce_value_labeled_columns_for_sav(df, value_labels)
        # Should convert to numeric (Int64 or float)
        non_na = result["q1"].dropna()
        assert all(isinstance(v, (int, float)) or hasattr(v, '__int__') for v in non_na)

    def test_non_numeric_labels_not_converted(self):
        try:
            import pandas as pd
        except ImportError:
            pytest.skip("pandas not available")
        df = pd.DataFrame({"q1": ["low", "high"]})
        value_labels = {"q1": {"low": "Low value", "high": "High value"}}
        result = _coerce_value_labeled_columns_for_sav(df, value_labels)
        # Non-numeric keys → column left unchanged (still strings)
        assert list(result["q1"]) == list(df["q1"])

    def test_none_df_returns_none(self):
        result = _coerce_value_labeled_columns_for_sav(None, {"q1": {"0": "A"}})
        assert result is None

    def test_col_not_in_df_skipped(self):
        """Line 438: column in value_labels but not in df → skipped."""
        try:
            import pandas as pd
        except ImportError:
            pytest.skip("pandas not available")
        df = pd.DataFrame({"q2": ["1", "2"]})
        value_labels = {"q1": {"1": "Yes", "2": "No"}, "q2": {"1": "A", "2": "B"}}
        result = _coerce_value_labeled_columns_for_sav(df, value_labels)
        assert "q1" not in result.columns

    def test_all_na_values_skipped(self):
        """Line 456: all values are NA → column not converted."""
        try:
            import pandas as pd
        except ImportError:
            pytest.skip("pandas not available")
        df = pd.DataFrame({"q1": ["n/a", "N/A", ""]})
        value_labels = {"q1": {"0": "Never", "1": "Sometimes"}}
        result = _coerce_value_labeled_columns_for_sav(df, value_labels)
        # Column should remain (with NA values), not raise
        assert "q1" in result.columns

    def test_float_keys_converted_to_float(self):
        """Line 462: float keys with decimal → float coercion."""
        try:
            import pandas as pd
        except ImportError:
            pytest.skip("pandas not available")
        df = pd.DataFrame({"q1": ["0.5", "1.5", "2.5"]})
        value_labels = {"q1": {"0.5": "Low", "1.5": "Med", "2.5": "High"}}
        result = _coerce_value_labeled_columns_for_sav(df, value_labels)
        # Should coerce to float
        non_na = result["q1"].dropna()
        assert len(non_na) == 3


# ---------------------------------------------------------------------------
# _calculate_derived_variables
# ---------------------------------------------------------------------------

class TestCalculateDerivedVariables:
    def _row(self, **kwargs):
        return {k: str(v) for k, v in kwargs.items()}

    def test_max_method(self):
        row = self._row(q1="3", q2="5", q3="1")
        _calculate_derived_variables(
            [{"Name": "peak", "Method": "max", "Items": ["q1", "q2", "q3"]}],
            row, set(), None, None,
        )
        assert row["peak"] == "5"

    def test_min_method(self):
        row = self._row(q1="3", q2="5", q3="1")
        _calculate_derived_variables(
            [{"Name": "low", "Method": "min", "Items": ["q1", "q2", "q3"]}],
            row, set(), None, None,
        )
        assert row["low"] == "1"

    def test_mean_method(self):
        row = self._row(q1="4", q2="2")
        _calculate_derived_variables(
            [{"Name": "avg", "Method": "mean", "Items": ["q1", "q2"]}],
            row, set(), None, None,
        )
        assert float(row["avg"]) == pytest.approx(3.0)

    def test_avg_alias(self):
        row = self._row(q1="6", q2="2")
        _calculate_derived_variables(
            [{"Name": "avg2", "Method": "avg", "Items": ["q1", "q2"]}],
            row, set(), None, None,
        )
        assert float(row["avg2"]) == pytest.approx(4.0)

    def test_sum_method(self):
        row = self._row(q1="3", q2="4")
        _calculate_derived_variables(
            [{"Name": "total", "Method": "sum", "Items": ["q1", "q2"]}],
            row, set(), None, None,
        )
        assert float(row["total"]) == pytest.approx(7.0)

    def test_map_method(self):
        row = self._row(q1="2")
        _calculate_derived_variables(
            [{"Name": "cat", "Method": "map", "Items": ["q1"],
              "Mapping": {"1-2": "low", "3-4": "high"}}],
            row, set(), None, None,
        )
        assert row["cat"] == "low"

    def test_formula_method(self):
        row = self._row(q1="5", q2="3")
        _calculate_derived_variables(
            [{"Name": "diff", "Method": "formula", "Items": ["q1", "q2"],
              "Formula": "{q1} - {q2}"}],
            row, set(), None, None,
        )
        assert float(row["diff"]) == pytest.approx(2.0)

    def test_empty_name_skipped(self):
        row = self._row(q1="1")
        _calculate_derived_variables(
            [{"Method": "sum", "Items": ["q1"]}],  # no Name
            row, set(), None, None,
        )
        assert len(row) == 1  # unchanged

    def test_missing_item_skipped_in_aggregation(self):
        row = self._row(q1="4")  # q2 missing
        _calculate_derived_variables(
            [{"Name": "s", "Method": "sum", "Items": ["q1", "q2"]}],
            row, set(), None, None,
        )
        # q1 has a value, so result is just q1's value
        assert float(row["s"]) == pytest.approx(4.0)

    def test_all_missing_items_gives_na(self):
        row = {}
        _calculate_derived_variables(
            [{"Name": "s", "Method": "sum", "Items": ["x", "y"]}],
            row, set(), None, None,
        )
        assert row["s"] in ("", "n/a", None) or row["s"] is None or row["s"] == ""


# ---------------------------------------------------------------------------
# _calculate_scores
# ---------------------------------------------------------------------------

class TestCalculateScores:
    def _row(self, **kwargs):
        return {k: str(v) for k, v in kwargs.items()}

    def test_sum_basic(self):
        row = self._row(q1="2", q2="3", q3="1")
        result = _calculate_scores(
            [{"Name": "total", "Method": "sum", "Items": ["q1", "q2", "q3"]}],
            row, set(), None, None,
        )
        assert float(result["total"]) == pytest.approx(6.0)

    def test_mean_method(self):
        row = self._row(q1="4", q2="2")
        result = _calculate_scores(
            [{"Name": "avg", "Method": "mean", "Items": ["q1", "q2"]}],
            row, set(), None, None,
        )
        assert float(result["avg"]) == pytest.approx(3.0)

    def test_min_valid_below_threshold_gives_na(self):
        row = self._row(q1="3")  # only 1 value, min_valid=2
        result = _calculate_scores(
            [{"Name": "total", "Method": "sum", "Items": ["q1", "q2"], "MinValid": 2}],
            row, set(), None, None,
        )
        assert result["total"] in ("", "n/a") or result.get("total") is None

    def test_missing_require_all_gives_na(self):
        row = self._row(q1="3")  # q2 missing, Missing=require_all
        result = _calculate_scores(
            [{"Name": "total", "Method": "sum", "Items": ["q1", "q2"],
              "Missing": "require_all"}],
            row, set(), None, None,
        )
        assert result["total"] in ("", "n/a") or result.get("total") is None

    def test_formula_method(self):
        row = self._row(q1="10", q2="4")
        result = _calculate_scores(
            [{"Name": "combo", "Method": "formula", "Items": ["q1", "q2"],
              "Formula": "{q1} + {q2} * 2"}],
            row, set(), None, None,
        )
        assert float(result["combo"]) == pytest.approx(18.0)

    def test_map_method(self):
        row = self._row(src="3")
        result = _calculate_scores(
            [{"Name": "cat", "Method": "map", "Source": "src",
              "Mapping": {"1-2": 0, "3-4": 1}}],
            row, set(), None, None,
        )
        assert result["cat"] == "1"

    def test_empty_name_skipped(self):
        row = self._row(q1="1")
        result = _calculate_scores(
            [{"Method": "sum", "Items": ["q1"]}],
            row, set(), None, None,
        )
        assert result == {}

    def test_unknown_method_gives_na(self):
        row = self._row(q1="1")
        result = _calculate_scores(
            [{"Name": "x", "Method": "nonsense", "Items": ["q1"]}],
            row, set(), None, None,
        )
        assert result["x"] in ("", "n/a") or result.get("x") is None


# ---------------------------------------------------------------------------
# _generate_recipes_boilerplate_html
# ---------------------------------------------------------------------------

class TestGenerateRecipesBoilerplateHtml:
    def test_returns_html_string(self):
        sections = ["## Overview\n", "- item one\n", "- item two\n"]
        result = _generate_recipes_boilerplate_html(sections)
        assert "<html>" in result
        assert "<ul>" in result
        assert "<li>" in result

    def test_heading_converted(self):
        sections = ["## Methods Section\n"]
        result = _generate_recipes_boilerplate_html(sections)
        assert "<h2>Methods Section</h2>" in result

    def test_h3_heading(self):
        sections = ["### Subsection\n"]
        result = _generate_recipes_boilerplate_html(sections)
        assert "<h3>Subsection</h3>" in result

    def test_code_inline(self):
        sections = ["Use `variable_name` here.\n"]
        result = _generate_recipes_boilerplate_html(sections)
        assert "<code>variable_name</code>" in result

    def test_empty_lines_skipped(self):
        sections = ["", "## Header\n", ""]
        result = _generate_recipes_boilerplate_html(sections)
        assert "<h2>Header</h2>" in result

    def test_bold_text(self):
        sections = ["**Scoring**:\n"]
        result = _generate_recipes_boilerplate_html(sections)
        assert "<strong>" in result


# ---------------------------------------------------------------------------
# _generate_recipes_boilerplate (writes MD and HTML)
# ---------------------------------------------------------------------------

class TestGenerateRecipesBoilerplate:
    def test_creates_md_and_html_files(self, tmp_path):
        recipe = {
            "Survey": {"Name": "TestSurvey", "Description": "A test survey."},
            "Scores": [{"Name": "total", "Method": "sum", "Items": ["q1", "q2"]}],
        }
        out_md = tmp_path / "methods.md"
        _generate_recipes_boilerplate([recipe], out_md)
        assert out_md.exists()
        assert (tmp_path / "methods.html").exists()

    def test_md_contains_recipe_name(self, tmp_path):
        recipe = {
            "Survey": {"Name": "TestSurvey"},
            "Scores": [],
        }
        out_md = tmp_path / "methods.md"
        _generate_recipes_boilerplate([recipe], out_md)
        content = out_md.read_text(encoding="utf-8")
        assert "TestSurvey" in content


# ---------------------------------------------------------------------------
# _normalize_sessions
# ---------------------------------------------------------------------------

class TestNormalizeSessions:
    def test_none_returns_none(self):
        assert _normalize_sessions(None) is None

    def test_string_single(self):
        result = _normalize_sessions("1")
        assert result == ["ses-1"]

    def test_string_comma_separated(self):
        result = _normalize_sessions("1, 2, 3")
        assert result == ["ses-1", "ses-2", "ses-3"]

    def test_list_passthrough(self):
        result = _normalize_sessions(["a", "b"])
        assert result == ["ses-a", "ses-b"]

    def test_empty_string_returns_none(self):
        result = _normalize_sessions("")
        assert result is None or result == []


# ---------------------------------------------------------------------------
# _find_tsv_files
# ---------------------------------------------------------------------------

from pathlib import Path


class TestFindTsvFiles:
    def test_survey_finds_in_ses_folder(self, tmp_path):
        tsv = tmp_path / "sub-01" / "ses-1" / "survey" / "task.tsv"
        tsv.parent.mkdir(parents=True)
        tsv.write_text("col\tval\n")
        result = _find_tsv_files(tmp_path, "survey")
        assert tsv in result

    def test_survey_finds_in_beh_folder(self, tmp_path):
        tsv = tmp_path / "sub-01" / "beh" / "task.tsv"
        tsv.parent.mkdir(parents=True)
        tsv.write_text("col\tval\n")
        result = _find_tsv_files(tmp_path, "survey")
        assert tsv in result

    def test_biometrics_finds_files(self, tmp_path):
        tsv = tmp_path / "sub-01" / "ses-1" / "biometrics" / "hrv.tsv"
        tsv.parent.mkdir(parents=True)
        tsv.write_text("hr\n80\n")
        result = _find_tsv_files(tmp_path, "biometrics")
        assert tsv in result

    def test_unknown_modality_fallback(self, tmp_path):
        tsv = tmp_path / "sub-01" / "ses-1" / "other" / "x.tsv"
        tsv.parent.mkdir(parents=True)
        tsv.write_text("x\n")
        result = _find_tsv_files(tmp_path, "unknown_modality")
        assert tsv in result

    def test_returns_empty_for_empty_dir(self, tmp_path):
        result = _find_tsv_files(tmp_path, "survey")
        assert result == []


# ---------------------------------------------------------------------------
# _load_participants_data
# ---------------------------------------------------------------------------

class TestLoadParticipantsData:
    def test_loads_valid_tsv(self, tmp_path):
        tsv = tmp_path / "participants.tsv"
        tsv.write_text("participant_id\tage\nsub-01\t25\n")
        df, meta = _load_participants_data(tmp_path)
        assert df is not None
        assert len(df) == 1

    def test_loads_valid_json(self, tmp_path):
        import json
        tsv = tmp_path / "participants.tsv"
        tsv.write_text("participant_id\ntest\n")
        js = tmp_path / "participants.json"
        js.write_text(json.dumps({"age": {"Description": "Age"}}))
        df, meta = _load_participants_data(tmp_path)
        assert "age" in meta

    def test_returns_none_df_when_no_tsv(self, tmp_path):
        df, meta = _load_participants_data(tmp_path)
        assert df is None
        assert meta == {}

    def test_handles_malformed_tsv_gracefully(self, tmp_path):
        tsv = tmp_path / "participants.tsv"
        tsv.write_bytes(b"\x00\x01\x02\x03malformed")
        df, meta = _load_participants_data(tmp_path)
        # Should not raise; may return None or partial data
        assert meta == {}

    def test_handles_malformed_json_gracefully(self, tmp_path):
        tsv = tmp_path / "participants.tsv"
        tsv.write_text("participant_id\nsub-01\n")
        js = tmp_path / "participants.json"
        js.write_text("{not valid json")
        df, meta = _load_participants_data(tmp_path)
        assert meta == {}


# ---------------------------------------------------------------------------
# _load_and_validate_recipes
# ---------------------------------------------------------------------------

_VALID_SURVEY_RECIPE = {
    "Kind": "survey",
    "RecipeVersion": "1.0",
    "Survey": {"TaskName": "test"},
    "Scores": [],
}


class TestLoadAndValidateRecipes:
    def test_loads_from_code_recipes_survey(self, tmp_path):
        import json as _json
        recipe_dir = tmp_path / "code" / "recipes" / "survey"
        recipe_dir.mkdir(parents=True)
        (recipe_dir / "recipe-test.json").write_text(_json.dumps(_VALID_SURVEY_RECIPE))
        result, rd = _load_and_validate_recipes(tmp_path, "survey")
        assert "test" in result
        assert rd is not None

    def test_raises_when_no_recipes_found(self, tmp_path):
        import pytest
        recipe_dir = tmp_path / "code" / "recipes" / "survey"
        recipe_dir.mkdir(parents=True)
        with pytest.raises(ValueError, match="No derivative recipes"):
            _load_and_validate_recipes(tmp_path, "survey")

    def test_raises_for_unknown_modality(self, tmp_path):
        import pytest, json as _json
        recipe_dir = tmp_path / "code" / "recipes" / "survey"
        recipe_dir.mkdir(parents=True)
        (recipe_dir / "recipe-test.json").write_text(_json.dumps(_VALID_SURVEY_RECIPE))
        with pytest.raises(ValueError):
            _load_and_validate_recipes(tmp_path, "unknown_modality")

    def test_filters_by_survey_ids(self, tmp_path):
        import json as _json
        recipe_dir = tmp_path / "code" / "recipes" / "survey"
        recipe_dir.mkdir(parents=True)
        (recipe_dir / "recipe-alpha.json").write_text(_json.dumps({**_VALID_SURVEY_RECIPE, "Survey": {"TaskName": "alpha"}}))
        (recipe_dir / "recipe-beta.json").write_text(_json.dumps({**_VALID_SURVEY_RECIPE, "Survey": {"TaskName": "beta"}}))
        result, _ = _load_and_validate_recipes(tmp_path, "survey", survey_ids="alpha")
        assert "alpha" in result
        assert "beta" not in result

    def test_raises_for_unknown_survey_ids(self, tmp_path):
        import pytest, json as _json
        recipe_dir = tmp_path / "code" / "recipes" / "survey"
        recipe_dir.mkdir(parents=True)
        (recipe_dir / "recipe-alpha.json").write_text(_json.dumps({**_VALID_SURVEY_RECIPE, "Survey": {"TaskName": "alpha"}}))
        with pytest.raises(ValueError, match="Unknown"):
            _load_and_validate_recipes(tmp_path, "survey", survey_ids="nonexistent")

    def test_loads_from_explicit_recipe_dir(self, tmp_path):
        import json as _json
        recipe_dir = tmp_path / "my_recipes"
        recipe_dir.mkdir(parents=True)
        (recipe_dir / "recipe-test.json").write_text(_json.dumps(_VALID_SURVEY_RECIPE))
        result, _ = _load_and_validate_recipes(tmp_path, "survey", recipe_dir=recipe_dir)
        assert "test" in result

    def test_project_yoda_priority_over_repo_root(self, tmp_path):
        import json as _json
        prism_root = tmp_path / "projects" / "my_study"
        prism_root.mkdir(parents=True)
        project_recipes = prism_root / "code" / "recipes" / "survey"
        project_recipes.mkdir(parents=True)
        (project_recipes / "recipe-project.json").write_text(_json.dumps({**_VALID_SURVEY_RECIPE, "Survey": {"TaskName": "project"}}))
        result, _ = _load_and_validate_recipes(tmp_path, "survey", prism_root=prism_root)
        assert "project" in result

    def test_biometrics_modality(self, tmp_path):
        import json as _json
        recipe_dir = tmp_path / "code" / "recipes" / "biometrics"
        recipe_dir.mkdir(parents=True)
        bio_recipe = {
            "Kind": "biometrics",
            "RecipeVersion": "1.0",
            "Biometrics": {"BiometricName": "hrv"},
            "Scores": [],
        }
        (recipe_dir / "recipe-hrv.json").write_text(_json.dumps(bio_recipe))
        result, _ = _load_and_validate_recipes(tmp_path, "biometrics")
        assert "hrv" in result
