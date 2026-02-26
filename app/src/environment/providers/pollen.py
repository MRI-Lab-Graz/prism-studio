from __future__ import annotations

import hashlib


def _stable_int(seed: str, lo: int, hi: int) -> int:
    raw = hashlib.sha256(seed.encode("utf-8")).hexdigest()[:8]
    ratio = int(raw, 16) / 0xFFFFFFFF
    return int(lo + (hi - lo) * ratio)


def fetch_pollen(lat: float, lon: float, anchor: str) -> dict[str, int]:
    seed = f"pollen:{lat:.4f}:{lon:.4f}:{anchor}"
    birch = _stable_int(seed + ":birch", 0, 300)
    grass = _stable_int(seed + ":grass", 0, 300)

    return {
        "pollen_birch": birch,
        "pollen_grass": grass,
        "pollen_total": birch + grass,
    }
