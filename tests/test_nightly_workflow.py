"""The full test suite runs once a night, not on every change, and a failure is reported."""

import re
from pathlib import Path

WORKFLOW = Path(__file__).resolve().parents[1] / ".github" / "workflows" / "nightly.yml"


def _text() -> str:
    assert WORKFLOW.is_file(), "the nightly workflow is missing"
    return WORKFLOW.read_text(encoding="utf-8")


def _triggers(text: str) -> str:
    return text.split("\njobs:")[0]


def test_it_runs_on_a_schedule_and_by_hand_but_never_per_push_or_pull_request():
    triggers = _triggers(_text())
    assert re.search(r"^\s+schedule:\s*$", triggers, re.M)
    assert "cron:" in triggers
    assert "workflow_dispatch" in triggers
    assert not re.search(r"^\s+(push|pull_request):", triggers, re.M)


def test_it_runs_both_test_suites_including_the_browser_tests():
    text = _text()
    assert "pytest tests/" in text  # includes tests/e2e
    assert "playwright install" in text
    assert "vitest run" in text  # the JavaScript unit tests


def test_a_failed_first_run_is_retried_once_for_the_failures_only_to_tell_flakes_from_real_failures():
    text = _text()
    assert "--last-failed" in text
    assert "--last-failed-no-failures none" in text  # a run that failed without a failing test stays failed


def test_a_failure_opens_or_updates_one_issue_instead_of_piling_up():
    text = _text()
    assert "if: failure()" in text
    assert "issues: write" in text
    assert "nightly-failure" in text
    assert "gh issue comment" in text and "gh issue create" in text
