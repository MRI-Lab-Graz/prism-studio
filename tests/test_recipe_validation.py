"""Tests for src/recipe_validation.py — derivative recipe validation."""

import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from src.recipe_validation import (
    validate_recipe,
    _is_nonempty_str,
    _as_list_of_str,
    _unknown_items,
)


def _valid_survey_recipe(**overrides):
    recipe = {
        "Kind": "survey",
        "RecipeVersion": "1.0",
        "Survey": {"TaskName": "demo"},
        "Scores": [
            {"Name": "total", "Method": "sum", "Items": ["q1", "q2"]},
        ],
    }
    recipe.update(overrides)
    return recipe


# ---------------------------------------------------------------------------
# Small helpers
# ---------------------------------------------------------------------------

class TestIsNonemptyStr:
    def test_nonempty_string_true(self):
        assert _is_nonempty_str("hello") is True

    def test_empty_string_false(self):
        assert _is_nonempty_str("") is False

    def test_whitespace_only_false(self):
        assert _is_nonempty_str("   ") is False

    def test_non_string_false(self):
        assert _is_nonempty_str(123) is False
        assert _is_nonempty_str(None) is False


class TestAsListOfStr:
    def test_filters_non_strings_and_blanks(self):
        assert _as_list_of_str(["a", "", "  ", 1, "b"]) == ["a", "b"]

    def test_not_a_list_returns_empty(self):
        assert _as_list_of_str("not-a-list") == []
        assert _as_list_of_str(None) == []

    def test_strips_whitespace(self):
        assert _as_list_of_str([" a ", "b"]) == ["a", "b"]


class TestUnknownItems:
    def test_none_known_items_returns_empty(self):
        assert _unknown_items(["a", "b"], None) == []

    def test_case_insensitive_match(self):
        assert _unknown_items(["Q1"], {"q1"}) == []

    def test_reports_unknown_sorted(self):
        assert _unknown_items(["z", "a", "q1"], {"q1"}) == ["a", "z"]


# ---------------------------------------------------------------------------
# validate_recipe — top-level shape
# ---------------------------------------------------------------------------

class TestValidateRecipeTopLevel:
    def test_valid_survey_recipe_has_no_errors(self):
        assert validate_recipe(_valid_survey_recipe()) == []

    def test_non_dict_recipe(self):
        errors = validate_recipe("not-a-dict")
        assert len(errors) == 1
        assert "must be a JSON object" in errors[0]

    def test_recipe_id_prefixes_errors(self):
        errors = validate_recipe({}, recipe_id="my-recipe")
        assert all(e.startswith("recipe 'my-recipe': ") for e in errors)

    def test_invalid_kind(self):
        recipe = _valid_survey_recipe(Kind="nonsense")
        errors = validate_recipe(recipe)
        assert any("Kind must be" in e for e in errors)

    def test_missing_recipe_version(self):
        recipe = _valid_survey_recipe()
        del recipe["RecipeVersion"]
        errors = validate_recipe(recipe)
        assert any("RecipeVersion" in e for e in errors)

    def test_survey_missing_survey_block(self):
        recipe = _valid_survey_recipe()
        del recipe["Survey"]
        errors = validate_recipe(recipe)
        assert any("Survey must be an object" in e for e in errors)

    def test_survey_missing_task_name(self):
        recipe = _valid_survey_recipe(Survey={})
        errors = validate_recipe(recipe)
        assert any("Survey.TaskName" in e for e in errors)

    def test_biometrics_missing_biometrics_block(self):
        recipe = {
            "Kind": "biometrics",
            "RecipeVersion": "1.0",
            "Scores": [{"Name": "x", "Method": "sum", "Items": ["a"]}],
        }
        errors = validate_recipe(recipe)
        assert any("Biometrics must be an object" in e for e in errors)

    def test_biometrics_missing_biometric_name(self):
        recipe = {
            "Kind": "biometrics",
            "RecipeVersion": "1.0",
            "Biometrics": {},
            "Scores": [{"Name": "x", "Method": "sum", "Items": ["a"]}],
        }
        errors = validate_recipe(recipe)
        assert any("Biometrics.BiometricName" in e for e in errors)

    def test_valid_biometrics_recipe_has_no_errors(self):
        recipe = {
            "Kind": "biometrics",
            "RecipeVersion": "1.0",
            "Biometrics": {"BiometricName": "hr"},
            "Scores": [{"Name": "x", "Method": "sum", "Items": ["a"]}],
        }
        assert validate_recipe(recipe) == []

    def test_transforms_not_an_object(self):
        recipe = _valid_survey_recipe(Transforms=["nope"])
        errors = validate_recipe(recipe)
        assert any("Transforms must be an object" in e for e in errors)

    def test_missing_scores_and_versioned_scores(self):
        recipe = _valid_survey_recipe()
        del recipe["Scores"]
        errors = validate_recipe(recipe)
        assert any("Scores is missing" in e for e in errors)


# ---------------------------------------------------------------------------
# Transforms.Invert
# ---------------------------------------------------------------------------

class TestTransformsInvert:
    def _recipe_with_invert(self, invert):
        return _valid_survey_recipe(Transforms={"Invert": invert})

    def test_invert_not_an_object(self):
        errors = validate_recipe(self._recipe_with_invert(["nope"]))
        assert any("Transforms.Invert must be an object" in e for e in errors)

    def test_invert_missing_items(self):
        errors = validate_recipe(
            self._recipe_with_invert({"Scale": {"min": 1, "max": 5}})
        )
        assert any("Transforms.Invert.Items must be a non-empty list" in e for e in errors)

    def test_invert_unknown_items(self):
        recipe = self._recipe_with_invert(
            {"Items": ["q1", "bogus"], "Scale": {"min": 1, "max": 5}}
        )
        errors = validate_recipe(recipe, known_items={"q1", "q2"})
        assert any("Transforms.Invert.Items references item(s)" in e for e in errors)
        assert any("bogus" in e for e in errors)

    def test_invert_missing_scale(self):
        errors = validate_recipe(self._recipe_with_invert({"Items": ["q1"]}))
        assert any("Transforms.Invert.Scale must be an object" in e for e in errors)

    def test_invert_scale_missing_min_max(self):
        errors = validate_recipe(
            self._recipe_with_invert({"Items": ["q1"], "Scale": {"min": 1}})
        )
        assert any("Transforms.Invert.Scale must include min and max" in e for e in errors)

    def test_invert_valid(self):
        recipe = self._recipe_with_invert(
            {"Items": ["q1"], "Scale": {"min": 1, "max": 5}}
        )
        errors = validate_recipe(recipe, known_items={"q1", "q2"})
        assert errors == []

    def test_invert_item_scales_not_object(self):
        recipe = self._recipe_with_invert(
            {
                "Items": ["q1"],
                "Scale": {"min": 1, "max": 5},
                "ItemScales": ["nope"],
            }
        )
        errors = validate_recipe(recipe)
        assert any("Transforms.Invert.ItemScales must be an object" in e for e in errors)

    def test_invert_item_scales_missing_min_max(self):
        recipe = self._recipe_with_invert(
            {
                "Items": ["q1"],
                "Scale": {"min": 1, "max": 5},
                "ItemScales": {"q1": {"min": 1}},
            }
        )
        errors = validate_recipe(recipe)
        assert any("ItemScales.q1 must have min and max" in e for e in errors)

    def test_invert_item_scales_unknown_item(self):
        recipe = self._recipe_with_invert(
            {
                "Items": ["q1"],
                "Scale": {"min": 1, "max": 5},
                "ItemScales": {"bogus": {"min": 1, "max": 5}},
            }
        )
        errors = validate_recipe(recipe, known_items={"q1"})
        assert any("Transforms.Invert.ItemScales references item(s)" in e for e in errors)

    def test_invert_item_scales_valid(self):
        recipe = self._recipe_with_invert(
            {
                "Items": ["q1"],
                "Scale": {"min": 1, "max": 5},
                "ItemScales": {"q1": {"min": 1, "max": 5}},
            }
        )
        errors = validate_recipe(recipe, known_items={"q1", "q2"})
        assert errors == []


# ---------------------------------------------------------------------------
# Transforms.Derived
# ---------------------------------------------------------------------------

class TestTransformsDerived:
    def _recipe_with_derived(self, derived):
        return _valid_survey_recipe(Transforms={"Derived": derived})

    def test_derived_not_a_list(self):
        errors = validate_recipe(self._recipe_with_derived({"nope": 1}))
        assert any("Transforms.Derived must be a list" in e for e in errors)

    def test_derived_entry_not_an_object(self):
        errors = validate_recipe(self._recipe_with_derived(["nope"]))
        assert any("Transforms.Derived[0] must be an object" in e for e in errors)

    def test_derived_missing_name(self):
        errors = validate_recipe(
            self._recipe_with_derived([{"Method": "sum", "Items": ["q1"]}])
        )
        assert any("Transforms.Derived[0].Name must be" in e for e in errors)

    def test_derived_duplicate_name(self):
        derived = [
            {"Name": "d1", "Method": "sum", "Items": ["q1"]},
            {"Name": "d1", "Method": "sum", "Items": ["q2"]},
        ]
        errors = validate_recipe(self._recipe_with_derived(derived))
        assert any("duplicate derived Name 'd1'" in e for e in errors)

    def test_derived_invalid_method(self):
        errors = validate_recipe(
            self._recipe_with_derived([{"Name": "d1", "Method": "bogus", "Items": ["q1"]}])
        )
        assert any("Transforms.Derived[0].Method must be one of" in e for e in errors)

    def test_derived_unknown_items(self):
        derived = [{"Name": "d1", "Method": "sum", "Items": ["bogus"]}]
        errors = validate_recipe(self._recipe_with_derived(derived), known_items={"q1"})
        assert any("Transforms.Derived[0].Items references item(s)" in e for e in errors)

    def test_derived_map_missing_source_and_items(self):
        derived = [{"Name": "d1", "Method": "map", "Mapping": {"a": 1}}]
        errors = validate_recipe(self._recipe_with_derived(derived))
        assert any("no non-empty Source and no Items" in e for e in errors)

    def test_derived_map_unknown_source(self):
        derived = [
            {
                "Name": "d1",
                "Method": "map",
                "Source": "bogus",
                "Mapping": {"a": 1},
            }
        ]
        errors = validate_recipe(self._recipe_with_derived(derived), known_items={"q1"})
        assert any("Source 'bogus' is not an item" in e for e in errors)

    def test_derived_map_missing_mapping(self):
        derived = [{"Name": "d1", "Method": "map", "Source": "q1"}]
        errors = validate_recipe(self._recipe_with_derived(derived), known_items={"q1"})
        assert any("no non-empty Mapping object" in e for e in errors)

    def test_derived_map_valid(self):
        derived = [
            {
                "Name": "d1",
                "Method": "map",
                "Source": "q1",
                "Mapping": {"1": "a"},
            }
        ]
        errors = validate_recipe(
            self._recipe_with_derived(derived), known_items={"q1", "q2"}
        )
        assert errors == []

    def test_derived_formula_missing_formula(self):
        derived = [{"Name": "d1", "Method": "formula", "Items": ["q1"]}]
        errors = validate_recipe(self._recipe_with_derived(derived), known_items={"q1"})
        assert any("no non-empty Formula" in e for e in errors)

    def test_derived_formula_missing_items(self):
        derived = [{"Name": "d1", "Method": "formula", "Formula": "{q1}+{q2}"}]
        errors = validate_recipe(self._recipe_with_derived(derived))
        assert any("Transforms.Derived[0].Items must be a non-empty list" in e for e in errors)

    def test_derived_formula_missing_placeholder_ref(self):
        derived = [
            {
                "Name": "d1",
                "Method": "formula",
                "Formula": "{q1}+{q3}",
                "Items": ["q1", "q2"],
            }
        ]
        errors = validate_recipe(
            self._recipe_with_derived(derived), known_items={"q1", "q2", "q3"}
        )
        assert any("Formula references ['q3']" in e for e in errors)

    def test_derived_formula_valid(self):
        derived = [
            {
                "Name": "d1",
                "Method": "formula",
                "Formula": "{q1}+{q2}",
                "Items": ["q1", "q2"],
            }
        ]
        errors = validate_recipe(
            self._recipe_with_derived(derived), known_items={"q1", "q2"}
        )
        assert errors == []

    def test_derived_default_method_missing_items(self):
        errors = validate_recipe(self._recipe_with_derived([{"Name": "d1"}]))
        assert any("Transforms.Derived[0].Items must be a non-empty list" in e for e in errors)

    def test_derived_later_entry_can_reference_earlier_derived_name(self):
        derived = [
            {"Name": "d1", "Method": "sum", "Items": ["q1"]},
            {"Name": "d2", "Method": "sum", "Items": ["d1"]},
        ]
        errors = validate_recipe(
            self._recipe_with_derived(derived), known_items={"q1", "q2"}
        )
        assert errors == []


# ---------------------------------------------------------------------------
# Scores / VersionedScores
# ---------------------------------------------------------------------------

class TestScoresValidation:
    def test_scores_not_a_list(self):
        recipe = _valid_survey_recipe(Scores={"nope": 1})
        errors = validate_recipe(recipe)
        assert any("Scores must be a list" in e for e in errors)

    def test_score_entry_not_an_object(self):
        recipe = _valid_survey_recipe(Scores=["nope"])
        errors = validate_recipe(recipe)
        assert any("Scores[0] must be an object" in e for e in errors)

    def test_score_missing_name(self):
        recipe = _valid_survey_recipe(Scores=[{"Method": "sum", "Items": ["q1"]}])
        errors = validate_recipe(recipe)
        assert any("Scores[0].Name must be a non-empty string" in e for e in errors)

    def test_score_duplicate_name(self):
        recipe = _valid_survey_recipe(
            Scores=[
                {"Name": "total", "Method": "sum", "Items": ["q1"]},
                {"Name": "total", "Method": "sum", "Items": ["q2"]},
            ]
        )
        errors = validate_recipe(recipe)
        assert any("duplicate score Name 'total'" in e for e in errors)

    def test_score_invalid_method(self):
        recipe = _valid_survey_recipe(
            Scores=[{"Name": "total", "Method": "bogus", "Items": ["q1"]}]
        )
        errors = validate_recipe(recipe)
        assert any("Scores[0].Method must be one of" in e for e in errors)

    def test_score_map_missing_source(self):
        recipe = _valid_survey_recipe(
            Scores=[{"Name": "total", "Method": "map", "Mapping": {"1": "a"}}]
        )
        errors = validate_recipe(recipe)
        assert any("no non-empty Source" in e for e in errors)

    def test_score_map_unknown_source(self):
        recipe = _valid_survey_recipe(
            Scores=[
                {
                    "Name": "total",
                    "Method": "map",
                    "Source": "bogus",
                    "Mapping": {"1": "a"},
                }
            ]
        )
        errors = validate_recipe(recipe, known_items={"q1"})
        assert any("is not an item" in e for e in errors)

    def test_score_map_missing_mapping(self):
        recipe = _valid_survey_recipe(
            Scores=[{"Name": "total", "Method": "map", "Source": "q1"}]
        )
        errors = validate_recipe(recipe, known_items={"q1"})
        assert any("no non-empty Mapping object" in e for e in errors)

    def test_score_non_map_missing_items(self):
        recipe = _valid_survey_recipe(Scores=[{"Name": "total", "Method": "sum"}])
        errors = validate_recipe(recipe)
        assert any("Scores[0].Items must be a non-empty list" in e for e in errors)

    def test_score_unknown_items(self):
        recipe = _valid_survey_recipe(
            Scores=[{"Name": "total", "Method": "sum", "Items": ["bogus"]}]
        )
        errors = validate_recipe(recipe, known_items={"q1"})
        assert any("Items references item(s) not found" in e for e in errors)

    def test_score_invalid_missing_field(self):
        recipe = _valid_survey_recipe(
            Scores=[
                {
                    "Name": "total",
                    "Method": "sum",
                    "Items": ["q1"],
                    "Missing": "bogus",
                }
            ]
        )
        errors = validate_recipe(recipe, known_items={"q1"})
        assert any("Missing must be one of" in e for e in errors)

    def test_score_min_valid_not_int(self):
        recipe = _valid_survey_recipe(
            Scores=[
                {
                    "Name": "total",
                    "Method": "sum",
                    "Items": ["q1"],
                    "MinValid": "one",
                }
            ]
        )
        errors = validate_recipe(recipe, known_items={"q1"})
        assert any("MinValid must be an integer >= 1" in e for e in errors)

    def test_score_min_valid_bool_rejected(self):
        recipe = _valid_survey_recipe(
            Scores=[
                {"Name": "total", "Method": "sum", "Items": ["q1"], "MinValid": True}
            ]
        )
        errors = validate_recipe(recipe, known_items={"q1"})
        assert any("MinValid must be an integer >= 1" in e for e in errors)

    def test_score_min_valid_less_than_one(self):
        recipe = _valid_survey_recipe(
            Scores=[{"Name": "total", "Method": "sum", "Items": ["q1"], "MinValid": 0}]
        )
        errors = validate_recipe(recipe, known_items={"q1"})
        assert any("MinValid must be >= 1" in e for e in errors)

    def test_score_min_valid_requires_nonempty_items(self):
        recipe = _valid_survey_recipe(
            Scores=[
                {
                    "Name": "total",
                    "Method": "map",
                    "Source": "q1",
                    "Mapping": {"1": "a"},
                    "MinValid": 1,
                }
            ]
        )
        errors = validate_recipe(recipe, known_items={"q1"})
        assert any("MinValid requires a non-empty Items list" in e for e in errors)

    def test_score_min_valid_exceeds_items(self):
        recipe = _valid_survey_recipe(
            Scores=[
                {
                    "Name": "total",
                    "Method": "sum",
                    "Items": ["q1"],
                    "MinValid": 5,
                }
            ]
        )
        errors = validate_recipe(recipe, known_items={"q1"})
        assert any("cannot exceed number of Items" in e for e in errors)

    def test_score_formula_missing_formula(self):
        recipe = _valid_survey_recipe(
            Scores=[{"Name": "total", "Method": "formula", "Items": ["q1"]}]
        )
        errors = validate_recipe(recipe, known_items={"q1"})
        assert any("no non-empty Formula" in e for e in errors)

    def test_score_formula_no_placeholders(self):
        recipe = _valid_survey_recipe(
            Scores=[
                {
                    "Name": "total",
                    "Method": "formula",
                    "Items": ["q1"],
                    "Formula": "no placeholders here",
                }
            ]
        )
        errors = validate_recipe(recipe, known_items={"q1"})
        assert any("Formula has no {placeholders}" in e for e in errors)

    def test_score_formula_missing_ref(self):
        recipe = _valid_survey_recipe(
            Scores=[
                {
                    "Name": "total",
                    "Method": "formula",
                    "Items": ["q1"],
                    "Formula": "{q1}+{q2}",
                }
            ]
        )
        errors = validate_recipe(recipe, known_items={"q1", "q2"})
        assert any("Formula references ['q2']" in e for e in errors)

    def test_versioned_scores_not_an_object(self):
        recipe = _valid_survey_recipe(VersionedScores=["nope"])
        del recipe["Scores"]
        errors = validate_recipe(recipe)
        assert any("VersionedScores must be an object" in e for e in errors)

    def test_versioned_scores_key_empty(self):
        recipe = _valid_survey_recipe(
            VersionedScores={"": [{"Name": "x", "Method": "sum", "Items": ["q1"]}]}
        )
        del recipe["Scores"]
        errors = validate_recipe(recipe)
        assert any("VersionedScores keys must be non-empty strings" in e for e in errors)

    def test_versioned_scores_valid(self):
        recipe = _valid_survey_recipe(
            VersionedScores={
                "v1": [{"Name": "total", "Method": "sum", "Items": ["q1"]}]
            }
        )
        del recipe["Scores"]
        errors = validate_recipe(recipe, known_items={"q1"})
        assert errors == []

    def test_score_map_available_from_earlier_score_in_same_list(self):
        recipe = _valid_survey_recipe(
            Scores=[
                {"Name": "s1", "Method": "sum", "Items": ["q1"]},
                {"Name": "s2", "Method": "sum", "Items": ["s1"]},
            ]
        )
        errors = validate_recipe(recipe, known_items={"q1"})
        assert errors == []

    def test_collision_between_derived_and_scores(self):
        recipe = _valid_survey_recipe(
            Transforms={"Derived": [{"Name": "total", "Method": "sum", "Items": ["q1"]}]},
            Scores=[{"Name": "total", "Method": "sum", "Items": ["q1"]}],
        )
        errors = validate_recipe(recipe, known_items={"q1"})
        assert any("Name collision between Derived and Scores" in e for e in errors)
