from __future__ import annotations

import os
import re
from dataclasses import dataclass
from pathlib import Path

from src.anonymizer import replace_participant_ids_in_text
from src.bids_entity_parser import BidsEntityParser
from src.system_files import filter_system_files
from src.token_rewrite_rules import build_example_keep_rule, rewrite_token

# Mirrors src/subject_code_rewriter.py's traversal/collision/merge machinery
# with sub- swapped for ses- -- the strip/add rule logic itself (the part
# with the most edge cases: prefix/suffix/slice anchoring, add_text) is NOT
# duplicated, both classes share src/token_rewrite_rules.py for that. Fully
# unifying this remaining traversal layer too would mean restructuring
# SubjectCodeRewriter's already-tested, production apply/collision pipeline;
# left as tracked duplication for now rather than risking that class under
# time pressure. Keep changes to collision/merge/iteration logic in sync
# between the two files until/unless they're unified into one base class.
_SESSION_TOKEN_PATTERN = re.compile(r"ses-[A-Za-z0-9]+")
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
    allow_many_to_one: bool
    session_examples: list[str]
    sessions: list[str]
    session_token_sources: dict[str, list[str]]
    mapping: dict[str, str]
    directory_ops: list[_RenameOperation]
    file_ops: list[_RenameOperation]
    preview_text_updates: list[Path]
    conflicts: list[str]


class SessionCodeRewriter:
    """Rewrite existing session codes (ses-XXX) in a project tree.

    Session labels are free-form strings, never numbers -- "pre", "1", and
    "01" are three distinct, independent labels. This rewriter never
    zero-pads or otherwise coerces one into another; it only ever applies
    the exact strip/add rule the caller supplies (see
    src/token_rewrite_rules.py), same as SubjectCodeRewriter.
    """

    def __init__(self, project_root: Path):
        self.project_root = Path(project_root)

    @staticmethod
    def _path_present(path: Path) -> bool:
        """True if `path` is a real file/dir OR a symlink (including a
        broken one pointing at not-yet-fetched git-annex content).
        """
        return path.is_symlink() or path.exists()

    def list_session_ids(self) -> list[str]:
        """Return distinct session IDs found anywhere in the project.

        Unlike subject IDs, session directories are never at the project
        root (they nest one level inside each subject directory), so this
        scans the whole tree for ses- directory names rather than just
        top-level entries.
        """
        if not self.project_root.exists() or not self.project_root.is_dir():
            return []

        session_ids: set[str] = set()
        for directory in self._iter_directories():
            if BidsEntityParser.is_session_dir(directory.name):
                session_ids.add(directory.name)
        return sorted(session_ids)

    def preview(
        self,
        mode: str = "example_keep",
        example_session: str | None = None,
        keep_fragment: str | None = None,
        add_text: str | None = None,
        add_position: str | None = None,
        allow_many_to_one: bool = False,
        sessions: list[str] | None = None,
        explicit_mapping: dict[str, str] | None = None,
        cap_results: bool = True,
    ) -> dict:
        plan = self._build_plan(
            mode,
            example_session=example_session,
            keep_fragment=keep_fragment,
            add_text=add_text,
            add_position=add_position,
            allow_many_to_one=allow_many_to_one,
            sessions=sessions,
            explicit_mapping=explicit_mapping,
        )
        return self._plan_to_dict(plan, applied=False, cap_results=cap_results)

    def apply(
        self,
        mode: str = "example_keep",
        example_session: str | None = None,
        keep_fragment: str | None = None,
        add_text: str | None = None,
        add_position: str | None = None,
        allow_many_to_one: bool = False,
        sessions: list[str] | None = None,
        explicit_mapping: dict[str, str] | None = None,
    ) -> dict:
        plan = self._build_plan(
            mode,
            example_session=example_session,
            keep_fragment=keep_fragment,
            add_text=add_text,
            add_position=add_position,
            allow_many_to_one=allow_many_to_one,
            sessions=sessions,
            explicit_mapping=explicit_mapping,
        )
        if plan.conflicts:
            raise ValueError(
                "Session rewrite cannot be applied due to conflicts: "
                + "; ".join(plan.conflicts)
            )

        for op in sorted(
            plan.file_ops,
            key=lambda item: (-len(item.old_path.parts), str(item.old_path)),
        ):
            if not self._path_present(op.old_path):
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
            is_case_only_change = (
                op.old_path != op.new_path
                and str(op.old_path).casefold() == str(op.new_path).casefold()
            )
            if (
                allow_many_to_one
                and not is_case_only_change
                and op.old_path.is_dir()
                and op.new_path.exists()
                and op.new_path.is_dir()
            ):
                self._merge_directories(op.old_path, op.new_path)
                continue
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
        example_session: str | None,
        keep_fragment: str | None,
        allow_many_to_one: bool,
        sessions: list[str] | None,
        add_text: str | None = None,
        add_position: str | None = None,
        explicit_mapping: dict[str, str] | None = None,
    ) -> _RewritePlan:
        if not self.project_root.exists() or not self.project_root.is_dir():
            raise ValueError(f"Project root does not exist: {self.project_root}")

        normalized_mode = self._normalize_mode(mode)
        normalized_sessions = self._normalize_sessions(sessions)
        session_tokens, session_token_sources = self._collect_session_tokens()
        if explicit_mapping is not None:
            # Same bypass rationale as SubjectCodeRewriter: a caller that
            # already resolved the mapping once wants it applied as-is,
            # without re-deriving from a possibly-now-stale example_session.
            mapping = dict(explicit_mapping)
            rule = None
        else:
            mapping, rule = self._build_session_mapping(
                normalized_mode,
                session_tokens,
                example_session=example_session,
                keep_fragment=keep_fragment,
                add_text=add_text,
                add_position=add_position,
            )

        if normalized_sessions:
            filtered_mapping: dict[str, str] = {}
            for old_session, new_session in mapping.items():
                old_label = old_session[4:] if old_session.startswith("ses-") else old_session
                if old_label in normalized_sessions:
                    filtered_mapping[old_session] = new_session
            mapping = filtered_mapping

        if not mapping:
            return _RewritePlan(
                mode=normalized_mode,
                rule=rule,
                allow_many_to_one=allow_many_to_one,
                session_examples=session_tokens,
                sessions=sorted(normalized_sessions),
                session_token_sources=session_token_sources,
                mapping={},
                directory_ops=[],
                file_ops=[],
                preview_text_updates=[],
                conflicts=[],
            )

        collisions = self._mapping_collisions(mapping)
        conflicts: list[str] = []
        if collisions and not allow_many_to_one:
            for new_session, old_sessions in collisions.items():
                joined_old = ", ".join(sorted(old_sessions))
                conflicts.append(
                    f"Multiple source sessions map to {new_session}: {joined_old}"
                )

        directory_ops = self._build_directory_rename_ops(mapping)
        file_ops = self._build_file_rename_ops(mapping)
        preview_text_updates = self._preview_text_updates(mapping)
        if allow_many_to_one:
            conflicts.extend(self._detect_final_file_path_collisions(mapping))
        conflicts.extend(
            self._detect_rename_conflicts(
                directory_ops + file_ops,
                allow_many_to_one=allow_many_to_one,
            )
        )

        return _RewritePlan(
            mode=normalized_mode,
            rule=rule,
            allow_many_to_one=allow_many_to_one,
            session_examples=session_tokens,
            sessions=sorted(normalized_sessions),
            session_token_sources=session_token_sources,
            mapping=mapping,
            directory_ops=directory_ops,
            file_ops=file_ops,
            preview_text_updates=preview_text_updates,
            conflicts=conflicts,
        )

    @staticmethod
    def _normalize_sessions(sessions: list[str] | None) -> set[str]:
        if not sessions:
            return set()
        normalized: set[str] = set()
        for session in sessions:
            token = str(session or "").strip()
            if token.startswith("ses-"):
                token = token[4:]
            if BidsEntityParser.is_valid_label(token):
                normalized.add(token)
        return normalized

    @staticmethod
    def _normalize_mode(mode: str | None) -> str:
        normalized = (mode or "example_keep").strip().lower()
        if normalized not in {"last3", "example_keep"}:
            raise ValueError(f"Unsupported session rewrite mode: {mode}")
        return normalized

    def _collect_session_tokens(self) -> tuple[list[str], dict[str, list[str]]]:
        session_tokens: set[str] = set()
        session_sources: dict[str, set[str]] = {}

        def add_occurrence(token: str, source: str):
            session_tokens.add(token)
            bucket = session_sources.setdefault(token, set())
            if len(bucket) < 50:
                bucket.add(source)

        for directory in self._iter_directories():
            rel_dir = directory.relative_to(self.project_root).as_posix()
            for token in _SESSION_TOKEN_PATTERN.findall(directory.name):
                add_occurrence(token, rel_dir)

        for file_path in self._iter_files():
            rel_path = file_path.relative_to(self.project_root).as_posix()
            for token in _SESSION_TOKEN_PATTERN.findall(file_path.name):
                add_occurrence(token, rel_path)
            for token in _SESSION_TOKEN_PATTERN.findall(rel_path):
                add_occurrence(token, rel_path)

        sorted_tokens = sorted(session_tokens)
        normalized_sources = {
            token: sorted(session_sources.get(token, set()))[:20]
            for token in sorted_tokens
        }
        return sorted_tokens, normalized_sources

    def _build_session_mapping(
        self,
        mode: str,
        session_tokens: list[str],
        example_session: str | None,
        keep_fragment: str | None,
        add_text: str | None = None,
        add_position: str | None = None,
    ) -> tuple[dict[str, str], dict[str, str | int] | None]:
        rule: dict[str, str | int] | None = None
        if mode == "example_keep":
            rule = self._build_example_keep_rule(
                session_tokens,
                example_session=example_session,
                keep_fragment=keep_fragment,
                add_text=add_text,
                add_position=add_position,
            )

        mapping: dict[str, str] = {}
        for token in session_tokens:
            rewritten = self._rewrite_session_token(token, mode, rule=rule)
            if rewritten and rewritten != token:
                mapping[token] = rewritten
        return mapping, rule

    @staticmethod
    def _build_example_keep_rule(
        session_tokens: list[str],
        example_session: str | None,
        keep_fragment: str | None,
        add_text: str | None = None,
        add_position: str | None = None,
    ) -> dict[str, str | int]:
        rule = build_example_keep_rule(
            tokens=session_tokens,
            example_token=example_session,
            keep_fragment=keep_fragment,
            token_prefix="ses-",
            add_text=add_text,
            add_position=add_position,
            id_noun="session ID",
        )
        rule["example_session"] = rule.pop("example_token")
        return rule

    @staticmethod
    def _rewrite_session_token(
        session_token: str,
        mode: str,
        rule: dict[str, str | int] | None,
    ) -> str:
        return rewrite_token(session_token, mode, rule, "ses-")

    @staticmethod
    def _mapping_collisions(mapping: dict[str, str]) -> dict[str, list[str]]:
        reverse: dict[str, list[str]] = {}
        for old, new in mapping.items():
            reverse.setdefault(new, []).append(old)
        return {new: olds for new, olds in reverse.items() if len(olds) > 1}

    def _build_directory_rename_ops(self, mapping: dict[str, str]) -> list[_RenameOperation]:
        ops: list[_RenameOperation] = []
        for directory in self._iter_directories():
            if not BidsEntityParser.is_session_dir(directory.name):
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

    def _merge_directories(self, source_dir: Path, target_dir: Path) -> None:
        for child in source_dir.iterdir():
            destination = target_dir / child.name
            if not destination.exists():
                child.rename(destination)
                continue
            if child.is_dir() and destination.is_dir():
                self._merge_directories(child, destination)
                continue
            raise ValueError(
                "Session rewrite cannot merge because target path already exists: "
                f"{self._rel(destination)}"
            )
        source_dir.rmdir()

    def _detect_final_file_path_collisions(self, mapping: dict[str, str]) -> list[str]:
        rewritten_to_sources: dict[str, list[str]] = {}
        for file_path in self._iter_files():
            rel = file_path.relative_to(self.project_root).as_posix()
            rewritten_rel = replace_participant_ids_in_text(rel, mapping)
            rewritten_to_sources.setdefault(rewritten_rel, []).append(rel)

        conflicts: list[str] = []
        for rewritten_rel, sources in sorted(rewritten_to_sources.items()):
            unique_sources = sorted(set(sources))
            if len(unique_sources) <= 1:
                continue
            preview = ", ".join(unique_sources[:5])
            if len(unique_sources) > 5:
                preview = f"{preview}, ..."
            conflicts.append(
                "Final file path collision after harmonization: "
                f"{rewritten_rel} <= {preview}"
            )
        return conflicts

    @staticmethod
    def _read_text_file(file_path: Path) -> str | None:
        try:
            return file_path.read_text(encoding="utf-8")
        except (UnicodeDecodeError, OSError):
            return None

    def _detect_rename_conflicts(
        self,
        ops: list[_RenameOperation],
        allow_many_to_one: bool = False,
    ) -> list[str]:
        conflicts: list[str] = []
        old_paths = {op.old_path for op in ops}
        old_paths_casefold = {str(p).casefold() for p in old_paths}
        seen_targets: dict[Path, Path] = {}

        for op in ops:
            existing_source = seen_targets.get(op.new_path)
            if existing_source is not None and existing_source != op.old_path:
                can_merge_dirs = (
                    allow_many_to_one
                    and existing_source.is_dir()
                    and op.old_path.is_dir()
                    and (not self._path_present(op.new_path) or op.new_path.is_dir())
                )
                if not can_merge_dirs:
                    conflicts.append(
                        "Rename target collision: "
                        f"{self._rel(existing_source)} and {self._rel(op.old_path)} "
                        f"both map to {self._rel(op.new_path)}"
                    )
            else:
                seen_targets[op.new_path] = op.old_path

            if (
                self._path_present(op.new_path)
                and op.new_path not in old_paths
                and str(op.new_path).casefold() not in old_paths_casefold
            ):
                if allow_many_to_one and op.old_path.is_dir() and op.new_path.is_dir():
                    continue
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
                if file_path.is_file() or file_path.is_symlink():
                    yield file_path

    def _iter_text_files(self):
        for file_path in self._iter_files():
            suffix = file_path.suffix.lower()
            if suffix in _TEXT_SUFFIXES or file_path.name.lower() in _TEXT_FILENAMES:
                yield file_path

    def _plan_to_dict(
        self, plan: _RewritePlan, applied: bool, cap_results: bool = True
    ) -> dict:
        cap = (lambda items: items[:200]) if cap_results else (lambda items: items)
        return {
            "mode": plan.mode,
            "rule": plan.rule,
            "allow_many_to_one": bool(plan.allow_many_to_one),
            "sessions": plan.sessions,
            "applied": applied,
            "session_examples": cap(plan.session_examples),
            "session_token_sources": {
                key: value[:20]
                for key, value in sorted(plan.session_token_sources.items())
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
                for op in cap(plan.directory_ops)
            ],
            "file_renames": [
                {
                    "from": self._rel(op.old_path),
                    "to": self._rel(op.new_path),
                }
                for op in cap(plan.file_ops)
            ],
            "text_update_files": [
                path.relative_to(self.project_root).as_posix()
                for path in cap(plan.preview_text_updates)
            ],
            "conflicts": plan.conflicts,
        }

    def _rel(self, path: Path) -> str:
        return path.relative_to(self.project_root).as_posix()
