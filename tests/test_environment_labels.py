"""Environment rows get BIDS-safe subject/session labels (no folders from slashes) and say so."""

import csv
import sys

import pytest

import src.environment_conversion as env


@pytest.mark.parametrize("raw,prefix,expected", [
    ("P1", "sub", "sub-P1"), ("sub-P2", "sub", "sub-P2"), ("P 3", "sub", "sub-P3"), ("P/4", "sub", "sub-P4"),
    ("../x", "sub", "sub-x"), ("ünï", "sub", "sub-n"), ("1", "ses", "ses-1"), ("01", "ses", "ses-01"),
    ("pre test", "ses", "ses-pretest"), ("ses-2", "ses", "ses-2"), ("n/a", "sub", ""), ("///", "sub", ""), ("", "ses", ""),
])
def test_bids_label_keeps_ascii_letters_and_digits_only(raw, prefix, expected):
    assert env._bids_label(raw, prefix) == expected


def _convert(tmp_path, monkeypatch, rows, **kw):
    for name in ("_fetch_environment_day", "_fetch_environment_hour"):
        monkeypatch.setattr(env, name, lambda *a, **k: {})
    monkeypatch.setattr(env, "_geocode_location", lambda *a, **k: None)
    project = tmp_path / "p"
    project.mkdir()
    (project / "project.json").write_text("{}")
    src = tmp_path / "env.csv"
    src.write_text("pid,ses,ts,lat,lon\n" + "".join(",".join(f'"{c}"' for c in r) + "\n" for r in rows))
    logs: list[str] = []
    args = dict(
        input_path=src, filename="env.csv", suffix=".csv", separator_option="comma", timestamp_col="ts",
        participant_col="pid", participant_override=None, session_col="ses", session_override=None,
        location_col=None, lat_col="lat", lon_col="lon", location_label_override="", lat_manual=None,
        lon_manual=None, project_path=str(project), pilot_random_subject=False,
        log_callback=lambda message, level="info": logs.append(message),
    )
    args.update(kw)
    env.perform_environment_conversion(**args)
    return project, logs


def test_hostile_ids_never_make_nested_or_escaping_folders_and_the_cleaning_is_reported(tmp_path, monkeypatch):
    rows = [("P 1", "pre test", "2025-03-04 10:00", "47.1", "15.4"), ("../evil", "1", "2025-03-04 11:00", "47.1", "15.4"),
            ("a/b", "", "2025-03-04 12:00", "47.1", "15.4")]
    project, logs = _convert(tmp_path, monkeypatch, rows)

    folders = sorted(p.name for p in project.glob("sub-*"))
    assert folders == ["sub-P1", "sub-ab", "sub-evil"]
    assert not (tmp_path / "evil").exists() and not list(tmp_path.glob("sub-*"))
    assert sorted(p.name for p in project.glob("sub-P1/*")) == ["ses-pretest"]
    assert sorted(p.name for p in project.glob("sub-ab/*")) == ["ses-1"]  # no session given: the usual default
    text = " ".join(logs)
    assert "'P 1' → sub-P1" in text and "'pre test' → ses-pretest" in text


def test_slash_dates_that_could_be_day_first_are_reported(tmp_path, monkeypatch):
    rows = [("P1", "1", "03/04/2025 10:00", "47.1", "15.4"), ("P1", "1", "2025-03-04 11:00", "47.1", "15.4"),
            ("P1", "1", "13/04/2025 10:00", "47.1", "15.4")]
    _, logs = _convert(tmp_path, monkeypatch, rows)
    assert any("month/day" in m and "1 timestamp" in m for m in logs), logs
