"""
Utilities for scanning PRISM / BIDS project structure.

Provides information about available sessions and modalities
within a project directory, used for selective export/sharing.
"""

import json
import os
import re
from pathlib import Path
from typing import Dict, List, Set


def _extract_acq(filename: str) -> str | None:
    """Return the acq- label value from a BIDS filename, or None."""
    m = re.search(r"_acq-([A-Za-z0-9]+)", filename)
    return m.group(1) if m else None


def _extract_task(filename: str) -> str | None:
    """Return the task- label value from a BIDS filename, or None."""
    m = re.search(r"(?:^|_)task-([A-Za-z0-9]+)", filename)
    return m.group(1) if m else None


def _extract_suffix_label(filename: str) -> str | None:
    """Return the terminal BIDS suffix token from a filename, or None.

    Examples:
        sub-01_ses-01_task-rest_bold.nii.gz -> bold
        sub-01_ses-01_T1w.nii.gz -> T1w
    """
    name = str(filename or "").strip()
    if not name:
        return None

    lower_name = name.lower()
    for compound_ext in (".nii.gz", ".tsv.gz"):
        if lower_name.endswith(compound_ext):
            name = name[: -len(compound_ext)]
            break
    else:
        if "." in name:
            name = name.rsplit(".", 1)[0]

    if not name:
        return None

    suffix = name.rsplit("_", 1)[-1]
    # Ignore trailing entities (e.g., run-01) and keep true suffix-like tokens.
    if not suffix or "-" in suffix:
        return None
    return suffix


def _declared_sessions_and_modalities(project_path: Path) -> tuple[List[str], List[str]]:
    """Read declared sessions and modalities out of project.json.

    This is what a PRISM project states about itself, so it needs no directory
    walk at all -- one file read answers both. Returns empty lists for plain
    BIDS folders with no project.json.
    """
    try:
        with open(project_path / "project.json", "r", encoding="utf-8") as handle:
            data = json.load(handle)
    except (OSError, json.JSONDecodeError):
        return [], []

    if not isinstance(data, dict):
        return [], []

    sessions = {
        str(entry.get("id")).strip()
        for entry in (data.get("Sessions") or [])
        if isinstance(entry, dict) and str(entry.get("id") or "").strip()
    }
    task_definitions = data.get("TaskDefinitions")
    modalities = {
        str(definition.get("modality")).strip()
        for definition in (task_definitions or {}).values()
        if isinstance(definition, dict) and str(definition.get("modality") or "").strip()
    } if isinstance(task_definitions, dict) else set()

    return sorted(sessions), sorted(modalities)


def get_project_quick_summary(
    project_path: Path, *, deep: bool = True
) -> Dict[str, object]:
    """Return lightweight project summary counts without running validation.

    ``deep=True`` (the default) walks the subject/session/modality directory
    levels and reports what is actually on disk.

    ``deep=False`` reads only the project root listing and project.json, so it
    costs one directory read regardless of project size. Sessions and
    modalities are then the *declared* ones rather than the on-disk ones --
    the ``scan`` key says which, so callers can show the fast answer first and
    fill in the counted one afterwards. On a network-mounted project with a
    few hundred subjects that is the difference between instant and ~20s.
    """

    with os.scandir(project_path) as root_scan:
        root_entries = [(entry.name, entry.is_dir(), entry.is_file()) for entry in root_scan]

    subject_count = sum(
        1 for name, is_dir, _ in root_entries if is_dir and name.startswith("sub-")
    )
    root_files = {name for name, _, is_file in root_entries if is_file}

    summary: Dict[str, object] = {
        "subjects": subject_count,
        "has_dataset_description": "dataset_description.json" in root_files,
        "has_participants_tsv": "participants.tsv" in root_files,
    }

    if not deep:
        declared_sessions, declared_modalities = _declared_sessions_and_modalities(
            project_path
        )
        summary.update(
            {
                "sessions": len(declared_sessions),
                "modalities": len(declared_modalities),
                "session_labels": declared_sessions,
                "modality_labels": declared_modalities,
                "scan": "shallow",
            }
        )
        return summary

    sessions: Set[str] = set()
    modalities: Set[str] = set()

    for name, is_dir, _ in root_entries:
        if not (is_dir and name.startswith("sub-")):
            continue
        # os.scandir carries the entry type from the directory read itself, so
        # each level costs one round trip instead of one stat per child.
        with os.scandir(project_path / name) as sub_scan:
            children = [(child.name, child.is_dir(), child.path) for child in sub_scan]
        for child_name, child_is_dir, child_path in children:
            if not child_is_dir:
                continue
            if child_name.startswith("ses-"):
                sessions.add(child_name)
                with os.scandir(child_path) as session_scan:
                    modalities.update(
                        entry.name
                        for entry in session_scan
                        if entry.is_dir() and not entry.name.startswith(".")
                    )
            elif not child_name.startswith("."):
                modalities.add(child_name)

    summary.update(
        {
            "sessions": len(sessions),
            "modalities": len(modalities),
            "session_labels": sorted(sessions),
            "modality_labels": sorted(modalities),
            "scan": "deep",
        }
    )
    return summary


def get_project_modalities_and_sessions(project_path: Path) -> Dict[str, object]:
    """
    Scan a PRISM/BIDS project and return available subjects, sessions,
    modalities, and per-modality acq/task labels.

    Returns a dict with:
        subjects: sorted list of subject folder labels (e.g. ["sub-01", "sub-02"]).
        sessions: sorted list of session labels (e.g. ["ses-01", "ses-02"]),
                  empty list when no session level is used.
        modalities: sorted list of modality folder names (e.g. ["eeg", "survey", "func"]).
        acq_labels: dict mapping modality name -> sorted list of differentiators found.
            For most modalities this is acq- values. For MRI modalities where
            suffixes are semantically meaningful (anat, dwi, fmap, perf),
            labels combine acq+suffix when both are present (for example,
            diffall-epi) so they appear as a single acquisition variant.
        task_labels: dict mapping modality name -> sorted list of unique task- values found.
    """
    subjects: Set[str] = set()
    sessions: Set[str] = set()
    modalities: Set[str] = set()
    acq_labels: Dict[str, Set[str]] = {}
    task_labels: Dict[str, Set[str]] = {}
    task_label_modalities = {"survey", "func"}
    acq_label_modalities = {"dwi", "eeg", "fmap", "func", "perf"}
    suffix_label_modalities = {"anat", "dwi", "fmap", "perf"}

    def _scan_modality_dir(modality_name: str, modality_dir: Path) -> None:
        modalities.add(modality_name)
        if not modality_dir.is_dir():
            return
        for fname in modality_dir.iterdir():
            if not fname.is_file():
                continue

            if modality_name in task_label_modalities:
                task = _extract_task(fname.name)
                if task:
                    task_labels.setdefault(modality_name, set()).add(task)

            suffix = _extract_suffix_label(fname.name) if modality_name in suffix_label_modalities else None
            acq = _extract_acq(fname.name) if modality_name in acq_label_modalities else None

            if modality_name in {"dwi", "fmap", "perf"} and acq and suffix:
                acq_labels.setdefault(modality_name, set()).add(f"{acq}-{suffix}")
            elif suffix:
                acq_labels.setdefault(modality_name, set()).add(suffix)
            elif acq:
                acq_labels.setdefault(modality_name, set()).add(acq)

    for sub_dir in sorted(project_path.iterdir()):
        if not (sub_dir.is_dir() and sub_dir.name.startswith("sub-")):
            continue
        subjects.add(sub_dir.name)
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
        "subjects": sorted(subjects),
        "sessions": sorted(sessions),
        "modalities": sorted(modalities),
        "acq_labels": {k: sorted(v) for k, v in acq_labels.items()},
        "task_labels": {k: sorted(v) for k, v in task_labels.items()},
    }
