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
import json
import re
from dataclasses import dataclass, field
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


def _build_numeric_lookup(existing_participant_ids: Iterable[str]) -> dict[str, list[str]]:
    numeric_lookup: dict[str, list[str]] = {}
    for existing_id in existing_participant_ids:
        numeric_key = _numeric_key(_strip_sub_prefix(existing_id))
        if numeric_key is not None:
            numeric_lookup.setdefault(numeric_key, []).append(existing_id)
    return numeric_lookup


def build_subject_id_matcher(
    existing_participant_ids: Iterable[str],
) -> Callable[[str], Optional[str]]:
    """Return a function that resolves an already-sanitized "sub-<label>" id
    to an existing canonical participant_id when there's an unambiguous
    numeric match, else returns None.
    """
    existing = set(existing_participant_ids)
    numeric_lookup = _build_numeric_lookup(existing)

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


def _id_aliases_file(project_root: Path | str) -> Path:
    return Path(project_root) / "code" / "library" / "participant_id_aliases.json"


def load_id_aliases(project_root: Path | str) -> dict[str, str]:
    """Read manually-confirmed raw-id -> participant_id mappings for a project.

    These are explicit decisions a user made when resolving an id that the
    automatic numeric matcher couldn't place unambiguously (see
    `resolve_participant_ids`). Returns an empty dict if no aliases have been
    recorded yet.
    """
    alias_file = _id_aliases_file(project_root)
    if not alias_file.is_file():
        return {}
    try:
        payload = json.loads(alias_file.read_text(encoding="utf-8"))
    except Exception:
        return {}
    aliases = payload.get("aliases") if isinstance(payload, dict) else None
    if not isinstance(aliases, dict):
        return {}
    return {str(k): str(v) for k, v in aliases.items() if k and v}


def save_id_alias(project_root: Path | str, raw_id: str, participant_id: str) -> None:
    """Persist a single raw-id -> participant_id alias for a project.

    Subsequent calls to `resolve_participant_ids` for the same project will
    resolve `raw_id` to `participant_id` without re-prompting the user.
    """
    alias_file = _id_aliases_file(project_root)
    alias_file.parent.mkdir(parents=True, exist_ok=True)
    aliases = load_id_aliases(project_root)
    aliases[str(raw_id)] = str(participant_id)
    payload = {
        "version": "1.0",
        "description": (
            "Manually confirmed raw-id -> participant_id mappings, recorded "
            "when a user resolved an unmatched id during a PRISM import."
        ),
        "aliases": aliases,
    }
    alias_file.write_text(
        json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8"
    )


@dataclass
class IdResolution:
    """Result of resolving a batch of raw, sanitized "sub-<label>" ids against
    a project's participants.tsv ground truth (plus any saved aliases)."""

    matched: dict[str, str] = field(default_factory=dict)
    unmatched: list[str] = field(default_factory=list)
    suggested_matches: dict[str, list[str]] = field(default_factory=dict)
    has_ground_truth: bool = False


def resolve_participant_ids(
    raw_ids: Iterable[str],
    project_root: Path | str,
) -> IdResolution:
    """Resolve already-sanitized "sub-<label>" ids against participants.tsv.

    Resolution order per id: saved alias, exact/unambiguous-numeric match
    (`build_subject_id_matcher`), else unmatched. When participants.tsv
    doesn't exist yet (`has_ground_truth=False`), there is no ground truth to
    validate against, so every id is treated as matched/new -- nothing
    should block a project's first import.

    For unmatched ids, `suggested_matches` lists existing participant_ids
    that share the same numeric value but couldn't be chosen unambiguously
    (e.g. the project already has both sub-01 and sub-001), so a resolution
    UI can offer them as candidates.
    """
    existing_ids = load_existing_participant_ids(project_root)
    has_ground_truth = bool(existing_ids)

    resolution = IdResolution(has_ground_truth=has_ground_truth)
    if not has_ground_truth:
        for raw_id in dict.fromkeys(rid for rid in raw_ids if rid):
            resolution.matched[raw_id] = raw_id
        return resolution

    aliases = load_id_aliases(project_root)
    matcher = build_subject_id_matcher(existing_ids)
    numeric_lookup = _build_numeric_lookup(existing_ids)

    for raw_id in dict.fromkeys(rid for rid in raw_ids if rid):
        alias_target = aliases.get(raw_id)
        if alias_target and alias_target in existing_ids:
            resolution.matched[raw_id] = alias_target
            continue

        direct_match = matcher(raw_id)
        if direct_match is not None:
            resolution.matched[raw_id] = direct_match
            continue

        resolution.unmatched.append(raw_id)
        numeric_key = _numeric_key(_strip_sub_prefix(raw_id))
        candidates = numeric_lookup.get(numeric_key) if numeric_key is not None else None
        if candidates:
            resolution.suggested_matches[raw_id] = list(candidates)

    return resolution


def apply_id_resolution_decisions(
    unmatched_ids: Iterable[str],
    decisions: dict[str, dict],
    project_root: Path | str,
) -> dict[str, str]:
    """Resolve previously-unmatched ids using explicit user decisions.

    `decisions` maps a raw id to
    `{"action": "map" | "create_new", "target_participant_id"?: str, "remember"?: bool}`.
    "map" resolves the raw id to an existing participant_id (and, unless
    `remember` is explicitly False, persists it via `save_id_alias` so future
    imports don't re-prompt). "create_new" is an explicit, user-confirmed
    decision that the raw id is a genuinely new participant -- it resolves to
    its own (already-sanitized) value.

    Returns `{raw_id: canonical_participant_id}` only for ids that had a
    decision; callers should treat any id from `unmatched_ids` missing from
    the result as still unresolved.
    """
    resolved: dict[str, str] = {}
    for raw_id in unmatched_ids:
        decision = decisions.get(raw_id)
        if not decision:
            continue
        action = decision.get("action")
        if action == "map":
            target = decision.get("target_participant_id")
            if not target:
                continue
            resolved[raw_id] = target
            if decision.get("remember", True):
                save_id_alias(project_root, raw_id, target)
        elif action == "create_new":
            resolved[raw_id] = raw_id
    return resolved
