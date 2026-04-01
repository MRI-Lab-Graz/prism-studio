#!/usr/bin/env python3
"""Backfill explicit numeric survey metadata from survey response levels.

This is intended as a semi-automatic maintenance tool for survey templates.
It safely populates:
- DataType = integer
- MinValue / MaxValue

Optionally, it can also set:
- ScaleType = binary / likert / frequency / vas
- sanitize embedded score annotations from Levels

The optional ScaleType pass is deliberately separate because it is a stronger
semantic assumption than integer coding and numeric bounds.
"""

from __future__ import annotations

import argparse
import json
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from src.survey_scale_inference import infer_contiguous_numeric_levels_range
from src.text_sanitizer import sanitize_answer_text
from src.utils.io import dump_json_text

_RESERVED_KEYS = {
    "Technical",
    "Study",
    "Metadata",
    "Questions",
    "I18n",
    "LimeSurvey",
    "Scoring",
    "Normative",
    "StudyMetadata",
    "LimesurveyID",
}


_AGREEMENT_TERMS = (
    "strongly disagree",
    "disagree",
    "slightly disagree",
    "neither agree nor disagree",
    "neutral",
    "slightly agree",
    "agree",
    "strongly agree",
)

_INTENSITY_TERMS = (
    "not at all",
    "a little",
    "slightly",
    "somewhat",
    "moderately",
    "quite a bit",
    "a lot",
    "very much",
    "extremely",
    "completely",
    "totally",
)

_FREQUENCY_REGEX = re.compile(
    r"\b(never|rarely|sometimes|often|always|time|times|daily|weekly|monthly|yearly|annually|once|twice|or more|almost never|almost always|all the time|every day|every week|every month)\b",
    re.IGNORECASE,
)


@dataclass
class ItemBackfillChange:
    item_id: str
    fields: list[str] = field(default_factory=list)
    variant_id: str | None = None


@dataclass
class FileBackfillReport:
    path: Path
    changes: list[ItemBackfillChange] = field(default_factory=list)

    @property
    def changed(self) -> bool:
        return bool(self.changes)


def _get_question_items(data: dict[str, Any]) -> dict[str, Any]:
    questions = data.get("Questions")
    if isinstance(questions, dict):
        return questions
    return data


def _coerce_float(value: Any) -> float | None:
    if value in (None, ""):
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _iter_item_defs(data: dict[str, Any]):
    items_src = _get_question_items(data)
    for key, value in items_src.items():
        if key in _RESERVED_KEYS or not isinstance(value, dict):
            continue
        yield key, value


def _extract_sanitized_level_labels(scale_def: dict[str, Any]) -> list[str]:
    labels: list[str] = []
    levels = scale_def.get("Levels")
    if not isinstance(levels, dict):
        return labels

    for value in levels.values():
        if isinstance(value, dict):
            for localized_text in value.values():
                if isinstance(localized_text, str):
                    sanitized = sanitize_answer_text(localized_text)
                    if sanitized:
                        labels.append(sanitized.lower())
        elif isinstance(value, str):
            sanitized = sanitize_answer_text(value)
            if sanitized:
                labels.append(sanitized.lower())

    return labels


def _get_numeric_level_keys(scale_def: dict[str, Any]) -> list[int]:
    levels = scale_def.get("Levels")
    if not isinstance(levels, dict):
        return []

    numeric_keys: list[int] = []
    for key in levels:
        try:
            numeric_value = float(str(key).strip())
        except (TypeError, ValueError):
            return []
        if not numeric_value.is_integer():
            return []
        numeric_keys.append(int(numeric_value))
    return sorted(numeric_keys)


def _get_scale_range(scale_def: dict[str, Any]) -> tuple[int, int] | None:
    inferred = infer_contiguous_numeric_levels_range(scale_def.get("Levels"))
    if inferred is not None:
        return inferred

    min_value = scale_def.get("MinValue")
    max_value = scale_def.get("MaxValue")
    min_numeric = _coerce_float(min_value)
    max_numeric = _coerce_float(max_value)
    if min_numeric is None or max_numeric is None:
        return None

    if not min_numeric.is_integer() or not max_numeric.is_integer():
        return None
    return int(min_numeric), int(max_numeric)


def _looks_like_vas(scale_def: dict[str, Any]) -> bool:
    scale_range = _get_scale_range(scale_def)
    if scale_range is None:
        return False

    min_value, max_value = scale_range
    if (max_value - min_value) < 10:
        return False

    numeric_keys = _get_numeric_level_keys(scale_def)
    if len(numeric_keys) != 2 or numeric_keys != [min_value, max_value]:
        return False

    return True


def _looks_like_binary(scale_def: dict[str, Any]) -> bool:
    inferred = infer_contiguous_numeric_levels_range(scale_def.get("Levels"))
    if inferred is None:
        return False

    min_value, max_value = inferred
    return (max_value - min_value) == 1


def _looks_like_frequency(scale_def: dict[str, Any]) -> bool:
    inferred = infer_contiguous_numeric_levels_range(scale_def.get("Levels"))
    if inferred is None:
        return False

    labels = _extract_sanitized_level_labels(scale_def)
    if not labels:
        return False

    hits = sum(bool(_FREQUENCY_REGEX.search(label)) for label in labels)
    return hits >= max(2, (len(labels) + 1) // 2)


def _looks_like_likert(scale_def: dict[str, Any]) -> bool:
    inferred = infer_contiguous_numeric_levels_range(scale_def.get("Levels"))
    if inferred is None:
        return False
    if scale_def.get("Unit") not in (None, ""):
        return False

    labels = _extract_sanitized_level_labels(scale_def)
    if not labels:
        return False

    min_value, max_value = inferred
    level_count = (max_value - min_value) + 1
    if not (4 <= level_count <= 11):
        return False

    agreement_hits = sum(
        any(term in label for term in _AGREEMENT_TERMS) for label in labels
    )
    intensity_hits = sum(
        any(term in label for term in _INTENSITY_TERMS) for label in labels
    )
    return agreement_hits >= 2 or intensity_hits >= max(2, len(labels) // 2)


def _infer_scale_type(scale_def: dict[str, Any]) -> str | None:
    if _looks_like_vas(scale_def):
        return "vas"
    if _looks_like_binary(scale_def):
        return "binary"
    if _looks_like_frequency(scale_def):
        return "frequency"
    if _looks_like_likert(scale_def):
        return "likert"
    return None


def _sanitize_levels(scale_def: dict[str, Any]) -> bool:
    levels = scale_def.get("Levels")
    if not isinstance(levels, dict):
        return False

    changed = False
    for key, value in levels.items():
        if isinstance(value, dict):
            for locale, localized_text in value.items():
                if not isinstance(localized_text, str):
                    continue
                sanitized = sanitize_answer_text(localized_text)
                if sanitized != localized_text:
                    value[locale] = sanitized
                    changed = True
        elif isinstance(value, str):
            sanitized = sanitize_answer_text(value)
            if sanitized != value:
                levels[key] = sanitized
                changed = True
    return changed


def _backfill_single_item(
    item_id: str,
    item_def: dict[str, Any],
    *,
    apply_scale_type_likert: bool,
    apply_scale_type_heuristic: bool,
    strip_level_score_annotations: bool,
) -> list[ItemBackfillChange]:
    changes: list[ItemBackfillChange] = []

    inferred = infer_contiguous_numeric_levels_range(item_def.get("Levels"))
    changed_fields: list[str] = []
    if strip_level_score_annotations and _sanitize_levels(item_def):
        changed_fields.append("Levels")

    if inferred is not None:
        min_value, max_value = inferred

        if item_def.get("DataType") in (None, ""):
            item_def["DataType"] = "integer"
            changed_fields.append("DataType")
        if item_def.get("MinValue") in (None, ""):
            item_def["MinValue"] = min_value
            changed_fields.append("MinValue")
        if item_def.get("MaxValue") in (None, ""):
            item_def["MaxValue"] = max_value
            changed_fields.append("MaxValue")

    if item_def.get("ScaleType") in (None, ""):
        inferred_scale_type: str | None = None
        if apply_scale_type_heuristic:
            inferred_scale_type = _infer_scale_type(item_def)
        elif apply_scale_type_likert and _looks_like_likert(item_def):
            inferred_scale_type = "likert"

        if inferred_scale_type:
            item_def["ScaleType"] = inferred_scale_type
            changed_fields.append("ScaleType")

    if changed_fields:
        changes.append(
            ItemBackfillChange(
                item_id=item_id, fields=list(dict.fromkeys(changed_fields))
            )
        )

    variant_scales = item_def.get("VariantScales")
    if isinstance(variant_scales, list):
        for entry in variant_scales:
            if not isinstance(entry, dict):
                continue

            changed_fields = []
            if strip_level_score_annotations and _sanitize_levels(entry):
                changed_fields.append("Levels")

            inferred_variant = infer_contiguous_numeric_levels_range(
                entry.get("Levels")
            )
            if inferred_variant is not None:
                min_value, max_value = inferred_variant
                if entry.get("DataType") in (None, ""):
                    entry["DataType"] = "integer"
                    changed_fields.append("DataType")
                if entry.get("MinValue") in (None, ""):
                    entry["MinValue"] = min_value
                    changed_fields.append("MinValue")
                if entry.get("MaxValue") in (None, ""):
                    entry["MaxValue"] = max_value
                    changed_fields.append("MaxValue")

            if entry.get("ScaleType") in (None, ""):
                inferred_scale_type = None
                if apply_scale_type_heuristic:
                    inferred_scale_type = _infer_scale_type(entry)
                elif apply_scale_type_likert and _looks_like_likert(entry):
                    inferred_scale_type = "likert"

                if inferred_scale_type:
                    entry["ScaleType"] = inferred_scale_type
                    changed_fields.append("ScaleType")

            if changed_fields:
                deduped_fields = list(dict.fromkeys(changed_fields))
                changes.append(
                    ItemBackfillChange(
                        item_id=item_id,
                        variant_id=str(entry.get("VariantID") or "").strip() or None,
                        fields=deduped_fields,
                    )
                )

    return changes


def backfill_survey_data(
    data: dict[str, Any],
    *,
    apply_scale_type: bool = False,
    apply_scale_type_heuristic: bool = False,
    strip_level_score_annotations: bool = False,
) -> list[ItemBackfillChange]:
    changes: list[ItemBackfillChange] = []
    for item_id, item_def in _iter_item_defs(data):
        changes.extend(
            _backfill_single_item(
                item_id,
                item_def,
                apply_scale_type_likert=apply_scale_type,
                apply_scale_type_heuristic=apply_scale_type_heuristic,
                strip_level_score_annotations=strip_level_score_annotations,
            )
        )
    return changes


def backfill_survey_file(
    path: Path,
    *,
    apply_scale_type: bool = False,
    apply_scale_type_heuristic: bool = False,
    strip_level_score_annotations: bool = False,
    dry_run: bool = False,
) -> FileBackfillReport:
    data = json.load(open(path, encoding="utf-8"))
    changes = backfill_survey_data(
        data,
        apply_scale_type=apply_scale_type,
        apply_scale_type_heuristic=apply_scale_type_heuristic,
        strip_level_score_annotations=strip_level_score_annotations,
    )
    report = FileBackfillReport(path=path, changes=changes)

    if report.changed and not dry_run:
        path.write_text(dump_json_text(data), encoding="utf-8")

    return report


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Backfill explicit integer DataType and MinValue/MaxValue from contiguous numeric survey Levels."
    )
    parser.add_argument("path", help="Survey JSON file or directory")
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Report changes without writing files",
    )
    parser.add_argument(
        "--apply-scale-type-likert",
        action="store_true",
        help="Also set ScaleType=likert for 4-11 point contiguous integer scales",
    )
    parser.add_argument(
        "--apply-scale-type-heuristic",
        action="store_true",
        help="Also set ScaleType using a conservative likert/frequency/vas heuristic",
    )
    parser.add_argument(
        "--strip-level-score-annotations",
        action="store_true",
        help="Remove embedded score markers like {score=4} from Levels text",
    )
    args = parser.parse_args()

    target = Path(args.path)
    if target.is_file():
        files = [target]
    elif target.is_dir():
        files = sorted(target.glob("survey-*.json"))
    else:
        raise SystemExit(f"Path not found: {target}")

    file_reports: list[FileBackfillReport] = []
    for path in files:
        report = backfill_survey_file(
            path,
            apply_scale_type=args.apply_scale_type_likert,
            apply_scale_type_heuristic=args.apply_scale_type_heuristic,
            strip_level_score_annotations=args.strip_level_score_annotations,
            dry_run=args.dry_run,
        )
        if report.changed:
            file_reports.append(report)

    total_changes = sum(len(report.changes) for report in file_reports)
    print(
        f"{'Would update' if args.dry_run else 'Updated'} {len(file_reports)} file(s), {total_changes} item block(s)"
    )
    for report in file_reports[:20]:
        print(report.path)
        for change in report.changes[:10]:
            suffix = f" [VariantID={change.variant_id}]" if change.variant_id else ""
            print(f"  - {change.item_id}{suffix}: {', '.join(change.fields)}")
        if len(report.changes) > 10:
            print(f"  ... {len(report.changes) - 10} more")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
