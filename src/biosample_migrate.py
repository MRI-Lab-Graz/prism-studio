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


_UMASK = os.umask(0)  # read once at import (single-threaded); os.umask in a call races other threads
os.umask(_UMASK)
# C0 controls and DEL; tab, LF and CR stay allowed (openpyxl refuses the others, terminals obey ESC)
_CONTROL = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]")


def _show(text: str) -> str:
    """Text from the input as it may be printed: unchanged when printable, else repr (CR/LF escaped)."""
    return text if text.isprintable() else repr(text)


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
    for j, name in enumerate(df.columns, start=1):
        if _CONTROL.search(name):
            raise MigrationError(f"Column {j} name {name!r} of {path.name} holds a control character")
    bad = df.apply(lambda col: col.str.contains(_CONTROL.pattern, regex=True)).to_numpy().nonzero()
    if len(bad[0]):
        r, c = bad[0][0], bad[1][0]
        raise MigrationError(f"Data row {r + 1} of {path.name}, column {_show(df.columns[c])}: "
                             f"{df.iat[r, c]!r} holds a control character")
    twice = sorted(set(df.columns[df.columns.duplicated()]))
    if twice:
        raise MigrationError(f"{path.name} has duplicate column names: {', '.join(map(_show, twice))}")
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
            f"groups: {', '.join(map(_show, rest)) or '(none)'}. Pass --id-column and --session-column.")
    fill = iter(rest)
    return id_column or next(fill), session_column or next(fill)


def migrate_wide(input_path: Path, output_path: Path, panel: str = "bloodhormones",
                 specimen: str | None = None, id_column: str | None = None,
                 session_column: str | None = None, overwrite: bool = False) -> MigrationReport:
    """Write the legacy wide sheet as the biosample template; cell text is copied as written."""
    output_path = Path(output_path)
    if output_path.suffix.lower() != ".xlsx":
        raise MigrationError(f"{output_path}: the output must be an .xlsx file")
    if not re.fullmatch(r"[A-Za-z0-9]+", panel or ""):
        raise MigrationError(f"Panel name {panel!r} must be letters and digits only")
    if specimen is not None and specimen not in specimen_types():
        raise MigrationError(f"Specimen {specimen!r} is not one of {', '.join(specimen_types())}")
    if not output_path.parent.is_dir():
        raise MigrationError(f"{output_path.parent}: not a directory")
    input_path = Path(input_path)
    same = (os.path.samefile(input_path, output_path) if input_path.exists() and output_path.exists()
            else input_path.resolve() == output_path.resolve())
    if same:
        raise MigrationError(f"{output_path}: the output would replace the input; choose another file")
    if output_path.exists() and not overwrite:
        raise MigrationError(f"{output_path} already exists; pass --overwrite to replace it")

    df = read_legacy_wide(input_path)
    columns = list(df.columns)
    groups, other = detect_analytes(columns)
    if not groups:
        raise MigrationError("No analyte columns ('<analyte> Results') found; columns seen: "
                             + ", ".join(map(_show, columns)))
    id_col, ses_col = _id_session(other, id_column, session_column, columns)
    for col in (id_col, ses_col):
        df[col] = df[col].str.strip()  # surrounding whitespace only; labels stay exact
    who = lambda row: f"{_show(row[id_col])} {_show(row[ses_col])}"  # noqa: E731

    def has_text(col):
        return col is not None and df[col].str.strip().ne("").any()

    rep = MigrationReport(rows_read=len(df))
    unused = [c for c in other if c not in (id_col, ses_col) and has_text(c)]
    if unused:
        rep.warnings.append("columns not migrated: " + ", ".join(map(_show, unused)))
    empty = {e["row_index"] for e in find_empty_data_rows(df, id_column=id_col,
                                                          data_columns=[g.value for g in groups])}
    rep.rows_skipped_empty = [who(df.loc[i]) for i in sorted(empty)]
    kept = df.drop(index=list(empty))
    mapped = [g for g in groups if has_text(g.value)]
    rep.analytes_mapped = [_show(g.name) for g in mapped]
    # comments without values are no "empty" analyte: they are named in the warnings below
    rep.analytes_dropped_empty = [_show(g.name) for g in groups if g not in mapped and not has_text(g.flag)]
    orphans = [f"{who(row)} {_show(g.name)}: {what} {row[col].strip()!r} has no value, not written"
               for _, row in df.iterrows() for g in groups if not row[g.value].strip()
               for what, col in (("comment", g.flag), ("unit", g.unit)) if col and row[col].strip()]
    if len(orphans) > 10:
        orphans = [f"{len(orphans)} comment or unit cells have no value and are not written, e.g. "
                   + "; ".join(orphans[:3])]
    rep.warnings += orphans
    for g in mapped:
        if g.unit is None:
            rep.warnings.append(f"{_show(g.name)}: no unit column; rows written with an empty unit, "
                                "the importer needs a unit or a registry term")
    pairs = kept[id_col].map(_show) + " " + kept[ses_col].map(_show)
    twice = sorted(set(pairs[pairs.duplicated()]))
    if twice:
        rep.warnings.append("participant and session twice in the sheet (the importer will refuse "
                            "them as measured twice): " + ", ".join(twice))
    if specimen is None:
        rep.assumptions.append("SpecimenType assumed to be serum (unverified); pass --specimen")

    data: list[dict[str, str]] = []
    repairs: dict[str, str] = {}
    no_unit: dict[str, list[str]] = {}
    for _, row in kept.iterrows():
        for g in mapped:
            value = row[g.value].strip()
            if not value:
                continue
            unit = row[g.unit].strip() if g.unit else ""
            if g.unit and not unit:
                no_unit.setdefault(g.name, []).append(who(row))
            fixed = repair_mojibake(unit)
            if fixed != unit:
                repairs.setdefault(unit, fixed)
            data.append({"participant_id": row[id_col], "session": row[ses_col], "panel": panel,
                         "analyte": g.name, "value": value, "unit": fixed,
                         "comment": row[g.flag].strip() if g.flag else ""})
    rep.unit_repairs = [f"{_show(a)} -> {_show(b)}" for a, b in repairs.items()]
    rep.warnings += [f"{_show(name)}: no unit in {len(p)} row(s) (e.g. {', '.join(p[:3])}); "
                     "the importer will use the unit of the other rows" for name, p in no_unit.items()]
    rep.data_rows = len(data)

    from openpyxl import load_workbook

    tmp = None
    try:
        fd, tmp_name = tempfile.mkstemp(dir=output_path.parent, suffix=".xlsx")
        os.close(fd)
        tmp = Path(tmp_name)
        write_biosample_template(tmp)
        wb = load_workbook(tmp)

        def put(ws, r, c, v):
            cell = ws.cell(row=r, column=c, value=v)
            cell.data_type = "s"  # openpyxl turns "=..." into a formula Excel would run; keep it text
            cell.number_format = "@"  # text, never a number

        for r, cells in enumerate(data, start=2):
            for c, name in enumerate(DATA_COLUMNS, start=1):
                if v := cells.get(name):
                    put(wb["data"], r, c, v)
        put(wb["panels"], 2, 1, panel)
        put(wb["panels"], 2, PANEL_COLUMNS.index("SpecimenType") + 1, specimen or "serum")
        wb.save(tmp)
        os.chmod(tmp, 0o666 & ~_UMASK)  # mkstemp makes it owner-only
        os.replace(tmp, output_path)
    except OSError as exc:
        raise MigrationError(f"{output_path}: cannot write ({exc})") from exc
    finally:
        if tmp is not None:
            tmp.unlink(missing_ok=True)
    return rep
