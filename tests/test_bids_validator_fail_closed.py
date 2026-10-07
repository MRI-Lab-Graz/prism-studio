"""--bids must fail closed: no runnable BIDS validator is an ERROR, not a warning (#162)."""

import os
import subprocess
import sys
from types import SimpleNamespace

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(__file__)), "app", "src"))

import bids_validator
from src.core.validation import determine_exit_code, normalize_issues


def _assert_fails_closed(issues):
    errors = [i for i in issues if i[0] == "ERROR" and i[1].startswith("PRISM902")]
    assert errors, issues
    normalized = normalize_issues(issues)
    assert any(i.code == "PRISM902" for i in normalized)
    assert determine_exit_code(normalized) == 1


def test_no_validator_installed_is_an_error(monkeypatch, tmp_path):
    def fake_run(cmd, **kw):
        raise FileNotFoundError(cmd[0])

    monkeypatch.setattr(bids_validator.subprocess, "run", fake_run)
    _assert_fails_closed(bids_validator.run_bids_validator(str(tmp_path)))


def test_deno_without_output_and_no_legacy_cli_is_an_error(monkeypatch, tmp_path):
    def fake_run(cmd, **kw):
        if cmd[0] == "deno":
            return SimpleNamespace(stdout="", stderr="boom", returncode=1)
        raise FileNotFoundError(cmd[0])

    monkeypatch.setattr(bids_validator.subprocess, "run", fake_run)
    issues = bids_validator.run_bids_validator(str(tmp_path))
    _assert_fails_closed(issues)
    assert any("boom" in i[1] for i in issues)  # Deno failure detail kept


def test_legacy_unparseable_output_with_nonzero_exit_is_an_error(monkeypatch, tmp_path):
    def fake_run(cmd, **kw):
        if cmd[0] == "deno":
            return SimpleNamespace(stdout="", stderr="boom", returncode=1)
        return SimpleNamespace(stdout="not json", stderr="bad", returncode=1)

    monkeypatch.setattr(bids_validator.subprocess, "run", fake_run)
    _assert_fails_closed(bids_validator.run_bids_validator(str(tmp_path)))
