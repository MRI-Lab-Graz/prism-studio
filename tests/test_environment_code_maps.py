"""Environment import uses the project's code maps (invented codes only)."""

import json

import pytest

import src.environment_conversion as env
from src.code_maps import CodeMapError, UnknownCodeError

PROJECT = json.dumps({"StudyDesign": {"Timepoints": "multiple"}})


def _run(tmp_path, monkeypatch, rows, maps, **kw):
    requests: list = []
    monkeypatch.setattr(env, "_fetch_environment_day", lambda *a, **k: (requests.append(a), ({"weather": {}, "air": {}, "pollen": {}}, []))[1])
    monkeypatch.setattr(env, "_geocode_location", lambda *a, **k: None)
    project = tmp_path / "p"
    (project / "code").mkdir(parents=True)
    (project / "project.json").write_text(PROJECT)
    (project / "code" / "session_map.json").write_text(json.dumps({"pre": "1", "post": "2"}))
    for name, entries in maps.items():
        (project / "code" / name).write_text("code\tparticipant_id\n" + "".join(f"{c}\t{p}\n" for c, p in entries))
    src = tmp_path / "env.csv"
    src.write_text("pid,ses,ts,lat,lon\n" + "".join(f"{pid},{ses},2025-03-04 1{n}:00,47.1,15.4\n" for n, (pid, ses) in enumerate(rows)))
    logs: list[str] = []
    args = dict(
        input_path=src, filename="env.csv", suffix=".csv", separator_option="comma", timestamp_col="ts",
        participant_col="pid", participant_override=None, session_col="ses", session_override=None,
        location_col=None, lat_col="lat", lon_col="lon", location_label_override="", lat_manual=None,
        lon_manual=None, project_path=str(project), pilot_random_subject=False,
        log_callback=lambda message, level="info": logs.append(message),
    )
    args.update(kw)
    try:
        env.perform_environment_conversion(**args)
    except CodeMapError:
        assert not list(project.glob("sub-*")) and requests == [], "a stopped run writes and requests nothing"
        raise
    return project, " ".join(logs)


def folders(project):
    return sorted(p.relative_to(project).as_posix() for p in project.glob("sub-*/ses-*"))


GENERAL = {"environment_code_map.tsv": [("QQAA", "sub-001")]}


def test_general_and_session_maps_and_no_code_anywhere(tmp_path, monkeypatch):
    maps = {**GENERAL, "environment_ses-2_code_map.tsv": [("QQAA", "sub-002")]}
    project, log = _run(tmp_path, monkeypatch, [("qqaa", "pre"), ("qqaa", "post")], maps)
    assert folders(project) == ["sub-001/ses-1", "sub-002/ses-2"]
    assert "Applied code map environment_code_map.tsv: 1 code(s)." in log
    assert "qqaa" not in log.lower()
    assert not any(
        "qqaa" in p.read_text(errors="ignore").lower()
        for p in project.rglob("*") if p.is_file() and "code_map" not in p.name
    )


@pytest.mark.parametrize("rows", [[("QQAA", "pre"), ("QQBB", "pre")], [("QQAA", "pre"), ("", "pre")]])
def test_an_unlisted_or_empty_cell_stops(tmp_path, monkeypatch, rows):
    with pytest.raises(CodeMapError):
        _run(tmp_path, monkeypatch, rows, GENERAL)


def test_an_unfilled_map_stops(tmp_path, monkeypatch):
    with pytest.raises(UnknownCodeError):
        _run(tmp_path, monkeypatch, [("QQAA", "pre")], {"environment_code_map.tsv": []})


def test_pilot_picks_a_mapped_participant(tmp_path, monkeypatch):
    project, log = _run(tmp_path, monkeypatch, [("QQAA", "pre")], GENERAL, pilot_random_subject=True)
    assert folders(project) == ["sub-001/ses-1"]
    assert "qqaa" not in log.lower()


def test_a_typed_participant_fills_an_empty_cell(tmp_path, monkeypatch):
    project, _ = _run(tmp_path, monkeypatch, [("", "pre")], GENERAL, participant_override="007")
    assert folders(project) == ["sub-007/ses-1"]
