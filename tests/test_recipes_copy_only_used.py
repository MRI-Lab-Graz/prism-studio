from pathlib import Path

from src.recipes_surveys import compute_survey_recipes


def _write_recipe(path: Path, task_name: str) -> None:
    path.write_text(
        """
{
  "Kind": "survey",
  "RecipeVersion": "1.0",
  "Survey": {
    "TaskName": "__TASK__"
  },
  "Scores": [
    {
      "Name": "Total",
      "Method": "sum",
      "Items": ["Q1"]
    }
  ]
}
""".replace("__TASK__", task_name).strip()
        + "\n",
        encoding="utf-8",
    )


def test_compute_survey_recipes_copies_only_matched_recipes(tmp_path: Path) -> None:
    project_root = tmp_path / "project"
    recipe_dir = tmp_path / "recipes"

    (project_root / "sub-001" / "ses-1" / "survey").mkdir(parents=True)
    recipe_dir.mkdir(parents=True)

    # Only task "aaa" exists in this dataset.
    survey_tsv = (
        project_root
        / "sub-001"
        / "ses-1"
        / "survey"
        / "sub-001_ses-1_task-aaa_survey.tsv"
    )
    survey_tsv.write_text("Q1\n1\n", encoding="utf-8")

    _write_recipe(recipe_dir / "recipe-aaa.json", "aaa")
    _write_recipe(recipe_dir / "recipe-bbb.json", "bbb")

    result = compute_survey_recipes(
        prism_root=project_root,
        repo_root=tmp_path,
        recipe_dir=recipe_dir,
        modality="survey",
        out_format="csv",
    )

    copied_dir = project_root / "code" / "recipes" / "survey"
    assert result.written_files == 1
    assert (copied_dir / "aaa.json").exists()
    assert not (copied_dir / "bbb.json").exists()
