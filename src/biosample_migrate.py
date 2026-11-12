"""Reshape a legacy wide blood-sample sheet into the biosample Excel template."""

from __future__ import annotations

import os
import re
import tempfile
from dataclasses import dataclass, field
from pathlib import Path
from typing import Sequence

from src.biosample_template import DATA_COLUMNS, PANEL_COLUMNS, specimen_types, write_biosample_template
from src.converters.file_reader import infer_tabular_kind, read_tabular_file
from src.converters.wide_to_long import find_empty_data_rows


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


@dataclass
class MigrationReport:
    rows_read: int = 0
    rows_skipped_empty: list[str] = field(default_factory=list)
    data_rows: int = 0
    analytes_mapped: list[str] = field(default_factory=list)
    analytes_dropped_empty: list[str] = field(default_factory=list)
    unit_repairs: list[str] = field(default_factory=list)
    assumptions: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)


def _id_session(other: list[str], id_column: str | None, session_column: str | None,
                columns: list[str]) -> tuple[str, str]:
    for flag, col in (("--id-column", id_column), ("--session-column", session_column)):
        if col is not None and col not in columns:
            raise MigrationError(f"{flag} {col!r} is not a column of the sheet")
    rest = [c for c in other if c not in (id_column, session_column)]
    need = [id_column, session_column].count(None)
    if need and len(rest) != need:
        raise MigrationError(
            "Cannot tell the participant and session columns apart; columns outside the analyte "
            f"groups: {', '.join(rest) or '(none)'}. Pass --id-column and --session-column.")
    fill = iter(rest)
    return id_column or next(fill), session_column or next(fill)


def migrate_wide(input_path: Path, output_path: Path, panel: str = "bloodhormones",
                 specimen: str | None = None, id_column: str | None = None,
                 session_column: str | None = None, overwrite: bool = False) -> MigrationReport:
    """Write the legacy wide sheet as the biosample template; cell text is copied as written."""
    output_path = Path(output_path)
    if not re.fullmatch(r"[A-Za-z0-9]+", panel or ""):
        raise MigrationError(f"Panel name {panel!r} must be letters and digits only")
    if specimen is not None and specimen not in specimen_types():
        raise MigrationError(f"Specimen {specimen!r} is not one of {', '.join(specimen_types())}")
    if not output_path.parent.is_dir():
        raise MigrationError(f"{output_path.parent}: not a directory")
    if output_path.exists() and not overwrite:
        raise MigrationError(f"{output_path} already exists; pass --overwrite to replace it")

    df = read_legacy_wide(Path(input_path))
    columns = list(df.columns)
    groups, other = detect_analytes(columns)
    if not groups:
        raise MigrationError("No analyte columns ('<analyte> Results') found; columns seen: "
                             + ", ".join(columns))
    id_col, ses_col = _id_session(other, id_column, session_column, columns)

    rep = MigrationReport(rows_read=len(df))
    empty = {e["row_index"] for e in find_empty_data_rows(df, id_column=id_col,
                                                          data_columns=[g.value for g in groups])}
    rep.rows_skipped_empty = [f"{df.at[i, id_col]} {df.at[i, ses_col]}" for i in sorted(empty)]
    kept = df.drop(index=list(empty))
    mapped = [g for g in groups if kept[g.value].str.strip().ne("").any()]
    rep.analytes_mapped = [g.name for g in mapped]
    rep.analytes_dropped_empty = [g.name for g in groups if g not in mapped]
    for g in mapped:
        if g.unit is None:
            rep.warnings.append(f"{g.name}: no unit column; rows written with an empty unit, "
                                "the importer needs a unit or a registry term")
    pairs = kept[id_col] + " " + kept[ses_col]
    twice = sorted(set(pairs[pairs.duplicated()]))
    if twice:
        rep.warnings.append("participant and session twice in the sheet (the importer will refuse "
                            "them as measured twice): " + ", ".join(twice))
    if specimen is None:
        rep.assumptions.append("SpecimenType assumed to be serum (unverified); pass --specimen")

    data: list[dict[str, str]] = []
    repairs: dict[str, str] = {}
    for _, row in kept.iterrows():
        for g in mapped:
            value = row[g.value].strip()
            if not value:
                continue
            unit = row[g.unit].strip() if g.unit else ""
            fixed = repair_mojibake(unit)
            if fixed != unit:
                repairs.setdefault(unit, fixed)
            data.append({"participant_id": row[id_col], "session": row[ses_col], "panel": panel,
                         "analyte": g.name, "value": value, "unit": fixed,
                         "comment": row[g.flag].strip() if g.flag else ""})
    rep.unit_repairs = [f"{a} -> {b}" for a, b in repairs.items()]
    rep.data_rows = len(data)

    from openpyxl import load_workbook

    fd, tmp_name = tempfile.mkstemp(dir=output_path.parent, suffix=".xlsx")
    os.close(fd)
    tmp = Path(tmp_name)
    try:
        write_biosample_template(tmp)
        wb = load_workbook(tmp)
        for r, cells in enumerate(data, start=2):
            for c, name in enumerate(DATA_COLUMNS, start=1):
                if v := cells.get(name):
                    wb["data"].cell(row=r, column=c, value=v).number_format = "@"  # text, never a number
        wb["panels"].cell(row=2, column=1, value=panel)
        wb["panels"].cell(row=2, column=PANEL_COLUMNS.index("SpecimenType") + 1, value=specimen or "serum")
        wb.save(tmp)
        os.replace(tmp, output_path)
    except OSError as exc:
        raise MigrationError(f"{output_path}: cannot write ({exc})") from exc
    finally:
        tmp.unlink(missing_ok=True)
    return rep
