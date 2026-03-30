from pathlib import Path

import pytest

from src.recipes_surveys import _load_and_validate_recipes


def _write_minimal_recipe(path: Path, task_name: str) -> None:
    path.write_text(
        (
            "{\n"
            '  "Kind": "survey",\n'
            '  "RecipeVersion": "1.0",\n'
            '  "Survey": {"TaskName": "__TASK__"},\n'
            '  "Scores": []\n'
            "}\n"
        ).replace("__TASK__", task_name),
        encoding="utf-8",
    )


def test_load_and_validate_recipes_requires_recipe_prefix(tmp_path: Path) -> None:
    recipe_dir = tmp_path / "recipes"
    recipe_dir.mkdir()
    _write_minimal_recipe(recipe_dir / "ads.json", "ads")

    with pytest.raises(ValueError, match=r"Expected recipe-\*\.json"):
        _load_and_validate_recipes(
            repo_root=tmp_path,
            modality="survey",
            recipe_dir=recipe_dir,
        )


def test_load_and_validate_recipes_accepts_recipe_prefix(tmp_path: Path) -> None:
    recipe_dir = tmp_path / "recipes"
    recipe_dir.mkdir()
    _write_minimal_recipe(recipe_dir / "recipe-ads.json", "ads")

    recipes, loaded_dir = _load_and_validate_recipes(
        repo_root=tmp_path,
        modality="survey",
        recipe_dir=recipe_dir,
    )

    assert "ads" in recipes
    assert loaded_dir == recipe_dir.resolve()
