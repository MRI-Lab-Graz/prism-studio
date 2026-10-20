"""Tell new LimeSurvey responses from ones the project already holds.

A response's identity in the project is the fingerprint recorded for it in
``code/survey_imports.json`` (outside the PRISM-checked BIDS folders):
``{"version": 1, "responses": {"sub-1": {"ses-1": ["<startdate>", "<seed>", "<token>"]}},
"seen": {"<survey id>": {"<response id>": ["<submitdate>", "<lastpage>"]}}}``.
``seen`` remembers every response of an imported file, finished or not, in the state it was reviewed in.
Session labels are compared as exact strings (never normalized).
"""

from __future__ import annotations

import json
from pathlib import Path

FINGERPRINT_COLUMNS = ("startdate", "seed", "token")
LEDGER = Path("code") / "survey_imports.json"


def _clean(value) -> str:
    if value is None or (isinstance(value, float) and value != value):
        return "n/a"
    return str(value)


def row_fingerprint(row, columns=FINGERPRINT_COLUMNS) -> tuple[str, ...]:
    """Fingerprint of one response row, as the ledger stores it."""
    return tuple(_clean(row.get(c)) for c in columns)


def _read_ledger(root: str | Path) -> dict:
    try:
        data = json.loads((Path(root) / LEDGER).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}
    return data if isinstance(data, dict) else {}


def _load_ledger(root: str | Path) -> dict[str, dict[str, list[str]]]:
    responses = _read_ledger(root).get("responses")
    return responses if isinstance(responses, dict) else {}


def seen_entry(row) -> tuple[str, list[str]]:
    """(key, state) of a response for the "seen" memory: its id and (submitdate, lastpage)."""
    from src.participants_sessions import session_label

    key = session_label(row.get("id")) or "|".join(row_fingerprint(row))
    return key, [session_label(row.get("submitdate")), session_label(row.get("lastpage"))]


def record_imports(
    project_root: str | Path,
    output_root: str | Path,
    entries,
    *,
    seen: dict[str, list[str]] | None = None,
    survey_id: str = "default",
) -> None:
    """Add ``(sub, ses, fingerprint)`` entries and ``seen`` responses to the project's ledger, written under ``output_root``.

    The GUI converts into a scratch ``output_root`` and copies it into the project,
    so the project's ledger is merged in here and the copy carries the full result.
    """
    data = _read_ledger(project_root)
    responses = _load_ledger(project_root)
    for sub, ses, fp in entries:
        responses.setdefault(sub, {})[ses] = list(fp)
    all_seen = data.get("seen") if isinstance(data.get("seen"), dict) else {}
    if seen:
        all_seen.setdefault(survey_id, {}).update(seen)
    path = Path(output_root) / LEDGER
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps({"version": 1, "responses": responses, "seen": all_seen}, indent=2) + "\n",
        encoding="utf-8",
    )


class ImportIndex:
    """Fingerprints of the responses already imported below ``root``."""

    def __init__(self, root: str | Path):
        seen = _read_ledger(root).get("seen")
        self._seen: dict[str, dict[str, list[str]]] = seen if isinstance(seen, dict) else {}
        self._by_slot: dict[tuple[str, str], tuple[str, ...]] = {
            (sub, ses): tuple(fp) for sub, slots in _load_ledger(root).items() for ses, fp in slots.items()
        }

    def where_imported(self, sub: str, fingerprint) -> str | None:
        """Session under which this response is already stored for ``sub``."""
        return next(
            (s for (u, s), fp in self._by_slot.items() if u == sub and fp == fingerprint),
            None,
        )

    def is_seen(self, survey_id: str, key: str, state) -> bool:
        """True when this response was reviewed before and has not changed since."""
        stored = (self._seen.get(survey_id) or {}).get(key)
        return stored is not None and list(stored) == list(state)

    def is_imported(self, fingerprint) -> bool:
        """True when this response is recorded anywhere in the project (whatever its session)."""
        return fingerprint in self._by_slot.values()

    def classify(self, sub: str, ses: str, fingerprint, *, target_exists: bool) -> str:
        """skip_imported | skip_unverified | conflict | moved | import

        A recorded response is skipped as a whole: a questionnaire file the project
        never had (a sociodemographic one, say) does not make it new again.
        """
        stored = self._by_slot.get((sub, ses))
        if stored == fingerprint:
            return "skip_imported"
        if target_exists:
            return "skip_unverified" if stored is None else "conflict"
        return "moved" if self.where_imported(sub, fingerprint) else "import"


class ExistingPolicy:
    """Per-conversion decisions: one ``decide`` call per (response row, target file)."""

    def __init__(self, root: str | Path, available_columns, output_root: str | Path | None = None):
        # Files are written under output_root (a scratch folder in the GUI) but
        # "already there" means: under root (the project).
        self._root = Path(root)
        self._output_root = Path(output_root) if output_root is not None else self._root
        self.columns = tuple(c for c in FINGERPRINT_COLUMNS if c in set(available_columns))
        self._index = ImportIndex(root)
        self._verdicts: dict[tuple, set[str]] = {}

    def decide(self, row, sub: str, ses: str, target: str | Path) -> str:
        fp = row_fingerprint(row, self.columns)
        existing = self._root / Path(target).relative_to(self._output_root)
        verdict = self._index.classify(sub, ses, fp, target_exists=existing.exists())
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
