"""Loader/compiler for the declarative entity/filename rules in
app/schemas/*/entities.json.

This is the single source of truth for per-modality suffix/extension/entity
grammar. Consumers (validator, fixer, issue hints, entity rewriter) compile
concrete regexes/strings from it instead of hardcoding their own copies.
"""

from __future__ import annotations

from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

from src.schema_manager import load_schema

_REPO_ROOT = Path(__file__).resolve().parent.parent
_DEFAULT_SCHEMA_DIR = str(_REPO_ROOT / "app" / "schemas")


@dataclass(frozen=True)
class EntityValueRule:
    pattern: str | None = None
    enum: tuple[str, ...] = ()
    allow_other: bool = False
    other_pattern: str | None = None

    @classmethod
    def from_json(cls, data: dict) -> "EntityValueRule":
        return cls(
            pattern=data.get("pattern"),
            enum=tuple(data.get("enum", ())),
            allow_other=bool(data.get("allowOther", False)),
            other_pattern=data.get("otherPattern"),
        )

    def alternatives(self) -> str:
        if self.enum:
            alts = list(self.enum)
            if self.allow_other and self.other_pattern:
                alts.append(self.other_pattern)
            return "|".join(alts)
        return self.pattern or ""


@dataclass(frozen=True)
class ModalityRule:
    name: str
    kind: str
    suffixes: tuple[str, ...] = ()
    extensions: tuple[str, ...] = ()
    required_entity_values: tuple[tuple[str, EntityValueRule], ...] = ()
    optional_entity_values: tuple[tuple[str, EntityValueRule], ...] = ()
    example_task: str = "rest"

    @classmethod
    def from_json(cls, name: str, data: dict) -> "ModalityRule":
        return cls(
            name=name,
            kind=data.get("kind", "prism"),
            suffixes=tuple(data.get("suffixes", ())),
            extensions=tuple(data.get("extensions", ())),
            required_entity_values=tuple(
                (key, EntityValueRule.from_json(value))
                for key, value in data.get("requiredEntityValues", {}).items()
            ),
            optional_entity_values=tuple(
                (key, EntityValueRule.from_json(value))
                for key, value in data.get("optionalEntityValues", {}).items()
            ),
            example_task=data.get("example", {}).get("task", "rest"),
        )


@dataclass(frozen=True)
class EntityRules:
    entity_order: tuple[str, ...]
    default_required_entities: frozenset
    modalities: dict[str, ModalityRule]
    aliases: dict[str, str]

    @property
    def prism_modalities(self) -> set[str]:
        return {name for name, rule in self.modalities.items() if rule.kind == "prism"}

    @property
    def bids_modalities(self) -> set[str]:
        return {
            name for name, rule in self.modalities.items() if rule.kind == "bidsPassthrough"
        }

    def pattern_for(self, modality: str) -> str:
        rule = self.modalities.get(modality)
        if rule is None or not rule.suffixes or not rule.extensions:
            return r".*"
        return compile_modality_regex(rule)


def compile_modality_regex(rule: ModalityRule) -> str:
    """Rebuild the MODALITY_PATTERNS-style regex source for a modality rule."""
    prefix_parts: list[str] = []
    for key, value_rule in rule.required_entity_values:
        alt = value_rule.alternatives()
        prefix_parts.append(f"_{key}-({alt})" if value_rule.enum else f"_{key}-{alt}")
    for key, value_rule in rule.optional_entity_values:
        prefix_parts.append(f"(_{key}-({value_rule.alternatives()}))?")

    suffix_part = (
        rule.suffixes[0] if len(rule.suffixes) == 1 else "(" + "|".join(rule.suffixes) + ")"
    )
    escaped_exts = [ext.replace(".", r"\.") for ext in rule.extensions]
    ext_part = escaped_exts[0] if len(escaped_exts) == 1 else "(" + "|".join(escaped_exts) + ")"

    return rf".+{''.join(prefix_parts)}_{suffix_part}\.{ext_part}$"


def _human_join(items: tuple[str, ...]) -> str:
    parts = list(items)
    if len(parts) == 1:
        return parts[0]
    return ", ".join(parts[:-1]) + ", or " + parts[-1]


def describe_modality_pattern(rule: ModalityRule) -> str:
    """Rebuild the get_fix_hint()-style human-readable hint for a modality rule."""
    if not rule.suffixes or not rule.extensions:
        return f"Ensure the filename ends with '_{rule.name}.<ext>' appropriate for this modality"

    entity_values = rule.required_entity_values + rule.optional_entity_values
    entity_token = ""
    if entity_values:
        key, value_rule = entity_values[0]
        example_value = value_rule.enum[0] if value_rule.enum else "example"
        entity_token = f"{key}-{example_value}_"

    example_suffix = rule.suffixes[0]
    example_ext = rule.extensions[0]

    if len(rule.extensions) >= 3:
        ext_list_str = _human_join(rule.extensions)
        suffix_clause = " or ".join(f"'_{s}.<ext>'" for s in rule.suffixes)
        head = f"Ensure the filename ends with {suffix_clause} where <ext> is {ext_list_str}"
    elif len(rule.extensions) == 2:
        head = (
            f"Ensure the filename ends with '_{example_suffix}.{rule.extensions[0]}' "
            f"or '_{example_suffix}.{rule.extensions[1]}'"
        )
    else:
        head = f"Ensure the filename ends with '_{example_suffix}.{rule.extensions[0]}'"

    example = f"(e.g., sub-001_task-{rule.example_task}_{entity_token}{example_suffix}.{example_ext})"
    return f"{head} {example}"


@lru_cache(maxsize=None)
def load_entity_rules(schema_dir: str | None = None, version: str = "stable") -> EntityRules:
    schema = load_schema("entities", schema_dir or _DEFAULT_SCHEMA_DIR, version)
    if not schema:
        raise RuntimeError(
            "Could not load entities.json rules file from "
            f"{schema_dir or _DEFAULT_SCHEMA_DIR}/{version}."
        )

    aliases = dict(schema.get("aliases", {}))
    modalities: dict[str, ModalityRule] = {
        name: ModalityRule.from_json(name, data)
        for name, data in schema.get("modalities", {}).items()
    }
    for alias_name, target_name in aliases.items():
        if target_name in modalities:
            modalities[alias_name] = modalities[target_name]

    return EntityRules(
        entity_order=tuple(schema.get("entityOrder", ())),
        default_required_entities=frozenset(schema.get("defaultRequiredEntities", ())),
        modalities=modalities,
        aliases=aliases,
    )
