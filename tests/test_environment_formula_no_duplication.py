"""Guards against re-introducing duplicate environment-math implementations.

The environment engine (src.environment_conversion /
src.environment_provider_helpers) must call through to src.environment_temporal
rather than carry its own copy of the season/sun-phase/daylight/pollen-risk
formulas (see docs/_archive/GUI_BACKEND_AUDIT_2026-08-07.md, P1-1). Checked by
monkeypatching the shared function and observing the wrapper's output change.
"""

from __future__ import annotations

import sys
from pathlib import Path

APP_ROOT = Path(__file__).resolve().parents[1] / "app"
if str(APP_ROOT) not in sys.path:
    sys.path.insert(0, str(APP_ROOT))

import src.environment_temporal as shared  # noqa: E402
# The GUI/`environment convert` engine moved out of the Flask blueprint into
# src.environment_conversion (+ src.environment_provider_helpers).
import src.environment_conversion as gui_handlers  # noqa: E402
import src.environment_provider_helpers as gui_provider_helpers  # noqa: E402


class TestGuiHandlersDelegateToSharedModule:
    """The engine keeps its own `_`-prefixed wrapper names (called throughout
    a large file), so confirm each wrapper calls through by monkeypatching
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
