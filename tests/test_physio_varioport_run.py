"""One place decides when a Varioport conversion is retried with the multiplexed decoder."""

from pathlib import Path

import pytest

from src.physio_varioport import run_varioport_conversion


def _run(convert, **kw):
    logs = []
    run_varioport_conversion(
        convert, Path("a.raw"), Path("a.edf"), Path("a.json"), task="rest", sampling_rate=256.0, log_fn=logs.append, **kw
    )
    return logs


def test_a_plain_conversion_runs_once():
    calls = []
    assert _run(lambda *a, **k: calls.append(k)) == []
    assert calls == [{"task_name": "rest", "base_freq": 256.0}]


def test_an_unsupported_header_is_retried_with_the_multiplexed_decoder_and_says_so():
    calls = []

    def convert(*args, **kwargs):
        calls.append(kwargs)
        if len(calls) == 1:
            raise ValueError("Unsupported Varioport header type 7")

    logs = _run(convert)
    assert len(calls) == 2 and calls[1]["allow_raw_multiplexed"] is True
    assert "multiplexed" in logs[0]


def test_any_other_error_is_not_retried():
    def convert(*args, **kwargs):
        raise ValueError("file is corrupt")

    with pytest.raises(ValueError, match="corrupt"):
        _run(convert)


def test_the_bids_base_is_passed_on_only_when_given():
    calls = []
    _run(lambda *a, **k: calls.append(k), bids_base=Path("/x"))
    assert calls[0]["bids_base"] == Path("/x")
