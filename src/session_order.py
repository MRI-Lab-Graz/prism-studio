"""Per-participant session order for projects whose sessions are conditions.

Spec: docs/superpowers/specs/2026-11-02-content-sessions-design.md

In a project with ``StudyDesign.SessionLabels = content`` the date numbering of
repeated responses (1, 2, ...) is not the same condition for everyone. The lab
records each participant's order in ``code/session_order.tsv``
(``participant_id``, ``session_number``, ``session``); nothing is guessed or
generated. Participant IDs are LimeSurvey's own (a leading ``sub-`` is ignored),
numbers and names are exact strings.
"""

from __future__ import annotations

import csv
import io
import os
import re
from collections.abc import Iterable, Mapping
from pathlib import Path

from src.participants_sessions import _natural_key, session_label
from src.session_map import _TARGET, SessionMapError, _root, project_session_labels

ORDER_FILE = Path("code") / "session_order.tsv"
COLUMNS = ("participant_id", "session_number", "session")

Order = dict[str, dict[str, str]]


class SessionOrderError(SessionMapError):
    """Anything wrong with the session order file or a requested change."""


class SessionsNotOrderedError(SessionOrderError):
    def __init__(self, problems: Iterable[str]) -> None:
        self.problems = list(problems)
        super().__init__(
            "Sessions cannot be named from the session order: "
            + "; ".join(self.problems)
            + ". Name these responses in the review table (`sessions set --session <name>`) "
            f"or fix {ORDER_FILE.as_posix()}."
        )


def order_path(project_path: str | Path) -> Path:
    return _root(project_path) / ORDER_FILE


def participant_key(raw: object) -> str:
    """The participant as LimeSurvey has it; one leading 'sub-' is ignored."""
    key = session_label(raw)
    return key[4:] if key.startswith("sub-") else key


def _name(value: object, where: str) -> str:
    name = str(value).strip()
    if not _TARGET.fullmatch(name):
        raise SessionOrderError(
            f"{where}: session name must be letters and digits only, got {value!r}"
        )
    return name


def _add(order: Order, participant: str, number: str, name: str, where: str) -> None:
    if not participant or not number:
        raise SessionOrderError(f"{where}: participant_id and session_number must be filled")
    entries = order.setdefault(participant, {})
    if number in entries:
        raise SessionOrderError(f"{where}: {participant!r} has session_number {number!r} twice")
    if name in entries.values():
        raise SessionOrderError(f"{where}: {participant!r} has the session {name!r} twice")
    entries[number] = name


def _from_rows(rows: Iterable[Mapping[str, object]], source: str) -> Order:
    order: Order = {}
    for line, row in rows:
        where = f"{source} line {line}"
        _add(
            order,
            participant_key(row["participant_id"]),
            session_label(row["session_number"]),
            _name(row["session"], where),
            where,
        )
    return order


def _check_columns(columns: Iterable[object], source: str) -> None:
    missing = [c for c in COLUMNS if c not in list(columns)]
    if missing:
        raise SessionOrderError(f"{source} lacks the column(s): {', '.join(missing)}")


def load_session_order(project_path: str | Path) -> Order:
    path = order_path(project_path)
    if not path.is_file():
        return {}
    try:
        text = path.read_text(encoding="utf-8-sig")
    except OSError as exc:
        raise SessionOrderError(f"{path} could not be read: {exc}") from exc
    reader = csv.DictReader(io.StringIO(text), delimiter="\t")
    _check_columns(reader.fieldnames or [], str(path))
    return _from_rows(((n, r) for n, r in enumerate(reader, start=2)), str(path))


def save_session_order(project_path: str | Path, order: Order) -> None:
    path = order_path(project_path)
    checked: Order = {}
    for participant, entries in order.items():
        for number, name in entries.items():
            _add(checked, participant_key(participant), session_label(number),
                 _name(name, str(path)), str(path))
    rows = [
        (p, n, checked[p][n])
        for p in sorted(checked, key=_natural_key)
        for n in sorted(checked[p], key=_natural_key)
    ]
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(".tsv.tmp")
    with tmp.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.writer(handle, delimiter="\t", lineterminator="\n")
        writer.writerow(COLUMNS)
        writer.writerows(rows)
    os.replace(tmp, path)


def set_order_entries(
    project_path: str | Path, participant: str, entries: Mapping[str, str]
) -> Order:
    order = load_session_order(project_path)
    merged = dict(order.get(participant_key(participant), {}))
    merged.update({session_label(n): _name(v, "entries") for n, v in entries.items()})
    order[participant_key(participant)] = merged
    save_session_order(project_path, order)
    return order


def remove_order_entries(
    project_path: str | Path, participant: str, numbers: Iterable[str] | None = None
) -> Order:
    """Drop a participant (or only some of their numbers); unknown ones raise."""
    order = load_session_order(project_path)
    key = participant_key(participant)
    if key not in order:
        raise SessionOrderError(f"Not in the session order (IDs match exactly): {participant!r}")
    if numbers is None:
        del order[key]
    else:
        wanted = [session_label(n) for n in numbers]
        unknown = [n for n in wanted if n not in order[key]]
        if unknown:
            raise SessionOrderError(f"{participant!r} has no session_number {', '.join(unknown)}")
        for n in wanted:
            del order[key][n]
        if not order[key]:
            del order[key]
    save_session_order(project_path, order)
    return order


def import_session_order(
    project_path: str | Path, file: str | Path, replace: bool = False
) -> Order:
    """Read a prepared .tsv/.csv/.xlsx; the whole file is validated before anything is saved."""
    import pandas as pd

    file = Path(file)
    kind = file.suffix.lower()
    try:
        if kind in (".xlsx", ".xls"):
            df = pd.read_excel(file, dtype=str)
        else:
            df = pd.read_csv(file, dtype=str, sep=None, engine="python", encoding="utf-8-sig")
    except (OSError, ValueError) as exc:
        raise SessionOrderError(f"{file} could not be read: {exc}") from exc
    _check_columns(df.columns, str(file))
    imported = _from_rows(
        ((n, r) for n, r in enumerate(df.fillna("").to_dict("records"), start=2)), str(file)
    )
    order = {} if replace else load_session_order(project_path)
    for participant, entries in imported.items():
        order.setdefault(participant, {}).update(entries)
    save_session_order(project_path, order)  # re-checks the merged result
    return order


def content_session_order(project_path: str | Path | None) -> Order | None:
    """The order of a content project ({} when none is recorded yet); None otherwise."""
    if not project_path or project_session_labels(project_path) != "content":
        return None
    return load_session_order(project_path)
