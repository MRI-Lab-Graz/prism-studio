"""Shared participant ID selection helpers for web and CLI workflows."""

from __future__ import annotations

from typing import Any, Callable

from src.converters.id_detection import detect_id_column, has_prismmeta_columns


DetectIdFn = Callable[..., str | None]


def _normalize_source_format(source_format: str) -> str:
    """Normalize suffix/source format tokens to id_detection-compatible values."""
    normalized = str(source_format or "").strip().lower()
    if normalized.startswith("."):
        normalized = normalized[1:]
    return normalized or "xlsx"


def find_exact_participant_id_column(columns: list[str]) -> str | None:
    for col in columns:
        col_name = str(col or "").strip()
        if col_name.lower() == "participant_id":
            return col_name
    return None


def resolve_participants_id_selection(
    columns: list[str],
    source_format: str,
    detect_id_fn: DetectIdFn = detect_id_column,
    has_prismmeta: bool | None = None,
    explicit_id_column: str | None = None,
) -> dict[str, Any]:
    """Resolve participant ID selection with strict participant_id-first semantics.

    Rules:
    1) If an exact participant_id column exists, use it directly.
    2) Otherwise, require explicit manual selection from caller/UI.
    """

    source_columns = [str(col) for col in columns]
    normalized_source_format = _normalize_source_format(source_format)
    participant_id_column = find_exact_participant_id_column(source_columns)
    explicit_id = str(explicit_id_column or "").strip() or None
    has_pm = (
        bool(has_prismmeta)
        if has_prismmeta is not None
        else has_prismmeta_columns(source_columns)
    )

    suggested_id = detect_id_fn(
        source_columns,
        normalized_source_format,
        explicit_id_column=None,
        has_prismmeta=has_pm,
    )

    if participant_id_column:
        return {
            "resolved_id_column": participant_id_column,
            "source_id_column": participant_id_column,
            "suggested_id_column": suggested_id or participant_id_column,
            "participant_id_column": participant_id_column,
            "participant_id_found": True,
            "id_selection_required": False,
        }

    if explicit_id:
        resolved_id = detect_id_fn(
            source_columns,
            normalized_source_format,
            explicit_id_column=explicit_id,
            has_prismmeta=has_pm,
        )
        return {
            "resolved_id_column": resolved_id,
            "source_id_column": resolved_id,
            "suggested_id_column": suggested_id,
            "participant_id_column": None,
            "participant_id_found": False,
            "id_selection_required": False,
        }

    return {
        "resolved_id_column": None,
        "source_id_column": None,
        "suggested_id_column": suggested_id,
        "participant_id_column": None,
        "participant_id_found": False,
        "id_selection_required": True,
    }
