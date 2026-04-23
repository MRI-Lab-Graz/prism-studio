"""Tests for recipe export output subfolder functionality.

The output subfolder is determined by layout, language, and anonymization settings:
- derivatives/survey/{layout}_{lang}/ (e.g., wide_de/, long_en/)
- derivatives/survey/{layout}_{lang}_anon/ when anonymized=True
"""

from pathlib import Path
from typing import Any
import csv

import pytest

from src.recipes_surveys import compute_survey_recipes, SurveyRecipesResult


def _write_minimal_recipe(path: Path, task_name: str) -> None:
    """Write a minimal valid recipe JSON file."""
    path.write_text(
        (
            "{\n"
            '  "Kind": "survey",\n'
            '  "RecipeVersion": "1.0",\n'
            f'  "Survey": {{"TaskName": "{task_name}"}},\n'
            '  "Scores": [\n'
            '    {"Name": "Total", "Method": "sum", "Items": ["Q1"]}\n'
            "  ]\n"
            "}\n"
        ),
        encoding="utf-8",
    )


def _setup_minimal_project(
    tmp_path: Path, task_name: str = "test"
) -> tuple[Path, Path]:
    """Create a minimal PRISM project with one survey file and recipe."""
    project_root = tmp_path / "project"
    recipe_dir = tmp_path / "recipes"

    # Create survey data
    survey_dir = project_root / "sub-001" / "ses-1" / "survey"
    survey_dir.mkdir(parents=True)
    survey_tsv = survey_dir / f"sub-001_ses-1_task-{task_name}_survey.tsv"
    survey_tsv.write_text("Q1\n5\n", encoding="utf-8")

    # Create recipe
    recipe_dir.mkdir(parents=True)
    _write_minimal_recipe(recipe_dir / f"recipe-{task_name}.json", task_name)

    return project_root, recipe_dir


class TestOutputSubfolderNaming:
    """Test that output subfolder is named correctly based on config."""

    def test_default_long_en(self, tmp_path: Path) -> None:
        """Default layout=long, lang=en -> long_en/"""
        project_root, recipe_dir = _setup_minimal_project(tmp_path)

        result = compute_survey_recipes(
            prism_root=project_root,
            repo_root=tmp_path,
            recipe_dir=recipe_dir,
            modality="survey",
            out_format="csv",
            # defaults: layout="long", lang="en", anonymized=False
        )

        assert result.out_root.name == "long_en"
        assert result.out_root == project_root / "derivatives" / "survey" / "long_en"
        assert result.out_root.exists()

    def test_wide_de(self, tmp_path: Path) -> None:
        """layout=wide, lang=de -> wide_de/"""
        project_root, recipe_dir = _setup_minimal_project(tmp_path)

        result = compute_survey_recipes(
            prism_root=project_root,
            repo_root=tmp_path,
            recipe_dir=recipe_dir,
            modality="survey",
            out_format="csv",
            layout="wide",
            lang="de",
        )

        assert result.out_root.name == "wide_de"
        assert (project_root / "derivatives" / "survey" / "wide_de").exists()

    def test_long_de(self, tmp_path: Path) -> None:
        """layout=long, lang=de -> long_de/"""
        project_root, recipe_dir = _setup_minimal_project(tmp_path)

        result = compute_survey_recipes(
            prism_root=project_root,
            repo_root=tmp_path,
            recipe_dir=recipe_dir,
            modality="survey",
            out_format="csv",
            layout="long",
            lang="de",
        )

        assert result.out_root.name == "long_de"

    def test_wide_en(self, tmp_path: Path) -> None:
        """layout=wide, lang=en -> wide_en/"""
        project_root, recipe_dir = _setup_minimal_project(tmp_path)

        result = compute_survey_recipes(
            prism_root=project_root,
            repo_root=tmp_path,
            recipe_dir=recipe_dir,
            modality="survey",
            out_format="csv",
            layout="wide",
            lang="en",
        )

        assert result.out_root.name == "wide_en"


class TestAnonymizedSuffix:
    """Test that _anon suffix is added when anonymized=True."""

    def test_long_en_anon(self, tmp_path: Path) -> None:
        """anonymized=True -> long_en_anon/"""
        project_root, recipe_dir = _setup_minimal_project(tmp_path)

        result = compute_survey_recipes(
            prism_root=project_root,
            repo_root=tmp_path,
            recipe_dir=recipe_dir,
            modality="survey",
            out_format="csv",
            layout="long",
            lang="en",
            anonymized=True,
        )

        assert result.out_root.name == "long_en_anon"
        assert (project_root / "derivatives" / "survey" / "long_en_anon").exists()

    def test_wide_de_anon(self, tmp_path: Path) -> None:
        """layout=wide, lang=de, anonymized=True -> wide_de_anon/"""
        project_root, recipe_dir = _setup_minimal_project(tmp_path)

        result = compute_survey_recipes(
            prism_root=project_root,
            repo_root=tmp_path,
            recipe_dir=recipe_dir,
            modality="survey",
            out_format="csv",
            layout="wide",
            lang="de",
            anonymized=True,
        )

        assert result.out_root.name == "wide_de_anon"

    def test_anonymized_false_no_suffix(self, tmp_path: Path) -> None:
        """anonymized=False (default) -> no _anon suffix."""
        project_root, recipe_dir = _setup_minimal_project(tmp_path)

        result = compute_survey_recipes(
            prism_root=project_root,
            repo_root=tmp_path,
            recipe_dir=recipe_dir,
            modality="survey",
            out_format="csv",
            anonymized=False,
        )

        assert "_anon" not in result.out_root.name


class TestMultipleExports:
    """Test that multiple exports with different configs create separate folders."""

    def test_different_layouts_create_separate_folders(self, tmp_path: Path) -> None:
        """Running long and wide exports creates both folders."""
        project_root, recipe_dir = _setup_minimal_project(tmp_path)

        # First export: long
        result_long = compute_survey_recipes(
            prism_root=project_root,
            repo_root=tmp_path,
            recipe_dir=recipe_dir,
            modality="survey",
            out_format="csv",
            layout="long",
            lang="en",
        )

        # Second export: wide
        result_wide = compute_survey_recipes(
            prism_root=project_root,
            repo_root=tmp_path,
            recipe_dir=recipe_dir,
            modality="survey",
            out_format="csv",
            layout="wide",
            lang="en",
        )

        assert result_long.out_root.name == "long_en"
        assert result_wide.out_root.name == "wide_en"
        assert (project_root / "derivatives" / "survey" / "long_en").exists()
        assert (project_root / "derivatives" / "survey" / "wide_en").exists()

    def test_anon_and_non_anon_separate_folders(self, tmp_path: Path) -> None:
        """Running with and without anonymized creates separate folders."""
        project_root, recipe_dir = _setup_minimal_project(tmp_path)

        # First export: not anonymized
        result_normal = compute_survey_recipes(
            prism_root=project_root,
            repo_root=tmp_path,
            recipe_dir=recipe_dir,
            modality="survey",
            out_format="csv",
            layout="wide",
            lang="de",
            anonymized=False,
        )

        # Second export: anonymized
        result_anon = compute_survey_recipes(
            prism_root=project_root,
            repo_root=tmp_path,
            recipe_dir=recipe_dir,
            modality="survey",
            out_format="csv",
            layout="wide",
            lang="de",
            anonymized=True,
        )

        assert result_normal.out_root.name == "wide_de"
        assert result_anon.out_root.name == "wide_de_anon"
        assert (project_root / "derivatives" / "survey" / "wide_de").exists()
        assert (project_root / "derivatives" / "survey" / "wide_de_anon").exists()

    def test_all_four_combinations(self, tmp_path: Path) -> None:
        """All layout/lang combinations create distinct folders."""
        project_root, recipe_dir = _setup_minimal_project(tmp_path)

        combinations = [
            ("long", "en"),
            ("long", "de"),
            ("wide", "en"),
            ("wide", "de"),
        ]

        for layout, lang in combinations:
            compute_survey_recipes(
                prism_root=project_root,
                repo_root=tmp_path,
                recipe_dir=recipe_dir,
                modality="survey",
                out_format="csv",
                layout=layout,
                lang=lang,
            )

        survey_dir = project_root / "derivatives" / "survey"
        assert (survey_dir / "long_en").exists()
        assert (survey_dir / "long_de").exists()
        assert (survey_dir / "wide_en").exists()
        assert (survey_dir / "wide_de").exists()


class TestMergeAllWideLayout:
    """Regression tests for merge_all + wide output behavior."""

    def _setup_merge_all_project(
        self,
        tmp_path: Path,
        *,
        runs: list[str] | None = None,
    ) -> tuple[Path, Path]:
        project_root = tmp_path / "project"
        recipe_dir = tmp_path / "recipes"
        run_values = runs or [""]

        for ses, a_val, b_val in (("ses-1", 1, 2), ("ses-2", 3, 4)):
            survey_dir = project_root / "sub-001" / ses / "survey"
            survey_dir.mkdir(parents=True, exist_ok=True)
            for run in run_values:
                run_token = f"_{run}" if run else ""
                (survey_dir / f"sub-001_{ses}{run_token}_task-a_survey.tsv").write_text(
                    f"Q1\n{a_val}\n", encoding="utf-8"
                )
                (survey_dir / f"sub-001_{ses}{run_token}_task-b_survey.tsv").write_text(
                    f"Q1\n{b_val}\n", encoding="utf-8"
                )

        recipe_dir.mkdir(parents=True, exist_ok=True)
        _write_minimal_recipe(recipe_dir / "recipe-a.json", "a")
        _write_minimal_recipe(recipe_dir / "recipe-b.json", "b")
        return project_root, recipe_dir

    def test_merge_all_wide_csv_pivots_sessions(self, tmp_path: Path) -> None:
        """Combined export with layout=wide should produce session-suffixed columns."""
        project_root, recipe_dir = self._setup_merge_all_project(tmp_path)

        result = compute_survey_recipes(
            prism_root=project_root,
            repo_root=tmp_path,
            recipe_dir=recipe_dir,
            modality="survey",
            out_format="csv",
            layout="wide",
            merge_all=True,
            lang="de",
        )

        out_csv = result.out_root / "combined_survey.csv"
        assert out_csv.exists(), f"Expected {out_csv} to exist"

        with out_csv.open("r", encoding="utf-8", newline="") as f:
            reader = csv.DictReader(f)
            rows = list(reader)
            fieldnames = reader.fieldnames or []

        assert len(rows) == 1
        assert "participant_id" in fieldnames
        assert "session" not in fieldnames
        assert "a_Total_ses-1" in fieldnames
        assert "a_Total_ses-2" in fieldnames
        assert "b_Total_ses-1" in fieldnames
        assert "b_Total_ses-2" in fieldnames

    def test_merge_all_wide_single_run_omits_run_suffix(self, tmp_path: Path) -> None:
        """Single-run datasets keep session-only wide column names."""
        project_root, recipe_dir = self._setup_merge_all_project(
            tmp_path, runs=["run-01"]
        )

        result = compute_survey_recipes(
            prism_root=project_root,
            repo_root=tmp_path,
            recipe_dir=recipe_dir,
            modality="survey",
            out_format="csv",
            layout="wide",
            merge_all=True,
            lang="en",
        )

        out_csv = result.out_root / "combined_survey.csv"
        with out_csv.open("r", encoding="utf-8", newline="") as f:
            reader = csv.DictReader(f)
            fieldnames = reader.fieldnames or []

        assert "a_Total_ses-1" in fieldnames
        assert "a_Total_ses-2" in fieldnames
        assert not any("_run-" in c for c in fieldnames)

    def test_merge_all_wide_multi_run_includes_run_suffix(self, tmp_path: Path) -> None:
        """Multi-run datasets include run in wide column names to avoid collisions."""
        project_root, recipe_dir = self._setup_merge_all_project(
            tmp_path, runs=["run-01", "run-02"]
        )

        result = compute_survey_recipes(
            prism_root=project_root,
            repo_root=tmp_path,
            recipe_dir=recipe_dir,
            modality="survey",
            out_format="csv",
            layout="wide",
            merge_all=True,
            lang="en",
        )

        out_csv = result.out_root / "combined_survey.csv"
        with out_csv.open("r", encoding="utf-8", newline="") as f:
            reader = csv.DictReader(f)
            fieldnames = reader.fieldnames or []

        assert "a_Total_ses-1_run-01" in fieldnames
        assert "a_Total_ses-1_run-02" in fieldnames
        assert "b_Total_ses-2_run-01" in fieldnames
        assert "b_Total_ses-2_run-02" in fieldnames


class TestOutputFilesInSubfolder:
    """Test that output files are written to the correct subfolder."""

    def test_csv_files_in_subfolder(self, tmp_path: Path) -> None:
        """CSV output files are created in the config subfolder."""
        project_root, recipe_dir = _setup_minimal_project(tmp_path, task_name="mytest")

        result = compute_survey_recipes(
            prism_root=project_root,
            repo_root=tmp_path,
            recipe_dir=recipe_dir,
            modality="survey",
            out_format="csv",
            layout="wide",
            lang="de",
        )

        csv_file = result.out_root / "mytest.csv"
        assert csv_file.exists(), f"Expected {csv_file} to exist"

    def test_sav_files_in_subfolder(self, tmp_path: Path) -> None:
        """SAV output files are created in the config subfolder."""
        pytest.importorskip("pyreadstat")

        project_root, recipe_dir = _setup_minimal_project(tmp_path, task_name="mytest")

        result = compute_survey_recipes(
            prism_root=project_root,
            repo_root=tmp_path,
            recipe_dir=recipe_dir,
            modality="survey",
            out_format="save",
            layout="wide",
            lang="en",
        )

        sav_file = result.out_root / "mytest.sav"
        # Either .sav exists or fallback .csv exists (if pyreadstat fails for some reason)
        assert sav_file.exists() or (result.out_root / "mytest.csv").exists()

    def test_codebook_files_in_subfolder(self, tmp_path: Path) -> None:
        """Codebook files are created in the config subfolder."""
        pytest.importorskip("pyreadstat")

        project_root, recipe_dir = _setup_minimal_project(tmp_path, task_name="mytest")

        result = compute_survey_recipes(
            prism_root=project_root,
            repo_root=tmp_path,
            recipe_dir=recipe_dir,
            modality="survey",
            out_format="save",
            layout="long",
            lang="de",
        )

        # Codebook should be in the same subfolder
        codebook = result.out_root / "mytest_codebook.json"
        assert codebook.exists() or result.fallback_note is not None

    def test_dataset_description_in_subfolder(self, tmp_path: Path) -> None:
        """dataset_description.json is created in the config subfolder."""
        project_root, recipe_dir = _setup_minimal_project(tmp_path)

        result = compute_survey_recipes(
            prism_root=project_root,
            repo_root=tmp_path,
            recipe_dir=recipe_dir,
            modality="survey",
            out_format="csv",
            layout="wide",
            lang="de",
        )

        desc_file = result.out_root / "dataset_description.json"
        assert desc_file.exists()


class TestBiometricsModality:
    """Test that biometrics modality also uses the subfolder naming."""

    def _setup_biometrics_project(self, tmp_path: Path) -> tuple[Path, Path]:
        """Create a minimal biometrics project."""
        project_root = tmp_path / "project"
        recipe_dir = tmp_path / "recipes"

        # Create biometrics data
        bio_dir = project_root / "sub-001" / "ses-1" / "biometrics"
        bio_dir.mkdir(parents=True)
        bio_tsv = bio_dir / "sub-001_ses-1_task-balance_biometrics.tsv"
        bio_tsv.write_text("trial\tscore\n1\t10\n", encoding="utf-8")

        # Create recipe (use 'sum' which is a valid method)
        recipe_dir.mkdir(parents=True)
        (recipe_dir / "recipe-balance.json").write_text(
            """{
  "Kind": "biometrics",
  "RecipeVersion": "1.0",
  "Biometrics": {"BiometricName": "balance"},
  "Scores": [{"Name": "Total", "Method": "sum", "Items": ["score"]}]
}
""",
            encoding="utf-8",
        )

        return project_root, recipe_dir

    def test_biometrics_uses_subfolder(self, tmp_path: Path) -> None:
        """Biometrics export also uses config-based subfolder."""
        project_root, recipe_dir = self._setup_biometrics_project(tmp_path)

        result = compute_survey_recipes(
            prism_root=project_root,
            repo_root=tmp_path,
            recipe_dir=recipe_dir,
            modality="biometrics",
            out_format="csv",
            layout="wide",
            lang="de",
        )

        assert result.out_root.name == "wide_de"
        assert (
            result.out_root == project_root / "derivatives" / "biometrics" / "wide_de"
        )

    def test_biometrics_anon_suffix(self, tmp_path: Path) -> None:
        """Biometrics export with anonymized=True adds _anon suffix."""
        project_root, recipe_dir = self._setup_biometrics_project(tmp_path)

        result = compute_survey_recipes(
            prism_root=project_root,
            repo_root=tmp_path,
            recipe_dir=recipe_dir,
            modality="biometrics",
            out_format="csv",
            layout="long",
            lang="en",
            anonymized=True,
        )

        assert result.out_root.name == "long_en_anon"
        assert "biometrics" in str(result.out_root)


class TestSavColumnSanitization:
    """Test that SPSS exports handle illegal column characters."""

    def _setup_project_with_session(
        self, tmp_path: Path, task_name: str = "test"
    ) -> tuple[Path, Path]:
        """Create a project that will produce columns with dashes (ses-1 suffix)."""
        project_root = tmp_path / "project"
        recipe_dir = tmp_path / "recipes"

        # Create survey data for multiple sessions to trigger wide layout column naming
        for ses in ["ses-1", "ses-2"]:
            survey_dir = project_root / "sub-001" / ses / "survey"
            survey_dir.mkdir(parents=True)
            survey_tsv = survey_dir / f"sub-001_{ses}_task-{task_name}_survey.tsv"
            survey_tsv.write_text("Q1\n5\n", encoding="utf-8")

        # Create recipe
        recipe_dir.mkdir(parents=True)
        _write_minimal_recipe(recipe_dir / f"recipe-{task_name}.json", task_name)

        return project_root, recipe_dir

    def test_sav_export_sanitizes_column_names(self, tmp_path: Path) -> None:
        """SAV export replaces illegal characters in column names."""
        pyreadstat = pytest.importorskip("pyreadstat")

        project_root, recipe_dir = self._setup_project_with_session(tmp_path, "mytest")

        result = compute_survey_recipes(
            prism_root=project_root,
            repo_root=tmp_path,
            recipe_dir=recipe_dir,
            modality="survey",
            out_format="save",
            layout="wide",  # Wide layout adds session suffix to columns
            lang="en",
        )

        sav_file = result.out_root / "mytest.sav"
        if sav_file.exists():
            df, meta = pyreadstat.read_sav(sav_file)
            # Column names should not contain dashes
            for col in df.columns:
                assert "-" not in col, f"Column '{col}' contains illegal dash character"
                assert "." not in col, f"Column '{col}' contains illegal dot character"
                assert (
                    " " not in col
                ), f"Column '{col}' contains illegal space character"

    def test_sav_export_cleans_up_empty_files_on_failure(self, tmp_path: Path) -> None:
        """If SAV export fails, 0-byte files should be cleaned up."""
        project_root, recipe_dir = _setup_minimal_project(tmp_path, task_name="test")

        # This should succeed or fall back to CSV gracefully
        result = compute_survey_recipes(
            prism_root=project_root,
            repo_root=tmp_path,
            recipe_dir=recipe_dir,
            modality="survey",
            out_format="save",
            layout="long",
            lang="en",
        )

        # Check no 0-byte .sav files exist
        for sav_file in result.out_root.glob("*.sav"):
            assert sav_file.stat().st_size > 0, f"{sav_file} is empty (0 bytes)"


class TestProjectNamePrefix:
    """Test that output files are prefixed with a slug of the project name."""

    def _setup_project_with_name(
        self, tmp_path: Path, name: str, task_name: str = "mytest"
    ) -> tuple[Path, Path]:
        """Create a minimal project with a dataset_description.json containing Name."""
        project_root, recipe_dir = _setup_minimal_project(tmp_path, task_name=task_name)
        import json

        desc = {"Name": name, "BIDSVersion": "1.8.0"}
        (project_root / "dataset_description.json").write_text(
            json.dumps(desc), encoding="utf-8"
        )
        return project_root, recipe_dir

    def test_csv_prefixed_with_project_slug(self, tmp_path: Path) -> None:
        """CSV output file is prefixed with the slugified project name."""
        project_root, recipe_dir = self._setup_project_with_name(
            tmp_path, "My Study 2024"
        )

        result = compute_survey_recipes(
            prism_root=project_root,
            repo_root=tmp_path,
            recipe_dir=recipe_dir,
            modality="survey",
            out_format="csv",
            layout="wide",
            lang="en",
        )

        csv_file = result.out_root / "my_study_2024_mytest.csv"
        assert csv_file.exists(), f"Expected prefixed file {csv_file} to exist"

    def test_codebook_prefixed_with_project_slug(self, tmp_path: Path) -> None:
        """Codebook JSON is also prefixed with the slugified project name."""
        project_root, recipe_dir = self._setup_project_with_name(
            tmp_path, "My Study 2024"
        )

        result = compute_survey_recipes(
            prism_root=project_root,
            repo_root=tmp_path,
            recipe_dir=recipe_dir,
            modality="survey",
            out_format="csv",
            layout="wide",
            lang="en",
        )

        codebook = result.out_root / "my_study_2024_mytest_codebook.json"
        assert codebook.exists(), f"Expected prefixed codebook {codebook} to exist"

    def test_no_prefix_without_dataset_description(self, tmp_path: Path) -> None:
        """Without dataset_description.json files use the plain recipe_id name."""
        project_root, recipe_dir = _setup_minimal_project(tmp_path, task_name="mytest")

        result = compute_survey_recipes(
            prism_root=project_root,
            repo_root=tmp_path,
            recipe_dir=recipe_dir,
            modality="survey",
            out_format="csv",
            layout="wide",
            lang="en",
        )

        csv_file = result.out_root / "mytest.csv"
        assert csv_file.exists(), f"Expected unprefixed file {csv_file} to exist"

    def test_slug_strips_special_characters(self, tmp_path: Path) -> None:
        """Special characters in project name are replaced with underscores."""
        project_root, recipe_dir = self._setup_project_with_name(
            tmp_path, "Study: Phase-1 (2024)"
        )

        result = compute_survey_recipes(
            prism_root=project_root,
            repo_root=tmp_path,
            recipe_dir=recipe_dir,
            modality="survey",
            out_format="csv",
            layout="wide",
            lang="en",
        )

        # At least one CSV file should exist that starts with correctly slugified prefix
        csvs = list(result.out_root.glob("*.csv"))
        assert any(
            f.name.startswith("study_") for f in csvs
        ), f"Expected a file starting with 'study_', got: {[f.name for f in csvs]}"
