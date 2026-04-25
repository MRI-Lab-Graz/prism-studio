"""Rename legacy physio filenames to canonical recording-<label>_physio.

This migration targets legacy files such as:
- sub-001_ses-1_task-rest_ecg.edf
- sub-001_ses-1_task-rest_ecg.json
- task-rest_ecg.json

and rewrites them to:
- sub-001_ses-1_task-rest_recording-ecg_physio.edf
- sub-001_ses-1_task-rest_recording-ecg_physio.json
- task-rest_recording-ecg_physio.json

Dry-run is the default behavior. Use --apply to execute renames.
"""

from __future__ import annotations

import argparse
from dataclasses import dataclass
from pathlib import Path
import re

KNOWN_NON_PHYSIO_SUFFIXES = {
    "survey",
    "biometrics",
    "events",
    "environment",
    "eyetracking",
    "eyetrack",
    "physio",
}
COMPOUND_EXTS = (".tsv.gz",)

LEGACY_SUBJECT_STEM = re.compile(
    r"^(?P<prefix>sub-[^_]+(?:_ses-[^_]+)?_task-[^_]+)_(?P<label>[A-Za-z0-9]+)$"
)
LEGACY_ROOT_STEM = re.compile(r"^task-(?P<task>[^_]+)_(?P<label>[A-Za-z0-9]+)$")


@dataclass(frozen=True)
class RenameAction:
    old_path: Path
    new_path: Path
    reason: str


def _split_ext(filename: str) -> tuple[str, str]:
    lower = filename.lower()
    for ext in COMPOUND_EXTS:
        if lower.endswith(ext):
            return filename[: -len(ext)], filename[-len(ext) :]
    path = Path(filename)
    return path.stem, path.suffix


def _canonical_subject_stem(prefix: str, label: str) -> str:
    return f"{prefix}_recording-{label}_physio"


def _canonical_root_stem(task: str, label: str) -> str:
    return f"task-{task}_recording-{label}_physio"


def _is_physio_label(label: str) -> bool:
    return bool(label) and label.lower() not in KNOWN_NON_PHYSIO_SUFFIXES


def _iter_subject_physio_dirs(dataset_root: Path):
    for subject_dir in sorted(dataset_root.glob("sub-*")):
        if not subject_dir.is_dir():
            continue
        direct = subject_dir / "physio"
        if direct.is_dir():
            yield direct
        for session_dir in sorted(subject_dir.glob("ses-*")):
            physio_dir = session_dir / "physio"
            if physio_dir.is_dir():
                yield physio_dir


def collect_legacy_physio_renames(dataset_root: Path) -> list[RenameAction]:
    """Collect planned renames without changing files."""
    root = Path(dataset_root).resolve()
    actions: list[RenameAction] = []
    planned_old: set[Path] = set()

    def _append(old_path: Path, new_path: Path, reason: str) -> None:
        if old_path in planned_old:
            return
        if old_path == new_path:
            return
        planned_old.add(old_path)
        actions.append(RenameAction(old_path=old_path, new_path=new_path, reason=reason))

    data_exts = {".edf", ".tsv", ".tsv.gz"}

    for physio_dir in _iter_subject_physio_dirs(root):
        for file_path in sorted(physio_dir.iterdir()):
            if not file_path.is_file() or file_path.suffix.lower() == ".json":
                continue

            stem, ext = _split_ext(file_path.name)
            if ext.lower() not in data_exts:
                continue
            if stem.endswith("_physio"):
                continue

            match = LEGACY_SUBJECT_STEM.match(stem)
            if not match:
                continue

            label = match.group("label")
            if not _is_physio_label(label):
                continue

            canonical_stem = _canonical_subject_stem(match.group("prefix"), label.lower())
            _append(
                file_path,
                file_path.with_name(f"{canonical_stem}{ext}"),
                "legacy-subject-data",
            )

            local_sidecar = file_path.with_suffix(".json")
            if local_sidecar.exists() and local_sidecar.is_file():
                _append(
                    local_sidecar,
                    local_sidecar.with_name(f"{canonical_stem}.json"),
                    "legacy-subject-sidecar",
                )

    root_sidecar_dirs = [root, root / "physio", root / "physiological"]
    for sidecar_dir in root_sidecar_dirs:
        if not sidecar_dir.is_dir():
            continue
        for file_path in sorted(sidecar_dir.glob("task-*_*.json")):
            stem = file_path.stem
            if "_recording-" in stem and stem.endswith("_physio"):
                continue

            match = LEGACY_ROOT_STEM.match(stem)
            if not match:
                continue

            label = match.group("label")
            if not _is_physio_label(label):
                continue

            canonical_stem = _canonical_root_stem(match.group("task"), label.lower())
            _append(
                file_path,
                file_path.with_name(f"{canonical_stem}.json"),
                "legacy-root-sidecar",
            )

    return actions


def apply_rename_actions(actions: list[RenameAction], *, apply: bool) -> dict[str, int]:
    """Apply planned actions with collision checks.

    Returns a summary with keys: renamed, skipped_existing, planned.
    """
    summary = {"renamed": 0, "skipped_existing": 0, "planned": 0}

    for action in actions:
        if action.new_path.exists():
            summary["skipped_existing"] += 1
            continue

        if apply:
            action.new_path.parent.mkdir(parents=True, exist_ok=True)
            action.old_path.rename(action.new_path)
            summary["renamed"] += 1
        else:
            summary["planned"] += 1

    return summary


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Rename legacy physio filenames to canonical "
            "recording-<label>_physio naming."
        )
    )
    parser.add_argument("dataset_root", help="Path to PRISM/BIDS dataset root")
    parser.add_argument(
        "--apply",
        action="store_true",
        help="Apply renames. Without this flag, only a dry-run plan is printed.",
    )
    return parser


def main() -> int:
    parser = _build_parser()
    args = parser.parse_args()

    dataset_root = Path(args.dataset_root).expanduser().resolve()
    if not dataset_root.exists() or not dataset_root.is_dir():
        print(f"Error: dataset root does not exist: {dataset_root}")
        return 1

    actions = collect_legacy_physio_renames(dataset_root)
    if not actions:
        print("No legacy physio filenames detected.")
        return 0

    mode = "APPLY" if args.apply else "DRY-RUN"
    print(f"[{mode}] Found {len(actions)} rename action(s):")
    for action in actions:
        old_rel = action.old_path.relative_to(dataset_root).as_posix()
        new_rel = action.new_path.relative_to(dataset_root).as_posix()
        print(f"  - {old_rel} -> {new_rel} ({action.reason})")

    summary = apply_rename_actions(actions, apply=bool(args.apply))
    if args.apply:
        print(
            "Applied renames: "
            f"{summary['renamed']} | skipped existing targets: {summary['skipped_existing']}"
        )
    else:
        print(
            "Planned renames: "
            f"{summary['planned']} | blocked by existing targets: {summary['skipped_existing']}"
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
