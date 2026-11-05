"""Which files of a project an export (and "Get data") takes: one selection, used by both.

The filters are the export's: subjects, sessions, modalities, acq and task labels to leave out, and whether
derivatives, code, analysis and sourcedata come along. Paths are relative to the dataset root, with ``/``.
"""

from __future__ import annotations

import os
import re
from pathlib import Path
from typing import Dict, List, Optional, Set

from src.project_export_helpers import extract_export_task_label, matches_excluded_acq_label
from src.system_files import filter_system_files

MRI_SUFFIX_LABEL_MODALITIES = {"anat", "dwi", "fmap", "perf"}  # same set as the export's own copy rules

_NEVER_SELECTED = {".git", ".datalad", ".gitattributes", ".gitignore", ".gitmodules", "CHANGES"}


def _labels(values) -> Set[str]:
    return {str(v).strip() for v in (values or set()) if str(v).strip()}


def _grouped(values) -> Dict[str, Set[str]]:
    return {
        str(m).strip(): _labels(labels)
        for m, labels in (values or {}).items()
        if str(m).strip() and labels
    }


class ExportFilters:
    def __init__(
        self,
        exclude_subjects=None,
        exclude_sessions=None,
        exclude_modalities=None,
        exclude_acq=None,
        exclude_tasks=None,
        include_derivatives=True,
        include_code=True,
        include_analysis=True,
        include_sourcedata=False,
    ):
        self.subjects = _labels(exclude_subjects)
        self.sessions = _labels(exclude_sessions)
        self.modalities = _labels(exclude_modalities)
        self.acq = _grouped(exclude_acq)
        self.tasks = _grouped(exclude_tasks)
        self.top_level = {
            "derivatives": include_derivatives,
            "sourcedata": include_sourcedata,
            "code": include_code,
            "analysis": include_analysis,
        }

    def excludes(self, rel_parts: tuple, *, is_dir: bool) -> bool:
        if not rel_parts:
            return False
        if rel_parts[0].startswith("sub-") and rel_parts[0] in self.subjects:
            return True

        if len(rel_parts) == 1:
            root_name = rel_parts[0]
            if root_name in self.top_level:
                return not self.top_level[root_name]
            if not is_dir:
                survey_tasks = self.tasks.get("survey", set())
                if survey_tasks:
                    match = re.search(r"^task-([A-Za-z0-9]+)_survey\\.json$", root_name)
                    if match and match.group(1) in survey_tasks:
                        return True
            return False

        if not rel_parts[0].startswith("sub-"):
            return False

        index = 1
        if index < len(rel_parts) and rel_parts[index].startswith("ses-"):
            if rel_parts[index] in self.sessions:
                return True
            index += 1
        if index >= len(rel_parts):
            return False

        modality = rel_parts[index]
        if modality in self.modalities:
            return True
        if is_dir:
            return False

        filename = rel_parts[-1]
        acq_labels = self.acq.get(modality, set())
        if acq_labels and matches_excluded_acq_label(filename, acq_labels):
            return True
        task_labels = self.tasks.get(modality, set())
        if task_labels:
            task = extract_export_task_label(filename, modality)
            if task and task in task_labels:
                return True
        return False


def _walk(dataset_root: Path, filters: ExportFilters):
    """Yield ``(rel_parts, is_dir)`` of every kept entry, not descending into excluded or system folders."""
    for current_raw, dirnames, filenames in os.walk(dataset_root):
        current = Path(current_raw)
        usable_dirs = set(filter_system_files(dirnames))
        kept: List[str] = []
        for name in dirnames:
            if name not in usable_dirs or name in _NEVER_SELECTED:
                continue
            try:
                parts = (current / name).relative_to(dataset_root).parts
            except ValueError:
                continue
            if filters.excludes(parts, is_dir=True):
                continue
            kept.append(name)
            yield parts, True
        dirnames[:] = kept

        usable_files = set(filter_system_files(filenames))
        for name in filenames:
            if name not in usable_files or name in _NEVER_SELECTED:
                continue
            try:
                parts = (current / name).relative_to(dataset_root).parts
            except ValueError:
                continue
            if filters.excludes(parts, is_dir=False):
                continue
            yield parts, False


def select_content_paths(dataset_root: Path, **filters) -> List[str]:
    """The files the filters keep, sorted, relative to ``dataset_root``."""
    root = Path(dataset_root)
    return sorted({Path(*parts).as_posix() for parts, is_dir in _walk(root, ExportFilters(**filters)) if not is_dir})


def select_scope_dirs(dataset_root: Path, **filters) -> List[str]:
    """Modality folders of the kept subjects (a session or subject folder when it has nothing deeper), sorted.

    Used to fetch nested dataset structure before the files are listed.
    """
    root = Path(dataset_root)
    subject_dirs: Set[str] = set()
    session_dirs: Set[str] = set()
    modality_dirs: Set[str] = set()
    subject_has_children: Dict[str, bool] = {}
    session_has_modalities: Dict[str, bool] = {}

    for parts, is_dir in _walk(root, ExportFilters(**filters)):
        if not is_dir or not parts[0].startswith("sub-"):
            continue
        rel = Path(*parts).as_posix()
        subject = parts[0]
        if len(parts) == 1:
            subject_dirs.add(rel)
            subject_has_children.setdefault(subject, False)
            continue
        subject_has_children[subject] = True
        index = 1
        session: Optional[str] = None
        if parts[index].startswith("ses-"):
            session = Path(*parts[:2]).as_posix()
            session_dirs.add(session)
            session_has_modalities.setdefault(session, False)
            index += 1
        if index >= len(parts):
            continue
        if len(parts) == index + 1:
            modality_dirs.add(rel)
            if session:
                session_has_modalities[session] = True

    selected = set(modality_dirs)
    selected.update(s for s in session_dirs if not session_has_modalities.get(s, False))
    selected.update(s for s in subject_dirs if not subject_has_children.get(s, False))
    return sorted(selected)
