"""--bids must fail closed: no runnable BIDS engine is an ERROR, not a warning (#162)."""

import os
import sys
from types import SimpleNamespace

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(__file__)), "app", "src"))

import bids_validator
from src.core.validation import determine_exit_code, normalize_issues

ENGINE = "/fake/bin/bids-validator-deno"


def _assert_fails_closed(issues):
    errors = [i for i in issues if i[0] == "ERROR" and i[1].startswith("PRISM902")]
    assert errors, issues
    normalized = normalize_issues(issues)
    assert any(i.code == "PRISM902" for i in normalized)
    assert determine_exit_code(normalized) == 1


def _engine(monkeypatch, run):
    monkeypatch.setattr(bids_validator, "find_bids_engine", lambda: ENGINE)
    monkeypatch.setattr(bids_validator, "bids_engine_version", lambda: "3.0.2")
    monkeypatch.setattr(bids_validator.subprocess, "run", run)


def test_engine_not_found_is_an_error_that_names_the_fix(monkeypatch, tmp_path):
    monkeypatch.setattr(bids_validator, "find_bids_engine", lambda: None)
    issues = bids_validator.run_bids_validator(str(tmp_path))
    _assert_fails_closed(issues)
    assert "bids-validator-deno" in issues[0][1] and "--no-bids" in issues[0][1]


def test_engine_without_output_is_an_error_and_keeps_stderr(monkeypatch, tmp_path):
    _engine(monkeypatch, lambda cmd, **kw: SimpleNamespace(stdout="", stderr="boom", returncode=1))
    issues = bids_validator.run_bids_validator(str(tmp_path))
    _assert_fails_closed(issues)
    assert any("boom" in i[1] for i in issues)


def test_unparseable_output_is_an_error(monkeypatch, tmp_path):
    _engine(monkeypatch, lambda cmd, **kw: SimpleNamespace(stdout="not json", stderr="", returncode=0))
    _assert_fails_closed(bids_validator.run_bids_validator(str(tmp_path)))


def test_engine_that_cannot_be_started_is_an_error(monkeypatch, tmp_path):
    def run(cmd, **kw):
        raise OSError("exec format error")

    _engine(monkeypatch, run)
    issues = bids_validator.run_bids_validator(str(tmp_path))
    _assert_fails_closed(issues)
    assert any("exec format error" in i[1] for i in issues)


import json  # noqa: E402

import pytest  # noqa: E402

ERR = {"issues": {"issues": [{"code": "X", "severity": "error", "location": "/a"}]}}
WARN = {"issues": {"issues": [{"code": "X", "severity": "warning", "location": "/a"}]}}
EMPTY = {"issues": {"issues": []}}


def _report(monkeypatch, stdout, returncode):
    _engine(
        monkeypatch,
        lambda cmd, **kw: SimpleNamespace(stdout=json.dumps(stdout), stderr="", returncode=returncode),
    )


@pytest.mark.parametrize(
    "report,rc",
    [
        ({}, 0),
        ({}, 1),
        ([], 0),
        ({"summary": {}}, 0),
        ({"issues": {"issues": "x"}}, 0),
        (EMPTY, 16),
        (EMPTY, 137),
        (WARN, 16),
        (ERR, 0),
        (ERR, 137),
    ],
)
def test_inconsistent_report_or_exit_code_fails_closed(monkeypatch, tmp_path, report, rc):
    _report(monkeypatch, report, rc)
    issues = bids_validator.run_bids_validator(str(tmp_path))
    _assert_fails_closed(issues)
    assert "--no-bids" in issues[-1][1]


@pytest.mark.parametrize("report,rc", [(ERR, 16), (WARN, 0), (EMPTY, 0)])
def test_consistent_reports_are_not_failures(monkeypatch, tmp_path, report, rc):
    _report(monkeypatch, report, rc)
    issues = bids_validator.run_bids_validator(str(tmp_path))
    assert not any(i[1].startswith("PRISM902") for i in issues)


def test_all_errors_filtered_away_is_still_consistent(monkeypatch, tmp_path):
    report = {"issues": {"issues": [{"code": "JSON_KEY_RECOMMENDED", "severity": "error", "location": "/a"}]}}
    _report(monkeypatch, report, 16)
    assert bids_validator.run_bids_validator(str(tmp_path)) == []


def test_engine_timeout_is_an_error(monkeypatch, tmp_path):
    def run(cmd, **kw):
        raise bids_validator.subprocess.TimeoutExpired(cmd, kw["timeout"])

    _engine(monkeypatch, run)
    issues = bids_validator.run_bids_validator(str(tmp_path))
    _assert_fails_closed(issues)
    assert "30 minutes" in issues[-1][1]


def test_engine_runs_without_colour_in_utf8_with_a_timeout(monkeypatch, tmp_path):
    seen = {}

    def run(cmd, **kw):
        seen.update(kw)
        return SimpleNamespace(stdout=json.dumps(EMPTY), stderr="", returncode=0)

    _engine(monkeypatch, run)
    bids_validator.run_bids_validator(str(tmp_path))
    assert seen["env"]["NO_COLOR"] == "1"
    assert seen["encoding"] == "utf-8" and seen["errors"] == "replace"
    assert seen["timeout"] == bids_validator.BIDS_ENGINE_TIMEOUT_SECONDS == 1800
    assert "text" not in seen
