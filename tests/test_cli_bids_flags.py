"""The command line runs the BIDS check by default; --no-bids skips it (spec 2026-10-07)."""

import inspect
import json
import os
import sys

import pytest

APP = os.path.join(os.path.dirname(os.path.dirname(__file__)), "app")
sys.path.insert(0, APP)
sys.path.insert(0, os.path.join(APP, "src"))

import prism  # noqa: E402
from stats import DatasetStats  # noqa: E402


@pytest.fixture
def seen(monkeypatch):
    calls = {}

    def spy(dataset, **kwargs):
        calls.update(kwargs)
        return [], DatasetStats()

    monkeypatch.setattr(prism, "validate_dataset", spy)
    return calls


def run(monkeypatch, tmp_path, *flags, config=None):
    if config is not None:
        (tmp_path / ".prismrc.json").write_text(json.dumps(config), encoding="utf-8")
    monkeypatch.setattr(sys, "argv", ["prism", str(tmp_path), "--json", *flags])
    with pytest.raises(SystemExit) as exc:
        prism.main()
    return exc.value.code


def test_bids_runs_by_default(monkeypatch, tmp_path, seen):
    run(monkeypatch, tmp_path)
    assert seen["run_bids"] is True and seen["run_prism"] is True


def test_no_bids_skips_it(monkeypatch, tmp_path, seen):
    run(monkeypatch, tmp_path, "--no-bids")
    assert seen["run_bids"] is False and seen["run_prism"] is True


def test_bids_flag_is_still_accepted(monkeypatch, tmp_path, seen):
    run(monkeypatch, tmp_path, "--bids")
    assert seen["run_bids"] is True


def test_config_can_turn_it_off_and_the_flag_turns_it_back_on(monkeypatch, tmp_path, seen):
    run(monkeypatch, tmp_path, config={"runBids": False})
    assert seen["run_bids"] is False
    seen.clear()
    run(monkeypatch, tmp_path, "--bids", config={"runBids": False})
    assert seen["run_bids"] is True


def test_bids_and_no_bids_together_are_a_usage_error(monkeypatch, tmp_path, seen):
    assert run(monkeypatch, tmp_path, "--bids", "--no-bids") == 2
    assert not seen


def test_a_run_with_no_checks_is_an_error_never_valid(monkeypatch, tmp_path, seen, capsys):
    assert run(monkeypatch, tmp_path, "--no-bids", "--no-prism") == 2
    assert run(monkeypatch, tmp_path, "--no-prism", config={"runBids": False}) == 2
    assert not seen
    assert "no checks" in capsys.readouterr().err.lower()


def test_library_default_and_studio_callers_are_untouched():
    from runner import validate_dataset

    assert inspect.signature(validate_dataset).parameters["run_bids"].default is False
