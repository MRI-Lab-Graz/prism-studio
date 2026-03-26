"""Tests for multi-version survey support: validator ApplicableVersions / VariantScales
and recipe engine VersionedScores."""

from __future__ import annotations

import json
import sys
import os
from pathlib import Path

import pytest

# Make app/src importable
sys.path.insert(0, str(Path(__file__).parent.parent / "app" / "src"))


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _write(path: Path, content) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(content) if isinstance(content, dict) else content, encoding="utf-8")
    return path


def _tsv(path: Path, rows: list[dict]) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    if not rows:
        path.write_text("", encoding="utf-8")
        return path
    header = "\t".join(rows[0].keys())
    body = "\n".join("\t".join(str(r.get(k, "n/a")) for k in rows[0].keys()) for r in rows)
    path.write_text(f"{header}\n{body}\n", encoding="utf-8")
    return path


# ---------------------------------------------------------------------------
# Validator multi-version tests
# ---------------------------------------------------------------------------

class TestValidatorMultiVersion:
    """validate_data_content applies ApplicableVersions and VariantScales."""

    @pytest.fixture()
    def validator(self):
        from validator import DatasetValidator
        return DatasetValidator()

    def _build_project(self, tmp_path: Path, version_mapping: dict | None = None) -> tuple[Path, Path]:
        """Create a minimal multi-version project and return (root, library_path)."""
        root = tmp_path / "project"
        library = root / "code" / "library" / "survey"
        library.mkdir(parents=True)

        sidecar = {
            "Study": {
                "TaskName": "wb",
                "Versions": ["likert", "vas"],
            },
            "WB01": {
                "Description": {"en": "Item 1"},
                "DataType": "integer",
                "MinValue": 1,
                "MaxValue": 5,
                "ApplicableVersions": ["likert"],
                "VariantScales": [
                    {"VariantID": "likert", "MinValue": 1, "MaxValue": 5},
                    {"VariantID": "vas", "MinValue": 0, "MaxValue": 100},
                ],
            },
            "WB02": {
                "Description": {"en": "Item 2"},
                "DataType": "integer",
                "MinValue": 0,
                "MaxValue": 100,
                "ApplicableVersions": ["vas"],
                "VariantScales": [
                    {"VariantID": "vas", "MinValue": 0, "MaxValue": 100},
                ],
            },
        }
        _write(library / "task-wb_survey.json", sidecar)

        if version_mapping is not None:
            project_json = root / "project.json"
            _write(project_json, {"survey_version_mapping": version_mapping})

        return root, library

    def test_excluded_column_triggers_warning_when_version_resolved(
        self, validator, tmp_path, monkeypatch
    ):
        """WB01 (likert-only) in a VAS data file should emit a WARNING."""
        root, library = self._build_project(
            tmp_path,
            version_mapping={"wb": {"default_version": "vas"}},
        )
        data_dir = root / "sub-01" / "ses-01" / "survey"
        data_file = _tsv(
            data_dir / "sub-01_ses-01_task-wb_survey.tsv",
            [{"WB01": "50", "WB02": "75"}],
        )

        # Patch resolve function so we don't need a real project layout
        monkeypatch.setattr(
            "validator._resolve_survey_version",
            lambda root_dir, task_name, session=None, run=None: "vas",
            raising=False,
        )

        v = validator.__class__(library_path=str(library))
        issues = v.validate_data_content(str(data_file), "survey", str(root))
        warnings = [msg for level, msg in issues if level == "WARNING"]
        assert any("WB01" in msg and "ApplicableVersions" in msg for msg in warnings), (
            f"Expected ApplicableVersions warning for WB01. Got: {warnings}"
        )

    def test_variant_scale_overrides_range_check(
        self, validator, tmp_path, monkeypatch
    ):
        """WB02 (VAS 0-100) with value=80 should pass when VAS variant is resolved."""
        root, library = self._build_project(
            tmp_path,
            version_mapping={"wb": {"default_version": "vas"}},
        )
        data_dir = root / "sub-01" / "ses-01" / "survey"
        data_file = _tsv(
            data_dir / "sub-01_ses-01_task-wb_survey.tsv",
            [{"WB02": "80"}],
        )

        monkeypatch.setattr(
            "validator._resolve_survey_version",
            lambda root_dir, task_name, session=None, run=None: "vas",
            raising=False,
        )

        v = validator.__class__(library_path=str(library))
        issues = v.validate_data_content(str(data_file), "survey", str(root))
        errors = [msg for level, msg in issues if level == "ERROR"]
        assert not any("WB02" in msg and "range" in msg.lower() for msg in errors), (
            f"VAS value 80 should be valid but got range errors: {errors}"
        )

    def test_no_version_resolved_skips_exclusion_check(
        self, validator, tmp_path, monkeypatch
    ):
        """Without a resolved version, all columns should be validated without exclusion."""
        root, library = self._build_project(tmp_path)  # no version mapping

        monkeypatch.setattr(
            "validator._resolve_survey_version",
            lambda *a, **kw: None,
            raising=False,
        )

        data_dir = root / "sub-01" / "ses-01" / "survey"
        data_file = _tsv(
            data_dir / "sub-01_ses-01_task-wb_survey.tsv",
            [{"WB01": "3", "WB02": "50"}],
        )

        v = validator.__class__(library_path=str(library))
        issues = v.validate_data_content(str(data_file), "survey", str(root))
        warnings = [msg for level, msg in issues if "ApplicableVersions" in msg]
        assert not warnings, f"No ApplicableVersions warnings expected without resolved version: {warnings}"


# ---------------------------------------------------------------------------
# Recipe VersionedScores tests
# ---------------------------------------------------------------------------

class TestRecipeVersionedScores:
    """_apply_survey_derivative_recipe_to_rows selects VersionedScores by resolved_version."""

    @pytest.fixture()
    def apply_fn(self):
        # Try canonical first, fall back to app mirror
        try:
            from recipes_surveys import _apply_survey_derivative_recipe_to_rows
        except ImportError:
            sys.path.insert(0, str(Path(__file__).parent.parent / "src"))
            from recipes_surveys import _apply_survey_derivative_recipe_to_rows
        return _apply_survey_derivative_recipe_to_rows

    def _base_recipe(self, scores: list) -> dict:
        return {
            "RecipeVersion": "1.0",
            "Kind": "survey",
            "Survey": {"Name": "Demo", "TaskName": "wb"},
            "Scores": scores,
        }

    def test_falls_back_to_top_level_scores_when_no_version(self, apply_fn):
        recipe = self._base_recipe([
            {"Name": "total", "Method": "sum", "Items": ["WB01"], "Range": {"min": 0, "max": 5}},
        ])
        rows = [{"WB01": "3"}]
        header, out = apply_fn(recipe, rows, resolved_version=None)
        assert "total" in header
        assert out[0]["total"] == "3"

    def test_versioned_scores_selected_when_version_matches(self, apply_fn):
        recipe = self._base_recipe([
            {"Name": "total", "Method": "sum", "Items": ["WB01"], "Range": {"min": 0, "max": 5}},
        ])
        recipe["VersionedScores"] = {
            "vas": [
                {"Name": "vas_total", "Method": "mean", "Items": ["WB01"], "Range": {"min": 0, "max": 100}},
            ]
        }
        rows = [{"WB01": "50"}]
        header, out = apply_fn(recipe, rows, resolved_version="vas")
        assert "vas_total" in header, f"Expected vas_total, got {header}"
        assert "total" not in header, f"Unexpected top-level score in {header}"
        assert out[0]["vas_total"] == "50"

    def test_falls_back_to_top_level_when_version_not_in_versioned_scores(self, apply_fn):
        recipe = self._base_recipe([
            {"Name": "total", "Method": "sum", "Items": ["WB01"], "Range": {"min": 0, "max": 5}},
        ])
        recipe["VersionedScores"] = {
            "other-variant": [
                {"Name": "other_total", "Method": "sum", "Items": ["WB01"], "Range": {"min": 0, "max": 5}},
            ]
        }
        rows = [{"WB01": "3"}]
        header, out = apply_fn(recipe, rows, resolved_version="likert")
        assert "total" in header
        assert "other_total" not in header

    def test_versioned_scores_empty_list_produces_empty_output(self, apply_fn):
        recipe = self._base_recipe([
            {"Name": "total", "Method": "sum", "Items": ["WB01"], "Range": {"min": 0, "max": 5}},
        ])
        recipe["VersionedScores"] = {"vas": []}
        rows = [{"WB01": "50"}]
        header, out = apply_fn(recipe, rows, resolved_version="vas")
        # Empty VersionedScores → no score columns (just raw if include_raw)
        score_cols = [h for h in header if h not in ("WB01",)]
        assert not score_cols, f"Expected no score columns for empty VersionedScores, got {score_cols}"


# ---------------------------------------------------------------------------
# End-to-end recipe pipeline tests
# ---------------------------------------------------------------------------

class TestVersionedRecipeEndToEnd:
    """Full pipeline: resolved version selects VersionedScores → correct computed scores."""

    @pytest.fixture()
    def apply_fn(self):
        try:
            from recipes_surveys import _apply_survey_derivative_recipe_to_rows
        except ImportError:
            sys.path.insert(0, str(Path(__file__).parent.parent / "src"))
            from recipes_surveys import _apply_survey_derivative_recipe_to_rows
        return _apply_survey_derivative_recipe_to_rows

    def _make_recipe(self) -> dict:
        return {
            "RecipeVersion": "1.0",
            "Kind": "survey",
            "Survey": {"Name": "Wellbeing", "TaskName": "wb"},
            "Scores": [
                {
                    "Name": "wb_likert_total",
                    "Method": "sum",
                    "Items": ["WB01", "WB02"],
                    "Range": {"min": 2, "max": 10},
                },
            ],
            "VersionedScores": {
                "vas": [
                    {
                        "Name": "wb_vas_mean",
                        "Method": "mean",
                        "Items": ["WB01", "WB02"],
                        "Range": {"min": 0, "max": 100},
                    },
                ],
                "likert": [
                    {
                        "Name": "wb_likert_total",
                        "Method": "sum",
                        "Items": ["WB01", "WB02"],
                        "Range": {"min": 2, "max": 10},
                    },
                ],
            },
        }

    def test_vas_version_selects_vas_scores(self, apply_fn):
        """Resolving 'vas' version picks wb_vas_mean, not wb_likert_total."""
        recipe = self._make_recipe()
        header, _ = apply_fn(recipe, [{"WB01": "60", "WB02": "80"}], resolved_version="vas")
        assert "wb_vas_mean" in header, f"Expected vas score in {header}"
        assert "wb_likert_total" not in header, f"Unexpected likert score in {header}"

    def test_likert_version_selects_likert_scores(self, apply_fn):
        """Resolving 'likert' version picks wb_likert_total, not wb_vas_mean."""
        recipe = self._make_recipe()
        header, _ = apply_fn(recipe, [{"WB01": "3", "WB02": "4"}], resolved_version="likert")
        assert "wb_likert_total" in header, f"Expected likert score in {header}"
        assert "wb_vas_mean" not in header, f"Unexpected vas score in {header}"

    def test_no_version_falls_back_to_top_level(self, apply_fn):
        """Without a resolved version, top-level Scores are used."""
        recipe = self._make_recipe()
        header, _ = apply_fn(recipe, [{"WB01": "2", "WB02": "3"}], resolved_version=None)
        assert "wb_likert_total" in header
        assert "wb_vas_mean" not in header

    def test_unknown_version_falls_back_to_top_level(self, apply_fn):
        """A version not in VersionedScores keys falls back to top-level Scores."""
        recipe = self._make_recipe()
        header, _ = apply_fn(recipe, [{"WB01": "3", "WB02": "5"}], resolved_version="unknown-form")
        assert "wb_likert_total" in header
        assert "wb_vas_mean" not in header

    def test_two_versions_are_independent(self, apply_fn):
        """VAS and Likert produce non-overlapping score sets."""
        recipe = self._make_recipe()
        vas_header, _ = apply_fn(recipe, [{"WB01": "75", "WB02": "25"}], resolved_version="vas")
        likert_header, _ = apply_fn(recipe, [{"WB01": "3", "WB02": "5"}], resolved_version="likert")
        assert set(vas_header) != set(likert_header)
        assert "wb_vas_mean" in vas_header and "wb_vas_mean" not in likert_header
        assert "wb_likert_total" in likert_header and "wb_likert_total" not in vas_header
