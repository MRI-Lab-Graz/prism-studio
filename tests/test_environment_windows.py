"""Environment time windows of any duration (src/environment_windows.py + the converter)."""

from __future__ import annotations

import csv
import json
import sys
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[1]
if str(REPO / "app") not in sys.path:
    sys.path.insert(0, str(REPO / "app"))

import src.environment_conversion as ec
from src.environment_windows import (
    WINDOW_COLUMNS,
    WindowSpec,
    compute_window,
    duration_to_timedelta,
    missing_hours,
    parse_window,
    window_column_name,
)


def test_parse_window_ok():
    assert parse_window("temp_c:P3D:max") == WindowSpec("temp_c", "P3D", "max")
    assert window_column_name(parse_window("temp_c:P3D:max")) == "temp_c_max_p3d"


@pytest.mark.parametrize("text,needle", [
    ("temp_c:3d:max", "duration"),
    ("temp_c:P1M:max", "fixed length"),
    ("temp_c:P1Y:max", "fixed length"),
    ("temp_c:P1D:median", "statistic"),
    ("foo:P1D:max", "foo"),
    ("temp_c:P1D", "VAR:DURATION:STAT"),
])
def test_parse_window_refuses(text, needle):
    with pytest.raises(ValueError, match=needle):
        parse_window(text)


def test_duration_to_timedelta_fixed_units():
    assert duration_to_timedelta("P1W") == timedelta(weeks=1)
    assert duration_to_timedelta("P1DT6H30M15S") == timedelta(days=1, hours=6, minutes=30, seconds=15)
    assert duration_to_timedelta("PT0S") == timedelta(0)


def test_window_columns_are_hourly_numeric_provider_columns():
    assert {"temp_c", "pm25_ug_m3", "pollen_birch"} <= set(WINDOW_COLUMNS)
    assert "heatwave_status" not in WINDOW_COLUMNS and "pollen_risk_bin" not in WINDOW_COLUMNS


def _series(start: datetime, hours: int, value) -> dict:
    return {(start + timedelta(hours=h)).strftime("%Y-%m-%dT%H:00"): value(h) for h in range(hours)}


def test_compute_window_max():
    hourly = _series(datetime(2025, 6, 1), 4 * 24, lambda h: float(h % 24))
    hourly["2025-06-03T15:00"] = 40.0
    hourly["2025-06-01T09:00"] = 99.0  # before the 3-day window
    end = datetime(2025, 6, 4, 10, 0)
    assert compute_window(hourly, end, WindowSpec("temp_c", "P3D", "max")) == 40.0
    assert compute_window(hourly, end, WindowSpec("temp_c", "PT2H", "min")) == 9.0
    assert compute_window(hourly, end, WindowSpec("temp_c", "PT2H", "mean")) == 9.5
    aware = end.replace(tzinfo=timezone(timedelta(hours=2)))  # provider hours are local wall-clock
    assert compute_window(hourly, aware, WindowSpec("temp_c", "PT2H", "mean")) == 9.5


# The window is half-open (end - duration, end] on the session's hour: start hour out, session hour in.
@pytest.mark.parametrize("minute", [0, 30])
def test_p1d_window_holds_exactly_24_hours(minute):
    hourly = _series(datetime(2025, 6, 1), 3 * 24, lambda h: 1.0)
    end = datetime(2025, 6, 2, 10, minute)
    assert compute_window(hourly, end, WindowSpec("temp_c", "P1D", "count")) == 24
    assert missing_hours(hourly, end, WindowSpec("temp_c", "P1D", "count")) == 0


def test_pt3h_sum_on_the_hour_sums_three_values():
    hourly = _series(datetime(2025, 6, 1), 24, lambda h: float(h))
    assert compute_window(hourly, datetime(2025, 6, 1, 10), WindowSpec("temp_c", "PT3H", "sum")) == 8.0 + 9.0 + 10.0


def test_missing_hours_counts_the_whole_window():
    hourly = _series(datetime(2025, 6, 1), 4 * 24, lambda h: 1.0)
    for h in range(24):  # a failed middle day
        del hourly[f"2025-06-02T{h:02d}:00"]
    hourly["2025-06-03T05:00"] = None  # a None value is missing too
    end = datetime(2025, 6, 4, 10)
    assert missing_hours(hourly, end, WindowSpec("temp_c", "P3D", "mean")) == 25
    assert missing_hours(hourly, end, WindowSpec("temp_c", "PT6H", "mean")) == 0
    # a failed day at the window's edge counts only its hours inside the window: (06-01 22:00, 06-02 10:00]
    assert missing_hours(hourly, datetime(2025, 6, 2, 10), WindowSpec("temp_c", "PT12H", "mean")) == 11


def test_spring_forward_hour_is_not_missing():
    # 2025-03-30: local clocks jump 02:00 -> 03:00, so the provider timeline has no 02:00 that day
    hourly = _series(datetime(2025, 3, 29), 3 * 24, lambda h: 1.0)
    del hourly["2025-03-30T02:00"]
    end = datetime(2025, 3, 30, 10)
    spec = WindowSpec("temp_c", "P1D", "count")
    assert missing_hours(hourly, end, spec) == 0
    assert compute_window(hourly, end, spec) == 23


def test_window_crosses_midnight():
    hourly = _series(datetime(2025, 6, 1, 20), 8, lambda h: float(h))  # 20:00 .. 03:00
    hourly["2025-06-02T00:00"] = None  # a gap is skipped
    end = datetime(2025, 6, 2, 1, 30)
    # (22:00, 01:00] covers 23:00 (3.0), 00:00 (gap), 01:00 (5.0)
    assert compute_window(hourly, end, WindowSpec("temp_c", "PT3H", "mean")) == 4.0


def test_compute_window_nothing_left_is_none():
    hourly = _series(datetime(2025, 6, 1), 24, lambda h: None)
    assert compute_window(hourly, datetime(2025, 6, 1, 12), WindowSpec("temp_c", "PT6H", "mean")) is None


# ── Through the converter (provider fetch stubbed, counted) ───────────────────


def _stub_fetch(calls: list, *, value=lambda var, ts: 1.0, air_ok=lambda day: True):
    def fetch(url, params, timeout):
        calls.append((url, params["start_date"], params["end_date"], params["hourly"]))
        start = datetime.fromisoformat(params["start_date"])
        end = datetime.fromisoformat(params["end_date"]) + timedelta(days=1)
        variables = params["hourly"].split(",")
        if "pm2_5" in variables and not air_ok(start.date()):
            return {"hourly": {"time": [], **{v: [] for v in variables}}}
        times = []
        t = start
        while t < end:
            times.append(t.strftime("%Y-%m-%dT%H:00"))
            t += timedelta(hours=1)
        return {"hourly": {"time": times, **{v: [value(v, ts) for ts in times] for v in variables}}}

    return fetch


def _convert(tmp_path, monkeypatch, rows, windows, fetch):
    monkeypatch.setattr(ec, "_fetch_provider_json", fetch)
    project = tmp_path / "project"
    project.mkdir()
    (project / "project.json").write_text(json.dumps({"StudyDesign": {"Timepoints": "single"}}), encoding="utf-8")
    src_dir = tmp_path / "in"
    src_dir.mkdir()
    src = src_dir / "env.csv"
    src.write_text("pid,ts\n" + "".join(f"{p},{t}\n" for p, t in rows), encoding="utf-8")
    logs: list[tuple[str, str]] = []
    result = ec.perform_environment_conversion(
        input_path=src, filename="env.csv", suffix=".csv", separator_option="comma", timestamp_col="ts",
        participant_col="pid", participant_override=None, session_col=None, session_override="1",
        location_col=None, lat_col=None, lon_col=None, location_label_override="", lat_manual=47.07,
        lon_manual=15.45, project_path=str(project), pilot_random_subject=False,
        log_callback=lambda message, level="info": logs.append((level, message)), windows=windows,
    )
    out = {}
    for tsv in project.glob("sub-*/ses-*/environment/*_environment.tsv"):
        with tsv.open(encoding="utf-8") as fh:
            out[tsv.name.split("_")[0]] = next(csv.DictReader(fh, delimiter="\t"))
    sidecar = json.loads((project / "recording-weather_environment.json").read_text(encoding="utf-8"))
    return project, out, sidecar, logs, result


def test_window_column_and_sidecar_entry(tmp_path, monkeypatch):
    calls: list = []
    fetch = _stub_fetch(calls, value=lambda var, ts: float(ts[8:10]))  # the day of month
    project, out, sidecar, _, _ = _convert(
        tmp_path, monkeypatch, [("P1", "2025-06-04 10:00")], [parse_window("temp_c:P3D:max")], fetch
    )
    assert out["sub-P1"]["temp_c_max_p3d"] == "4.0"
    assert sidecar["temp_c_max_p3d"] == {
        "Term": sidecar["temp_c"]["Term"], "Window": {"Start": "P3D", "End": "PT0S"}, "Statistic": "max",
    }

    from schema_manager import load_all_schemas
    from validator import DatasetValidator

    from src.specification import load_specification, use_specification

    tsv = next(project.glob("sub-*/ses-*/environment/*_environment.tsv"))
    with use_specification(load_specification(project_root=project)):
        v = DatasetValidator(load_all_schemas(str(REPO / "app" / "schemas")))
        issues = v.validate_sidecar(str(tsv), "environment", str(project)) + v.validate_data_content(
            str(tsv), "environment", str(project)
        )
    assert not [i for i in issues if i[0] == "ERROR"], issues


def test_count_window_is_unitless_and_validates_without_notice(tmp_path, monkeypatch):
    calls: list = []
    fetch = _stub_fetch(calls, value=lambda var, ts: 1.0)
    project, out, sidecar, _, _ = _convert(
        tmp_path, monkeypatch, [("P1", "2025-06-04 10:00")], [parse_window("temp_c:P3D:count")], fetch
    )
    assert sidecar["temp_c_count_p3d"]["Units"] == "1"  # a count of hours, not degrees
    assert float(out["sub-P1"]["temp_c_count_p3d"]) == 72

    from schema_manager import load_all_schemas
    from validator import DatasetValidator

    from src.specification import load_specification, use_specification

    tsv = next(project.glob("sub-*/ses-*/environment/*_environment.tsv"))
    with use_specification(load_specification(project_root=project)):
        v = DatasetValidator(load_all_schemas(str(REPO / "app" / "schemas")))
        issues = v.validate_sidecar(str(tsv), "environment", str(project)) + v.validate_data_content(
            str(tsv), "environment", str(project)
        )
    assert not [i for i in issues if i[0] in ("ERROR", "WARNING")], issues
    assert not [i for i in issues if "differs from the recommended" in i[1]], issues


def test_window_all_missing_is_empty_with_warning(tmp_path, monkeypatch):
    fetch = _stub_fetch([], value=lambda var, ts: None if var == "temperature_2m" else 1.0)
    _, out, _, logs, result = _convert(
        tmp_path, monkeypatch, [("P1", "2025-06-04 10:00")], [parse_window("temp_c:P1D:mean")], fetch
    )
    assert out["sub-P1"]["temp_c_mean_p1d"] == ""
    assert any(level == "warning" and "temp_c_mean_p1d" in msg for level, msg in logs), logs
    assert result["window_problems"] == [{"column": "temp_c_mean_p1d", "empty_rows": 1, "partial_rows": 0}]


def test_window_beyond_provider_history_is_partial(tmp_path, monkeypatch):
    fetch = _stub_fetch([], air_ok=lambda day: day == date(2025, 6, 4))
    _, out, _, logs, result = _convert(
        tmp_path, monkeypatch, [("P1", "2025-06-04 10:00")], [parse_window("pm25_ug_m3:P2D:mean")], fetch
    )
    assert out["sub-P1"]["pm25_ug_m3_mean_p2d"] == "1.0"  # computed from the hours that are there
    assert any(level == "warning" and "pm25_ug_m3" in msg and "P2D" in msg for level, msg in logs), logs
    assert result["window_problems"] == [{"column": "pm25_ug_m3_mean_p2d", "empty_rows": 0, "partial_rows": 1}]


def test_failed_middle_day_keeps_the_value_and_counts_partial(tmp_path, monkeypatch):
    fetch = _stub_fetch([], value=lambda var, ts: float(ts[8:10]), air_ok=lambda day: day != date(2025, 6, 3))
    _, out, _, _, result = _convert(
        tmp_path, monkeypatch, [("P1", "2025-06-04 10:00")], [parse_window("pm25_ug_m3:P3D:max")], fetch
    )
    assert out["sub-P1"]["pm25_ug_m3_max_p3d"] == "4.0"
    assert result["window_problems"] == [{"column": "pm25_ug_m3_max_p3d", "empty_rows": 0, "partial_rows": 1}]


def test_all_days_failed_is_empty(tmp_path, monkeypatch):
    fetch = _stub_fetch([], air_ok=lambda day: False)
    _, out, _, _, result = _convert(
        tmp_path, monkeypatch, [("P1", "2025-06-04 10:00")], [parse_window("pm25_ug_m3:P3D:mean")], fetch
    )
    assert out["sub-P1"]["pm25_ug_m3_mean_p3d"] == ""
    assert result["window_problems"] == [{"column": "pm25_ug_m3_mean_p3d", "empty_rows": 1, "partial_rows": 0}]


def test_window_problems_are_totals_one_line_per_column(tmp_path, monkeypatch):
    # P1: middle day 06-03 failed; P2: its own session day 06-06 failed; P3 complete; P4: every day failed
    fetch = _stub_fetch([], air_ok=lambda day: day not in (date(2025, 6, 3), date(2025, 6, 6)) and day.month == 6)
    rows = [("P1", "2025-06-04 10:00"), ("P2", "2025-06-06 10:00"), ("P3", "2025-06-10 10:00"), ("P4", "2025-07-10 10:00")]
    _, out, _, logs, result = _convert(tmp_path, monkeypatch, rows, [parse_window("pm25_ug_m3:P2D:mean")], fetch)
    assert [out[s]["pm25_ug_m3_mean_p2d"] for s in ("sub-P1", "sub-P2", "sub-P3", "sub-P4")] == ["1.0", "1.0", "1.0", ""]
    assert result["window_problems"] == [{"column": "pm25_ug_m3_mean_p2d", "empty_rows": 1, "partial_rows": 2}]
    lines = [msg for level, msg in logs if "pm25_ug_m3_mean_p2d" in msg]
    assert len(lines) == 1 and "1 row(s) left empty" in lines[0] and "2 row(s)" in lines[0], lines


def test_no_window_problems_when_complete(tmp_path, monkeypatch):
    *_, result = _convert(
        tmp_path, monkeypatch, [("P1", "2025-06-04 10:00")], [parse_window("temp_c:P1D:sum")], _stub_fetch([])
    )
    assert result["window_problems"] == []


def test_window_days_fetched_once(tmp_path, monkeypatch):
    calls: list = []
    rows = [("P1", "2025-06-04 10:00"), ("P2", "2025-06-05 09:00"), ("P3", "2025-06-05 18:00")]
    windows = [parse_window("temp_c:P3D:max"), parse_window("pm25_ug_m3:P1D:mean")]
    _convert(tmp_path, monkeypatch, rows, windows, _stub_fetch(calls))
    # days 06-01 .. 06-05 (longest window P3D before 06-04 and 06-05), three providers each, each once
    assert len(calls) == len(set(calls)) == 5 * 3


def test_a_repeated_window_is_written_once(tmp_path, monkeypatch):
    windows = [parse_window("temp_c:P3D:max"), parse_window("temp_c:p3d:max"), parse_window("temp_c:P3D:max")]
    project, out, sidecar, _, _ = _convert(
        tmp_path, monkeypatch, [("P1", "2025-06-04 10:00")], windows, _stub_fetch([])
    )
    tsv = next(project.glob("sub-*/ses-*/environment/*_environment.tsv"))
    header = tsv.read_text(encoding="utf-8").splitlines()[0].split("\t")
    assert header.count("temp_c_max_p3d") == 1, header
