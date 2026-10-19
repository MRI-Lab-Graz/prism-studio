"""Problems in a participants source table, reported before anything is written."""

from __future__ import annotations

from typing import Any

from src.cleaning_notes import shown_examples

import pandas as pd

_MISSING = {"", "n/a", "na", "nan", "none"}


_AGE_LIMITS = (0, 120)  # years; anything else in a column called "age" is a typing error
_NUMERIC_SHARE = 0.5  # a column is numeric when at least this share of its values are numbers


def _number_or_none(value: Any) -> float | None:
    try:
        number = float(str(value).strip().replace(",", "."))
    except ValueError:
        return None
    return number if number == number else None  # "nan" is no measurement


def find_participant_data_problems(
    df: pd.DataFrame, id_column: str, columns: list[str] | None = None
) -> dict[str, list[str]]:
    """Problems in a source table that the preview reports before anything is written.

    ``warnings``: rows that cannot become participants (no ID) and different IDs that
    become the same PRISM ID. ``errors``: text in a numeric column and ages outside 0-120.
    """
    from src.participants_converter import ParticipantsConverter

    warnings: list[str] = []
    errors: list[str] = []
    if id_column not in df.columns:
        return {"warnings": warnings, "errors": errors}

    from src.cleaning_notes import cleaning_note, missing_id_note

    ids = df[id_column]
    cleaned = [ParticipantsConverter._normalize_participant_id(value) for value in ids]
    note = missing_id_note([pos + 1 for pos, value in enumerate(cleaned) if value is None])
    if note:
        warnings.append(note)
    note = cleaning_note(list(ids), [c or "" for c in cleaned], "participant ID", "sub-")
    if note:
        warnings.append(note)

    typed_by_id: dict[str, list[str]] = {}
    for value in ids:
        prism_id = ParticipantsConverter._normalize_participant_id(value)
        typed = str(value).strip()
        if prism_id and typed not in typed_by_id.setdefault(prism_id, []):
            typed_by_id[prism_id].append(typed)
    for prism_id, typed in typed_by_id.items():
        if len(typed) > 1:
            warnings.append(
                f"Different IDs in the source become the same participant {prism_id}: "
                f"{', '.join(repr(t) for t in typed)}. Their rows will be merged - check that they are one person."
            )

    for col in (columns if columns is not None else df.columns):
        if str(col) == id_column or col not in df.columns:
            continue
        values = [(str(pid).strip(), str(v).strip()) for pid, v in zip(ids, df[col]) if str(v).strip().lower() not in _MISSING]
        numbers = [_number_or_none(v) for _, v in values]
        if not values or sum(n is not None for n in numbers) / len(values) < _NUMERIC_SHARE:
            continue
        text = [f"{pid}: '{v}'" for (pid, v), n in zip(values, numbers) if n is None]
        if text:
            errors.append(f"Column '{col}' is numeric but {len(text)} value(s) are not numbers - {shown_examples(text)}.")
        if str(col).strip().lower() == "age":
            low, high = _AGE_LIMITS
            bad = [f"{pid}: {v}" for (pid, v), n in zip(values, numbers) if n is not None and not low <= n <= high]
            if bad:
                errors.append(f"Column '{col}' has {len(bad)} age(s) outside {low}-{high} years - {shown_examples(bad)}.")
    return {"warnings": warnings, "errors": errors}
