from __future__ import annotations

import importlib
import sys
from pathlib import Path


def _import_handlers_module():
    app_root = Path(__file__).resolve().parents[1] / "app"
    if str(app_root) not in sys.path:
        sys.path.insert(0, str(app_root))
    return importlib.import_module("src.web.blueprints.tools_recipes_surveys_handlers")


def test_combined_output_check_ignores_single_file_exports(tmp_path: Path) -> None:
    handlers = _import_handlers_module()

    out_dir = tmp_path / "derivatives" / "survey" / "long_en"
    out_dir.mkdir(parents=True)
    (out_dir / "ads.csv").write_text(
        "participant_id,score\nsub-001,1\n", encoding="utf-8"
    )
    (out_dir / "ads_codebook.json").write_text("{}", encoding="utf-8")

    existing = handlers._find_existing_recipe_output_files(
        derivatives_dir=out_dir,
        out_format="save",
        merge_all=True,
        modality="survey",
        pyreadstat_available=True,
    )

    assert existing == []


def test_combined_output_check_only_flags_combined_targets(tmp_path: Path) -> None:
    handlers = _import_handlers_module()

    out_dir = tmp_path / "derivatives" / "survey" / "long_en"
    out_dir.mkdir(parents=True)
    combined_sav = out_dir / "combined_survey.sav"
    combined_codebook = out_dir / "combined_survey_codebook.tsv"
    combined_sav.write_text("sav", encoding="utf-8")
    combined_codebook.write_text("variable\tlabel\n", encoding="utf-8")
    (out_dir / "ads.sav").write_text("single", encoding="utf-8")

    existing = handlers._find_existing_recipe_output_files(
        derivatives_dir=out_dir,
        out_format="save",
        merge_all=True,
        modality="survey",
        pyreadstat_available=True,
    )

    assert existing == [combined_sav, combined_codebook]


def test_recipes_template_defaults_to_spss_output() -> None:
    template_path = (
        Path(__file__).resolve().parents[1] / "app" / "templates" / "recipes.html"
    )
    content = template_path.read_text(encoding="utf-8")

    assert '<option value="save" selected>' in content
    assert '<option value="csv" selected>' not in content


def test_recipes_ui_uses_analysis_outputs_labeling() -> None:
    repo_root = Path(__file__).resolve().parents[1]
    recipes_template = (repo_root / "app" / "templates" / "recipes.html").read_text(
        encoding="utf-8"
    )
    base_template = (repo_root / "app" / "templates" / "base.html").read_text(
        encoding="utf-8"
    )

    assert "Analysis Outputs" in recipes_template
    assert "Create Output" in recipes_template
    assert "Analysis Outputs" in base_template
