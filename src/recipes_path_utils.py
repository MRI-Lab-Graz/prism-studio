"""Pure path, filename, and participant-ID helpers for survey recipes.

These helpers are intentionally side-effect free and have no dependencies
on the larger recipes pipeline. They are re-exported from
``src.recipes_surveys`` to preserve the historical import surface.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any


def _normalize_survey_key(raw: str) -> str:
    s = str(raw or "").strip().lower()
    if not s:
        return s
    for prefix in ("recipe-", "survey-", "task-"):
        if s.startswith(prefix):
            s = s[len(prefix) :]
    return s


def _extract_task_from_survey_filename(path: Path) -> str | None:
    stem = path.stem
    # Examples:
    # sub-001_ses-1_task-ads_survey.tsv
    # sub-001_ses-1_survey-ads_survey.tsv
    # (legacy) sub-001_ses-1_task-ads_beh.tsv
    # (legacy) sub-001_ses-1_survey-ads_beh.tsv
    task_value = None
    acq_value = None
    for token in stem.split("_"):
        if token.startswith("task-"):
            task_value = _normalize_survey_key(token)
        elif token.startswith("survey-"):
            task_value = _normalize_survey_key(token)
        elif token.startswith("acq-"):
            acq_value = token[len("acq-") :].strip().lower()

    if not task_value:
        return None
    if acq_value:
        return f"{task_value}_acq-{acq_value}"
    return task_value


def _extract_acq_from_filename(path: Path) -> str | None:
    for token in path.stem.split("_"):
        if token.startswith("acq-"):
            value = token[len("acq-") :].strip().lower()
            if value:
                return value
    return None


def _strip_acq_from_task(task_name: str | None) -> str | None:
    if not task_name:
        return None
    return task_name.split("_acq-", 1)[0]


def _strip_suffix(stem: str) -> tuple[str, str | None]:
    for suffix in ("_survey", "_beh"):
        if stem.endswith(suffix):
            return stem[: -len(suffix)], suffix
    return stem, None


def _infer_sub_ses_from_path(path: Path) -> tuple[str | None, str | None]:
    sub_id = None
    ses_id = None
    for part in path.parts:
        # Avoid treating the TSV filename (e.g. "sub-001_ses-1_task-ads_beh.tsv")
        # as a subject/session folder.
        if sub_id is None and part.startswith("sub-") and Path(part).suffix == "":
            sub_id = part
        if ses_id is None and part.startswith("ses-") and Path(part).suffix == "":
            ses_id = part
    return sub_id, ses_id


def _infer_run_from_path(path: Path) -> str | None:
    """Extract run entity (e.g., 'run-01') from BIDS filename stem."""
    for part in path.stem.split("_"):
        if part.startswith("run-") and len(part) > 4:
            return part
    return None


def _normalize_participant_id_for_join(value: str | None) -> str | None:
    """Normalize participant IDs to BIDS-like `sub-<id>` for merge stability."""
    raw = str(value or "").strip()
    if not raw:
        return None
    if raw.lower() in {"nan", "none", "null", "na", "n/a"}:
        return None
    lowered = raw.lower()
    if lowered.startswith("sub-"):
        rest = raw[4:].strip()
        return f"sub-{rest}" if rest else None
    if lowered.startswith("sub"):
        rest = raw[3:].lstrip("-_")
        return f"sub-{rest}" if rest else None
    return f"sub-{raw}"


def _participant_join_key(value: str | None) -> str | None:
    """Build a tolerant join key so `sub-001`, `001`, and `1` match."""
    normalized = _normalize_participant_id_for_join(value)
    if not normalized:
        return None
    token = normalized[4:] if normalized.startswith("sub-") else normalized
    token = token.strip().lower()
    if not token:
        return None
    if token.isdigit():
        return str(int(token))
    return token


def _is_missing_cell_value(value: Any) -> bool:
    if value is None:
        return True
    text = str(value).strip().lower()
    return text in {"", "n/a", "na", "nan", "none", "null"}
