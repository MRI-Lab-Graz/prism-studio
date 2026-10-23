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
from functools import cached_property, lru_cache
from typing import Iterator

from src.entity_rules import EntityRules, load_entity_rules
from src.schema_manager import DEFAULT_SCHEMA_DIR, load_all_schemas
from src.spec_overlay import _vendored, load_local_patches, load_local_terms, merge_terms
from src.term_registry import load_registry

_TERM_MODALITIES = ("biosample",)  # the modalities that have a term registry


@dataclass(frozen=True, eq=False)  # compared by identity: the dict fields would make a generated __eq__/__hash__ costly or fail
class Specification:
    rules: EntityRules
    schemas: dict
    terms: dict  # modality -> {term file stem -> term}, the official registry plus the project's local terms
    local_terms: frozenset = frozenset()  # TermIDs of the local terms in use
    ignored_local: tuple = ()  # TermIDs of local terms the official registry now has (the official one wins)
    overlay_problems: tuple = ()  # one message per project overlay file that was skipped
    local_patches: tuple = ()  # modalities whose schema carries the project's patch
    ignored_patch_items: tuple = ()  # additions of a patch the official schema now has (the official one wins)

    # Derived once per specification (the rules compute them on every access); they replace the constants
    # validator.py used to freeze at import.
    def patchable_fields(self, modality: str) -> list[str]:
        """Dotted paths of the enum fields of `modality` a project may extend (none when the scripts are missing)."""
        try:
            return _vendored("schema_patch").enum_fields(self.schemas.get(modality) or {})
        except OSError:
            return []

    @cached_property
    def prism_modalities(self) -> set[str]:
        return self.rules.prism_modalities

    @cached_property
    def bids_modalities(self) -> set[str]:
        return self.rules.bids_modalities

    @cached_property
    def modality_patterns(self) -> dict[str, str]:
        """Filename regex per modality that has suffixes (strict enforcement applies to PRISM modalities)."""
        return {name: self.rules.pattern_for(name) for name, rule in self.rules.modalities.items() if rule.suffixes}


def load_specification(
    rules: EntityRules | None = None, schemas: dict | None = None, project_root=None
) -> Specification:
    """Build a specification: the official one, or with other `rules` / already loaded `schemas`.

    The runner passes the schemas it loaded with the project's version pins and the project's root, whose
    code/specification/ overlay adds its own, not yet official terms (the official registry always wins).
    """
    terms, local, ignored, problems = {}, set(), [], []
    schemas = schemas if schemas is not None else load_all_schemas(DEFAULT_SCHEMA_DIR)
    patched, official_now = [], []
    for modality in _TERM_MODALITIES:
        registry = load_registry(modality)
        if project_root is not None:
            found, skipped = load_local_terms(project_root, modality)
            registry, in_use, dropped = merge_terms(registry, found)
            local |= in_use
            ignored += dropped
            problems += skipped
            patch, notes = load_local_patches(project_root, modality)
            official_now += [n for n in notes if n.endswith(" is already official")]
            problems += [n for n in notes if n not in official_now]
            if patch and isinstance(schemas.get(modality), dict):
                try:
                    schemas = {**schemas, modality: _vendored("schema_patch").apply_patch(schemas[modality], patch)[0]}
                    patched.append(modality)
                except ValueError as exc:  # the run's (version-pinned) schema may not fit the patch
                    problems.append(f"patches/{modality}.json: {exc}")
        terms[modality] = registry
    return Specification(
        rules=rules if rules is not None else load_entity_rules(),
        schemas=schemas,
        terms=terms,
        local_terms=frozenset(local),
        ignored_local=tuple(ignored),
        overlay_problems=tuple(problems),
        local_patches=tuple(patched),
        ignored_patch_items=tuple(official_now),
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
