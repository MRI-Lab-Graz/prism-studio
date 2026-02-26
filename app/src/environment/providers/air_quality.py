from __future__ import annotations

import hashlib


def _stable_float(seed: str, lo: float, hi: float) -> float:
    raw = hashlib.sha256(seed.encode("utf-8")).hexdigest()[:8]
    ratio = int(raw, 16) / 0xFFFFFFFF
    return lo + (hi - lo) * ratio


def fetch_air_quality(lat: float, lon: float, anchor: str) -> dict[str, float]:
    seed = f"air:{lat:.4f}:{lon:.4f}:{anchor}"
    pm25 = round(_stable_float(seed + ":pm25", 2.0, 80.0), 1)
    pm10 = round(_stable_float(seed + ":pm10", 5.0, 120.0), 1)
    no2 = round(_stable_float(seed + ":no2", 5.0, 120.0), 1)
    o3 = round(_stable_float(seed + ":o3", 10.0, 220.0), 1)
    aqi = int(max(pm25 / 1.2, pm10 / 1.5, no2 / 1.0, o3 / 1.1))

    return {
        "aqi": aqi,
        "pm25_ug_m3": pm25,
        "pm10_ug_m3": pm10,
        "no2_ug_m3": no2,
        "o3_ug_m3": o3,
    }
