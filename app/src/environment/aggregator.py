from __future__ import annotations

from typing import Callable, Dict, Iterable

Provider = Callable[[float, float, str], Dict[str, float | int | str]]


def collect(
    lat: float,
    lon: float,
    anchor: str,
    providers: Iterable[Provider],
) -> Dict[str, float | int | str]:
    merged: Dict[str, float | int | str] = {}
    for provider in providers:
        values = provider(lat, lon, anchor)
        for key, value in values.items():
            merged[key] = value
    return merged
