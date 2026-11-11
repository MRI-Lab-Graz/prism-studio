"""Read the biosample template (xlsx/csv): normalise cells, collect problems."""

import csv
import datetime as dt
import math
import re
from pathlib import Path

from openpyxl import load_workbook

from src.biosample_template import DATA_COLUMNS, PANEL_COLUMNS

_CODES = {"N/A": "n/a", "<LOD": "<LOD", "<LLOQ": "<LLOQ", ">ULOQ": ">ULOQ"}
_REQUIRED = ("participant_id", "panel", "analyte", "value")
_TIME = re.compile(r"^\d{1,2}:\d{2}$")


def _number(text: str) -> float:
    x = float(text.replace(",", "."))
    if not math.isfinite(x):
        raise ValueError
    return x


def _fmt(x: float) -> str:
    # 15 significant digits drop float noise (2.0099999999999998 -> 2.01) and keep tiny or
    # large values (1e-12, 123456789.123); exponent text is read as a number by the validator
    return f"{x:.15g}"


def normalise_value(raw: object) -> tuple[str, float | None]:
    """Return (cell text, detection limit or None); ValueError when unreadable."""
    if raw is None or (isinstance(raw, str) and not raw.strip()):
        return "n/a", None
    if isinstance(raw, bool) or isinstance(raw, (dt.date, dt.time)):
        raise ValueError(f"{raw!r} is not a number (dates and times are not values)")
    if isinstance(raw, (int, float)):
        return _fmt(float(raw)), None
    text = str(raw).strip()
    if text.upper() in _CODES:
        return _CODES[text.upper()], None
    # ponytail: provisional, to be confirmed with the lab: a bare "<5" is taken as a
    # limit of detection (<LOD). If it is a quantification limit, change it here only.
    if text.startswith("<"):
        try:
            return "<LOD", float(_fmt(_number(text[1:].strip())))
        except ValueError:
            pass
    else:
        try:
            return _fmt(_number(text)), None
        except ValueError:
            pass
    raise ValueError(f"{text!r} is not a number or one of n/a, <LOD, <LLOQ, >ULOQ, <number")


def _text(v: object) -> str:
    if v is None:
        return ""
    if isinstance(v, float) and v.is_integer():
        return str(int(v))
    return str(v).strip()


def _time(v: object) -> str:
    if isinstance(v, dt.datetime) or isinstance(v, dt.date):
        raise ValueError("must be hh:mm, not a date")
    if isinstance(v, dt.time):
        return v.strftime("%H:%M")
    s = _text(v)
    if not s:
        return s
    try:
        if not _TIME.match(s):
            raise ValueError
        return dt.datetime.strptime(s, "%H:%M").strftime("%H:%M")
    except ValueError:
        raise ValueError(f"{s!r} must be hh:mm") from None


def _sheets(path: Path) -> tuple[list[list], list[list] | None]:
    if path.suffix.lower() == ".csv":
        with path.open(newline="", encoding="utf-8-sig") as f:
            return list(csv.reader(f)), None
    wb = load_workbook(path, read_only=True, data_only=True)
    try:  # read-only keeps the file open until closed (Windows cannot delete it then)
        grid = lambda ws: [list(r) for r in ws.iter_rows(values_only=True)]  # noqa: E731
        if "data" not in wb.sheetnames:
            raise ValueError("sheet 'data' is missing")
        return grid(wb["data"]), grid(wb["panels"]) if "panels" in wb.sheetnames else None
    finally:
        wb.close()


def _too_wide(r, head) -> bool:
    """A cell beyond the header, or a filled one under an empty header (an unquoted "1,5" in a CSV).

    Beyond the header even an empty CSV cell counts: "...,1,5,nmol/L," has one separator too many.
    (xlsx rows come padded to the header's width, so there only filled cells count.)
    """
    return any(v is not None if i >= len(head) else not head[i] and _text(v) for i, v in enumerate(r))


_WIDE = "more cells than columns; quote decimals or use the .xlsx"


def _header(rows, sheet, expected, required, problems):
    head = [_text(c) for c in rows[0]] if rows else []
    unknown = [c for c in head if c and c not in expected]
    missing = [c for c in required if c not in head]
    if unknown:
        problems.append(f"{sheet}: unknown column(s) {', '.join(unknown)}")
    if missing:
        problems.append(f"{sheet}: missing column(s) {', '.join(missing)}")
    return None if missing else head


def read_template(path: Path, specimen: str | None = None):
    """Return (measurement rows, panels by name, problems); bad content never raises."""
    path = Path(path)
    problems: list[str] = []
    try:
        data, panel_rows = _sheets(path)
    except Exception as exc:  # unreadable file or sheet is a message, not a traceback
        return [], {}, [f"{path.name}: cannot read ({exc})"]

    panels: dict[str, dict] = {}
    if panel_rows is not None:
        head = _header(panel_rows, "panels", PANEL_COLUMNS, ("panel",), problems)
        first_row: dict[str, int] = {}
        for n, r in enumerate(panel_rows[1:] if head else [], start=2):
            if _too_wide(r, head):
                problems.append(f"panels row {n}: {_WIDE}")
                continue
            cells = {h: _text(r[i]) if i < len(r) else "" for i, h in enumerate(head) if h}
            if not any(cells.values()):
                continue
            if not cells["panel"]:
                problems.append(f"panels row {n}: panel name is empty")
            elif cells["panel"] in first_row:
                problems.append(f"panels rows {first_row[cells['panel']]} and {n}: "
                                f"panel {cells['panel']} is defined twice")
            elif not (cells.get("SpecimenType") or specimen):
                problems.append(f"panels row {n}: SpecimenType is empty for panel {cells['panel']}"
                                " (fill it in or pass --specimen)")
            else:
                cells["SpecimenType"] = cells.get("SpecimenType") or specimen
                first_row[cells["panel"]] = n
                panels[cells["panel"]] = {**cells, "limits": {}}
    elif not specimen:
        problems.append("panels: sheet is missing; add a 'panels' sheet or pass --specimen")

    rows: list[dict] = []
    units: dict[tuple[str, str], str] = {}
    head = _header(data, "data", DATA_COLUMNS, _REQUIRED, problems)
    for n, r in enumerate(data[1:] if head else [], start=2):
        if _too_wide(r, head):
            problems.append(f"data row {n}: {_WIDE}")
            continue
        cells = {h: r[i] if i < len(r) else None for i, h in enumerate(head) if h in DATA_COLUMNS}
        if all(v is None or (isinstance(v, str) and not v.strip()) for v in cells.values()):
            continue
        row = {c: _text(cells.get(c)) for c in DATA_COLUMNS}
        bad = [c for c in _REQUIRED[:3] if not row[c]]
        if bad:
            problems.append(f"data row {n}: {', '.join(bad)} is empty")
            continue
        try:
            row["collection_time"] = _time(cells.get("collection_time"))
        except ValueError as exc:
            problems.append(f"data row {n}: collection_time {exc}")
            continue
        try:
            row["value"], limit = normalise_value(cells.get("value"))
        except ValueError as exc:
            problems.append(f"data row {n}: value {exc}")
            continue
        row["row"], row["limit"] = n, limit
        rows.append(row)

        name, analyte = row["panel"], row["analyte"]
        if name not in panels:
            if not specimen:
                problems.append(f"data row {n}: panel {name!r} is not defined in the panels sheet")
                continue
            panels[name] = {"panel": name, "SpecimenType": specimen, "limits": {}}
        if limit is not None:
            panels[name]["limits"].setdefault(analyte, []).append(limit)
        if row["unit"]:
            seen = units.setdefault((name, analyte), row["unit"])
            if seen != row["unit"]:
                problems.append(f"data row {n}: analyte {analyte} in panel {name} has two units "
                                f"({seen} and {row['unit']})")
    return rows, panels, problems
