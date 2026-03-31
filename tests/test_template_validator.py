"""Tests for TemplateValidator cross-field consistency checks.

Covers:
- 6a: VariantDefinitions.VariantID ⊆ Study.Versions
- 6b: VariantScales.MinValue < MaxValue
- 6c: VariantDefinitions.ItemCount matches actual items per version
- 6d: Unused declared version warning
- VariantScales.VariantID ⊆ Study.Versions
- ApplicableVersions ⊆ Study.Versions
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "app" / "src"))

from template_validator import TemplateValidator, TemplateValidationError

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_validator(tmp_path: Path) -> TemplateValidator:
    (tmp_path / "lib").mkdir(exist_ok=True)
    return TemplateValidator(str(tmp_path / "lib"))


def _write_template(tmp_path: Path, name: str, data: dict) -> Path:
    p = tmp_path / "lib" / name
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(data), encoding="utf-8")
    return p


def _base_template(**kwargs) -> dict:
    """Minimal valid template with Study + one item."""
    tpl = {
        "Study": {
            "TaskName": "test",
            "OriginalName": "Test Scale",
            "Authors": ["Smith, J."],
            "Year": 2020,
            "Citation": "Smith 2020",
            "Versions": ["likert", "vas"],
        },
        "Q01": {
            "Description": {"en": "Item 1"},
            "ApplicableVersions": ["likert"],
        },
        "Q02": {
            "Description": {"en": "Item 2"},
            "ApplicableVersions": ["vas"],
        },
    }
    tpl.update(kwargs)
    return tpl


def _get_warnings(errors: list, keyword: str) -> list[TemplateValidationError]:
    return [e for e in errors if keyword in e.message and e.severity == "warning"]


# ---------------------------------------------------------------------------
# 6a: VariantDefinitions.VariantID ⊆ Study.Versions
# ---------------------------------------------------------------------------


class TestVariantDefinitionsVersionSubset:
    def test_variant_id_not_in_versions_warns(self, tmp_path):
        tpl = _base_template()
        tpl["Study"]["VariantDefinitions"] = [
            {
                "VariantID": "orphan",
                "ItemCount": 0,
                "ScaleType": "likert",
                "Description": {"en": "ghost"},
            },
        ]
        v = _make_validator(tmp_path)
        errors = v.validate_file(_write_template(tmp_path, "survey-test.json", tpl))
        assert any(
            "orphan" in e.message and "VariantDefinitions" in e.message for e in errors
        ), (
            f"Expected orphan VariantDefinitions warning, got: {[e.message for e in errors]}"
        )

    def test_variant_ids_all_in_versions_clean(self, tmp_path):
        tpl = _base_template()
        tpl["Study"]["VariantDefinitions"] = [
            {
                "VariantID": "likert",
                "ItemCount": 1,
                "ScaleType": "likert",
                "Description": {"en": "Likert"},
            },
            {
                "VariantID": "vas",
                "ItemCount": 1,
                "ScaleType": "vas",
                "Description": {"en": "VAS"},
            },
        ]
        v = _make_validator(tmp_path)
        errors = v.validate_file(_write_template(tmp_path, "survey-test.json", tpl))
        variant_def_warnings = [
            e
            for e in errors
            if "VariantDefinitions" in e.message
            and "not in Study.Versions" in e.message
        ]
        assert not variant_def_warnings, f"Unexpected warnings: {variant_def_warnings}"


# ---------------------------------------------------------------------------
# 6b: VariantScales.MinValue < MaxValue
# ---------------------------------------------------------------------------


class TestVariantScalesMinMaxConsistency:
    def test_minvalue_equals_maxvalue_warns(self, tmp_path):
        tpl = _base_template()
        tpl["Q01"]["VariantScales"] = [
            {"VariantID": "likert", "MinValue": 5, "MaxValue": 5},
        ]
        v = _make_validator(tmp_path)
        errors = v.validate_file(_write_template(tmp_path, "survey-test.json", tpl))
        assert any(
            "MinValue" in e.message and "MaxValue" in e.message for e in errors
        ), f"Expected MinValue/MaxValue warning: {[e.message for e in errors]}"

    def test_minvalue_greater_than_maxvalue_warns(self, tmp_path):
        tpl = _base_template()
        tpl["Q01"]["VariantScales"] = [
            {"VariantID": "likert", "MinValue": 10, "MaxValue": 1},
        ]
        v = _make_validator(tmp_path)
        errors = v.validate_file(_write_template(tmp_path, "survey-test.json", tpl))
        assert any("MinValue" in e.message and "MaxValue" in e.message for e in errors)

    def test_valid_range_no_warning(self, tmp_path):
        tpl = _base_template()
        tpl["Q01"]["VariantScales"] = [
            {"VariantID": "likert", "MinValue": 1, "MaxValue": 5},
        ]
        v = _make_validator(tmp_path)
        errors = v.validate_file(_write_template(tmp_path, "survey-test.json", tpl))
        range_warnings = [
            e for e in errors if "MinValue" in e.message and "MaxValue" in e.message
        ]
        assert not range_warnings, f"Unexpected range warnings: {range_warnings}"


# ---------------------------------------------------------------------------
# 6c: VariantDefinitions.ItemCount matches actual items per version
# ---------------------------------------------------------------------------


class TestVariantDefinitionsItemCount:
    def test_itemcount_mismatch_warns(self, tmp_path):
        tpl = _base_template()
        # Declare 5 items but only 1 item has ApplicableVersions=["likert"]
        tpl["Study"]["VariantDefinitions"] = [
            {
                "VariantID": "likert",
                "ItemCount": 5,
                "ScaleType": "likert",
                "Description": {"en": "Likert"},
            },
        ]
        v = _make_validator(tmp_path)
        errors = v.validate_file(_write_template(tmp_path, "survey-test.json", tpl))
        mismatch = [
            e for e in errors if "ItemCount" in e.message and "likert" in e.message
        ]
        assert mismatch, (
            f"Expected ItemCount mismatch warning, got: {[e.message for e in errors]}"
        )

    def test_itemcount_matches_no_warning(self, tmp_path):
        tpl = _base_template()
        # 1 item with ApplicableVersions=["likert"], declare ItemCount=1
        tpl["Study"]["VariantDefinitions"] = [
            {
                "VariantID": "likert",
                "ItemCount": 1,
                "ScaleType": "likert",
                "Description": {"en": "Likert"},
            },
        ]
        v = _make_validator(tmp_path)
        errors = v.validate_file(_write_template(tmp_path, "survey-test.json", tpl))
        mismatch = [
            e for e in errors if "ItemCount" in e.message and "likert" in e.message
        ]
        assert not mismatch, f"Unexpected ItemCount warnings: {mismatch}"

    def test_itemcount_null_ignored(self, tmp_path):
        """ItemCount: null (not specified) should not trigger the check."""
        tpl = _base_template()
        tpl["Study"]["VariantDefinitions"] = [
            {"VariantID": "likert", "ItemCount": None, "ScaleType": "likert"},
        ]
        v = _make_validator(tmp_path)
        errors = v.validate_file(_write_template(tmp_path, "survey-test.json", tpl))
        mismatch = [e for e in errors if "ItemCount" in e.message]
        assert not mismatch, f"Unexpected ItemCount warnings for null: {mismatch}"


# ---------------------------------------------------------------------------
# 6d: Unused-version warning
# ---------------------------------------------------------------------------


class TestUnusedVersionWarning:
    def test_warns_when_version_declared_but_no_items_reference_it(self, tmp_path):
        tpl = {
            "Study": {
                "TaskName": "test",
                "OriginalName": "Test",
                "Authors": ["A"],
                "Year": 2020,
                "Citation": "A 2020",
                "Versions": ["likert", "unused-version"],
            },
            "Q01": {
                "Description": {"en": "Item 1"},
                "ApplicableVersions": ["likert"],
            },
        }
        v = _make_validator(tmp_path)
        errors = v.validate_file(_write_template(tmp_path, "survey-test.json", tpl))
        unused = [
            e
            for e in errors
            if "unused-version" in e.message and "ApplicableVersions" in e.message
        ]
        assert unused, (
            f"Expected unused-version warning, got: {[e.message for e in errors]}"
        )

    def test_no_warning_when_all_versions_used(self, tmp_path):
        tpl = _base_template()  # Q01→likert, Q02→vas; both in Versions
        v = _make_validator(tmp_path)
        errors = v.validate_file(_write_template(tmp_path, "survey-test.json", tpl))
        unused = [
            e
            for e in errors
            if "ApplicableVersions" in e.message
            and "is declared in Study.Versions" in e.message
        ]
        assert not unused, f"Unexpected unused-version warnings: {unused}"

    def test_no_warning_without_versions(self, tmp_path):
        """Templates without Study.Versions don't trigger unused-version check."""
        tpl = {
            "Study": {
                "TaskName": "simple",
                "OriginalName": "Simple",
                "Authors": ["B"],
                "Year": 2021,
                "Citation": "B 2021",
            },
            "Q01": {"Description": {"en": "Item 1"}},
        }
        v = _make_validator(tmp_path)
        errors = v.validate_file(_write_template(tmp_path, "survey-simple.json", tpl))
        unused = [e for e in errors if "is declared in Study.Versions" in e.message]
        assert not unused, f"Unexpected warnings: {unused}"


# ---------------------------------------------------------------------------
# VariantScales.VariantID ⊆ Study.Versions cross-field check
# ---------------------------------------------------------------------------


class TestVariantScalesVariantIDSubset:
    def test_orphan_variant_scale_warns(self, tmp_path):
        tpl = _base_template()
        tpl["Q01"]["VariantScales"] = [
            {"VariantID": "nonexistent", "MinValue": 1, "MaxValue": 5},
        ]
        v = _make_validator(tmp_path)
        errors = v.validate_file(_write_template(tmp_path, "survey-test.json", tpl))
        assert any(
            "nonexistent" in e.message and "VariantScales" in e.message for e in errors
        ), f"Expected orphan VariantScales warning: {[e.message for e in errors]}"

    def test_valid_variant_scale_no_warning(self, tmp_path):
        tpl = _base_template()
        tpl["Q01"]["VariantScales"] = [
            {"VariantID": "likert", "MinValue": 1, "MaxValue": 5},
            {"VariantID": "vas", "MinValue": 0, "MaxValue": 100},
        ]
        v = _make_validator(tmp_path)
        errors = v.validate_file(_write_template(tmp_path, "survey-test.json", tpl))
        orphan = [
            e
            for e in errors
            if "VariantScales" in e.message and "not in Study.Versions" in e.message
        ]
        assert not orphan, f"Unexpected orphan warnings: {orphan}"


# ---------------------------------------------------------------------------
# ApplicableVersions ⊆ Study.Versions cross-field check
# ---------------------------------------------------------------------------


class TestApplicableVersionsSubset:
    def test_applicable_version_not_in_study_versions_warns(self, tmp_path):
        tpl = _base_template()
        tpl["Q01"]["ApplicableVersions"] = ["likert", "ghost-version"]
        v = _make_validator(tmp_path)
        errors = v.validate_file(_write_template(tmp_path, "survey-test.json", tpl))
        assert any(
            "ghost-version" in e.message and "ApplicableVersions" in e.message
            for e in errors
        )

    def test_applicable_version_subset_no_warning(self, tmp_path):
        tpl = _base_template()  # Q01→["likert"], Q02→["vas"], both in Versions
        v = _make_validator(tmp_path)
        errors = v.validate_file(_write_template(tmp_path, "survey-test.json", tpl))
        subset_warnings = [
            e
            for e in errors
            if "ApplicableVersions" in e.message
            and "not in Study.Versions" in e.message
        ]
        assert not subset_warnings, f"Unexpected warnings: {subset_warnings}"


class TestImplicitNumericLevelsBounds:
    def test_contiguous_numeric_levels_without_explicit_bounds_warns(self, tmp_path):
        tpl = _base_template()
        tpl["Q01"]["Levels"] = {
            "0": {"en": "Never"},
            "1": {"en": "Sometimes"},
            "2": {"en": "Often"},
        }

        v = _make_validator(tmp_path)
        errors = v.validate_file(_write_template(tmp_path, "survey-test.json", tpl))

        warnings = [
            e
            for e in errors
            if "Contiguous numeric Levels imply a bounded scale (0..2)" in e.message
        ]
        assert warnings, f"Expected implicit range warning, got: {[e.message for e in errors]}"

    def test_variant_scales_with_contiguous_numeric_levels_warn(self, tmp_path):
        tpl = _base_template()
        tpl["Q01"]["VariantScales"] = [
            {
                "VariantID": "likert",
                "Levels": {
                    "1": {"en": "low"},
                    "2": {"en": "mid"},
                    "3": {"en": "high"},
                },
            }
        ]

        v = _make_validator(tmp_path)
        errors = v.validate_file(_write_template(tmp_path, "survey-test.json", tpl))

        warnings = [
            e
            for e in errors
            if "VariantScales entry has contiguous numeric Levels implying a bounded scale (1..3)"
            in e.message
        ]
        assert warnings, (
            f"Expected implicit VariantScales warning, got: {[e.message for e in errors]}"
        )
