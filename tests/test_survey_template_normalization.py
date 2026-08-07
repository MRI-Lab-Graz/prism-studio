"""Unit tests for src.survey_template_normalization.

This module was extracted from app/src/web/blueprints/
tools_template_editor_blueprint.py so the CLI's `survey validate` could
apply the exact same pre-validation normalization the Studio GUI's
Template Editor already did (docs/_archive/GUI_BACKEND_AUDIT_2026-08-07.md,
P1-4). These tests exercise the functions directly; the blueprint's own
existing tests (tests/test_template_editor_single_version_variantid.py)
continue to cover them indirectly via the re-exported names.
"""

from src.survey_template_normalization import (
    autofill_single_version_variant_ids,
    is_blank_localized_value,
    is_empty_variant_definition_placeholder,
    normalize_survey_template_for_validation,
    prune_optional_variant_placeholders,
)


class TestAutofillSingleVersionVariantIds:
    def test_fills_from_single_versions_entry(self):
        template = {
            "Study": {
                "Versions": ["short"],
                "VariantDefinitions": [{"VariantID": ""}],
            },
            "Q01": {"VariantScales": [{"VariantID": ""}]},
        }
        out = autofill_single_version_variant_ids(template)
        assert out["Study"]["VariantDefinitions"][0]["VariantID"] == "short"
        assert out["Q01"]["VariantScales"][0]["VariantID"] == "short"

    def test_does_not_fill_with_multiple_versions(self):
        template = {
            "Study": {
                "Versions": ["short", "long"],
                "VariantDefinitions": [{"VariantID": ""}],
            }
        }
        out = autofill_single_version_variant_ids(template)
        assert out["Study"]["VariantDefinitions"][0]["VariantID"] == ""

    def test_falls_back_to_singular_version_field(self):
        template = {
            "Study": {"Version": "1.0", "VariantDefinitions": [{"VariantID": ""}]}
        }
        out = autofill_single_version_variant_ids(template)
        assert out["Study"]["VariantDefinitions"][0]["VariantID"] == "1.0"

    def test_skips_metadata_sections_when_scanning_for_variant_scales(self):
        template = {
            "Study": {"Versions": ["short"]},
            "Technical": {"VariantScales": [{"VariantID": ""}]},
        }
        out = autofill_single_version_variant_ids(template)
        # Technical is a metadata section, not an item — must be untouched.
        assert out["Technical"]["VariantScales"][0]["VariantID"] == ""

    def test_non_dict_input_returned_unchanged(self):
        assert autofill_single_version_variant_ids(None) is None


class TestIsBlankLocalizedValue:
    def test_none_is_blank(self):
        assert is_blank_localized_value(None) is True

    def test_empty_string_is_blank(self):
        assert is_blank_localized_value("   ") is True

    def test_nonempty_string_is_not_blank(self):
        assert is_blank_localized_value("hello") is False

    def test_dict_with_all_blank_values_is_blank(self):
        assert is_blank_localized_value({"en": "", "de": "  "}) is True

    def test_dict_with_one_nonblank_value_is_not_blank(self):
        assert is_blank_localized_value({"en": "", "de": "hallo"}) is False

    def test_list_recurses(self):
        assert is_blank_localized_value(["", None, "  "]) is True
        assert is_blank_localized_value(["", "x"]) is False


class TestIsEmptyVariantDefinitionPlaceholder:
    def test_fully_empty_entry_is_placeholder(self):
        assert is_empty_variant_definition_placeholder({}) is True

    def test_entry_with_variant_id_is_not_placeholder(self):
        assert (
            is_empty_variant_definition_placeholder({"VariantID": "short"}) is False
        )

    def test_entry_with_item_count_is_not_placeholder(self):
        assert is_empty_variant_definition_placeholder({"ItemCount": 5}) is False

    def test_non_dict_is_not_placeholder(self):
        assert is_empty_variant_definition_placeholder("not-a-dict") is False


class TestPruneOptionalVariantPlaceholders:
    def test_removes_empty_placeholder_when_single_version(self):
        template = {
            "Study": {
                "Versions": ["short"],
                "VariantDefinitions": [{}, {"VariantID": "short"}],
            }
        }
        out = prune_optional_variant_placeholders(template)
        defs = out["Study"]["VariantDefinitions"]
        assert len(defs) == 1
        assert defs[0]["VariantID"] == "short"

    def test_keeps_placeholder_when_multiple_versions(self):
        template = {
            "Study": {
                "Versions": ["short", "long"],
                "VariantDefinitions": [{}, {"VariantID": "short"}],
            }
        }
        out = prune_optional_variant_placeholders(template)
        assert len(out["Study"]["VariantDefinitions"]) == 2

    def test_removes_key_entirely_when_all_pruned(self):
        template = {"Study": {"Versions": ["short"], "VariantDefinitions": [{}]}}
        out = prune_optional_variant_placeholders(template)
        assert "VariantDefinitions" not in out["Study"]


class TestNormalizeSurveyTemplateForValidation:
    def test_autofill_runs_before_prune_so_filled_entries_survive(self):
        # Order matters: autofill_single_version_variant_ids runs first and
        # fills every empty VariantID (including bare placeholder rows), so
        # by the time prune_optional_variant_placeholders runs there's
        # nothing left that still looks like an empty placeholder to drop.
        template = {
            "Study": {
                "Versions": ["short"],
                "VariantDefinitions": [{}, {"VariantID": ""}],
            },
            "Q01": {"VariantScales": [{"VariantID": ""}]},
        }
        out = normalize_survey_template_for_validation(template)
        defs = out["Study"]["VariantDefinitions"]
        assert len(defs) == 2
        assert all(d["VariantID"] == "short" for d in defs)
        assert out["Q01"]["VariantScales"][0]["VariantID"] == "short"

    def test_prune_removes_placeholder_when_no_version_to_autofill_from(self):
        # With no Versions/Version at all, autofill has nothing to fill in,
        # so the empty placeholder is still empty when prune runs.
        template = {"Study": {"VariantDefinitions": [{}]}}
        out = normalize_survey_template_for_validation(template)
        assert "VariantDefinitions" not in out["Study"]

    def test_does_not_crash_on_minimal_template(self):
        out = normalize_survey_template_for_validation({"Study": {}})
        assert isinstance(out, dict)
