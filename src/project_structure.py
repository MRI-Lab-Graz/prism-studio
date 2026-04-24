"""
Utilities for scanning PRISM / BIDS project structure.

Provides information about available sessions and modalities
within a project directory, used for selective export/sharing.
"""

import re
from pathlib import Path
from typing import Dict, List, Set


def _extract_acq(filename: str) -> str | None:
    """Return the acq- label value from a BIDS filename, or None."""
    m = re.search(r"_acq-([A-Za-z0-9]+)", filename)
    return m.group(1) if m else None


def get_project_quick_summary(project_path: Path) -> Dict[str, object]:
    """Return lightweight project summary counts without running validation.

    The scan only walks subject/session/modality directory levels and checks
    a couple of root metadata files, so it remains fast on large datasets.
    """

    subject_dirs = [
        sub_dir
        for sub_dir in sorted(project_path.iterdir())
        if sub_dir.is_dir() and sub_dir.name.startswith("sub-")
    ]

    sessions: Set[str] = set()
    modalities: Set[str] = set()

    for sub_dir in subject_dirs:
        for child in sub_dir.iterdir():
            if not child.is_dir():
                continue
            if child.name.startswith("ses-"):
                sessions.add(child.name)
                for modality_dir in child.iterdir():
                    if modality_dir.is_dir() and not modality_dir.name.startswith("."):
                        modalities.add(modality_dir.name)
            elif not child.name.startswith("."):
                modalities.add(child.name)

    return {
        "subjects": len(subject_dirs),
        "sessions": len(sessions),
        "modalities": len(modalities),
        "session_labels": sorted(sessions),
        "modality_labels": sorted(modalities),
        "has_dataset_description": (project_path / "dataset_description.json").is_file(),
        "has_participants_tsv": (project_path / "participants.tsv").is_file(),
    }


def get_project_modalities_and_sessions(project_path: Path) -> Dict[str, object]:
    """
    Scan a PRISM/BIDS project and return the available sessions, modalities,
    and per-modality acq- labels.

    Returns a dict with:
        sessions: sorted list of session labels (e.g. ["ses-01", "ses-02"]),
                  empty list when no session level is used.
        modalities: sorted list of modality folder names (e.g. ["eeg", "survey", "func"]).
        acq_labels: dict mapping modality name -> sorted list of unique acq- values found.
    """
    sessions: Set[str] = set()
    modalities: Set[str] = set()
    acq_labels: Dict[str, Set[str]] = {}

    def _scan_modality_dir(modality_name: str, modality_dir: Path) -> None:
        modalities.add(modality_name)
        if not modality_dir.is_dir():
            return
        for fname in modality_dir.iterdir():
            if fname.is_file():
                acq = _extract_acq(fname.name)
                if acq:
                    acq_labels.setdefault(modality_name, set()).add(acq)

    for sub_dir in sorted(project_path.iterdir()):
        if not (sub_dir.is_dir() and sub_dir.name.startswith("sub-")):
            continue
        for child in sub_dir.iterdir():
            if not child.is_dir():
                continue
            if child.name.startswith("ses-"):
                sessions.add(child.name)
                for modality_dir in child.iterdir():
                    if modality_dir.is_dir() and not modality_dir.name.startswith("."):
                        _scan_modality_dir(modality_dir.name, modality_dir)
            elif not child.name.startswith("."):
                _scan_modality_dir(child.name, child)

    return {
        "sessions": sorted(sessions),
        "modalities": sorted(modalities),
        "acq_labels": {k: sorted(v) for k, v in acq_labels.items()},
    }
