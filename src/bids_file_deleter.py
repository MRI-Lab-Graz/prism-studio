from __future__ import annotations

import os
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Iterator

from src.system_files import filter_system_files

_IGNORED_DIR_NAMES = {
    ".git",
    ".venv",
    "venv",
    "node_modules",
    "__pycache__",
    ".pytest_cache",
    ".mypy_cache",
}

# Root-level JSON files that must never be auto-deleted
_PROTECTED_ROOT_JSONS = frozenset({
    "dataset_description.json",
    "participants.json",
    "project.json",
    "bidsignore.json",
    ".prismrc.json",
    "CITATION.cff",
})
_ENTITY_TOKEN_PATTERN = re.compile(r"^(?P<key>[A-Za-z0-9]+)-(?P<value>[A-Za-z0-9]+)$")
_LABEL_PATTERN = re.compile(r"^[A-Za-z0-9]+$")
_SUBJECT_DIR_PATTERN = re.compile(r"^sub-[A-Za-z0-9]+$")
_SESSION_DIR_PATTERN = re.compile(r"^ses-[A-Za-z0-9]+$")
_DOUBLE_SUFFIXES = (".nii.gz", ".tsv.gz")
_MAX_FILTER_VALUES = 200


@dataclass
class _DeletePlan:
    targets: list[Path]
    modality: str | None
    entity_filters: dict[str, str]
    subjects: list[str]
    empty_dirs: list[Path] = field(default_factory=list)
    orphaned_root_sidecars: list[Path] = field(default_factory=list)


class BidsFileDeleter:
    """Delete project files matching a combination of BIDS entity filters."""

    def __init__(self, project_root: Path):
        self.project_root = Path(project_root)

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def options(self) -> dict:
        """Return available modalities, subjects, and entity values."""
        modalities = self._list_modalities()
        subjects = self._list_subjects()
        entity_values_by_modality: dict[str, dict[str, list[str]]] = {}
        for modality in modalities:
            entity_values_by_modality[modality] = self._list_entity_values_for_modality(
                modality
            )
        all_entity_values = self._list_all_entity_values()
        return {
            "available_modalities": modalities,
            "available_subjects": subjects,
            "entity_values_by_modality": entity_values_by_modality,
            "all_entity_values": all_entity_values,
        }

    def preview(
        self,
        modality: str | None,
        entity_filters: dict[str, str],
        subjects: list[str] | None,
    ) -> dict:
        plan = self._build_plan(modality, entity_filters, subjects)
        return self._plan_to_dict(plan, applied=False)

    def apply(
        self,
        modality: str | None,
        entity_filters: dict[str, str],
        subjects: list[str] | None,
    ) -> dict:
        plan = self._build_plan(modality, entity_filters, subjects)

        deleted = 0
        for target in plan.targets:
            if target.is_file():
                target.unlink()
                deleted += 1

        # Delete orphaned root-level sidecar JSONs
        deleted_sidecars = 0
        for sidecar in plan.orphaned_root_sidecars:
            if sidecar.is_file():
                sidecar.unlink()
                deleted_sidecars += 1

        # Remove empty directories deepest-first.
        # Use filter_system_files so .DS_Store does not block cleanup.
        removed_dirs = 0
        for dir_path in sorted(plan.empty_dirs, key=lambda p: -len(p.parts)):
            try:
                if not dir_path.is_dir():
                    continue
                entries = list(dir_path.iterdir())
                non_sys_files = filter_system_files(
                    [e.name for e in entries if e.is_file()]
                )
                subdirs = [
                    e for e in entries
                    if e.is_dir() and e.name not in _IGNORED_DIR_NAMES
                ]
                if not non_sys_files and not subdirs:
                    # Remove any leftover system files (e.g. .DS_Store) then the dir
                    for entry in entries:
                        if entry.is_file():
                            try:
                                entry.unlink()
                            except OSError:
                                pass
                    dir_path.rmdir()
                    removed_dirs += 1
            except OSError:
                pass

        result = self._plan_to_dict(plan, applied=True)
        result["deleted_count"] = deleted
        result["deleted_sidecars"] = deleted_sidecars
        result["removed_empty_dirs"] = removed_dirs
        return result

    # ------------------------------------------------------------------
    # Internals
    # ------------------------------------------------------------------

    def _build_plan(
        self,
        modality: str | None,
        entity_filters: dict[str, str],
        subjects: list[str] | None,
    ) -> _DeletePlan:
        if not self.project_root.is_dir():
            raise ValueError(f"Project root does not exist: {self.project_root}")

        norm_modality = self._normalize_modality(modality)
        norm_filters = self._normalize_entity_filters(entity_filters)
        norm_subjects = self._normalize_subjects(subjects)

        if not norm_modality and not norm_filters and not norm_subjects:
            raise ValueError(
                "Specify at least one filter (modality, entity value, or subject) before previewing a deletion."
            )

        targets: list[Path] = []
        for file_path in self._iter_files():
            if self._file_matches(
                file_path,
                modality=norm_modality,
                entity_filters=norm_filters,
                subjects=norm_subjects,
            ):
                targets.append(file_path)

        empty_dirs = self._find_empty_dirs_after(targets)
        orphaned_sidecars = self._find_orphaned_root_sidecars(targets)

        return _DeletePlan(
            targets=targets,
            modality=norm_modality,
            entity_filters=norm_filters,
            subjects=norm_subjects,
            empty_dirs=empty_dirs,
            orphaned_root_sidecars=orphaned_sidecars,
        )

    def _file_matches(
        self,
        file_path: Path,
        modality: str | None,
        entity_filters: dict[str, str],
        subjects: list[str] | None,
    ) -> bool:
        rel_path = file_path.relative_to(self.project_root)
        parts = rel_path.parts

        # Only touch files under sub-XX directories
        sub_index: int | None = None
        for i, part in enumerate(parts):
            if _SUBJECT_DIR_PATTERN.fullmatch(part):
                sub_index = i
                break
        if sub_index is None:
            return False

        # Subject filter
        if subjects:
            subject_id = parts[sub_index][4:]  # strip "sub-"
            if subject_id not in subjects:
                return False

        # Modality filter
        if modality:
            path_modality = self._extract_modality_from_relative_path(rel_path)
            if path_modality != modality:
                return False

        # Entity filters
        if entity_filters:
            parsed = self._parse_filename_tokens(file_path.name)
            if parsed is None:
                return False
            tokens, _, _ = parsed
            file_entities: dict[str, str] = {}
            for token in tokens[:-1]:
                m = _ENTITY_TOKEN_PATTERN.fullmatch(token)
                if m:
                    file_entities[m.group("key").lower()] = m.group("value")

            for key, value in entity_filters.items():
                if key == "ses":
                    # Accept match either from filename entity OR session directory
                    in_ses_dir = any(
                        p == f"ses-{value}" for p in parts
                    )
                    if not in_ses_dir and file_entities.get("ses") != value:
                        return False
                else:
                    if file_entities.get(key) != value:
                        return False

        return True

    def _find_empty_dirs_after(self, targets: list[Path]) -> list[Path]:
        """Return directories that would become empty once all targets are deleted."""
        if not targets:
            return []

        target_set = set(targets)

        # Collect all ancestor directories of targets within project_root
        candidate_dirs: set[Path] = set()
        for target in targets:
            parent = target.parent
            while parent != self.project_root:
                try:
                    parent.relative_to(self.project_root)
                except ValueError:
                    break
                candidate_dirs.add(parent)
                parent = parent.parent

        # A directory is "would be empty" if every file inside it is in target_set
        empty_dirs: list[Path] = []
        for candidate_dir in candidate_dirs:
            if not candidate_dir.is_dir():
                continue
            all_files: set[Path] = set()
            for root, _, filenames in os.walk(candidate_dir):
                for fname in filter_system_files(list(filenames)):
                    all_files.add(Path(root) / fname)
            if all_files and all_files.issubset(target_set):
                empty_dirs.append(candidate_dir)

        return empty_dirs

    def _plan_to_dict(self, plan: _DeletePlan, applied: bool) -> dict:
        file_list = sorted(
            str(t.relative_to(self.project_root).as_posix()) for t in plan.targets
        )
        empty_dir_list = sorted(
            str(d.relative_to(self.project_root).as_posix()) for d in plan.empty_dirs
        )
        sidecar_list = sorted(
            str(s.relative_to(self.project_root).as_posix())
            for s in plan.orphaned_root_sidecars
        )
        return {
            "applied": applied,
            "file_count": len(plan.targets),
            "files": file_list,
            "empty_dirs_to_remove": empty_dir_list,
            "orphaned_root_sidecars": sidecar_list,
            "modality": plan.modality,
            "entity_filters": plan.entity_filters,
            "subjects": plan.subjects,
        }

    # ------------------------------------------------------------------
    # Listing helpers
    # ------------------------------------------------------------------

    def _list_modalities(self) -> list[str]:
        modalities: set[str] = set()
        for file_path in self._iter_files():
            rel_path = file_path.relative_to(self.project_root)
            m = self._extract_modality_from_relative_path(rel_path)
            if m:
                modalities.add(m)
        return sorted(modalities)

    def _list_subjects(self) -> list[str]:
        subjects: list[str] = []
        try:
            for entry in sorted(self.project_root.iterdir()):
                if entry.is_dir() and _SUBJECT_DIR_PATTERN.fullmatch(entry.name):
                    subjects.append(entry.name)  # keep "sub-XXX" form
        except OSError:
            pass
        return subjects

    def _list_entity_values_for_modality(self, modality: str) -> dict[str, list[str]]:
        values_by_entity: dict[str, set[str]] = {}
        for file_path in self._iter_files():
            rel_path = file_path.relative_to(self.project_root)
            if self._extract_modality_from_relative_path(rel_path) != modality:
                continue
            parsed = self._parse_filename_tokens(file_path.name)
            if parsed is None:
                continue
            tokens, _, _ = parsed
            for token in tokens[:-1]:
                m = _ENTITY_TOKEN_PATTERN.fullmatch(token)
                if not m:
                    continue
                key = m.group("key").lower()
                value = m.group("value")
                bucket = values_by_entity.setdefault(key, set())
                if len(bucket) < _MAX_FILTER_VALUES:
                    bucket.add(value)
            # Also expose ses from directory path
            for part in rel_path.parts:
                if _SESSION_DIR_PATTERN.fullmatch(part):
                    ses_value = part[4:]  # strip "ses-"
                    bucket = values_by_entity.setdefault("ses", set())
                    if len(bucket) < _MAX_FILTER_VALUES:
                        bucket.add(ses_value)
        return {k: sorted(v) for k, v in values_by_entity.items()}

    def _list_all_entity_values(self) -> dict[str, list[str]]:
        values_by_entity: dict[str, set[str]] = {}
        for file_path in self._iter_files():
            rel_path = file_path.relative_to(self.project_root)
            # Add ses from directory
            for part in rel_path.parts:
                if _SESSION_DIR_PATTERN.fullmatch(part):
                    ses_value = part[4:]
                    bucket = values_by_entity.setdefault("ses", set())
                    if len(bucket) < _MAX_FILTER_VALUES:
                        bucket.add(ses_value)
            parsed = self._parse_filename_tokens(file_path.name)
            if parsed is None:
                continue
            tokens, _, _ = parsed
            for token in tokens[:-1]:
                m = _ENTITY_TOKEN_PATTERN.fullmatch(token)
                if not m:
                    continue
                key = m.group("key").lower()
                value = m.group("value")
                bucket = values_by_entity.setdefault(key, set())
                if len(bucket) < _MAX_FILTER_VALUES:
                    bucket.add(value)
        return {k: sorted(v) for k, v in values_by_entity.items()}

    # ------------------------------------------------------------------
    # Static / path helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _normalize_modality(modality: str | None) -> str | None:
        if not modality:
            return None
        v = str(modality).strip().lower()
        return v if v else None

    @staticmethod
    def _normalize_entity_filters(filters: dict | None) -> dict[str, str]:
        if not filters or not isinstance(filters, dict):
            return {}
        result: dict[str, str] = {}
        for key, value in filters.items():
            k = str(key or "").strip().lower()
            v = str(value or "").strip()
            if k and v:
                if not _LABEL_PATTERN.fullmatch(k):
                    raise ValueError(
                        f"Entity filter key '{k}' must contain only letters and numbers."
                    )
                if not _LABEL_PATTERN.fullmatch(v):
                    raise ValueError(
                        f"Entity filter value '{v}' must contain only letters and numbers."
                    )
                result[k] = v
        return result

    @staticmethod
    def _normalize_subjects(subjects: list | None) -> list[str]:
        if not subjects:
            return []
        result: list[str] = []
        for s in subjects:
            raw = str(s or "").strip()
            # Accept "sub-001" or "001"
            if raw.startswith("sub-"):
                raw = raw[4:]
            if raw and _LABEL_PATTERN.fullmatch(raw):
                result.append(raw)
        return result

    @staticmethod
    def _extract_modality_from_relative_path(rel_path: Path) -> str | None:
        parts = rel_path.parts
        if len(parts) < 3:
            return None
        for index, value in enumerate(parts[:-1]):
            if not _SUBJECT_DIR_PATTERN.fullmatch(value):
                continue
            modality_index = index + 1
            if modality_index >= len(parts) - 1:
                continue
            if _SESSION_DIR_PATTERN.fullmatch(parts[modality_index]):
                modality_index += 1
                if modality_index >= len(parts) - 1:
                    continue
            modality = parts[modality_index].strip().lower()
            if modality and not modality.startswith("."):
                return modality
        return None

    @staticmethod
    def _split_stem_extension(filename: str) -> tuple[str, str]:
        lower = filename.lower()
        for suffix in _DOUBLE_SUFFIXES:
            if lower.endswith(suffix):
                return filename[: -len(suffix)], filename[-len(suffix) :]
        dot = filename.rfind(".")
        if dot <= 0:
            return filename, ""
        return filename[:dot], filename[dot:]

    def _parse_filename_tokens(
        self, filename: str
    ) -> tuple[list[str], str, str] | None:
        stem, extension = self._split_stem_extension(filename)
        if not stem:
            return None
        tokens = [t for t in stem.split("_") if t]
        if len(tokens) < 2:
            return None
        return tokens, stem, extension

    def _find_orphaned_root_sidecars(self, targets: list[Path]) -> list[Path]:
        """Return root-level inherited sidecar JSONs with no remaining matching data file."""
        target_set = set(targets)

        root_sidecars: list[tuple[Path, dict[str, str], str]] = []
        try:
            for entry in self.project_root.iterdir():
                if not entry.is_file() or entry.suffix != ".json":
                    continue
                if entry.name in _PROTECTED_ROOT_JSONS or entry.name.startswith("."):
                    continue
                sig = self._parse_root_sidecar_signature(entry.name)
                if sig is not None:
                    root_sidecars.append((entry, sig[0], sig[1]))
        except OSError:
            return []

        if not root_sidecars:
            return []

        remaining_files = [f for f in self._iter_files() if f not in target_set]

        orphaned: list[Path] = []
        for sidecar, entities, modality in root_sidecars:
            has_match = any(
                self._file_matches_sidecar(f, entities, modality)
                for f in remaining_files
            )
            if not has_match:
                orphaned.append(sidecar)

        return orphaned

    @staticmethod
    def _parse_root_sidecar_signature(
        filename: str,
    ) -> tuple[dict[str, str], str] | None:
        """Parse a root-level BIDS inherited sidecar filename.

        Returns (entity_dict, modality) or None if the filename does not
        match the expected pattern ``entity1-val1[_...]_modality.json``.
        """
        if not filename.endswith(".json"):
            return None
        stem = filename[:-5]
        tokens = [t for t in stem.split("_") if t]
        if len(tokens) < 2:
            return None
        # Last token must be a plain modality label (no dash)
        modality = tokens[-1]
        if "-" in modality or not _LABEL_PATTERN.fullmatch(modality):
            return None
        # All preceding tokens must be entity-value pairs
        entities: dict[str, str] = {}
        for token in tokens[:-1]:
            m = _ENTITY_TOKEN_PATTERN.fullmatch(token)
            if not m:
                return None
            entities[m.group("key").lower()] = m.group("value")
        # Must have at least one entity; subject-level files are not root sidecars
        if not entities or "sub" in entities:
            return None
        return entities, modality

    def _file_matches_sidecar(
        self,
        file_path: Path,
        sidecar_entities: dict[str, str],
        sidecar_modality: str,
    ) -> bool:
        """Return True if file_path is a data file described by sidecar_entities/modality."""
        rel_path = file_path.relative_to(self.project_root)
        # Only data files under sub-XXX directories count
        if not any(_SUBJECT_DIR_PATTERN.fullmatch(p) for p in rel_path.parts):
            return False
        # Modality folder must match
        if self._extract_modality_from_relative_path(rel_path) != sidecar_modality:
            return False
        # Parse filename entities
        parsed = self._parse_filename_tokens(file_path.name)
        if parsed is None:
            return False
        tokens, _, _ = parsed
        file_entities: dict[str, str] = {}
        for token in tokens[:-1]:
            m = _ENTITY_TOKEN_PATTERN.fullmatch(token)
            if m:
                file_entities[m.group("key").lower()] = m.group("value")
        # Supplement with session from directory path
        for part in rel_path.parts:
            if _SESSION_DIR_PATTERN.fullmatch(part):
                file_entities.setdefault("ses", part[4:])
        # All entities from sidecar must be present in file
        for key, value in sidecar_entities.items():
            if file_entities.get(key) != value:
                return False
        return True

    def _iter_files(self) -> Iterator[Path]:
        for root, dirnames, filenames in os.walk(self.project_root, topdown=True):
            dirnames[:] = [
                d
                for d in dirnames
                if d not in _IGNORED_DIR_NAMES and not d.startswith(".")
            ]
            root_path = Path(root)
            for filename in filter_system_files(list(filenames)):
                fp = root_path / filename
                if fp.is_file():
                    yield fp
