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
