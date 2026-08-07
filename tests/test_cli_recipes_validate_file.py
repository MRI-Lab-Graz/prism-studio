"""Tests for `prism_tools.py recipes validate-file`.

docs/_archive/GUI_BACKEND_AUDIT_2026-08-07.md (P2, Recipe Builder): the
interactive item-picking/reordering parts of the Studio GUI's Recipe
Builder page are pure client-side form state (no server round-trip), so
they're not a "missing backend command" in the CLAUDE.md sense — but there
was no CLI way to pre-flight-check a hand-authored (or Recipe
Builder-exported) recipe JSON's validity on its own, without running a
full `recipes surveys`/`recipes biometrics` scoring job. This adds that
using the same src.recipe_validation.validate_recipe both already use.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

APP_ROOT = Path(__file__).resolve().parents[1] / "app"
if str(APP_ROOT) not in sys.path:
    sys.path.insert(0, str(APP_ROOT))

from src.cli.commands.recipes import cmd_recipes_validate_file  # noqa: E402

VALID_RECIPE = {
    "RecipeVersion": "1.0",
    "Kind": "survey",
    "Survey": {"TaskName": "ads"},
    "VersionedScores": {
        "vas": [
            {
                "Name": "ads_total_vas",
                "Method": "mean",
                "Items": ["ADS01", "ADS02"],
            }
        ]
    },
}


def _args(**overrides) -> SimpleNamespace:
    defaults = dict(recipe=None, known_items_from=None, recipe_id=None, json=False)
    defaults.update(overrides)
    return SimpleNamespace(**defaults)


class TestValidRecipe:
    def test_valid_recipe_passes(self, tmp_path, capsys):
        recipe_path = tmp_path / "recipe-ads.json"
        recipe_path.write_text(json.dumps(VALID_RECIPE), encoding="utf-8")

        cmd_recipes_validate_file(_args(recipe=str(recipe_path)))

        assert "valid recipe" in capsys.readouterr().out

    def test_json_mode_reports_success(self, tmp_path, capsys):
        recipe_path = tmp_path / "recipe-ads.json"
        recipe_path.write_text(json.dumps(VALID_RECIPE), encoding="utf-8")

        cmd_recipes_validate_file(_args(recipe=str(recipe_path), json=True))

        payload = json.loads(capsys.readouterr().out)
        assert payload["success"] is True
        assert payload["errors"] == []


class TestInvalidRecipe:
    def test_missing_file_exits(self, tmp_path, capsys):
        with pytest.raises(SystemExit) as exc_info:
            cmd_recipes_validate_file(
                _args(recipe=str(tmp_path / "missing.json"))
            )
        assert exc_info.value.code == 1
        assert "not found" in capsys.readouterr().out

    def test_invalid_json_exits(self, tmp_path, capsys):
        bad_path = tmp_path / "bad.json"
        bad_path.write_text("not json", encoding="utf-8")

        with pytest.raises(SystemExit) as exc_info:
            cmd_recipes_validate_file(_args(recipe=str(bad_path)))
        assert exc_info.value.code == 1
        assert "not valid JSON" in capsys.readouterr().out

    def test_structurally_invalid_recipe_reports_errors(self, tmp_path, capsys):
        recipe_path = tmp_path / "recipe-bad.json"
        recipe_path.write_text(json.dumps({"not": "a recipe"}), encoding="utf-8")

        with pytest.raises(SystemExit) as exc_info:
            cmd_recipes_validate_file(_args(recipe=str(recipe_path)))
        assert exc_info.value.code == 1
        out = capsys.readouterr().out
        assert "validation error" in out

    def test_json_mode_reports_failure_and_exits(self, tmp_path, capsys):
        recipe_path = tmp_path / "recipe-bad.json"
        recipe_path.write_text(json.dumps({"not": "a recipe"}), encoding="utf-8")

        with pytest.raises(SystemExit) as exc_info:
            cmd_recipes_validate_file(_args(recipe=str(recipe_path), json=True))
        assert exc_info.value.code == 1
        payload = json.loads(capsys.readouterr().out)
        assert payload["success"] is False
        assert len(payload["errors"]) > 0


class TestKnownItemsFromTemplate:
    def test_typo_item_id_detected_via_known_items(self, tmp_path, capsys):
        template_path = tmp_path / "survey-ads.json"
        template_path.write_text(
            json.dumps(
                {
                    "Questions": {
                        "ADS01": {"Description": "Item 1"},
                        "ADS02": {"Description": "Item 2"},
                    }
                }
            ),
            encoding="utf-8",
        )

        recipe_with_typo = {
            "RecipeVersion": "1.0",
            "Kind": "survey",
            "Survey": {"TaskName": "ads"},
            "VersionedScores": {
                "vas": [
                    {
                        "Name": "ads_total_vas",
                        "Method": "mean",
                        "Items": ["ADS01", "ADS0_TYPO"],
                    }
                ]
            },
        }
        recipe_path = tmp_path / "recipe-ads.json"
        recipe_path.write_text(json.dumps(recipe_with_typo), encoding="utf-8")

        with pytest.raises(SystemExit) as exc_info:
            cmd_recipes_validate_file(
                _args(
                    recipe=str(recipe_path),
                    known_items_from=str(template_path),
                )
            )
        assert exc_info.value.code == 1
        assert "validation error" in capsys.readouterr().out

    def test_missing_known_items_template_exits(self, tmp_path, capsys):
        recipe_path = tmp_path / "recipe-ads.json"
        recipe_path.write_text(json.dumps(VALID_RECIPE), encoding="utf-8")

        with pytest.raises(SystemExit) as exc_info:
            cmd_recipes_validate_file(
                _args(
                    recipe=str(recipe_path),
                    known_items_from=str(tmp_path / "missing-template.json"),
                )
            )
        assert exc_info.value.code == 1
        assert "not found" in capsys.readouterr().out
