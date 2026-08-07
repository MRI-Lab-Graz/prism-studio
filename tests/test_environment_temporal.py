"""Tests for the shared src.environment_temporal formulas.

This module was extracted to end a documented case of duplicated business
logic silently diverging: app/src/environment/builder.py (the legacy,
privacy-safe `prism.py --build-environment` CLI path) and
app/src/web/blueprints/conversion_environment_handlers.py (the Studio GUI /
`environment preview|convert` CLI path) each carried their own copy of
season/sun-phase/daylight/pollen-risk math, and had already drifted (see
docs/_archive/GUI_BACKEND_AUDIT_2026-08-07.md, P1-1). Both now import these
functions from here instead.
"""

from src.environment_temporal import (
    estimate_daylight_hours,
    hour_to_bin,
    hours_since_sun,
    pollen_risk_bin,
    season_code,
    sun_phase,
    sun_window,
)


class TestHourToBin:
    def test_none_is_unknown(self):
        assert hour_to_bin(None) == "unknown"

    def test_night_boundaries(self):
        assert hour_to_bin(0) == "night"
        assert hour_to_bin(5) == "night"

    def test_morning_boundaries(self):
        assert hour_to_bin(6) == "morning"
        assert hour_to_bin(11) == "morning"

    def test_afternoon_boundaries(self):
        assert hour_to_bin(12) == "afternoon"
        assert hour_to_bin(17) == "afternoon"

    def test_evening_boundaries(self):
        assert hour_to_bin(18) == "evening"
        assert hour_to_bin(23) == "evening"


class TestSeasonCode:
    def test_none_is_unknown(self):
        assert season_code(None) == "unknown"

    def test_spring_boundaries(self):
        assert season_code(80) == "spring"
        assert season_code(171) == "spring"

    def test_summer_boundaries(self):
        assert season_code(172) == "summer"
        assert season_code(263) == "summer"

    def test_autumn_boundaries(self):
        assert season_code(264) == "autumn"
        assert season_code(354) == "autumn"

    def test_winter_wraps_year_end_and_start(self):
        assert season_code(355) == "winter"
        assert season_code(1) == "winter"
        assert season_code(79) == "winter"


class TestEstimateDaylightHours:
    def test_none_day_of_year_returns_default(self):
        assert estimate_daylight_hours(None, 47.0) == 10.0

    def test_default_latitude_is_47(self):
        # lat kwarg defaults to 47.0 (Austria) when omitted, matching the
        # GUI's _estimate_daylight default.
        assert estimate_daylight_hours(100) == estimate_daylight_hours(100, 47.0)

    def test_result_bounded_between_4_and_20(self):
        for doy in range(1, 367):
            for lat in (-90.0, -47.0, 0.0, 47.0, 90.0):
                value = estimate_daylight_hours(doy, lat)
                assert 4.0 <= value <= 20.0

    def test_higher_latitude_increases_seasonal_swing_in_summer(self):
        summer_doy = 172  # seasonal term near its peak
        equator = estimate_daylight_hours(summer_doy, 0.0)
        pole = estimate_daylight_hours(summer_doy, 90.0)
        assert pole >= equator


class TestSunWindow:
    def test_symmetric_around_noon(self):
        sunrise, sunset = sun_window(12.0)
        assert sunrise == 6.0
        assert sunset == 18.0


class TestSunPhase:
    def test_none_hour_is_unknown(self):
        assert sun_phase(None, 12.0) == "unknown"

    def test_midday_is_day(self):
        assert sun_phase(12, 12.0) == "day"

    def test_midnight_is_night(self):
        assert sun_phase(0, 10.0) == "night"

    def test_just_after_sunrise_is_dawn(self):
        # daylight=12 -> sunrise at 6.0; 6.5 falls within [6.0, 7.5)
        assert sun_phase(6, 12.0) == "dawn"

    def test_just_before_sunset_is_dusk(self):
        # daylight=12 -> sunset at 18.0; 17 falls within (16.5, 18.0]
        assert sun_phase(17, 12.0) == "dusk"


class TestHoursSinceSun:
    def test_none_hour_returns_sentinel(self):
        assert hours_since_sun(None, 12.0) == -1.0

    def test_zero_while_sun_is_up(self):
        assert hours_since_sun(12, 12.0) == 0.0

    def test_positive_after_sunset(self):
        # daylight=10 -> sunset at 17.0
        assert hours_since_sun(20, 10.0) == 3.0

    def test_wraps_past_midnight_before_sunrise(self):
        # daylight=10 -> sunrise 7.0, sunset 17.0; hour=2 is before sunrise
        value = hours_since_sun(2, 10.0)
        assert value == round((24.0 - 17.0) + 2, 1)


class TestPollenRiskBin:
    def test_none_is_unknown(self):
        assert pollen_risk_bin(None) == "unknown"

    def test_boundaries(self):
        assert pollen_risk_bin(0) == "low"
        assert pollen_risk_bin(49.9) == "low"
        assert pollen_risk_bin(50) == "medium"
        assert pollen_risk_bin(149.9) == "medium"
        assert pollen_risk_bin(150) == "high"
        assert pollen_risk_bin(299.9) == "high"
        assert pollen_risk_bin(300) == "very_high"
