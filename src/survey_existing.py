"""Tell new LimeSurvey responses from ones the project already holds.

A response's identity in the project is the fingerprint stored in its
``sub-X_ses-N_tool-limesurvey_survey.tsv``. Session labels are compared as
exact strings (never normalized).
"""

from __future__ import annotations

import csv
from pathlib import Path

FINGERPRINT_COLUMNS = ("startdate", "seed", "token")


def _clean(value) -> str:
    if value is None or (isinstance(value, float) and value != value):
        return "n/a"
    return str(value)


def row_fingerprint(row, columns=FINGERPRINT_COLUMNS) -> tuple[str, ...]:
    """Fingerprint of one response row, in the form the tool file stores it."""
    return tuple(_clean(row.get(c)) for c in columns)


class ImportIndex:
    """Fingerprints of the responses already imported below ``root``."""

    def __init__(self, root: str | Path, columns=FINGERPRINT_COLUMNS):
        self.columns = tuple(columns)
        self._by_slot: dict[tuple[str, str], tuple[str, ...]] = {}
        for path in Path(root).glob("sub-*/ses-*/survey/*_tool-limesurvey_survey.tsv"):
            try:
                with open(path, encoding="utf-8", newline="") as f:
                    row = next(csv.DictReader(f, delimiter="\t"), None)
            except OSError:
                continue
            if row:
                sub, ses = path.parts[-4], path.parts[-3]
                self._by_slot[(sub, ses)] = row_fingerprint(row, self.columns)

    def where_imported(self, sub: str, fingerprint) -> str | None:
        """Session under which this response is already stored for ``sub``."""
        return next(
            (s for (u, s), fp in self._by_slot.items() if u == sub and fp == fingerprint),
            None,
        )

    def classify(self, sub: str, ses: str, fingerprint, *, target_exists: bool) -> str:
        """import | skip_imported | skip_unverified | conflict | moved"""
        stored = self._by_slot.get((sub, ses))
        if target_exists:
            if stored is None:
                return "skip_unverified"
            return "skip_imported" if stored == fingerprint else "conflict"
        if stored != fingerprint and self.where_imported(sub, fingerprint):
            return "moved"
        return "import"


class ExistingPolicy:
    """Per-conversion decisions: one ``decide`` call per (response row, target file)."""

    def __init__(self, root: str | Path, available_columns):
        self.columns = tuple(c for c in FINGERPRINT_COLUMNS if c in set(available_columns))
        self._index = ImportIndex(root, self.columns)
        self._verdicts: dict[tuple, set[str]] = {}

    def decide(self, row, sub: str, ses: str, target: str | Path) -> str:
        fp = row_fingerprint(row, self.columns)
        verdict = self._index.classify(sub, ses, fp, target_exists=Path(target).exists())
        self._verdicts.setdefault((sub, ses, fp), set()).add(verdict)
        return verdict

    def row_imported(self, row, sub: str, ses: str) -> bool:
        """True when at least one file of this response is being written."""
        return "import" in self._verdicts.get((sub, ses, row_fingerprint(row, self.columns)), ())

    def summary(self) -> dict:
        """Responses by outcome: new, already_imported, conflict, moved (+ unverified)."""
        out = dict.fromkeys(("new", "already_imported", "conflict", "moved", "unverified"), 0)
        details: list[dict] = []
        for (sub, ses, fp), verdicts in self._verdicts.items():
            if "conflict" in verdicts:
                kind = "conflict"
            elif "moved" in verdicts:
                kind = "moved"
            elif "import" in verdicts:
                kind = "new"
            else:
                kind = "already_imported"
            out[kind] += 1
            if "skip_unverified" in verdicts and kind == "already_imported":
                out["unverified"] += 1
            if kind in ("conflict", "moved"):
                details.append(
                    {"kind": kind, "subject": sub, "session": ses, "stored_session": self._index.where_imported(sub, fp)}
                )
        out["details"] = details
        return out
