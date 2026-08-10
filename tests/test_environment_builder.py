"""Tests for app/src/environment/** — the environment.tsv builder pipeline.

Covers aggregator.collect, EnvironmentCache, dicom_bridge.read_prism_time_anchor,
the three deterministic providers, and builder.build_environment_tsv end to end.
Confirmed live (no src/environment/ mirror exists -- only src/environment_temporal.py,
an unrelated module builder.py imports from) via:
    PYTHONPATH=".:app:app/src" python3 -c "import environment.builder as m; print(m.__file__)"
"""

import csv
import json
from pathlib import Path

import pytest

from environment.aggregator import collect
from environment.cache import EnvironmentCache
from environment.dicom_bridge import read_prism_time_anchor
from environment.providers import fetch_weather, fetch_pollen, fetch_air_quality
from environment import builder


# ---------------------------------------------------------------------------
# aggregator.collect
# ---------------------------------------------------------------------------


class TestCollect:
    def test_merges_multiple_providers(self):
        p1 = lambda lat, lon, anchor: {"a": 1}
        p2 = lambda lat, lon, anchor: {"b": 2}

        result = collect(1.0, 2.0, "anchor", [p1, p2])

        assert result == {"a": 1, "b": 2}

    def test_later_provider_overwrites_earlier_key(self):
        p1 = lambda lat, lon, anchor: {"a": 1}
        p2 = lambda lat, lon, anchor: {"a": 99}

        result = collect(1.0, 2.0, "anchor", [p1, p2])

        assert result == {"a": 99}

    def test_no_providers_returns_empty_dict(self):
        assert collect(1.0, 2.0, "anchor", []) == {}

    def test_passes_lat_lon_anchor_through(self):
        seen = {}

        def provider(lat, lon, anchor):
            seen["args"] = (lat, lon, anchor)
            return {}

        collect(47.5, 15.1, "2024-DOY100-H10", [provider])

        assert seen["args"] == (47.5, 15.1, "2024-DOY100-H10")


# ---------------------------------------------------------------------------
# EnvironmentCache
# ---------------------------------------------------------------------------


class TestEnvironmentCache:
    def test_creates_parent_dir_and_starts_empty(self, tmp_path):
        cache_path = tmp_path / "nested" / "dir" / "cache.json"

        cache = EnvironmentCache(cache_path)

        assert cache_path.parent.is_dir()
        assert cache.get("missing") is None

    def test_get_set_roundtrip_before_flush(self, tmp_path):
        cache = EnvironmentCache(tmp_path / "cache.json")

        cache.set("key1", {"a": 1})

        assert cache.get("key1") == {"a": 1}

    def test_flush_writes_json_readable_by_new_instance(self, tmp_path):
        cache_path = tmp_path / "cache.json"
        cache = EnvironmentCache(cache_path)
        cache.set("key1", {"temp_c": 12.3})
        cache.flush()

        assert cache_path.exists()
        reloaded = EnvironmentCache(cache_path)
        assert reloaded.get("key1") == {"temp_c": 12.3}

    def test_corrupt_cache_file_resets_to_empty(self, tmp_path):
        cache_path = tmp_path / "cache.json"
        cache_path.write_text("{not valid json", encoding="utf-8")

        cache = EnvironmentCache(cache_path)

        assert cache.get("anything") is None

    def test_flush_output_is_sorted_and_indented(self, tmp_path):
        cache_path = tmp_path / "cache.json"
        cache = EnvironmentCache(cache_path)
        cache.set("z", 1)
        cache.set("a", 2)
        cache.flush()

        raw = cache_path.read_text(encoding="utf-8")
        assert list(json.loads(raw).keys()) == ["a", "z"]
        assert "\n" in raw  # indent=2 produces multi-line output


# ---------------------------------------------------------------------------
# dicom_bridge.read_prism_time_anchor
# ---------------------------------------------------------------------------


class TestReadPrismTimeAnchor:
    def test_uses_explicit_anchor_when_present(self):
        row = {"prism_time_anchor": "2024-DOY100-H10"}

        assert read_prism_time_anchor(row) == "2024-DOY100-H10"

    def test_explicit_anchor_takes_precedence_over_everything_else(self):
        row = {
            "prism_time_anchor": "2024-DOY100-H10",
            "acquisition_datetime": "2024-06-01T08:00:00",
            "session_relative_hour": "3",
        }

        assert read_prism_time_anchor(row) == "2024-DOY100-H10"

    def test_derives_from_acquisition_datetime(self):
        row = {"acquisition_datetime": "2024-06-01T08:30:00"}

        anchor = read_prism_time_anchor(row)

        assert anchor == "2024-DOY153-H08"

    def test_derives_from_acquisition_datetime_with_z_suffix(self):
        row = {"acquisition_datetime": "2024-06-01T08:30:00Z"}

        anchor = read_prism_time_anchor(row)

        assert anchor == "2024-DOY153-H08"

    def test_derives_from_acquisition_date_and_time(self):
        row = {"acquisition_date": "2024-06-01", "acquisition_time": "08:30:00"}

        anchor = read_prism_time_anchor(row)

        assert anchor == "2024-DOY153-H08"

    def test_date_without_time_falls_through_to_relative_hour(self):
        row = {"acquisition_date": "2024-06-01", "session_relative_hour": "2"}

        assert read_prism_time_anchor(row) == "relative-hour-2"

    def test_derives_from_relative_hour(self):
        row = {"session_relative_hour": "5"}

        assert read_prism_time_anchor(row) == "relative-hour-5"

    def test_raises_when_nothing_present(self):
        with pytest.raises(ValueError, match="Missing temporal input"):
            read_prism_time_anchor({})

    def test_blank_values_are_treated_as_absent(self):
        with pytest.raises(ValueError):
            read_prism_time_anchor(
                {"prism_time_anchor": "  ", "acquisition_datetime": "  "}
            )


# ---------------------------------------------------------------------------
# providers
# ---------------------------------------------------------------------------


class TestFetchWeather:
    def test_returns_expected_keys(self):
        result = fetch_weather(40.0, 10.0, "2024-DOY100-H10")

        assert set(result) == {
            "temp_c",
            "humidity_pct",
            "pressure_hpa",
            "precip_mm",
            "wind_speed_ms",
            "cloud_cover_pct",
            "weather_regime",
        }

    def test_deterministic_for_same_inputs(self):
        a = fetch_weather(47.5, 15.1, "2024-DOY100-H10")
        b = fetch_weather(47.5, 15.1, "2024-DOY100-H10")

        assert a == b

    def test_hochdruck_regime(self):
        result = fetch_weather(40.0, 10.0, "2024-DOY200-H14")

        assert result["weather_regime"] == "hochdruck"
        assert result["pressure_hpa"] >= 1020.0

    def test_tiefdruck_regime(self):
        result = fetch_weather(40.0, 10.0, "2024-DOY300-H20")

        assert result["weather_regime"] == "tiefdruck"
        assert result["pressure_hpa"] <= 1000.0

    def test_frontal_regime(self):
        result = fetch_weather(40.0, 10.0, "2024-DOY100-H10")

        assert result["weather_regime"] == "frontal"
        assert 1000.0 < result["pressure_hpa"] < 1020.0


class TestFetchPollen:
    def test_returns_expected_keys_and_total(self):
        result = fetch_pollen(47.5, 15.1, "2024-DOY100-H10")

        assert set(result) == {"pollen_birch", "pollen_grass", "pollen_total"}
        assert result["pollen_total"] == result["pollen_birch"] + result["pollen_grass"]

    def test_deterministic_for_same_inputs(self):
        a = fetch_pollen(47.5, 15.1, "2024-DOY100-H10")
        b = fetch_pollen(47.5, 15.1, "2024-DOY100-H10")

        assert a == b


class TestFetchAirQuality:
    def test_returns_expected_keys(self):
        result = fetch_air_quality(47.5, 15.1, "2024-DOY100-H10")

        assert set(result) == {"aqi", "pm25_ug_m3", "pm10_ug_m3", "no2_ug_m3", "o3_ug_m3"}

    def test_aqi_is_max_of_scaled_pollutants(self):
        result = fetch_air_quality(47.5, 15.1, "2024-DOY100-H10")

        expected = int(
            max(
                result["pm25_ug_m3"] / 1.2,
                result["pm10_ug_m3"] / 1.5,
                result["no2_ug_m3"] / 1.0,
                result["o3_ug_m3"] / 1.1,
            )
        )
        assert result["aqi"] == expected

    def test_deterministic_for_same_inputs(self):
        a = fetch_air_quality(47.5, 15.1, "2024-DOY100-H10")
        b = fetch_air_quality(47.5, 15.1, "2024-DOY100-H10")

        assert a == b


# ---------------------------------------------------------------------------
# builder helpers
# ---------------------------------------------------------------------------


class TestParseHourFromAnchor:
    def test_valid_hour(self):
        assert builder.parse_hour_from_anchor("2024-DOY100-H14") == 14

    def test_boundary_hours(self):
        assert builder.parse_hour_from_anchor("2024-DOY100-H00") == 0
        assert builder.parse_hour_from_anchor("2024-DOY100-H23") == 23

    def test_out_of_range_hour_returns_none(self):
        assert builder.parse_hour_from_anchor("2024-DOY100-H99") is None

    def test_no_match_returns_none(self):
        assert builder.parse_hour_from_anchor("relative-hour-3") is None


class TestParseDayOfYearFromAnchor:
    def test_valid_day(self):
        assert builder.parse_day_of_year_from_anchor("2024-DOY100-H14") == 100

    def test_boundary_days(self):
        assert builder.parse_day_of_year_from_anchor("2024-DOY001-H14") == 1
        assert builder.parse_day_of_year_from_anchor("2024-DOY366-H14") == 366

    def test_out_of_range_day_returns_none(self):
        assert builder.parse_day_of_year_from_anchor("2024-DOY999-H14") is None

    def test_no_match_returns_none(self):
        assert builder.parse_day_of_year_from_anchor("relative-hour-3") is None


class TestExtractSubjectSession:
    def test_both_present(self):
        subject, session = builder.extract_subject_session(
            "sub-01_ses-pre_task-rest_bold.nii.gz"
        )
        assert subject == "sub-01"
        assert session == "ses-pre"

    def test_subject_only(self):
        subject, session = builder.extract_subject_session("sub-02_task-rest_bold.nii.gz")
        assert subject == "sub-02"
        assert session == ""

    def test_neither_present(self):
        subject, session = builder.extract_subject_session("readme.txt")
        assert subject == ""
        assert session == ""


class TestProviderRegistry:
    def test_maps_names_to_functions(self):
        registry = builder._provider_registry()

        assert registry == {
            "weather": fetch_weather,
            "pollen": fetch_pollen,
            "air_quality": fetch_air_quality,
        }


# ---------------------------------------------------------------------------
# build_environment_tsv (integration)
# ---------------------------------------------------------------------------


def _write_scans_tsv(path: Path, rows):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(
            handle, fieldnames=["filename", "prism_time_anchor"], delimiter="\t"
        )
        writer.writeheader()
        for row in rows:
            writer.writerow(row)


class TestBuildEnvironmentTsv:
    def test_builds_tsv_with_all_default_providers(self, tmp_path):
        scans = tmp_path / "scans.tsv"
        output = tmp_path / "derivatives" / "environment.tsv"
        _write_scans_tsv(
            scans,
            [
                {
                    "filename": "sub-01_ses-pre_task-rest_bold.nii.gz",
                    "prism_time_anchor": "2024-DOY100-H10",
                }
            ],
        )

        result_path = builder.build_environment_tsv(scans, output, lat=47.5, lon=15.1)

        assert result_path == output
        assert output.exists()
        with output.open(encoding="utf-8") as handle:
            reader = csv.DictReader(handle, delimiter="\t")
            rows = list(reader)
        assert len(rows) == 1
        row = rows[0]
        assert row["subject_id"] == "sub-01"
        assert row["session_id"] == "ses-pre"
        assert row["hour_bin"] != ""
        # provider columns from all three default providers present
        assert "temp_c" in reader.fieldnames
        assert "pollen_total" in reader.fieldnames
        assert "aqi" in reader.fieldnames
        assert "pollen_risk_bin" in reader.fieldnames

    def test_raises_on_missing_header(self, tmp_path):
        scans = tmp_path / "scans.tsv"
        scans.write_text("", encoding="utf-8")
        output = tmp_path / "environment.tsv"

        with pytest.raises(ValueError, match="empty or has no header"):
            builder.build_environment_tsv(scans, output, lat=47.5, lon=15.1)

    def test_skips_rows_with_empty_filename(self, tmp_path):
        scans = tmp_path / "scans.tsv"
        output = tmp_path / "environment.tsv"
        _write_scans_tsv(
            scans,
            [
                {"filename": "", "prism_time_anchor": "2024-DOY100-H10"},
                {
                    "filename": "sub-01_task-rest_bold.nii.gz",
                    "prism_time_anchor": "2024-DOY100-H10",
                },
            ],
        )

        builder.build_environment_tsv(scans, output, lat=47.5, lon=15.1)

        with output.open(encoding="utf-8") as handle:
            rows = list(csv.DictReader(handle, delimiter="\t"))
        assert len(rows) == 1

    def test_selected_providers_restricts_populated_columns(self, tmp_path):
        # pollen_total/aqi are BIDS core columns so they still appear in the
        # header (blank), but only the enabled provider's values get filled in.
        scans = tmp_path / "scans.tsv"
        output = tmp_path / "environment.tsv"
        _write_scans_tsv(
            scans,
            [{"filename": "sub-01_bold.nii.gz", "prism_time_anchor": "2024-DOY100-H10"}],
        )

        builder.build_environment_tsv(
            scans, output, lat=47.5, lon=15.1, enabled_providers=["weather"]
        )

        with output.open(encoding="utf-8") as handle:
            row = next(csv.DictReader(handle, delimiter="\t"))

        assert row["temp_c"] != ""
        assert row["aqi"] == ""
        assert row["pollen_birch"] == ""

    def test_creates_output_parent_directories(self, tmp_path):
        scans = tmp_path / "scans.tsv"
        output = tmp_path / "a" / "b" / "c" / "environment.tsv"
        _write_scans_tsv(
            scans,
            [{"filename": "sub-01_bold.nii.gz", "prism_time_anchor": "2024-DOY100-H10"}],
        )

        builder.build_environment_tsv(scans, output, lat=47.5, lon=15.1)

        assert output.exists()

    def test_cache_avoids_recomputing_for_identical_rows(self, tmp_path, monkeypatch):
        scans = tmp_path / "scans.tsv"
        output = tmp_path / "environment.tsv"
        cache_path = tmp_path / "cache.json"
        _write_scans_tsv(
            scans,
            [
                {
                    "filename": "sub-01_bold.nii.gz",
                    "prism_time_anchor": "2024-DOY100-H10",
                },
                {
                    "filename": "sub-02_bold.nii.gz",
                    "prism_time_anchor": "2024-DOY100-H10",
                },
            ],
        )
        call_count = {"n": 0}
        real_collect = builder.collect

        def counting_collect(*args, **kwargs):
            call_count["n"] += 1
            return real_collect(*args, **kwargs)

        monkeypatch.setattr(builder, "collect", counting_collect)

        builder.build_environment_tsv(
            scans, output, lat=47.5, lon=15.1, cache_path=cache_path
        )

        # Both rows share the same lat/lon/anchor/providers -> same cache key,
        # so collect() should only run once (second row is a cache hit).
        assert call_count["n"] == 1
        assert cache_path.exists()

    def test_cache_persists_across_runs(self, tmp_path, monkeypatch):
        scans = tmp_path / "scans.tsv"
        output = tmp_path / "environment.tsv"
        cache_path = tmp_path / "cache.json"
        _write_scans_tsv(
            scans,
            [{"filename": "sub-01_bold.nii.gz", "prism_time_anchor": "2024-DOY100-H10"}],
        )

        builder.build_environment_tsv(
            scans, output, lat=47.5, lon=15.1, cache_path=cache_path
        )

        call_count = {"n": 0}
        real_collect = builder.collect

        def counting_collect(*args, **kwargs):
            call_count["n"] += 1
            return real_collect(*args, **kwargs)

        monkeypatch.setattr(builder, "collect", counting_collect)

        builder.build_environment_tsv(
            scans, output, lat=47.5, lon=15.1, cache_path=cache_path
        )

        assert call_count["n"] == 0

    def test_pollen_risk_bin_derived_from_total(self, tmp_path):
        scans = tmp_path / "scans.tsv"
        output = tmp_path / "environment.tsv"
        _write_scans_tsv(
            scans,
            [{"filename": "sub-01_bold.nii.gz", "prism_time_anchor": "2024-DOY100-H10"}],
        )

        builder.build_environment_tsv(scans, output, lat=47.5, lon=15.1)

        with output.open(encoding="utf-8") as handle:
            row = next(csv.DictReader(handle, delimiter="\t"))
        assert row["pollen_risk_bin"] != ""


# ---------------------------------------------------------------------------
# CLI (arg parser + main)
# ---------------------------------------------------------------------------


class TestBuildArgParser:
    def test_defaults(self):
        parser = builder._build_arg_parser()
        args = parser.parse_args(["scans.tsv", "out.tsv", "--lat", "47.5", "--lon", "15.1"])

        assert args.providers == ["weather", "pollen", "air_quality"]
        assert args.cache == ".prism/environment_cache.json"

    def test_requires_lat_and_lon(self):
        parser = builder._build_arg_parser()
        with pytest.raises(SystemExit):
            parser.parse_args(["scans.tsv", "out.tsv"])


class TestMain:
    def test_main_parses_args_and_calls_build(self, tmp_path, monkeypatch):
        scans = tmp_path / "scans.tsv"
        output = tmp_path / "out.tsv"
        _write_scans_tsv(
            scans,
            [{"filename": "sub-01_bold.nii.gz", "prism_time_anchor": "2024-DOY100-H10"}],
        )
        monkeypatch.setattr(
            "sys.argv",
            [
                "builder.py",
                str(scans),
                str(output),
                "--lat",
                "47.5",
                "--lon",
                "15.1",
                "--providers",
                "weather",
                "--cache",
                str(tmp_path / "cache.json"),
            ],
        )

        exit_code = builder.main()

        assert exit_code == 0
        assert output.exists()
