"""Plain-language notes for the preview when a converter changes or skips labels (BIDS-safe cleaning)."""

from __future__ import annotations

from typing import Sequence


def shown_examples(items: Sequence[str], limit: int = 3) -> str:
    return ", ".join(items[:limit]) + (f" (+{len(items) - limit} more)" if len(items) > limit else "")


def missing_id_note(positions: Sequence[int], limit: int = 8) -> str:
    """Warning for rows that have no usable participant ID; ``positions`` are 1-based data rows."""
    if not positions:
        return ""
    return f"{len(positions)} row(s) have no participant ID and will be skipped (data rows {shown_examples([str(p) for p in positions], limit)})."


def cleaning_note(raw: Sequence[object], cleaned: Sequence[str], kind: str, prefix: str, limit: int = 3) -> str:
    """Note listing labels whose characters were removed; adding or keeping ``prefix`` is not a change."""
    changes: dict[str, str] = {}
    for original, result in zip(raw, cleaned):
        text = str(original).strip()
        if not result or not text:
            continue
        label = text[len(prefix):] if text[: len(prefix)].lower() == prefix.lower() else text
        if result[len(prefix):] != label:
            changes.setdefault(text, result)
    if not changes:
        return ""
    listed = [f"'{before}' → {after}" for before, after in changes.items()]
    return (
        f"{len(changes)} {kind}(s) were cleaned to BIDS-safe labels (letters and digits only): "
        f"{shown_examples(listed, limit)}."
    )
