"""Shared physio/eyetracking batch-rename logic.

Extracted from app/src/web/blueprints/conversion_physio_handlers.py's
api_physio_rename (the Studio GUI's Converter -> Physio Renamer / File
Management renamer), which had no CLI equivalent despite being real,
non-trivial business logic (regex-based renaming, folder-path subject/
session inference, BIDS-organized output paths, subject-ID rewriting) —
see docs/_archive/GUI_BACKEND_AUDIT_2026-08-07.md, P2.

Both the GUI route and the CLI's `file-management rename-physio` command
call these functions, so the renaming rules can't drift between the two
entry points again.
"""

from __future__ import annotations

import re
from pathlib import Path, PurePosixPath

from src.utils.naming import normalize_filename

# ---------------------------------------------------------------------------
# Subject/session inference from a source file's folder path
# ---------------------------------------------------------------------------


def sanitize_bids_label(raw: str | None) -> str | None:
    cleaned = re.sub(r"[^A-Za-z0-9]", "", (raw or "").strip())
    return cleaned or None


def _split_parent_parts(path_value: str) -> list[str]:
    normalized_path = (path_value or "").replace("\\", "/")
    return [
        part
        for part in PurePosixPath(normalized_path).parts[:-1]
        if part not in {".", ".."}
    ]


def _part_at_level(parts_list: list[str], level_from_end: int) -> str | None:
    if not parts_list:
        return None
    idx = len(parts_list) - max(1, int(level_from_end))
    if idx < 0:
        idx = 0
    if idx >= len(parts_list):
        return None
    return parts_list[idx]


def _normalize_entity_label(part_value: str | None, entity: str) -> str | None:
    if part_value is None:
        return None
    if entity == "subject":
        sub_match = re.match(r"^sub[-_]?([A-Za-z0-9]+)$", part_value, re.IGNORECASE)
        if sub_match:
            return sanitize_bids_label(sub_match.group(1))
    if entity == "session":
        ses_match = re.match(r"^ses[-_]?([A-Za-z0-9]+)$", part_value, re.IGNORECASE)
        if ses_match:
            return sanitize_bids_label(ses_match.group(1))
        return sanitize_bids_label(part_value)
    return sanitize_bids_label(part_value)


def _extract_by_example(
    source_part: str | None,
    example_part: str | None,
    example_value: str,
    entity: str,
) -> str | None:
    if source_part is None:
        return None
    if not example_value:
        return _normalize_entity_label(source_part, entity)

    token = (example_value or "").strip()
    if not token:
        return _normalize_entity_label(source_part, entity)

    pos = example_part.find(token) if example_part is not None else -1
    if pos < 0 and example_part is not None:
        pos = example_part.lower().find(token.lower())

    if pos < 0:
        return _normalize_entity_label(source_part, entity)

    prefix = example_part[:pos]
    suffix = example_part[pos + len(token) :]

    candidate = source_part
    if prefix and candidate.startswith(prefix):
        candidate = candidate[len(prefix) :]
    if suffix and candidate.endswith(suffix):
        candidate = candidate[: -len(suffix)]

    return _normalize_entity_label(candidate, entity)


def extract_subject_session_from_source_path(
    source_path: str,
    subject_level_from_end: int = 2,
    session_level_from_end: int = 1,
    example_path: str = "",
    subject_example_value: str = "",
    session_example_value: str = "",
) -> tuple[str | None, str | None]:
    """Infer BIDS subject/session labels from a source file's folder path.

    Two strategies, tried in order: (1) look for a literal sub-XXX/ses-XXX
    path segment anywhere in the path; (2) fall back to positional
    extraction at a configured folder depth, optionally guided by an
    example path + example value pair (e.g. "the subject ID is the digits
    that appear where '1291003' appears in this example path").
    """
    normalized = (source_path or "").replace("\\", "/")
    parts = [
        part for part in PurePosixPath(normalized).parts[:-1] if part not in {".", ".."}
    ]

    subject_label = None
    session_label = None

    sub_pattern = re.compile(r"^sub[-_]?([A-Za-z0-9]+)$", re.IGNORECASE)
    ses_pattern = re.compile(r"^ses[-_]?([A-Za-z0-9]+)$", re.IGNORECASE)

    for part in parts:
        if subject_label is None:
            sub_match = sub_pattern.match(part)
            if sub_match:
                subject_label = sanitize_bids_label(sub_match.group(1))
        if session_label is None:
            ses_match = ses_pattern.match(part)
            if ses_match:
                session_label = sanitize_bids_label(ses_match.group(1))

    subject_level = max(1, int(subject_level_from_end or 2))
    session_level = max(1, int(session_level_from_end or 1))

    src_parts = _split_parent_parts(source_path)
    ex_parts = _split_parent_parts(example_path) if example_path else []

    source_subject_part = _part_at_level(src_parts, subject_level)
    source_session_part = _part_at_level(src_parts, session_level)
    example_subject_part = _part_at_level(ex_parts, subject_level) if ex_parts else ""
    example_session_part = _part_at_level(ex_parts, session_level) if ex_parts else ""

    if source_subject_part is not None:
        subject_label = _extract_by_example(
            source_subject_part,
            example_subject_part or source_subject_part,
            (subject_example_value or "").strip(),
            "subject",
        )

    session_token = (session_example_value or "").strip()
    if session_token and source_session_part is not None:
        session_label = _extract_by_example(
            source_session_part,
            example_session_part or source_session_part,
            session_token,
            "session",
        )

    if subject_label is None and parts:
        subject_idx = len(parts) - subject_level
        if subject_idx < 0:
            subject_idx = 0
        subject_label = sanitize_bids_label(parts[subject_idx])

    if session_label is None and parts:
        session_idx = len(parts) - session_level
        if session_idx < 0:
            session_idx = 0
        if subject_label is not None and len(parts) == 1:
            session_label = None
        elif session_idx < len(parts):
            candidate = sanitize_bids_label(parts[session_idx])
            if candidate is not None and candidate != subject_label:
                session_label = sanitize_bids_label(candidate)

    return subject_label, session_label


def apply_folder_placeholders(
    name_template: str,
    source_path: str,
    subject_level_from_end: int = 2,
    session_level_from_end: int = 1,
    example_path: str = "",
    subject_example_value: str = "",
    session_example_value: str = "",
) -> str:
    """Replace {subject}/{session} placeholders using folder-path inference."""
    subject_label, session_label = extract_subject_session_from_source_path(
        source_path,
        subject_level_from_end=subject_level_from_end,
        session_level_from_end=session_level_from_end,
        example_path=example_path,
        subject_example_value=subject_example_value,
        session_example_value=session_example_value,
    )

    if "{subject}" in name_template and not subject_label:
        raise ValueError("Could not extract subject from folder path")

    resolved = name_template.replace("{subject}", subject_label or "")

    if "{session}" in resolved:
        if session_label:
            resolved = resolved.replace("{session}", session_label)
        else:
            resolved = resolved.replace("_ses-{session}", "")
            resolved = resolved.replace("ses-{session}_", "")
            resolved = resolved.replace("ses-{session}", "")
            resolved = resolved.replace("{session}", "")

    resolved = re.sub(r"__+", "_", resolved)
    return re.sub(r"^_+|_+$", "", resolved)


# ---------------------------------------------------------------------------
# Subject-ID rewriting (e.g. keep only the last 3 digits)
# ---------------------------------------------------------------------------


def normalize_subject_rewrite_mode(raw_value: str | None) -> str:
    mode = (raw_value or "keep").strip().lower()
    if mode not in {"keep", "last3"}:
        return "keep"
    return mode


def rewrite_subject_label(subject_label: str, mode: str) -> str:
    normalized_mode = normalize_subject_rewrite_mode(mode)
    if normalized_mode != "last3":
        return subject_label

    text = (subject_label or "").strip()
    if not text:
        return subject_label

    base = text[4:] if text.lower().startswith("sub-") else text
    digits = "".join(ch for ch in base if ch.isdigit())
    if digits:
        return f"sub-{digits[-3:]}"

    cleaned = re.sub(r"[^A-Za-z0-9]", "", base)
    if not cleaned:
        return subject_label
    return f"sub-{cleaned[-3:]}"


def rewrite_subject_in_filename(filename: str, mode: str) -> str:
    normalized_mode = normalize_subject_rewrite_mode(mode)
    if normalized_mode != "last3":
        return filename
    return re.sub(
        r"sub-[A-Za-z0-9]+",
        lambda match: rewrite_subject_label(match.group(0), normalized_mode),
        filename,
        count=1,
    )


def rewrite_subject_in_relative_path(rel_path: Path, mode: str) -> Path:
    normalized_mode = normalize_subject_rewrite_mode(mode)
    if normalized_mode != "last3":
        return rel_path

    parts = list(rel_path.parts)
    if not parts:
        return rel_path

    if re.fullmatch(r"sub-[A-Za-z0-9]+", parts[0]):
        parts[0] = rewrite_subject_label(parts[0], normalized_mode)

    parts[-1] = rewrite_subject_in_filename(parts[-1], normalized_mode)
    return Path(*parts)


# ---------------------------------------------------------------------------
# Project-copy destination resolution
# ---------------------------------------------------------------------------


def normalize_project_dest_root(raw_value: str | None) -> str:
    dest_root = (raw_value or "prism").strip().lower()
    if dest_root == "root":
        dest_root = "prism"
    if dest_root not in {"prism", "rawdata", "sourcedata"}:
        dest_root = "prism"
    return dest_root


def resolve_project_copy_root(project_path: str | Path, dest_root: str) -> Path:
    project_root = Path(project_path)
    normalized_dest_root = normalize_project_dest_root(dest_root)
    if normalized_dest_root in {"rawdata", "sourcedata"}:
        project_root = project_root / normalized_dest_root
    return project_root


def should_use_flat_project_copy(dest_root: str, flat_structure: bool) -> bool:
    return bool(flat_structure) and normalize_project_dest_root(dest_root) in {
        "rawdata",
        "sourcedata",
    }


# ---------------------------------------------------------------------------
# Rename computation
# ---------------------------------------------------------------------------


def compute_organized_relative_path(
    filename: str, *, modality: str, organize: bool, parse_bids_filename=None
) -> str:
    """Return filename as-is, or a BIDS-organized sub-XXX/ses-XXX/<modality>/
    filename path when `organize` is set and the filename parses as BIDS."""
    if not organize or parse_bids_filename is None:
        return filename

    bids = parse_bids_filename(filename)
    if not bids:
        return filename

    sub = bids.get("sub")
    ses = bids.get("ses")
    parts = [sub]
    if ses:
        parts.append(ses)
    parts.append(modality)
    parts.append(filename)
    return "/".join(parts)


def compute_renamed_filename(
    source_path: str,
    *,
    pattern: "re.Pattern[str]",
    replacement: str,
    id_source: str = "filename",
    folder_subject_level: int = 2,
    folder_session_level: int = 1,
    folder_example_path: str = "",
    folder_subject_value: str = "",
    folder_session_value: str = "",
) -> str:
    """Apply the regex rename (and, for id_source='folder', placeholder
    substitution from the folder path) plus filename normalization."""
    old_name = Path(source_path).name
    new_name = pattern.sub(replacement, old_name)
    if id_source == "folder":
        new_name = apply_folder_placeholders(
            new_name,
            source_path,
            subject_level_from_end=folder_subject_level,
            session_level_from_end=folder_session_level,
            example_path=folder_example_path,
            subject_example_value=folder_subject_value,
            session_example_value=folder_session_value,
        )
    return normalize_filename(new_name)


def plan_rename(
    entries: list[tuple[str, str]],
    *,
    pattern: str,
    replacement: str,
    id_source: str = "filename",
    folder_subject_level: int = 2,
    folder_session_level: int = 1,
    folder_example_path: str = "",
    folder_subject_value: str = "",
    folder_session_value: str = "",
    modality: str = "physio",
    organize: bool = False,
    parse_bids_filename=None,
) -> tuple[list[dict], list[str]]:
    """Preview a batch rename: for each (source_path, display_path) entry,
    compute the new filename and (if organize) its BIDS-organized relative
    path. Returns (results, warnings); each result has old/new/path/success
    keys, matching the Studio GUI's dry-run response shape.
    """
    try:
        compiled = re.compile(pattern)
    except re.error as exc:
        raise ValueError(f"Invalid regex: {exc}") from exc

    results: list[dict] = []
    warnings: list[str] = []

    for source_path, _display_path in entries:
        try:
            new_name = compute_renamed_filename(
                source_path,
                pattern=compiled,
                replacement=replacement,
                id_source=id_source,
                folder_subject_level=folder_subject_level,
                folder_session_level=folder_session_level,
                folder_example_path=folder_example_path,
                folder_subject_value=folder_subject_value,
                folder_session_value=folder_session_value,
            )
            organized_path = compute_organized_relative_path(
                new_name,
                modality=modality,
                organize=organize,
                parse_bids_filename=parse_bids_filename,
            )
            results.append(
                {
                    "old": source_path,
                    "new": new_name,
                    "path": organized_path,
                    "success": True,
                }
            )
        except Exception as exc:
            results.append({"old": source_path, "new": str(exc), "success": False})

    return results, warnings
