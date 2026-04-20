#!/usr/bin/env python3
"""Contract tests for prism_tools CLI surface.

These tests lock the public command/option surface so internal refactors can
proceed safely without changing user-facing behavior.
"""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
PRISM_TOOLS_APP = PROJECT_ROOT / "app" / "prism_tools.py"


def _run_cli(*args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(PRISM_TOOLS_APP), *args],
        capture_output=True,
        text=True,
        cwd=str(PROJECT_ROOT),
        timeout=20,
    )


def _run_entrypoint_module(*args: str) -> subprocess.CompletedProcess[str]:
    env = os.environ.copy()
    app_path = str(PROJECT_ROOT / "app")
    env["PYTHONPATH"] = (
        app_path
        if not env.get("PYTHONPATH")
        else app_path + os.pathsep + env["PYTHONPATH"]
    )
    return subprocess.run(
        [sys.executable, "-m", "src.cli.entrypoint", *args],
        capture_output=True,
        text=True,
        cwd=str(PROJECT_ROOT),
        timeout=20,
        env=env,
    )


def _assert_help_contains(args: list[str], expected_tokens: list[str]) -> None:
    result = _run_cli(*args)
    output = (result.stdout or "") + "\n" + (result.stderr or "")

    assert result.returncode == 0, (
        f"Expected exit code 0 for {' '.join(args) or '<root>'} --help, "
        f"got {result.returncode}. Output:\n{output}"
    )

    normalized = output.lower()
    for token in expected_tokens:
        assert (
            token.lower() in normalized
        ), f"Missing token '{token}' in help output for {' '.join(args) or '<root>'}."


def test_root_help_lists_primary_command_groups() -> None:
    _assert_help_contains(
        ["--help"],
        [
            "convert",
            "wide-to-long",
            "environment",
            "survey",
            "biometrics",
            "recipes",
            "dataset",
            "library",
            "anonymize",
        ],
    )


def test_entrypoint_module_help_emits_output() -> None:
    result = _run_entrypoint_module("survey", "i18n-autotranslate", "--help")
    output = (result.stdout or "") + "\n" + (result.stderr or "")

    assert result.returncode == 0, output
    assert "--provider" in output
    assert "--source-lang" in output


def test_environment_preview_help_exposes_key_options() -> None:
    _assert_help_contains(
        ["environment", "preview", "--help"],
        [
            "--input",
            "--separator",
            "--json",
        ],
    )


def test_environment_convert_help_exposes_key_options() -> None:
    _assert_help_contains(
        ["environment", "convert", "--help"],
        [
            "--input",
            "--project",
            "--timestamp-col",
            "--participant-col",
            "--session-col",
            "--lat",
            "--lon",
            "--pilot-random-subject",
            "--json",
        ],
    )


def test_participants_help_lists_expected_actions() -> None:
    _assert_help_contains(
        ["participants", "--help"],
        [
            "detect-id",
            "preview",
            "convert",
            "save-mapping",
        ],
    )


def test_participants_convert_help_exposes_dataset_and_mapping_options() -> None:
    _assert_help_contains(
        ["participants", "convert", "--help"],
        [
            "--mode",
            "--project",
            "--extract-from-survey",
            "--extract-from-biometrics",
            "--neurobagel-schema",
            "--force",
        ],
    )


def test_wide_to_long_help_exposes_key_options() -> None:
    _assert_help_contains(
        ["wide-to-long", "--help"],
        [
            "--input",
            "--output",
            "--session-column",
            "--session-indicators",
            "--session-map",
            "--inspect-only",
            "--preview-limit",
        ],
    )


def test_survey_help_lists_expected_actions() -> None:
    _assert_help_contains(
        ["survey", "--help"],
        [
            "import-excel",
            "convert",
            "validate",
            "import-limesurvey",
            "import-limesurvey-batch",
            "i18n-migrate",
            "i18n-build",
        ],
    )


def test_recipes_surveys_help_exposes_key_options() -> None:
    _assert_help_contains(
        ["recipes", "surveys", "--help"],
        [
            "--prism",
            "--repo",
            "--recipes",
            "--format",
            "--layout",
            "--include-raw",
            "--boilerplate",
        ],
    )


def test_biometrics_import_excel_help_exposes_key_options() -> None:
    _assert_help_contains(
        ["biometrics", "import-excel", "--help"],
        [
            "--excel",
            "--output",
            "--library-root",
            "--sheet",
            "--equipment",
            "--supervisor",
        ],
    )


def test_dataset_smoketest_help_exposes_key_options() -> None:
    _assert_help_contains(
        ["dataset", "build-biometrics-smoketest", "--help"],
        [
            "--codebook",
            "--data",
            "--output",
            "--library-root",
            "--session",
            "--equipment",
        ],
    )


def test_biometrics_detect_help_exposes_key_options() -> None:
    _assert_help_contains(
        ["biometrics", "detect", "--help"],
        ["--input", "--library", "--sheet", "--json"],
    )


def test_biometrics_convert_help_exposes_key_options() -> None:
    _assert_help_contains(
        ["biometrics", "convert", "--help"],
        [
            "--input",
            "--library",
            "--output",
            "--id-column",
            "--session",
            "--tasks",
            "--unknown",
        ],
    )


def test_physio_batch_convert_help_exposes_key_options() -> None:
    _assert_help_contains(
        ["physio", "batch-convert", "--help"],
        ["--input", "--output", "--modality", "--sampling-rate", "--dry-run"],
    )


def test_root_help_lists_physio_command_group() -> None:
    _assert_help_contains(["--help"], ["physio"])
