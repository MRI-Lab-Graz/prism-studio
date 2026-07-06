"""Tests for the DataLad `save` step after recipe scoring.

Recipe scoring runs in-process as before; the only DataLad-aware addition
is a scoped `datalad save` at the end when the project is DataLad-tracked
(see src/recipes_surveys.py). This deliberately avoids `datalad run` -
see the module docstring context in the roadmap for why.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from src.recipes_surveys import compute_survey_recipes


def _setup_minimal_project(tmp_path: Path, task_name: str = "test") -> tuple[Path, Path]:
    """Create a minimal PRISM project with one survey file and recipe."""
    project_root = tmp_path / "project"
    recipe_dir = tmp_path / "recipes"

    survey_dir = project_root / "sub-001" / "ses-1" / "survey"
    survey_dir.mkdir(parents=True)
    survey_tsv = survey_dir / f"sub-001_ses-1_task-{task_name}_survey.tsv"
    survey_tsv.write_text("Q1\n5\n", encoding="utf-8")

    recipe_dir.mkdir(parents=True)
    (recipe_dir / f"recipe-{task_name}.json").write_text(
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

    return project_root, recipe_dir


def test_compute_survey_recipes_skips_datalad_for_plain_project(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A project with no .datalad/ marker never touches DataLad at all."""
    project_root, recipe_dir = _setup_minimal_project(tmp_path)

    def _fail_if_called(*args, **kwargs):
        raise AssertionError("resolve_datalad_executable should not be called")

    monkeypatch.setattr(
        "src.recipes_surveys.resolve_datalad_executable", _fail_if_called
    )

    result = compute_survey_recipes(
        prism_root=project_root,
        repo_root=tmp_path,
        recipe_dir=recipe_dir,
        modality="survey",
        out_format="csv",
    )

    assert result.out_root.exists()


def test_compute_survey_recipes_calls_datalad_save_when_tracked(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A DataLad-tracked project gets a scoped `datalad save` after scoring."""
    project_root, recipe_dir = _setup_minimal_project(tmp_path)
    (project_root / ".datalad").mkdir(parents=True)

    monkeypatch.setattr(
        "src.recipes_surveys.resolve_datalad_executable", lambda: "datalad"
    )

    captured_commands: list[list[str]] = []

    def _fake_run(command, cwd=None, capture_output=True, text=True, timeout=None, check=False):
        captured_commands.append(list(command))

        class _Proc:
            returncode = 0
            stdout = ""
            stderr = ""

        return _Proc()

    monkeypatch.setattr("src.datalad_execution.subprocess.run", _fake_run)

    result = compute_survey_recipes(
        prism_root=project_root,
        repo_root=tmp_path,
        recipe_dir=recipe_dir,
        modality="survey",
        out_format="csv",
    )

    assert len(captured_commands) == 1
    save_command = captured_commands[0]
    assert save_command[:2] == ["datalad", "save"]
    assert "-m" in save_command
    message_index = save_command.index("-m") + 1
    assert "recipes" in save_command[message_index]
    # Scoped to the paths this run actually touched (derivative output +
    # seeded recipe copy), not an unscoped whole-dataset save.
    relative_out_root = str(result.out_root.relative_to(project_root))
    assert relative_out_root in save_command
    assert str(Path("code") / "recipes" / "survey") in save_command
    assert "." not in save_command


def test_compute_survey_recipes_raises_when_datalad_tracked_but_missing_tool(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """DataLad-tracked project with no datalad executable fails loudly, not silently."""
    project_root, recipe_dir = _setup_minimal_project(tmp_path)
    (project_root / ".datalad").mkdir(parents=True)

    monkeypatch.setattr(
        "src.recipes_surveys.resolve_datalad_executable", lambda: None
    )

    with pytest.raises(ValueError, match="require DataLad"):
        compute_survey_recipes(
            prism_root=project_root,
            repo_root=tmp_path,
            recipe_dir=recipe_dir,
            modality="survey",
            out_format="csv",
        )
