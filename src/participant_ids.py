"""The participant ID rules: which column holds the ID, and what a BIDS-safe ``sub-<label>`` is.

Dependency-free on purpose: the validator checks participants.tsv against the folders with these
(also in the PyPI validator), and the participants converter writes IDs with the same code.
"""

from __future__ import annotations

import re
import unicodedata
from typing import Any


def normalize_participant_id(value: Any) -> str | None:
    """Return a BIDS-safe participant label without numeric coercion."""
    if value is None:
        return None

    text = str(value).strip()
    if not text or text.lower() in {"nan", "n/a", "na", "none"}:
        return None

    # Normalize to NFC before stripping non-ASCII characters. Without
    # this, a visually-identical name like "José" sanitizes
    # differently depending on which Unicode normalization form the
    # source system used: NFC's precomposed 'é' is stripped whole
    # (-> "Jos"), while NFD's decomposed 'e'+accent keeps the base
    # ASCII 'e' and only strips the combining mark (-> "Jose"). Two
    # collaborators on different platforms typing the "same" name
    # would otherwise get silently different, both-plausible-looking
    # participant ids with no error.
    text = unicodedata.normalize("NFC", text)

    label = text[4:] if text[:4].lower() == "sub-" else text
    label = re.sub(r"[^A-Za-z0-9]+", "", label)
    if not label:
        return None
    return f"sub-{label}"

def find_participant_id_source_column(columns: list[str]) -> str | None:
    """Find the most likely participant ID source column from a table header."""
    if not columns:
        return None

    # Prefer exact, explicit ID columns first
    preferred_exact = [
        "participant_id",
        "prism_participant_id",
        "participantid",
        "subject_id",
        "sub_id",
        "subject",
        "sub",
        "id",
    ]
    by_lower = {str(c).strip().lower(): c for c in columns}
    for key in preferred_exact:
        if key in by_lower:
            return by_lower[key]

    # Fallback: columns that contain both "participant" and "id"
    for column in columns:
        lowered = str(column).strip().lower()
        if "participant" in lowered and "id" in lowered:
            return column

    return None
