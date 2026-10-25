"""Check entities.schema.json entries and the conventions of every PRISM modality schema.

Usage: python scripts/check_modalities.py [--entities FILE] [--schemas DIR]
Prints one line per problem and exits 1 when there is any.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from jsonschema import Draft7Validator

REPO = Path(__file__).resolve().parent.parent
ENTRY_SCHEMA = Path(__file__).resolve().parent / "entities_entry.schema.json"
TOP_KEYS = ("$schema", "$id", "version", "title", "description", "type", "properties", "required")


def _schema_problems(name: str, schema_dir: Path) -> list[str]:
    path = schema_dir / f"{name}.schema.json"
    if not path.is_file():
        return [f"{name}: schema file {path.name} is missing in {schema_dir}"]
    schema = json.loads(path.read_text(encoding="utf-8"))
    problems = [f"{name}: schema lacks top-level key {k}" for k in TOP_KEYS if k not in schema]
    if schema.get("type") != "object":
        problems.append(f'{name}: schema type must be "object"')
    for key in schema.get("required", []):
        if key not in schema.get("properties", {}):
            problems.append(f"{name}: required key {key} is not in properties")
    if "version" in schema and not str(schema.get("$id", "")).endswith(f"/v{schema['version']}"):
        problems.append(f"{name}: $id {schema.get('$id')} does not end with /v{schema['version']}")
    try:
        Draft7Validator.check_schema(schema)
    except Exception as exc:  # jsonschema.SchemaError
        problems.append(f"{name}: not a valid draft-07 schema: {getattr(exc, 'message', exc)}")
    return problems


def check(entities: dict, schema_dir: Path) -> list[str]:
    entry_validator = Draft7Validator(json.loads(ENTRY_SCHEMA.read_text(encoding="utf-8")))
    problems = []
    for name, entry in entities["modalities"].items():
        problems += [f"{name}: {e.message}" for e in entry_validator.iter_errors(entry)]
        if entry.get("kind") == "prism" and "suffixes" in entry:
            problems += _schema_problems(name, schema_dir)
    return problems


def main(argv=None) -> int:
    stable = REPO / "schemas" / "stable"
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("--entities", type=Path, default=stable / "entities.schema.json")
    parser.add_argument("--schemas", type=Path, default=stable)
    args = parser.parse_args(argv)
    entities = json.loads(args.entities.read_text(encoding="utf-8"))
    problems = check(entities, args.schemas)
    for p in problems:
        print(p)
    return 1 if problems else 0


if __name__ == "__main__":
    sys.exit(main())
