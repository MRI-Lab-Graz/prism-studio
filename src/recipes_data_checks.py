"""What looks wrong in the data a recipe is about to score (reported next to the result)."""

from __future__ import annotations

from typing import Any, Iterable

from src.cleaning_notes import shown_examples

_MISSING = {"", "n/a", "na", "nan", "none"}
_STRICT = {"require_all", "all", "strict"}


def _number(value: Any) -> float | None:
    try:
        return float(str(value).strip().replace(",", "."))
    except ValueError:
        return None


def _scores(recipe: dict) -> list[dict]:
    scores = list(recipe.get("Scores") or [])
    versioned = recipe.get("VersionedScores")
    if isinstance(versioned, dict):
        for variant_scores in versioned.values():
            scores.extend(variant_scores if isinstance(variant_scores, list) else [])
    return [s for s in scores if isinstance(s, dict)]


def _scale(template: dict, item: str) -> tuple[float, float] | None:
    levels = (template.get(item) or {}).get("Levels") if isinstance(template.get(item), dict) else None
    numbers = [_number(k) for k in levels] if isinstance(levels, dict) and levels else []
    return (min(numbers), max(numbers)) if numbers and None not in numbers else None


def recipe_data_warnings(
    recipe_id: str, recipe: dict, files: Iterable[tuple[str, dict[str, str]]], template: dict
) -> list[str]:
    """Warnings for one recipe: answers outside the scale, text answers, and sums over partial answers.

    ``files`` are (participant/session label, row) pairs of the questionnaire data.
    """
    scores = _scores(recipe)
    items = sorted({str(i) for s in scores for i in (s.get("Items") or [])})
    rows = list(files)
    out_of_range: list[str] = []
    not_numbers: list[str] = []
    for label, row in rows:
        for item in items:
            raw = str(row.get(item, "")).strip()
            if raw.lower() in _MISSING:
                continue
            number = _number(raw)
            scale = _scale(template, item)
            if number is None:
                not_numbers.append(f"{label} {item}={raw}")
            elif scale and not scale[0] <= number <= scale[1]:
                out_of_range.append(f"{label} {item}={raw}")

    warnings: list[str] = []
    if out_of_range:
        warnings.append(
            f"{recipe_id}: {len(out_of_range)} answer(s) outside the scale of the questionnaire "
            f"- {shown_examples(out_of_range)}. They are scored as they are."
        )
    if not_numbers:
        warnings.append(
            f"{recipe_id}: {len(not_numbers)} answer(s) are not a number - {shown_examples(not_numbers)}. "
            "They are counted as missing."
        )
    for score in scores:
        method = str(score.get("Method", "sum")).strip().lower()
        names = [str(i) for i in (score.get("Items") or [])]
        if method != "sum" or not names or score.get("MinValid") is not None:
            continue
        if str(score.get("Missing", "ignore")).strip().lower() in _STRICT:
            continue
        partial = 0
        for _, row in rows:
            answered = sum(1 for i in names if _number(row.get(i, "")) is not None)
            partial += 0 < answered < len(names)
        if partial:
            warnings.append(
                f"{recipe_id} {score.get('Name', '')}: {partial} participant(s) answered only some of the "
                f"{len(names)} items; the sum is computed from the answered items "
                '(set "Missing": "require_all" in the recipe to leave it empty).'
            )
    return warnings
