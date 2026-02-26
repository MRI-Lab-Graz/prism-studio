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


def _assert_help_contains(args: list[str], expected_tokens: list[str]) -> None:
    result = _run_cli(*args)
    output = (result.stdout or "") + "\n" + (result.stderr or "")

    assert result.returncode == 0, (
        f"Expected exit code 0 for {' '.join(args) or '<root>'} --help, "
        f"got {result.returncode}. Output:\n{output}"
    )

    normalized = output.lower()
    for token in expected_tokens:
        assert token.lower() in normalized, (
            f"Missing token '{token}' in help output for {' '.join(args) or '<root>'}."
        )


def test_root_help_lists_primary_command_groups() -> None:
    _assert_help_contains(
        ["--help"],
        [
            "convert",
            "survey",
            "biometrics",
            "recipes",
            "dataset",
            "library",
            "anonymize",
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
