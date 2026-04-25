from __future__ import annotations

import os
import re
from dataclasses import dataclass
from pathlib import Path

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
_TEXT_SUFFIXES = {
    ".json",
    ".jsonld",
    ".tsv",
    ".csv",
    ".txt",
    ".md",
}
_TEXT_FILENAMES = {".bidsignore"}
_DOUBLE_SUFFIXES = (".nii.gz", ".tsv.gz")
_ENTITY_TOKEN_PATTERN = re.compile(r"^(?P<key>[A-Za-z0-9]+)-(?P<value>[A-Za-z0-9]+)$")
_LABEL_PATTERN = re.compile(r"^[A-Za-z0-9]+$")
_SUBJECT_DIR_PATTERN = re.compile(r"^sub-[A-Za-z0-9]+$")
_SESSION_DIR_PATTERN = re.compile(r"^ses-[A-Za-z0-9]+$")
_NON_EDITABLE_ENTITIES = {"sub"}
_ENTITY_ORDER = [
    "sub",
    "ses",
    "task",
    "acq",
    "run",
    "rec",
    "dir",
    "echo",
    "ce",
    "part",
    "space",
    "desc",
]
_REQUIRED_ENTITIES = {"sub", "task"}


@dataclass(frozen=True)
class _RenameOperation:
    old_path: Path
    new_path: Path


@dataclass
class _EntityRewritePlan:
    modality: str
    entity: str
    current_value: str | None
    operation: str
    replacement: str | None
    available_modalities: list[str]
    available_entities: list[str]
    file_ops: list[_RenameOperation]
    preview_text_updates: list[Path]
    conflicts: list[str]


class BidsEntityRewriter:
    """Rewrite a selected BIDS entity across files of one modality."""

    def __init__(self, project_root: Path):
        self.project_root = Path(project_root)

    def list_modalities(self) -> list[str]:
        modalities: set[str] = set()
        for file_path in self._iter_files():
            if self._parse_filename_tokens(file_path.name) is None:
                continue
            rel_path = file_path.relative_to(self.project_root)
            modality = self._extract_modality_from_relative_path(rel_path)
            if modality:
                modalities.add(modality)
        return sorted(modalities)

    def list_entities(self, modality: str) -> list[str]:
        normalized_modality = self._normalize_modality(modality)
        if not normalized_modality:
            return []

        entities: set[str] = set()
        for file_path in self._iter_files_for_modality(normalized_modality):
            parsed = self._parse_filename_tokens(file_path.name)
            if parsed is None:
                continue
            tokens, _stem, _ext = parsed
            for token in tokens[:-1]:
                entity_key = self._extract_entity_key(token)
                if entity_key:
                    if entity_key in _NON_EDITABLE_ENTITIES:
                        continue
                    entities.add(entity_key)

        ordered = [entity for entity in _ENTITY_ORDER if entity in entities]
        extras = sorted(entity for entity in entities if entity not in _ENTITY_ORDER)
        return ordered + extras

    def list_entity_values(self, modality: str) -> dict[str, list[str]]:
        normalized_modality = self._normalize_modality(modality)
        if not normalized_modality:
            return {}

        values_by_entity: dict[str, set[str]] = {}
        for file_path in self._iter_files_for_modality(normalized_modality):
            parsed = self._parse_filename_tokens(file_path.name)
            if parsed is None:
                continue

            tokens, _stem, _ext = parsed
            for token in tokens[:-1]:
                match = _ENTITY_TOKEN_PATTERN.fullmatch(token)
                if not match:
                    continue

                entity_key = match.group("key").lower()
                if entity_key in _NON_EDITABLE_ENTITIES:
                    continue
                entity_value = match.group("value")
                bucket = values_by_entity.setdefault(entity_key, set())
                if len(bucket) < 200:
                    bucket.add(entity_value)

        ordered_entities = self.list_entities(normalized_modality)
        entity_values: dict[str, list[str]] = {}
        for entity_key in ordered_entities:
            values = sorted(values_by_entity.get(entity_key, set()))
            entity_values[f"_{entity_key}"] = values

        extra_entities = sorted(
            entity_key
            for entity_key in values_by_entity
            if entity_key not in ordered_entities
        )
        for entity_key in extra_entities:
            entity_values[f"_{entity_key}"] = sorted(values_by_entity[entity_key])

        return entity_values

    def preview(
        self,
        modality: str,
        entity: str,
        operation: str,
        current_value: str | None = None,
        replacement: str | None = None,
    ) -> dict:
        plan = self._build_plan(
            modality=modality,
            entity=entity,
            current_value=current_value,
            operation=operation,
            replacement=replacement,
        )
        return self._plan_to_dict(plan, applied=False)

    def apply(
        self,
        modality: str,
        entity: str,
        operation: str,
        current_value: str | None = None,
        replacement: str | None = None,
    ) -> dict:
        plan = self._build_plan(
            modality=modality,
            entity=entity,
            current_value=current_value,
            operation=operation,
            replacement=replacement,
        )
        if plan.conflicts:
            raise ValueError(
                "Entity rewrite cannot be applied due to conflicts: "
                + "; ".join(plan.conflicts)
            )

        for op in sorted(
            plan.file_ops,
            key=lambda item: (-len(item.old_path.parts), str(item.old_path)),
        ):
            if not op.old_path.exists():
                continue
            op.new_path.parent.mkdir(parents=True, exist_ok=True)
            op.old_path.rename(op.new_path)

        replacements = self._build_text_replacements(plan.file_ops)
        changed_text_files = self._rewrite_text_file_contents(replacements)
        result = self._plan_to_dict(plan, applied=True)
        result["text_update_count"] = len(changed_text_files)
        result["text_update_files"] = [
            path.relative_to(self.project_root).as_posix()
            for path in changed_text_files[:200]
        ]
        return result

    def _build_plan(
        self,
        modality: str,
        entity: str,
        current_value: str | None,
        operation: str,
        replacement: str | None,
    ) -> _EntityRewritePlan:
        if not self.project_root.exists() or not self.project_root.is_dir():
            raise ValueError(f"Project root does not exist: {self.project_root}")

        available_modalities = self.list_modalities()
        normalized_modality = self._normalize_modality(modality)
        if not normalized_modality:
            raise ValueError("Select a modality before previewing this rewrite.")

        if normalized_modality not in available_modalities:
            raise ValueError(
                f"Modality '{normalized_modality}' was not found in this project."
            )

        available_entities = self.list_entities(normalized_modality)
        normalized_entity = self._normalize_entity(entity)
        if not normalized_entity:
            raise ValueError("Select a filename part before previewing this rewrite.")

        if normalized_entity not in available_entities:
            raise ValueError(
                f"Part _{normalized_entity} was not found for modality '{normalized_modality}'."
            )

        values_by_entity = self.list_entity_values(normalized_modality)
        values_for_entity = values_by_entity.get(f"_{normalized_entity}", [])

        normalized_current_value = self._normalize_current_value(current_value)
        if len(values_for_entity) > 1 and not normalized_current_value:
            raise ValueError(
                f"Select the current value for _{normalized_entity} first because this part has multiple values."
            )
        if normalized_current_value and normalized_current_value not in values_for_entity:
            raise ValueError(
                f"Current value '{normalized_current_value}' was not found for _{normalized_entity} in modality '{normalized_modality}'."
            )

        normalized_operation = self._normalize_operation(operation)
        replacement_value = None
        if normalized_operation == "rename":
            replacement_value = self._normalize_replacement(replacement)
        elif normalized_entity in _REQUIRED_ENTITIES:
            raise ValueError(f"Part _{normalized_entity} cannot be removed.")

        file_ops: list[_RenameOperation] = []
        for file_path in self._iter_files_for_modality(normalized_modality):
            rewritten_name = self._rewrite_filename_for_entity(
                file_path.name,
                entity=normalized_entity,
                current_value=normalized_current_value,
                operation=normalized_operation,
                replacement=replacement_value,
            )
            if not rewritten_name:
                continue
            new_path = file_path.with_name(rewritten_name)
            if new_path != file_path:
                file_ops.append(_RenameOperation(old_path=file_path, new_path=new_path))

        replacements = self._build_text_replacements(file_ops)
        preview_text_updates = self._preview_text_updates(replacements)
        conflicts = self._detect_rename_conflicts(file_ops)

        return _EntityRewritePlan(
            modality=normalized_modality,
            entity=normalized_entity,
            current_value=normalized_current_value,
            operation=normalized_operation,
            replacement=replacement_value,
            available_modalities=available_modalities,
            available_entities=available_entities,
            file_ops=file_ops,
            preview_text_updates=preview_text_updates,
            conflicts=conflicts,
        )

    @staticmethod
    def _normalize_modality(modality: str | None) -> str:
        return str(modality or "").strip().lower()

    @staticmethod
    def _normalize_entity(entity: str | None) -> str:
        raw_value = str(entity or "").strip()
        if raw_value.startswith("_"):
            raw_value = raw_value[1:]
        normalized = raw_value.lower()
        if not normalized:
            return ""
        if not _LABEL_PATTERN.fullmatch(normalized):
            raise ValueError(
                "Part labels must contain only letters and numbers (for example: _task, _acq)."
            )
        if normalized in _NON_EDITABLE_ENTITIES:
            raise ValueError(
                "Part _sub is not editable here. Use the dedicated subject-ID rewrite tool."
            )
        return normalized

    @staticmethod
    def _normalize_current_value(current_value: str | None) -> str | None:
        normalized = str(current_value or "").strip()
        if not normalized:
            return None
        if not _LABEL_PATTERN.fullmatch(normalized):
            raise ValueError(
                "Current value must contain only letters and numbers."
            )
        return normalized

    @staticmethod
    def _normalize_operation(operation: str | None) -> str:
        normalized = str(operation or "rename").strip().lower()
        if normalized not in {"rename", "delete"}:
            raise ValueError(f"Unsupported rewrite operation: {operation}")
        return normalized

    @staticmethod
    def _normalize_replacement(replacement: str | None) -> str:
        normalized = str(replacement or "").strip()
        if not normalized:
            raise ValueError("Enter a new value for the selected part.")
        if not _LABEL_PATTERN.fullmatch(normalized):
            raise ValueError(
                "Replacement values must contain only letters and numbers."
            )
        return normalized

    @staticmethod
    def _split_stem_extension(filename: str) -> tuple[str, str]:
        lower_filename = filename.lower()
        for suffix in _DOUBLE_SUFFIXES:
            if lower_filename.endswith(suffix):
                return filename[: -len(suffix)], filename[-len(suffix) :]

        dot_index = filename.rfind(".")
        if dot_index <= 0:
            return filename, ""
        return filename[:dot_index], filename[dot_index:]

    @staticmethod
    def _extract_modality_from_relative_path(rel_path: Path) -> str | None:
        parts = rel_path.parts
        if len(parts) < 3:
            return None

        # Modality is only valid when it appears after a subject folder,
        # optionally preceded by a session folder.
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

    def _parse_filename_tokens(self, filename: str) -> tuple[list[str], str, str] | None:
        stem, extension = self._split_stem_extension(filename)
        if not stem:
            return None

        tokens = [token for token in stem.split("_") if token]
        if len(tokens) < 2:
            return None
        return tokens, stem, extension

    @staticmethod
    def _extract_entity_key(token: str) -> str | None:
        match = _ENTITY_TOKEN_PATTERN.fullmatch(token)
        if not match:
            return None
        return match.group("key").lower()

    def _rewrite_filename_for_entity(
        self,
        filename: str,
        entity: str,
        current_value: str | None,
        operation: str,
        replacement: str | None,
    ) -> str | None:
        parsed = self._parse_filename_tokens(filename)
        if parsed is None:
            return None

        tokens, stem, extension = parsed
        prefix_tokens = tokens[:-1]
        suffix_token = tokens[-1]

        changed = False
        rewritten_prefix: list[str] = []
        for token in prefix_tokens:
            match = _ENTITY_TOKEN_PATTERN.fullmatch(token)
            if match is None:
                rewritten_prefix.append(token)
                continue

            token_entity = match.group("key").lower()
            token_value = match.group("value")
            if token_entity != entity:
                rewritten_prefix.append(token)
                continue
            if current_value and token_value != current_value:
                rewritten_prefix.append(token)
                continue

            changed = True
            if operation == "delete":
                continue

            rewritten_prefix.append(f"{entity}-{replacement}")

        if not changed:
            return None

        if not rewritten_prefix:
            return None

        rewritten_stem = "_".join(rewritten_prefix + [suffix_token])
        if rewritten_stem == stem:
            return None

        return f"{rewritten_stem}{extension}"

    def _iter_files_for_modality(self, modality: str):
        normalized_modality = self._normalize_modality(modality)
        for file_path in self._iter_files():
            rel_path = file_path.relative_to(self.project_root)
            path_modality = self._extract_modality_from_relative_path(rel_path)
            if path_modality == normalized_modality:
                yield file_path

    def _iter_files(self):
        for root, dirnames, filenames in os.walk(self.project_root, topdown=True):
            dirnames[:] = [
                dirname
                for dirname in dirnames
                if dirname not in _IGNORED_DIR_NAMES and not dirname.startswith(".")
            ]

            filtered_filenames = filter_system_files(list(filenames))
            root_path = Path(root)
            for filename in filtered_filenames:
                file_path = root_path / filename
                if file_path.is_file():
                    yield file_path

    def _iter_text_files(self):
        for file_path in self._iter_files():
            suffix = file_path.suffix.lower()
            if suffix in _TEXT_SUFFIXES or file_path.name.lower() in _TEXT_FILENAMES:
                yield file_path

    def _build_text_replacements(
        self,
        file_ops: list[_RenameOperation],
    ) -> list[tuple[str, str]]:
        replacements: dict[str, str] = {}
        subject_relative_candidates: dict[str, set[str]] = {}
        session_relative_candidates: dict[str, set[str]] = {}

        def _add_replacement(old_text: str, new_text: str):
            old_token = str(old_text or "").strip()
            new_token = str(new_text or "").strip()
            if not old_token or not new_token or old_token == new_token:
                return
            replacements[old_token] = new_token

            # Common IntendedFor-style variants used in fmap JSON sidecars.
            _add_prefixed_replacement(old_token, new_token, "./")
            _add_prefixed_replacement(old_token, new_token, "bids::")

        def _add_prefixed_replacement(old_text: str, new_text: str, prefix: str):
            if old_text.startswith(prefix):
                return
            _old = f"{prefix}{old_text}"
            _new = f"{prefix}{new_text}"
            replacements[_old] = _new

        for op in file_ops:
            old_rel = op.old_path.relative_to(self.project_root).as_posix()
            new_rel = op.new_path.relative_to(self.project_root).as_posix()
            _add_replacement(old_rel, new_rel)

            old_parts = old_rel.split("/", 1)
            new_parts = new_rel.split("/", 1)
            if (
                len(old_parts) == 2
                and len(new_parts) == 2
                and old_parts[0].startswith("sub-")
                and new_parts[0].startswith("sub-")
            ):
                subject_relative_candidates.setdefault(old_parts[1], set()).add(
                    new_parts[1]
                )

                old_subject_rel_parts = old_parts[1].split("/")
                new_subject_rel_parts = new_parts[1].split("/")
                if (
                    len(old_subject_rel_parts) >= 2
                    and len(new_subject_rel_parts) >= 2
                    and old_subject_rel_parts[0].startswith("ses-")
                    and new_subject_rel_parts[0].startswith("ses-")
                ):
                    old_session_relative = "/".join(old_subject_rel_parts[1:])
                    new_session_relative = "/".join(new_subject_rel_parts[1:])
                    session_relative_candidates.setdefault(
                        old_session_relative, set()
                    ).add(new_session_relative)

        for old_subject_relative, new_candidates in subject_relative_candidates.items():
            if len(new_candidates) != 1:
                continue
            new_subject_relative = next(iter(new_candidates))
            if old_subject_relative == new_subject_relative:
                continue

            _add_replacement(old_subject_relative, new_subject_relative)

        for old_session_relative, new_candidates in session_relative_candidates.items():
            if len(new_candidates) != 1:
                continue
            new_session_relative = next(iter(new_candidates))
            if old_session_relative == new_session_relative:
                continue
            _add_replacement(old_session_relative, new_session_relative)

        return sorted(replacements.items(), key=lambda item: len(item[0]), reverse=True)

    def _preview_text_updates(self, replacements: list[tuple[str, str]]) -> list[Path]:
        if not replacements:
            return []

        updated: list[Path] = []
        for file_path in self._iter_text_files():
            original_text = self._read_text_file(file_path)
            if original_text is None:
                continue
            rewritten_text = self._replace_text_tokens(original_text, replacements)
            if rewritten_text != original_text:
                updated.append(file_path)
        return updated

    def _rewrite_text_file_contents(
        self,
        replacements: list[tuple[str, str]],
    ) -> list[Path]:
        if not replacements:
            return []

        changed: list[Path] = []
        for file_path in self._iter_text_files():
            original_text = self._read_text_file(file_path)
            if original_text is None:
                continue
            rewritten_text = self._replace_text_tokens(original_text, replacements)
            if rewritten_text == original_text:
                continue
            file_path.write_text(rewritten_text, encoding="utf-8")
            changed.append(file_path)
        return changed

    @staticmethod
    def _replace_text_tokens(
        text: str,
        replacements: list[tuple[str, str]],
    ) -> str:
        updated = text
        for old_text, new_text in replacements:
            if old_text == new_text:
                continue
            updated = updated.replace(old_text, new_text)
        return updated

    @staticmethod
    def _read_text_file(file_path: Path) -> str | None:
        try:
            return file_path.read_text(encoding="utf-8")
        except (UnicodeDecodeError, OSError):
            return None

    def _detect_rename_conflicts(self, ops: list[_RenameOperation]) -> list[str]:
        conflicts: list[str] = []
        old_paths = {op.old_path for op in ops}
        seen_targets: dict[Path, Path] = {}

        for op in ops:
            existing_source = seen_targets.get(op.new_path)
            if existing_source is not None and existing_source != op.old_path:
                conflicts.append(
                    "Rename target collision: "
                    f"{self._rel(existing_source)} and {self._rel(op.old_path)} "
                    f"both map to {self._rel(op.new_path)}"
                )
            else:
                seen_targets[op.new_path] = op.old_path

            if op.new_path.exists() and op.new_path not in old_paths:
                conflicts.append(
                    f"Rename target already exists: {self._rel(op.new_path)}"
                )

        return conflicts

    def _plan_to_dict(self, plan: _EntityRewritePlan, applied: bool) -> dict:
        return {
            "modality": plan.modality,
            "entity": f"_{plan.entity}",
            "current_value": plan.current_value or "",
            "operation": plan.operation,
            "replacement": plan.replacement or "",
            "available_modalities": plan.available_modalities,
            "available_entities": [f"_{entity}" for entity in plan.available_entities],
            "applied": applied,
            "rename_count": len(plan.file_ops),
            "text_update_count": len(plan.preview_text_updates),
            "renames": [
                {
                    "from": self._rel(op.old_path),
                    "to": self._rel(op.new_path),
                }
                for op in plan.file_ops[:200]
            ],
            "text_update_files": [
                path.relative_to(self.project_root).as_posix()
                for path in plan.preview_text_updates[:200]
            ],
            "conflicts": plan.conflicts,
        }

    def _rel(self, path: Path) -> str:
        return path.relative_to(self.project_root).as_posix()
