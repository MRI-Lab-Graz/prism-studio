"""Tests for the explicit core validation boundary."""

import os
import sys
from types import SimpleNamespace
from enum import Enum

# Add app/src to path for testing
sys.path.insert(
    0, os.path.join(os.path.dirname(os.path.dirname(__file__)), "app", "src")
)

from core.validation import determine_exit_code, build_validation_report


class Severity(Enum):
    ERROR = "ERROR"
    WARNING = "WARNING"


def test_determine_exit_code_with_tuple_issues():
    issues = [
        ("WARNING", "Minor issue", "/tmp/path"),
        ("ERROR", "Major issue", "/tmp/path"),
    ]
    assert determine_exit_code(issues) == 1


def test_determine_exit_code_with_structured_issues():
    warning_issue = SimpleNamespace(severity=Severity.WARNING)
    assert determine_exit_code([warning_issue]) == 0


def test_build_validation_report_contains_expected_contract_fields():
    stats = SimpleNamespace(
        total_files=5,
        subjects={"sub-01"},
        sessions={"ses-1"},
        tasks={"rest"},
        modalities={"survey": 2},
        surveys={"ads"},
        biometrics=set(),
    )

    issue = ("WARNING", "Test warning", "/tmp/path")
    report = build_validation_report(
        dataset_path=".",
        schema_version="stable",
        structured_issues=[issue],
        stats=stats,
    )

    assert "dataset" in report
    assert report["schema_version"] == "stable"
    assert report["valid"] is True
    assert "summary" in report
    assert "issues" in report
    assert "statistics" in report
    assert report["statistics"]["total_files"] == 5
