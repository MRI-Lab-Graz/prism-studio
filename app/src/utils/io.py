from __future__ import annotations

from pathlib import Path
import json
import csv
from typing import Any


def ensure_dir(path: Path) -> Path:
    """Ensure directory exists."""
    path.mkdir(parents=True, exist_ok=True)
    return path


def read_json(path: Path) -> dict[str, Any]:
    """Read JSON file."""
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def write_json(path: Path, obj: dict[str, Any]) -> None:
    """Write JSON file with indentation."""
    ensure_dir(path.parent)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(obj, f, indent=2, ensure_ascii=False)


def read_tsv_rows(path: Path) -> tuple[list[str], list[dict[str, str]]]:
    """Read TSV file into header and list of dicts."""
    with open(path, "r", encoding="utf-8", newline="") as f:
        reader = csv.DictReader(f, delimiter="\t")
        header = list(reader.fieldnames or [])
        rows = [dict(r) for r in reader]
    return header, rows


def write_tsv_rows(path: Path, header: list[str], rows: list[dict[str, str]]) -> None:
    """Write list of dicts to TSV file."""
    ensure_dir(path.parent)
    with open(path, "w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(
            f, fieldnames=header, delimiter="\t", lineterminator="\n"
        )
        writer.writeheader()
        for row in rows:
            writer.writerow({k: row.get(k, "n/a") for k in header})


def update_participants_tsv(
    dataset_root: Path, participant_ids: set[str] | list[str], log_fn: Any = None
) -> None:
    """Update participants.tsv with new participant IDs.

    This function ensures that all participant IDs from imported data
    are present in participants.tsv. It creates the file if it doesn't exist,
    and adds missing participant IDs while preserving existing data.

    Args:
        dataset_root: Path to dataset root (where participants.tsv should be)
        participant_ids: Set or list of participant IDs to ensure are present (e.g., "sub-001")
        log_fn: Optional logging function (callable taking message string)
    """
    if not participant_ids:
        return

    # Ensure participant_ids is a set for efficient operations
    if not isinstance(participant_ids, set):
        participant_ids = set(participant_ids)

    # Canonical PRISM location: participants files live at dataset root.
    participants_tsv = dataset_root / "participants.tsv"
    participants_json = dataset_root / "participants.json"

    # Read existing participants.tsv if it exists
    existing_ids = set()
    existing_rows = []
    header = ["participant_id"]

    if participants_tsv.exists():
        try:
            header, existing_rows = read_tsv_rows(participants_tsv)
            if "participant_id" not in header:
                if log_fn:
                    log_fn(
                        "[WARNING] participants.tsv exists but has no participant_id column. Will recreate."
                    )
                existing_rows = []
                header = ["participant_id"]
            else:
                existing_ids = {
                    row.get("participant_id", "").strip()
                    for row in existing_rows
                    if row.get("participant_id", "").strip()
                }
        except Exception as e:
            if log_fn:
                log_fn(f"[WARNING] Could not read existing participants.tsv: {e}")
            existing_rows = []
            header = ["participant_id"]
            existing_ids = set()

    # Find new participant IDs
    new_ids = participant_ids - existing_ids

    if not new_ids:
        if log_fn:
            log_fn(
                f"[INFO] All {len(participant_ids)} participant IDs already in participants.tsv"
            )
        return

    # Add new participants (with n/a for other columns if they exist)
    for pid in sorted(new_ids):
        new_row = {col: "n/a" for col in header}
        new_row["participant_id"] = pid
        existing_rows.append(new_row)

    # Sort all rows by participant_id
    existing_rows.sort(key=lambda r: r.get("participant_id", ""))

    # Write updated participants.tsv
    write_tsv_rows(participants_tsv, header, existing_rows)

    if log_fn:
        log_fn(
            f"[INFO] Updated participants.tsv: added {len(new_ids)} new participant(s)"
        )

    # Create participants.json if it doesn't exist
    if not participants_json.exists():
        minimal_json = {
            "participant_id": {
                "Description": "Unique participant identifier",
                "LongName": "Participant ID",
            }
        }
        write_json(participants_json, minimal_json)
        if log_fn:
            log_fn("[INFO] Created minimal participants.json")
