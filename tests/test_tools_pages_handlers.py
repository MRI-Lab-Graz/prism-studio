from __future__ import annotations

from pathlib import Path


def test_run_modalities_require_prefixed_recipe_files(
    tmp_path: Path,
) -> None:
    from src.recipe_builder import list_run_modalities

    project_root = tmp_path / "project"
    (project_root / "sub-01" / "survey").mkdir(parents=True)
    (project_root / "sub-01" / "survey" / "task-ads.tsv").write_text(
        "participant_id\tscore\nsub-01\t1\n",
        encoding="utf-8",
    )
    (project_root / "sub-01" / "biometrics").mkdir(parents=True)
    (project_root / "sub-01" / "biometrics" / "hrv.tsv").write_text(
        "participant_id\tvalue\nsub-01\t1\n",
        encoding="utf-8",
    )

    survey_recipe_dir = project_root / "code" / "recipes" / "survey"
    survey_recipe_dir.mkdir(parents=True)
    (survey_recipe_dir / "ads.json").write_text("{}", encoding="utf-8")

    biometrics_recipe_dir = project_root / "code" / "recipes" / "biometrics"
    biometrics_recipe_dir.mkdir(parents=True)
    (biometrics_recipe_dir / "recipe-hrv.json").write_text("{}", encoding="utf-8")

    offered = list_run_modalities(project_root, None)

    assert offered == {"modalities": [{"value": "biometrics", "label": "Biometrics"}], "default": "biometrics"}
