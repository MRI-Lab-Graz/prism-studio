from __future__ import annotations

import os
import re
from dataclasses import dataclass
from pathlib import Path

from src.anonymizer import replace_participant_ids_in_text
from src.system_files import filter_system_files

_SUBJECT_TOKEN_PATTERN = re.compile(r"sub-[A-Za-z0-9]+")
_SUBJECT_DIR_PATTERN = re.compile(r"^sub-[A-Za-z0-9]+$")
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


@dataclass(frozen=True)
class _RenameOperation:
    old_path: Path
    new_path: Path


@dataclass
class _RewritePlan:
    mode: str
    rule: dict[str, str | int] | None
    subject_examples: list[str]
    subject_token_sources: dict[str, list[str]]
    mapping: dict[str, str]
    directory_ops: list[_RenameOperation]
    file_ops: list[_RenameOperation]
    preview_text_updates: list[Path]
    conflicts: list[str]


class SubjectCodeRewriter:
    """Rewrite existing subject codes in a project tree.

    The current supported mode is ``last3``:
    ``sub-1293167`` -> ``sub-167``.
    """

    def __init__(self, project_root: Path):
        self.project_root = Path(project_root)

    def list_root_subject_ids(self) -> list[str]:
        """Return subject IDs from top-level project folders only.

        This lightweight scan is used by the web UI to populate the
        subject-example dropdown quickly without traversing the full dataset.
        """
        if not self.project_root.exists() or not self.project_root.is_dir():
            return []

        subject_ids: list[str] = []
        for child in self.project_root.iterdir():
            if not child.is_dir():
                continue
            name = child.name
            if _SUBJECT_DIR_PATTERN.fullmatch(name):
                subject_ids.append(name)
        return sorted(subject_ids)

    def preview(
        self,
        mode: str = "last3",
        example_subject: str | None = None,
        keep_fragment: str | None = None,
    ) -> dict:
        plan = self._build_plan(
            mode,
            example_subject=example_subject,
            keep_fragment=keep_fragment,
        )
        return self._plan_to_dict(plan, applied=False)

    def apply(
        self,
        mode: str = "last3",
        example_subject: str | None = None,
        keep_fragment: str | None = None,
    ) -> dict:
        plan = self._build_plan(
            mode,
            example_subject=example_subject,
            keep_fragment=keep_fragment,
        )
        if plan.conflicts:
            raise ValueError(
                "Subject rewrite cannot be applied due to conflicts: "
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

        for op in sorted(
            plan.directory_ops,
            key=lambda item: (-len(item.old_path.parts), str(item.old_path)),
        ):
            if not op.old_path.exists():
                continue
            op.new_path.parent.mkdir(parents=True, exist_ok=True)
            op.old_path.rename(op.new_path)

        changed_text_files = self._rewrite_text_file_contents(plan.mapping)
        result = self._plan_to_dict(plan, applied=True)
        result["text_update_count"] = len(changed_text_files)
        result["text_update_files"] = [
            path.relative_to(self.project_root).as_posix()
            for path in changed_text_files[:200]
        ]
        return result

    def _build_plan(
        self,
        mode: str,
        example_subject: str | None,
        keep_fragment: str | None,
    ) -> _RewritePlan:
        if not self.project_root.exists() or not self.project_root.is_dir():
            raise ValueError(f"Project root does not exist: {self.project_root}")

        normalized_mode = self._normalize_mode(mode)
        subject_tokens, subject_token_sources = self._collect_subject_tokens()
        mapping, rule = self._build_subject_mapping(
            normalized_mode,
            subject_tokens,
            example_subject=example_subject,
            keep_fragment=keep_fragment,
        )
        if not mapping:
            return _RewritePlan(
                mode=normalized_mode,
                rule=rule,
                subject_examples=subject_tokens,
                subject_token_sources=subject_token_sources,
                mapping={},
                directory_ops=[],
                file_ops=[],
                preview_text_updates=[],
                conflicts=[],
            )

        collisions = self._mapping_collisions(mapping)
        conflicts: list[str] = []
        if collisions:
            for new_subject, old_subjects in collisions.items():
                joined_old = ", ".join(sorted(old_subjects))
                conflicts.append(
                    f"Multiple source subjects map to {new_subject}: {joined_old}"
                )

        directory_ops = self._build_directory_rename_ops(mapping)
        file_ops = self._build_file_rename_ops(mapping)
        preview_text_updates = self._preview_text_updates(mapping)
        conflicts.extend(self._detect_rename_conflicts(directory_ops + file_ops))

        return _RewritePlan(
            mode=normalized_mode,
            rule=rule,
            subject_examples=subject_tokens,
            subject_token_sources=subject_token_sources,
            mapping=mapping,
            directory_ops=directory_ops,
            file_ops=file_ops,
            preview_text_updates=preview_text_updates,
            conflicts=conflicts,
        )

    @staticmethod
    def _normalize_mode(mode: str | None) -> str:
        normalized = (mode or "last3").strip().lower()
        if normalized not in {"last3", "example_keep"}:
            raise ValueError(f"Unsupported subject rewrite mode: {mode}")
        return normalized

    def _collect_subject_tokens(self) -> tuple[list[str], dict[str, list[str]]]:
        subject_tokens: set[str] = set()
        subject_sources: dict[str, set[str]] = {}

        def add_occurrence(token: str, source: str):
            subject_tokens.add(token)
            bucket = subject_sources.setdefault(token, set())
            if len(bucket) < 50:
                bucket.add(source)

        for directory in self._iter_directories():
            rel_dir = directory.relative_to(self.project_root).as_posix()
            for token in _SUBJECT_TOKEN_PATTERN.findall(directory.name):
                add_occurrence(token, rel_dir)

        for file_path in self._iter_files():
            rel_path = file_path.relative_to(self.project_root).as_posix()
            for token in _SUBJECT_TOKEN_PATTERN.findall(file_path.name):
                add_occurrence(token, rel_path)
            for token in _SUBJECT_TOKEN_PATTERN.findall(rel_path):
                add_occurrence(token, rel_path)

        sorted_tokens = sorted(subject_tokens)
        normalized_sources = {
            token: sorted(subject_sources.get(token, set()))[:20]
            for token in sorted_tokens
        }
        return sorted_tokens, normalized_sources

    def _build_subject_mapping(
        self,
        mode: str,
        subject_tokens: list[str],
        example_subject: str | None,
        keep_fragment: str | None,
    ) -> tuple[dict[str, str], dict[str, str | int] | None]:
        rule: dict[str, str | int] | None = None
        if mode == "example_keep":
            rule = self._build_example_keep_rule(
                subject_tokens,
                example_subject=example_subject,
                keep_fragment=keep_fragment,
            )

        mapping: dict[str, str] = {}
        for token in subject_tokens:
            rewritten = self._rewrite_subject_token(token, mode, rule=rule)
            if rewritten and rewritten != token:
                mapping[token] = rewritten
        return mapping, rule

    @staticmethod
    def _build_example_keep_rule(
        subject_tokens: list[str],
        example_subject: str | None,
        keep_fragment: str | None,
    ) -> dict[str, str | int]:
        if not subject_tokens:
            raise ValueError("No subject IDs were found in this project.")

        raw_example = (example_subject or "").strip()
        if not raw_example:
            raise ValueError(
                "Select one current subject ID as example before previewing this rule."
            )

        normalized_example = (
            raw_example if raw_example.startswith("sub-") else f"sub-{raw_example}"
        )
        if normalized_example not in subject_tokens:
            raise ValueError(
                "The selected example subject ID was not found in this project. "
                "Choose a different example subject ID and retry."
            )

        raw_keep = (keep_fragment or "").strip()
        if not raw_keep:
            raise ValueError(
                "Enter the part that should stay from the selected example subject ID."
            )

        keep_value = raw_keep[4:] if raw_keep.startswith("sub-") else raw_keep
        example_label = normalized_example[4:]

        occurrence_count = example_label.count(keep_value)
        if occurrence_count == 0:
            raise ValueError(
                f"'{keep_value}' is not part of {normalized_example}."
            )
        if occurrence_count > 1:
            raise ValueError(
                "Pattern is not unique in the selected example (e.g. sub-103103 -> 103). "
                "Choose a different example or a more specific kept part."
            )

        start_index = example_label.find(keep_value)
        end_index = start_index + len(keep_value)

        if start_index == 0 and end_index == len(example_label):
            strategy = "full"
        elif end_index == len(example_label):
            strategy = "suffix"
        elif start_index == 0:
            strategy = "prefix"
        else:
            strategy = "slice"

        return {
            "type": "example_keep",
            "example_subject": normalized_example,
            "keep_fragment": keep_value,
            "strategy": strategy,
            "length": len(keep_value),
            "start": start_index,
            "end": end_index,
        }

    @staticmethod
    def _rewrite_subject_token(
        subject_token: str,
        mode: str,
        rule: dict[str, str | int] | None,
    ) -> str:
        if mode != "last3":
            if mode != "example_keep" or not rule:
                return subject_token

            label = (
                subject_token[4:] if subject_token.startswith("sub-") else subject_token
            )
            strategy = str(rule.get("strategy") or "")
            length = int(rule.get("length") or 0)
            start = int(rule.get("start") or 0)
            end = int(rule.get("end") or 0)

            if strategy == "suffix":
                if len(label) < length:
                    return subject_token
                rewritten_label = label[-length:]
            elif strategy == "prefix":
                if len(label) < length:
                    return subject_token
                rewritten_label = label[:length]
            elif strategy == "slice":
                if len(label) < end or end <= start:
                    return subject_token
                rewritten_label = label[start:end]
            elif strategy == "full":
                rewritten_label = label
            else:
                return subject_token

            if not rewritten_label:
                return subject_token
            return f"sub-{rewritten_label}"

        label = subject_token[4:] if subject_token.startswith("sub-") else subject_token
        digits = "".join(ch for ch in label if ch.isdigit())
        if not digits:
            return subject_token
        return f"sub-{digits[-3:]}"

    @staticmethod
    def _mapping_collisions(mapping: dict[str, str]) -> dict[str, list[str]]:
        reverse: dict[str, list[str]] = {}
        for old, new in mapping.items():
            reverse.setdefault(new, []).append(old)
        return {new: olds for new, olds in reverse.items() if len(olds) > 1}

    def _build_directory_rename_ops(self, mapping: dict[str, str]) -> list[_RenameOperation]:
        ops: list[_RenameOperation] = []
        for directory in self._iter_directories():
            if not _SUBJECT_DIR_PATTERN.fullmatch(directory.name):
                continue
            replacement = mapping.get(directory.name)
            if not replacement or replacement == directory.name:
                continue
            new_path = directory.with_name(replacement)
            if new_path != directory:
                ops.append(_RenameOperation(old_path=directory, new_path=new_path))
        return ops

    def _build_file_rename_ops(self, mapping: dict[str, str]) -> list[_RenameOperation]:
        ops: list[_RenameOperation] = []
        for file_path in self._iter_files():
            new_name = replace_participant_ids_in_text(file_path.name, mapping)
            if new_name == file_path.name:
                continue
            new_path = file_path.with_name(new_name)
            if new_path != file_path:
                ops.append(_RenameOperation(old_path=file_path, new_path=new_path))
        return ops

    def _preview_text_updates(self, mapping: dict[str, str]) -> list[Path]:
        updated: list[Path] = []
        for file_path in self._iter_text_files():
            original_text = self._read_text_file(file_path)
            if original_text is None:
                continue
            rewritten_text = replace_participant_ids_in_text(original_text, mapping)
            if rewritten_text != original_text:
                updated.append(file_path)
        return updated

    def _rewrite_text_file_contents(self, mapping: dict[str, str]) -> list[Path]:
        changed: list[Path] = []
        for file_path in self._iter_text_files():
            original_text = self._read_text_file(file_path)
            if original_text is None:
                continue
            rewritten_text = replace_participant_ids_in_text(original_text, mapping)
            if rewritten_text == original_text:
                continue
            file_path.write_text(rewritten_text, encoding="utf-8")
            changed.append(file_path)
        return changed

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

    def _iter_directories(self):
        for root, dirnames, _ in os.walk(self.project_root, topdown=True):
            dirnames[:] = [
                dirname
                for dirname in dirnames
                if dirname not in _IGNORED_DIR_NAMES
                and not (dirname.startswith(".") and dirname != ".")
            ]
            root_path = Path(root)
            for dirname in dirnames:
                yield root_path / dirname

    def _iter_files(self):
        for root, dirnames, filenames in os.walk(self.project_root, topdown=True):
            dirnames[:] = [
                dirname
                for dirname in dirnames
                if dirname not in _IGNORED_DIR_NAMES
                and not (dirname.startswith(".") and dirname != ".")
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

    def _plan_to_dict(self, plan: _RewritePlan, applied: bool) -> dict:
        return {
            "mode": plan.mode,
            "rule": plan.rule,
            "applied": applied,
            "subject_examples": plan.subject_examples[:200],
            "subject_token_sources": {
                key: value[:20]
                for key, value in sorted(plan.subject_token_sources.items())
            },
            "mapping": dict(sorted(plan.mapping.items())),
            "mapping_count": len(plan.mapping),
            "directory_rename_count": len(plan.directory_ops),
            "file_rename_count": len(plan.file_ops),
            "text_update_count": len(plan.preview_text_updates),
            "directory_renames": [
                {
                    "from": self._rel(op.old_path),
                    "to": self._rel(op.new_path),
                }
                for op in plan.directory_ops[:200]
            ],
            "file_renames": [
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
