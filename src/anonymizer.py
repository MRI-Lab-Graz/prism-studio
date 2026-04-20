"""
Anonymization utilities for data sharing.

Provides functionality to:
1. Randomize participant IDs (e.g., sub-001 → sub-R7X2K9)
2. Mask copyrighted question text (e.g., full text → "ADS Question 1")
3. Maintain reversible mappings for re-identification if needed
"""

from __future__ import annotations

import json
import random
import string
import re
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional
import hashlib


def generate_random_id(
    prefix: str = "sub", length: int = 6, seed: Optional[str] = None
) -> str:
    """
    Generate a random alphanumeric ID with the given prefix.

    Args:
        prefix: ID prefix (e.g., "sub", "ses")
        length: Length of random part
        seed: Optional seed for reproducibility

    Returns:
        Random ID like "sub-R7X2K9"
    """
    if seed:
        # Use hash of seed for reproducibility (not for security)
        hash_obj = hashlib.md5(seed.encode(), usedforsecurity=False)
        random.seed(int(hash_obj.hexdigest(), 16))

    chars = string.ascii_uppercase + string.digits
    random_part = "".join(random.choice(chars) for _ in range(length))
    return f"{prefix}-{random_part}"


def create_participant_mapping(
    participant_ids: List[str],
    output_file: Path,
    id_length: int = 6,
    deterministic: bool = True,
) -> Dict[str, str]:
    """
    Create a mapping from real participant IDs to randomized codes.

    Args:
        participant_ids: List of original participant IDs
        output_file: Path to save the mapping JSON
        id_length: Length of random ID part
        deterministic: If True, same input always generates same random IDs

    Returns:
        Dictionary mapping original_id → random_id
    """
    mapping = {}
    used_ids = set()

    for original_id in sorted(participant_ids):
        # Extract prefix (e.g., "sub" from "sub-001")
        if "-" in original_id:
            prefix = original_id.split("-")[0]
        else:
            prefix = "sub"

        # Generate unique random ID
        seed = original_id if deterministic else None
        attempts = 0
        while attempts < 1000:
            random_id = generate_random_id(prefix, id_length, seed)
            if random_id not in used_ids:
                mapping[original_id] = random_id
                used_ids.add(random_id)
                break
            # If collision, modify seed
            seed = f"{original_id}_{attempts}" if deterministic else None
            attempts += 1

        if attempts >= 1000:
            raise RuntimeError(f"Could not generate unique ID for {original_id}")

    # Save mapping
    output_file.parent.mkdir(parents=True, exist_ok=True)
    with open(output_file, "w", encoding="utf-8") as f:
        json.dump(
            {
                "_description": "Participant ID anonymization mapping",
                "_warning": "KEEP THIS FILE SECURE! It allows re-identification.",
                "mapping": mapping,
                "reverse_mapping": {v: k for k, v in mapping.items()},
            },
            f,
            indent=2,
        )

    return mapping


def create_question_mask_mapping(
    survey_template: Dict, survey_name: str, output_file: Optional[Path] = None
) -> Dict[str, str]:
    """
    Create a mapping to mask copyrighted question text.

    Args:
        survey_template: Survey template JSON (from library)
        survey_name: Survey name (e.g., "ADS")
        output_file: Optional path to save mapping

    Returns:
        Dictionary mapping item_id → masked description
    """
    mapping = {}
    items = list(_iter_survey_template_items(survey_template))

    for idx, (item_id, item) in enumerate(items, start=1):
        if not isinstance(item, dict):
            continue

        # Check if question has copyright restrictions
        license_info = item.get("License") or _get_survey_license_info(survey_template)
        is_copyrighted = _is_copyright_restricted(license_info)

        # Mask if copyrighted
        if is_copyrighted:
            masked_desc = f"{survey_name} Question {idx}"
        else:
            # Keep original for non-copyrighted
            masked_desc = _pick_preferred_text(
                item.get("Description"), fallback=f"{survey_name} Question {idx}"
            )

        mapping[item_id] = masked_desc

    # Save mapping if requested
    if output_file:
        output_file.parent.mkdir(parents=True, exist_ok=True)
        with open(output_file, "w", encoding="utf-8") as f:
            json.dump(
                {
                    "_description": f"Question text masking for {survey_name}",
                    "_survey": survey_name,
                    "mapping": mapping,
                },
                f,
                indent=2,
            )

    return mapping


def anonymize_tsv_file(
    input_file: Path,
    output_file: Path,
    participant_mapping: Dict[str, str],
    question_mapping: Optional[Dict[str, str]] = None,
) -> None:
    """
    Anonymize a TSV file by replacing participant IDs and optionally question descriptions.

    Args:
        input_file: Input TSV file path
        output_file: Output TSV file path
        participant_mapping: Dict mapping original_id → random_id
        question_mapping: Optional dict for masking column headers
    """
    import csv

    with open(input_file, "r", encoding="utf-8", newline="") as f:
        reader = csv.DictReader(f, delimiter="\t")
        header = list(reader.fieldnames or [])
        rows = list(reader)

    # Update header with masked question names if provided
    if question_mapping:
        new_header = []
        for col in header:
            if col in question_mapping:
                new_header.append(question_mapping[col])
            else:
                new_header.append(col)
        header = new_header

    # Update rows to match new header and update participant IDs
    for row in rows:
        # 1. Update keys based on question_mapping if they were renamed in header
        if question_mapping:
            for old_col, new_col in question_mapping.items():
                if old_col in row and old_col != new_col:
                    row[new_col] = row.pop(old_col)

        # 2. Update participant IDs
        if "participant_id" in row:
            original_id = row["participant_id"]
            row["participant_id"] = participant_mapping.get(original_id, original_id)

        # Also check for subject_id or sub
        for id_col in ["subject_id", "sub", "subject"]:
            if id_col in row:
                original_id = row[id_col]
                row[id_col] = participant_mapping.get(original_id, original_id)

    # Write anonymized file
    output_file.parent.mkdir(parents=True, exist_ok=True)
    with open(output_file, "w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(
            f, fieldnames=header, delimiter="\t", lineterminator="\n"
        )
        writer.writeheader()
        writer.writerows(rows)


def replace_participant_ids_in_text(
    value: str, participant_mapping: Dict[str, str]
) -> str:
    """
    Replace participant IDs in free text without corrupting overlapping IDs.

    Uses token-style boundaries so an ID like ``sub-01`` is not replaced inside
    a distinct ID like ``sub-010``.
    """
    if not value or not participant_mapping:
        return value

    participant_ids = [participant_id for participant_id in participant_mapping if participant_id]
    if not participant_ids:
        return value

    pattern = re.compile(
        r"(?<![A-Za-z0-9])(" 
        + "|".join(
            re.escape(participant_id)
            for participant_id in sorted(participant_ids, key=len, reverse=True)
        )
        + r")(?![A-Za-z0-9])"
    )

    return pattern.sub(lambda match: participant_mapping[match.group(0)], value)


def update_intendedfor_paths(
    json_data: Any, participant_mapping: Dict[str, str]
) -> Any:
    """
    Recursively replace participant IDs embedded in any JSON string value.

    Covers BIDS IntendedFor (string or list), BIDS URI style
    ("bids::sub-001/..."), and any other field that embeds a subject path.

    Args:
        json_data: Parsed JSON value (dict, list, str, or scalar).
        participant_mapping: Dict mapping original_id → anonymised_id.

    Returns:
        A new structure with all participant IDs replaced.
    """
    if not participant_mapping:
        return json_data

    def _remap(value: Any) -> Any:
        if isinstance(value, str):
            return replace_participant_ids_in_text(value, participant_mapping)
        if isinstance(value, list):
            return [_remap(v) for v in value]
        if isinstance(value, dict):
            return {k: _remap(v) for k, v in value.items()}
        return value

    return _remap(json_data)


def anonymize_dataset(
    dataset_path: Path,
    output_path: Path,
    mapping_path: Optional[Path] = None,
    mask_questions: bool = True,
    id_length: int = 6,
) -> Path:
    """
    Anonymize an entire PRISM dataset for sharing.

    Args:
        dataset_path: Path to original dataset
        output_path: Path for anonymized dataset
        mapping_path: Path to save ID mapping (default: output_path/code/anonymization_map.json)
        mask_questions: Whether to mask copyrighted question text
        id_length: Length of random ID part

    Returns:
        Path to mapping file
    """
    if mapping_path is None:
        mapping_path = output_path / "code" / "anonymization_map.json"

    # Collect all participant IDs
    participant_ids = set()
    for tsv_file in dataset_path.rglob("*.tsv"):
        if tsv_file.name == "participants.tsv":
            import csv

            with open(tsv_file, "r", encoding="utf-8") as f:
                reader = csv.DictReader(f, delimiter="\t")
                for row in reader:
                    pid = row.get("participant_id", "")
                    if pid:
                        participant_ids.add(pid)

    # Create participant mapping
    participant_mapping = create_participant_mapping(
        list(participant_ids), mapping_path, id_length=id_length
    )

    print(
        f"✓ Created anonymization mapping for {len(participant_mapping)} participants"
    )
    print(f"  Mapping saved to: {mapping_path}")
    print("  ⚠️  KEEP THIS FILE SECURE! It allows re-identification.")

    return mapping_path


def check_survey_copyright(survey_template: Dict) -> bool:
    """
    Check if a survey has copyright restrictions.

    Args:
        survey_template: Survey template JSON

    Returns:
        True if copyrighted, False if free/open
    """
    return _is_copyright_restricted(_get_survey_license_info(survey_template))


_NON_ITEM_TEMPLATE_KEYS = {
    "Technical",
    "Study",
    "Metadata",
    "Questions",
    "Items",
    "I18n",
    "Scoring",
    "Normative",
    "StudyMetadata",
    "LimesurveyID",
    "LimeSurvey",
    "_aliases",
    "_reverse_aliases",
}


def _iter_survey_template_items(
    survey_template: Dict[str, Any],
) -> Iterable[tuple[str, Any]]:
    if not isinstance(survey_template, dict):
        return []

    questions = survey_template.get("Questions")
    if isinstance(questions, dict):
        return questions.items()

    items = survey_template.get("Items")
    if isinstance(items, list):
        pairs: list[tuple[str, Any]] = []
        for idx, item in enumerate(items, start=1):
            if not isinstance(item, dict):
                continue
            item_id = str(item.get("ItemID") or "").strip() or f"item{idx}"
            pairs.append((item_id, item))
        return pairs

    return [
        (key, value)
        for key, value in survey_template.items()
        if key not in _NON_ITEM_TEMPLATE_KEYS and isinstance(value, dict)
    ]


def _get_survey_license_info(survey_template: Dict[str, Any]) -> Any:
    if not isinstance(survey_template, dict):
        return {}

    study = survey_template.get("Study")
    if isinstance(study, dict):
        for key in ("LicenseID", "License"):
            if study.get(key) not in (None, "", {}):
                return study.get(key)

    for key in ("LicenseID", "License"):
        if survey_template.get(key) not in (None, "", {}):
            return survey_template.get(key)

    return {}


def _is_copyright_restricted(license_info: Any) -> bool:
    if isinstance(license_info, dict):
        dict_values = [str(value).strip().lower() for value in license_info.values()]
        text = " ".join(v for v in dict_values if v)
    elif isinstance(license_info, str):
        text = license_info.strip().lower()
    else:
        text = ""

    if not text:
        return True

    allowed_tokens = (
        "free",
        "cc0",
        "public domain",
        "cc-by",
        "cc by",
        "cc-by-sa",
        "cc by sa",
    )
    return not any(token in text for token in allowed_tokens)


def _pick_preferred_text(value: Any, *, fallback: str) -> str:
    if isinstance(value, str) and value.strip():
        return value.strip()
    if isinstance(value, dict):
        for key in ("en", "default", "de"):
            candidate = value.get(key)
            if isinstance(candidate, str) and candidate.strip():
                return candidate.strip()
        for candidate in value.values():
            if isinstance(candidate, str) and candidate.strip():
                return candidate.strip()
    return fallback
