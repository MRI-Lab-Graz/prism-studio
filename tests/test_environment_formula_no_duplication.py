"""Guards against re-introducing duplicate environment-math implementations.

docs/_archive/GUI_BACKEND_AUDIT_2026-08-07.md (P1-1) found that
app/src/environment/builder.py (legacy `prism.py --build-environment`) and
app/src/web/blueprints/conversion_environment_handlers.py (Studio GUI /
`environment preview|convert`) each carried an independent copy of the same
season/sun-phase/daylight/pollen-risk formulas, and they had already
diverged. Both were refactored to import from src.environment_temporal
instead. These tests confirm the delegation actually happened — i.e. that
the wrapper functions call through to the shared module rather than
silently reimplementing it again — by monkeypatching the shared function
and checking the wrapper's return value changes accordingly.
"""

from __future__ import annotations

import sys
from pathlib import Path

APP_ROOT = Path(__file__).resolve().parents[1] / "app"
if str(APP_ROOT) not in sys.path:
    sys.path.insert(0, str(APP_ROOT))

import src.environment_temporal as shared  # noqa: E402
from src.environment import builder  # noqa: E402
from src.web.blueprints import conversion_environment_handlers as gui_handlers  # noqa: E402
from src.web.blueprints import (  # noqa: E402
    conversion_environment_provider_helpers as gui_provider_helpers,
)


class TestBuilderDelegatesToSharedModule:
    def test_season_code_is_the_shared_function(self):
        assert builder.season_code is shared.season_code

    def test_hour_to_bin_is_the_shared_function(self):
        assert builder.hour_to_bin is shared.hour_to_bin

    def test_sun_phase_is_the_shared_function(self):
        assert builder.sun_phase is shared.sun_phase

    def test_hours_since_sun_is_the_shared_function(self):
        assert builder.hours_since_sun is shared.hours_since_sun

    def test_pollen_risk_bin_is_the_shared_function(self):
        assert builder.pollen_risk_bin is shared.pollen_risk_bin

    def test_estimate_daylight_hours_is_the_shared_function(self):
        assert builder.estimate_daylight_hours is shared.estimate_daylight_hours


class TestGuiHandlersDelegateToSharedModule:
    """The GUI keeps its own `_`-prefixed wrapper names (called throughout
    a large file), so it can't use an identity check like the builder
    module — instead confirm each wrapper calls through by monkeypatching
    the shared implementation and observing the wrapper's output change."""

    def test_hour_bin_wrapper_delegates(self, monkeypatch):
        monkeypatch.setattr(
            gui_handlers, "_shared_hour_to_bin", lambda hour: "sentinel-hour-bin"
        )
        assert gui_handlers._hour_bin(9) == "sentinel-hour-bin"

    def test_season_code_wrapper_delegates(self, monkeypatch):
        monkeypatch.setattr(
            gui_handlers, "_shared_season_code", lambda doy: "sentinel-season"
        )
        assert gui_handlers._season_code(100) == "sentinel-season"

    def test_estimate_daylight_wrapper_delegates(self, monkeypatch):
        monkeypatch.setattr(
            gui_handlers,
            "_shared_estimate_daylight_hours",
            lambda doy, lat: 99.0,
        )
        assert gui_handlers._estimate_daylight(100, 47.0) == 99.0

    def test_sun_phase_wrapper_delegates(self, monkeypatch):
        monkeypatch.setattr(
            gui_handlers, "_shared_sun_phase", lambda hour, daylight: "sentinel-phase"
        )
        assert gui_handlers._sun_phase(12, 12.0) == "sentinel-phase"

    def test_hours_since_sun_wrapper_delegates(self, monkeypatch):
        monkeypatch.setattr(
            gui_handlers, "_shared_hours_since_sun", lambda hour, daylight: 12.34
        )
        assert gui_handlers._hours_since_sun(20, 10.0) == 12.34

    def test_pollen_risk_bin_wrapper_delegates(self, monkeypatch):
        monkeypatch.setattr(
            gui_provider_helpers,
            "_shared_pollen_risk_bin",
            lambda total: "sentinel-pollen",
        )
        assert gui_provider_helpers.handle_pollen_risk_bin(200) == "sentinel-pollen"


class TestBuilderAndGuiAgreeOnFormulaOutputs:
    """End-to-end confidence check: for representative inputs, the legacy
    builder path and the GUI path compute identical season/sun-phase/
    daylight/pollen values (they no longer can silently disagree, since
    both call the same underlying functions)."""

    def test_representative_inputs_agree(self):
        for doy in (1, 79, 80, 171, 172, 263, 264, 354, 355, 366):
            for hour in (0, 6, 9, 12, 17, 18, 23):
                for lat in (-47.0, 0.0, 47.0):
                    assert builder.season_code(doy) == gui_handlers._season_code(doy)
                    daylight_builder = builder.estimate_daylight_hours(doy, lat)
                    daylight_gui = gui_handlers._estimate_daylight(doy, lat)
                    assert daylight_builder == daylight_gui
                    assert builder.sun_phase(
                        hour, daylight_builder
                    ) == gui_handlers._sun_phase(hour, daylight_gui)
                    assert builder.hours_since_sun(
                        hour, daylight_builder
                    ) == gui_handlers._hours_since_sun(hour, daylight_gui)

        for total in (0, 49, 50, 149, 150, 299, 300, 500):
            assert builder.pollen_risk_bin(
                total
            ) == gui_provider_helpers.handle_pollen_risk_bin(total)
