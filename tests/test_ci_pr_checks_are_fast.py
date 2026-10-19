"""Pushes and pull requests get the fast checks; the full suite (browser tests, all systems) runs nightly.

The required checks on main are "Pytest (<os>)" for ubuntu, windows and macos, so those jobs still
report on every pull request, they just skip the slow browser tests.
"""

import re
from pathlib import Path

import yaml

WORKFLOWS = Path(__file__).resolve().parents[1] / ".github" / "workflows"


def _load(name):
    return yaml.safe_load((WORKFLOWS / name).read_text(encoding="utf-8"))


def _runs(job):
    return [str(step.get("run", "")) for step in job.get("steps", [])]


def _on_push_or_pr(job):
    condition = str(job.get("if", ""))
    return not condition or "push" in condition or "pull_request" in condition


def test_pull_request_jobs_install_no_browser_and_run_no_browser_tests():
    jobs = _load("ci.yml")["jobs"]
    offenders = []
    for name, job in jobs.items():
        if not _on_push_or_pr(job):
            continue
        for run in _runs(job):
            if "playwright install" in run:
                offenders.append(f"{name}: installs a browser")
            if re.search(r"pytest tests/(\s|$)", run) and "--ignore=tests/e2e" not in run:  # the whole suite
                offenders.append(f"{name}: runs the browser tests")
    assert not offenders, offenders


def test_the_required_pytest_checks_still_report_on_every_pull_request():
    job = _load("ci.yml")["jobs"]["cross-platform-tests"]
    assert job["name"] == "Pytest (${{ matrix.os }})"
    assert set(job["strategy"]["matrix"]["os"]) == {"ubuntu-latest", "windows-latest", "macos-latest"}
    assert _on_push_or_pr(job)


def test_coverage_is_one_upload_from_the_ubuntu_run_not_a_second_full_run():
    jobs = _load("ci.yml")["jobs"]
    assert "coverage" not in jobs
    text = (WORKFLOWS / "ci.yml").read_text(encoding="utf-8")
    assert "--cov=src" in text and "codecov/codecov-action" in text


def test_the_nightly_run_covers_windows_and_macos_with_the_browser_tests():
    job = _load("nightly.yml")["jobs"]["full-suite"]
    matrix = job["strategy"]["matrix"]
    systems = set(matrix.get("os", [])) | {entry.get("os") for entry in matrix.get("include", [])}
    assert {"windows-latest", "macos-latest"} <= systems
    assert job["defaults"]["run"]["shell"] == "bash"  # the steps are bash on every system
