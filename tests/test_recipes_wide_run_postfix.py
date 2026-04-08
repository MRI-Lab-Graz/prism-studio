"""Tests for session/run postfix in wide-format recipe output.

When files have a ``run-XX`` BIDS entity in the filename, wide-format output
must produce per-session-per-run columns such as ``Total_ses-1_run-01``.
Without a run entity the existing behaviour (``Total_ses-1``) is preserved.
"""

from pathlib import Path

import pandas as pd
import pytest

from src.recipes_surveys import compute_survey_recipes


# ---------------------------------------------------------------------------
# helpers
# ---------------------------------------------------------------------------


def _write_recipe(path: Path, task_name: str) -> None:
    path.write_text(
        "{\n"
        '  "Kind": "survey",\n'
        '  "RecipeVersion": "1.0",\n'
        f'  "Survey": {{"TaskName": "{task_name}"}},\n'
        '  "Scores": [\n'
        '    {"Name": "Total", "Method": "sum", "Items": ["Q1"]}\n'
        "  ]\n"
        "}\n",
        encoding="utf-8",
    )


def _setup_project_with_runs(
    tmp_path: Path,
    task_name: str = "test",
    runs_per_session: list[str] | None = None,
    sessions: list[str] | None = None,
) -> tuple[Path, Path]:
    """Create a PRISM project where each session has multiple run files."""
    if sessions is None:
        sessions = ["ses-1", "ses-2"]
    if runs_per_session is None:
        runs_per_session = ["run-01", "run-02"]

    project_root = tmp_path / "project"
    recipe_dir = tmp_path / "recipes"

    for ses in sessions:
        survey_dir = project_root / "sub-001" / ses / "survey"
        survey_dir.mkdir(parents=True)
        for run in runs_per_session:
            tsv = survey_dir / f"sub-001_{ses}_{run}_task-{task_name}_survey.tsv"
            tsv.write_text("Q1\n5\n", encoding="utf-8")

    recipe_dir.mkdir(parents=True)
    _write_recipe(recipe_dir / f"recipe-{task_name}.json", task_name)

    return project_root, recipe_dir


def _setup_project_no_runs(
    tmp_path: Path,
    task_name: str = "test",
    sessions: list[str] | None = None,
) -> tuple[Path, Path]:
    """Create a PRISM project with one file per session (no run entity)."""
    if sessions is None:
        sessions = ["ses-1", "ses-2"]

    project_root = tmp_path / "project"
    recipe_dir = tmp_path / "recipes"

    for ses in sessions:
        survey_dir = project_root / "sub-001" / ses / "survey"
        survey_dir.mkdir(parents=True)
        tsv = survey_dir / f"sub-001_{ses}_task-{task_name}_survey.tsv"
        tsv.write_text("Q1\n5\n", encoding="utf-8")

    recipe_dir.mkdir(parents=True)
    _write_recipe(recipe_dir / f"recipe-{task_name}.json", task_name)

    return project_root, recipe_dir


# ---------------------------------------------------------------------------
# tests
# ---------------------------------------------------------------------------


class TestWideRunPostfix:
    """Run entity in filename produces session_run composite column names."""

    def test_wide_columns_include_run_postfix(self, tmp_path: Path) -> None:
        """Wide output has columns like Total_ses-1_run-01, Total_ses-1_run-02."""
        project_root, recipe_dir = _setup_project_with_runs(tmp_path)

        result = compute_survey_recipes(
            prism_root=project_root,
            repo_root=tmp_path,
            recipe_dir=recipe_dir,
            modality="survey",
            out_format="csv",
            layout="wide",
            lang="en",
        )

        assert result.processed_files > 0, "No files were processed"
        out_files = list(result.out_root.glob("*.csv"))
        assert out_files, "No CSV output produced"

        df = pd.read_csv(out_files[0], dtype=str)
        score_cols = [c for c in df.columns if c != "participant_id"]
        # Each combination of session × run should give a separate column
        expected = {
            "Total_ses-1_run-01",
            "Total_ses-1_run-02",
            "Total_ses-2_run-01",
            "Total_ses-2_run-02",
        }
        assert expected <= set(score_cols), (
            f"Expected columns {expected} but got {sorted(score_cols)}"
        )

    def test_wide_no_run_preserves_session_only_postfix(self, tmp_path: Path) -> None:
        """Without run entity, wide output has columns like Total_ses-1 (no _run-XX)."""
        project_root, recipe_dir = _setup_project_no_runs(tmp_path)

        result = compute_survey_recipes(
            prism_root=project_root,
            repo_root=tmp_path,
            recipe_dir=recipe_dir,
            modality="survey",
            out_format="csv",
            layout="wide",
            lang="en",
        )

        out_files = list(result.out_root.glob("*.csv"))
        assert out_files, "No CSV output produced"

        df = pd.read_csv(out_files[0], dtype=str)
        score_cols = [c for c in df.columns if c != "participant_id"]
        # Must have session-only columns; must NOT have _run- in any column
        assert any("Total_ses-" in c for c in score_cols), (
            f"Expected Total_ses-* columns but got {sorted(score_cols)}"
        )
        assert not any("_run-" in c for c in score_cols), (
            f"Unexpected _run- suffix in columns: {sorted(score_cols)}"
        )

    def test_long_layout_with_run_has_run_column(self, tmp_path: Path) -> None:
        """Long-format output includes a 'run' column when files have run entities."""
        project_root, recipe_dir = _setup_project_with_runs(
            tmp_path, sessions=["ses-1"], runs_per_session=["run-01", "run-02"]
        )

        result = compute_survey_recipes(
            prism_root=project_root,
            repo_root=tmp_path,
            recipe_dir=recipe_dir,
            modality="survey",
            out_format="csv",
            layout="long",
            lang="en",
        )

        out_files = list(result.out_root.glob("*.csv"))
        assert out_files, "No CSV output produced"

        df = pd.read_csv(out_files[0], dtype=str)
        assert "run" in df.columns, (
            f"Expected 'run' column in long output but got: {list(df.columns)}"
        )
        assert set(df["run"].tolist()) == {"run-01", "run-02"}

    def test_infer_run_from_path(self, tmp_path: Path) -> None:
        """_infer_run_from_path extracts run entity from filename stem."""
        from src.recipes_surveys import _infer_run_from_path

        p_with_run = tmp_path / "sub-01" / "ses-1" / "survey" / "sub-01_ses-1_run-02_task-foo_survey.tsv"
        assert _infer_run_from_path(p_with_run) == "run-02"

        p_no_run = tmp_path / "sub-01" / "ses-1" / "survey" / "sub-01_ses-1_task-foo_survey.tsv"
        assert _infer_run_from_path(p_no_run) is None
