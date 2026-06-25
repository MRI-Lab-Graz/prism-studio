"""Match incoming raw participant identifiers against a project's existing
canonical participant_id values (participants.tsv).

Different input sources (survey exports, biometrics spreadsheets, etc.) often
spell the same participant's ID differently -- e.g. a biometrics table using
bare "1" where the project's established convention is "sub-001". Without
matching, each source would otherwise create its own duplicate subject
folder for the same person.

This module only ever maps a raw id onto an *existing* canonical id when the
match is unambiguous (their numeric values agree after stripping leading
zeros, and exactly one existing participant matches). It never invents a
zero-padded id for a participant that doesn't already exist in
participants.tsv -- new participants keep falling back to the caller's
normal (uncoerced) id-building behavior. participants.tsv is the ground
truth; this only ever resolves *to* it, never reformats it.
"""

from __future__ import annotations

import csv
import re
from pathlib import Path
from typing import Callable, Iterable, Optional

_NUMERIC_LABEL_RE = re.compile(r"^0*([0-9]+)$")


def _numeric_key(label: str) -> Optional[str]:
    """Return the leading-zero-stripped numeric form of a label, or None if
    the label isn't purely numeric."""
    match = _NUMERIC_LABEL_RE.fullmatch(label)
    if not match:
        return None
    return match.group(1)


def _strip_sub_prefix(value: str) -> str:
    return value[4:] if value[:4].lower() == "sub-" else value


def load_existing_participant_ids(project_root: Path | str) -> set[str]:
    """Read a project's participants.tsv and return its canonical, BIDS-safe
    participant_id values (e.g. {"sub-001", "sub-002", ...}).

    Returns an empty set if the file is missing or can't be parsed -- callers
    should treat that as "no ground truth available yet", not an error.
    """
    participants_tsv = Path(project_root) / "participants.tsv"
    if not participants_tsv.is_file():
        return set()

    try:
        from .participants_converter import ParticipantsConverter
    except Exception:
        return set()

    existing_ids: set[str] = set()
    try:
        with participants_tsv.open("r", encoding="utf-8", newline="") as handle:
            reader = csv.DictReader(handle, delimiter="\t")
            headers = [str(field) for field in (reader.fieldnames or []) if field]
            if not headers:
                return existing_ids

            id_column = (
                "participant_id"
                if "participant_id" in headers
                else ParticipantsConverter._find_participant_id_source_column(headers)
            )
            if not id_column:
                return existing_ids

            for row in reader:
                normalized = ParticipantsConverter._normalize_participant_id(
                    (row or {}).get(id_column)
                )
                if normalized:
                    existing_ids.add(normalized)
    except Exception:
        return set()

    return existing_ids


def build_subject_id_matcher(
    existing_participant_ids: Iterable[str],
) -> Callable[[str], Optional[str]]:
    """Return a function that resolves an already-sanitized "sub-<label>" id
    to an existing canonical participant_id when there's an unambiguous
    numeric match, else returns None.
    """
    existing = set(existing_participant_ids)

    numeric_lookup: dict[str, list[str]] = {}
    for existing_id in existing:
        numeric_key = _numeric_key(_strip_sub_prefix(existing_id))
        if numeric_key is not None:
            numeric_lookup.setdefault(numeric_key, []).append(existing_id)

    def match(candidate_id: str) -> Optional[str]:
        if not candidate_id:
            return None
        if candidate_id in existing:
            return candidate_id

        numeric_key = _numeric_key(_strip_sub_prefix(candidate_id))
        if numeric_key is None:
            return None

        matches = numeric_lookup.get(numeric_key)
        if matches and len(matches) == 1:
            return matches[0]
        return None

    return match
