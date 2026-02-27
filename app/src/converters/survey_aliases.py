"""Alias mapping and canonicalization helpers for survey conversion."""

from __future__ import annotations

from pathlib import Path
from typing import Iterable

try:
    import pandas as pd
except ImportError:
    pd = None


def _read_alias_rows(path: Path) -> list[list[str]]:
    rows: list[list[str]] = []
    with open(path, "r", encoding="utf-8") as f:
        for raw in f:
            line = raw.strip()
            if not line:
                continue
            if line.startswith("#"):
                continue
            parts = [
                p.strip() for p in (line.split("\t") if "\t" in line else line.split())
            ]
            parts = [p for p in parts if p]
            if len(parts) < 2:
                continue
            rows.append(parts)
    if rows:
        first = [p.lower() for p in rows[0]]
        if first[0] in {"canonical", "canonical_id", "canonicalid", "id"}:
            rows = rows[1:]
    return rows


def _build_alias_map(rows: Iterable[list[str]]) -> dict[str, str]:
    """Return mapping alias -> canonical (canonical maps to itself)."""
    out: dict[str, str] = {}
    for parts in rows:
        canonical = str(parts[0]).strip()
        if not canonical:
            continue
        out.setdefault(canonical, canonical)
        for alias in parts[1:]:
            a = str(alias).strip()
            if not a:
                continue
            if a in out and out[a] != canonical:
                raise ValueError(
                    f"Alias '{a}' maps to multiple canonical IDs: {out[a]} vs {canonical}"
                )
            out[a] = canonical
    return out


def _build_canonical_aliases(rows: Iterable[list[str]]) -> dict[str, list[str]]:
    out: dict[str, list[str]] = {}
    for parts in rows:
        canonical = str(parts[0]).strip()
        if not canonical:
            continue
        aliases = [str(p).strip() for p in parts[1:] if str(p).strip()]
        if not aliases:
            continue
        out.setdefault(canonical, [])
        for a in aliases:
            if a not in out[canonical]:
                out[canonical].append(a)
    return out


def _apply_alias_file_to_dataframe(*, df, alias_file: str | Path) -> "object":
    """Apply alias mapping to dataframe columns."""
    path = Path(alias_file).resolve()
    if not path.exists() or not path.is_file():
        raise ValueError(f"Alias file not found: {path}")

    rows = _read_alias_rows(path)
    if not rows:
        return df
    alias_map = _build_alias_map(rows)

    return _apply_alias_map_to_dataframe(df=df, alias_map=alias_map)


def _apply_alias_map_to_dataframe(*, df, alias_map: dict[str, str]) -> "object":
    """Apply an alias->canonical mapping to dataframe columns."""
    canonical_to_cols: dict[str, list[str]] = {}
    for c in list(df.columns):
        canonical = alias_map.get(str(c), str(c))
        if canonical != str(c):
            canonical_to_cols.setdefault(canonical, []).append(str(c))

    if not canonical_to_cols:
        return df

    df = df.copy()

    def _as_na(series):
        if series.dtype == object:
            s = series.astype(str)
            s = s.map(lambda v: v.strip() if isinstance(v, str) else v)
            s = s.replace({"": pd.NA, "nan": pd.NA, "None": pd.NA})
            return s
        return series

    for canonical, cols in canonical_to_cols.items():
        cols_present = [c for c in cols if c in df.columns]
        if not cols_present:
            continue

        if canonical in df.columns and canonical not in cols_present:
            cols_present = [canonical] + cols_present

        if len(cols_present) == 1:
            src = cols_present[0]
            if src != canonical:
                if canonical not in df.columns:
                    df = df.rename(columns={src: canonical})
            continue

        combined = _as_na(df[cols_present[0]])
        for c in cols_present[1:]:
            combined = combined.combine_first(_as_na(df[c]))

        df[canonical] = combined
        for c in cols_present:
            if c != canonical and c in df.columns:
                df = df.drop(columns=[c])

    return df


def _canonicalize_template_items(
    *, sidecar: dict, canonical_aliases: dict[str, list[str]]
) -> dict:
    """Remove/merge alias item IDs inside a survey template (in-memory)."""
    out = dict(sidecar)
    for canonical, aliases in (canonical_aliases or {}).items():
        for alias in aliases:
            if alias not in out:
                continue
            if canonical not in out:
                out[canonical] = out[alias]
            try:
                del out[alias]
            except Exception:
                pass
    return out
