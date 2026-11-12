"""Reshape a legacy wide blood-sample sheet into the biosample Excel template."""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path
from typing import Sequence

from src.converters.file_reader import infer_tabular_kind, read_tabular_file


class MigrationError(ValueError):
    """A readable reason why the legacy sheet cannot be migrated."""


def read_legacy_wide(path: Path):
    """Read .csv/.tsv/.xlsx with every cell as text.

    Legacy export quirk: each line is one quoted CSV cell holding tab-separated
    fields, so the reader sees one column whose header contains tabs; split it.
    """
    import pandas as pd

    path = Path(path)
    kind = infer_tabular_kind(path) or "csv"
    try:
        df = None
        if kind in ("csv", "tsv"):
            # \x1f never occurs, so the quirk file arrives as one column
            one = read_tabular_file(path, kind=kind, separator="\x1f").df
            if len(one.columns) == 1 and "\t" in str(one.columns[0]):
                df = one
        if df is None:
            df = read_tabular_file(path, kind=kind).df
    except (ValueError, OSError) as exc:
        raise MigrationError(f"Cannot read {path.name}: {exc}") from exc
    if len(df.columns) == 1 and "\t" in str(df.columns[0]):
        names = [c.strip() for c in str(df.columns[0]).split("\t")]
        rows = []
        for i, v in enumerate(df.iloc[:, 0].fillna(""), start=1):
            cells = str(v).split("\t")
            if any(c.strip() for c in cells[len(names) :]):
                raise MigrationError(
                    f"Data row {i} of {path.name} has more fields than the header ({len(names)})."
                )
            rows.append((cells + [""] * len(names))[: len(names)])
        df = pd.DataFrame(rows, columns=names, dtype=str)
    df = df.fillna("").astype(str)
    df.columns = [str(c).strip() for c in df.columns]
    return df


def repair_mojibake(text: str) -> str:
    """Undo Mac-Roman-decoded UTF-8 (`¬µU/ml` -> `µU/ml`); else return text unchanged."""
    try:
        return text.encode("mac_roman").decode("utf-8")
    except (UnicodeEncodeError, UnicodeDecodeError):
        return text


@dataclass(frozen=True)
class AnalyteColumns:
    name: str
    value: str
    unit: str | None
    flag: str | None


_PART = re.compile(r"^(.+?)\s+(results|unit|clin\b.*)$", re.IGNORECASE)


def detect_analytes(columns: Sequence[str]) -> tuple[list[AnalyteColumns], list[str]]:
    """Group `<A> Results` / `<A> Unit` / `<A> clin. significant...` columns.

    Returns the groups in header order and the columns that belong to none.
    """
    parts: list[tuple[int, str, str]] = []  # (column index, analyte, kind)
    for i, col in enumerate(columns):
        m = _PART.match(re.sub(r"\s+", " ", col).strip())
        if m:
            kind = m.group(2).lower()
            parts.append((i, m.group(1), "flag" if kind.startswith("clin") else kind))
    slots: dict[str, dict[str, str]] = {}
    used: set[int] = set()
    for i, name, kind in parts:
        if kind == "results" and name.casefold() not in slots:
            slots[name.casefold()] = {"name": name, "value": columns[i]}
            used.add(i)
    for i, name, kind in parts:
        slot = slots.get(name.casefold())
        if kind != "results" and slot is not None and kind not in slot:
            slot[kind] = columns[i]
            used.add(i)
    groups = [
        AnalyteColumns(v["name"], v["value"], v.get("unit"), v.get("flag")) for v in slots.values()
    ]
    return groups, [c for i, c in enumerate(columns) if i not in used]
