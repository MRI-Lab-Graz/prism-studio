"""What the validator knows (modalities, schemas, terms) as one object, current for one validation run.

Phase 0 of docs/superpowers/specs/2026-10-23-specification-contributions-design.md. Validation code asks
`current_specification()` instead of reading constants frozen at import or hand-written modality lists, so a
project's local additions (later phases) can be part of one run without leaking into the next project.
Outside a run the official specification is current, so converters and CLI tools without a project behave as before.
"""

from __future__ import annotations

import contextlib
import contextvars
from dataclasses import dataclass
from functools import lru_cache
from typing import Iterator

from src.entity_rules import EntityRules, load_entity_rules
from src.schema_manager import DEFAULT_SCHEMA_DIR, load_all_schemas
from src.term_registry import load_registry

_TERM_MODALITIES = ("biosample",)  # the modalities that have a term registry


@dataclass(frozen=True)
class Specification:
    rules: EntityRules
    schemas: dict
    terms: dict  # modality -> {term file stem -> term}


def load_specification(
    schema_dir: str | None = None,
    version: str | None = None,
    modality_versions: dict | None = None,
    rules: EntityRules | None = None,
) -> Specification:
    """Build a specification: the official one, or with `rules` (and later phases' overlay) instead."""
    if rules is None:  # load_entity_rules() and load_entity_rules(None) are different cache entries
        rules = load_entity_rules(schema_dir) if schema_dir else load_entity_rules()
    return Specification(
        rules=rules,
        schemas=load_all_schemas(schema_dir or DEFAULT_SCHEMA_DIR, version=version, modality_versions=modality_versions),
        terms={modality: load_registry(modality) for modality in _TERM_MODALITIES},
    )


@lru_cache(maxsize=None)
def official_specification() -> Specification:
    return load_specification()


_current: contextvars.ContextVar[Specification | None] = contextvars.ContextVar("prism_specification", default=None)


@contextlib.contextmanager
def use_specification(spec: Specification) -> Iterator[Specification]:
    """Make `spec` the current specification for the duration of one validation run."""
    token = _current.set(spec)
    try:
        yield spec
    finally:
        _current.reset(token)


def current_specification() -> Specification:
    return _current.get() or official_specification()
