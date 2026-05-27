from __future__ import annotations

import re
from pathlib import Path


class BidsEntityParser:
    ENTITY_TOKEN_PATTERN = re.compile(
        r"^(?P<key>[A-Za-z0-9]+)-(?P<value>[A-Za-z0-9]+)$"
    )
    LABEL_PATTERN = re.compile(r"^[A-Za-z0-9]+$")
    SUBJECT_DIR_PATTERN = re.compile(r"^sub-[A-Za-z0-9]+$")
    SESSION_DIR_PATTERN = re.compile(r"^ses-[A-Za-z0-9]+$")

    @classmethod
    def parse_entity_token(cls, token: str) -> tuple[str, str] | None:
        match = cls.ENTITY_TOKEN_PATTERN.fullmatch(str(token or "").strip())
        if match is None:
            return None
        return match.group("key").lower(), match.group("value")

    @classmethod
    def extract_entity_key(cls, token: str) -> str | None:
        parsed = cls.parse_entity_token(token)
        if parsed is None:
            return None
        return parsed[0]

    @classmethod
    def is_valid_label(cls, value: str | None) -> bool:
        return cls.LABEL_PATTERN.fullmatch(str(value or "").strip()) is not None

    @classmethod
    def is_subject_dir(cls, value: str | None) -> bool:
        return cls.SUBJECT_DIR_PATTERN.fullmatch(str(value or "").strip()) is not None

    @classmethod
    def is_session_dir(cls, value: str | None) -> bool:
        return cls.SESSION_DIR_PATTERN.fullmatch(str(value or "").strip()) is not None

    @classmethod
    def subject_label_from_dir(cls, value: str | None) -> str | None:
        part = str(value or "").strip()
        if not cls.is_subject_dir(part):
            return None
        return part[4:]

    @classmethod
    def session_label_from_dir(cls, value: str | None) -> str | None:
        part = str(value or "").strip()
        if not cls.is_session_dir(part):
            return None
        return part[4:]

    @classmethod
    def extract_subject_from_path(cls, path_text: str | Path) -> str | None:
        for part in Path(str(path_text or "").strip()).parts:
            if cls.is_subject_dir(part):
                return part
        return None