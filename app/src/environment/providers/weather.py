from __future__ import annotations

import hashlib


def _stable_float(seed: str, lo: float, hi: float) -> float:
    raw = hashlib.sha256(seed.encode("utf-8")).hexdigest()[:8]
    ratio = int(raw, 16) / 0xFFFFFFFF
    return lo + (hi - lo) * ratio


def fetch_weather(lat: float, lon: float, anchor: str) -> dict[str, float]:
    seed = f"weather:{lat:.4f}:{lon:.4f}:{anchor}"
    pressure_hpa = round(_stable_float(seed + ":p", 980.0, 1040.0), 1)
    weather_regime = "frontal"
    if pressure_hpa >= 1020.0:
        weather_regime = "hochdruck"
    elif pressure_hpa <= 1000.0:
        weather_regime = "tiefdruck"

    return {
        "temp_c": round(_stable_float(seed + ":t", -10.0, 35.0), 1),
        "humidity_pct": round(_stable_float(seed + ":h", 20.0, 95.0), 1),
        "pressure_hpa": pressure_hpa,
        "precip_mm": round(_stable_float(seed + ":r", 0.0, 25.0), 1),
        "wind_speed_ms": round(_stable_float(seed + ":w", 0.0, 20.0), 1),
        "cloud_cover_pct": round(_stable_float(seed + ":c", 0.0, 100.0), 1),
        "weather_regime": weather_regime,
    }
