"""Pure CITATION.cff validation (stdlib + yaml + jsonschema only).

Shared by the validator (runner) and PRISM Studio (ProjectManager); it ships in
the prism-validator wheel, so it must not import any Studio-only module.
"""

import datetime as _dt
import functools
import json
from pathlib import Path
from typing import Any, Dict, Optional

import yaml
from jsonschema import Draft7Validator


@functools.lru_cache(maxsize=1)
def load_citation_cff_schema() -> Optional[Dict[str, Any]]:
    """Load the vendored official Citation File Format JSON Schema.

    Sourced from https://github.com/citation-file-format/citation-file-format
    (schema.json, CFF 1.2.0, draft-07). Update
    app/schemas/citation_cff/schema.json from that upstream file when a newer
    CFF version needs to be supported.
    """
    schema_path = Path(__file__).parent.parent / "schemas" / "citation_cff" / "schema.json"
    try:
        with open(schema_path, "r", encoding="utf-8") as handle:
            return json.load(handle)
    except Exception:
        return None


def normalize_dates(value: Any) -> Any:
    """YAML parses an unquoted 2026-01-01 into a date; CFF wants a string."""
    if isinstance(value, _dt.datetime):
        if value.time() == _dt.time(0):
            return value.date().isoformat()
        return value.isoformat()
    if isinstance(value, _dt.date):
        return value.isoformat()
    if isinstance(value, dict):
        return {k: normalize_dates(v) for k, v in value.items()}
    if isinstance(value, list):
        return [normalize_dates(v) for v in value]
    return value


def _result(exists: bool, issues, parsed=None) -> Dict[str, Any]:
    return {"exists": exists, "valid": not issues, "issues": issues, "parsed": parsed}


def validate_citation_cff_file(citation_path: Path) -> Dict[str, Any]:
    """Validate a CITATION.cff against the CFF schema.

    Returns {"exists", "valid", "issues", "parsed"}.
    """
    citation_path = Path(citation_path)
    if not citation_path.exists():
        return _result(False, ["CITATION.cff is missing at the dataset root."])
    try:
        content = citation_path.read_text(encoding="utf-8")
    except Exception as exc:
        return _result(True, [f"CITATION.cff could not be read: {exc}"])
    try:
        parsed = yaml.safe_load(content)
    except yaml.YAMLError as exc:
        return _result(True, [f"CITATION.cff is not valid YAML: {exc}"])
    if not isinstance(parsed, dict):
        return _result(True, ["CITATION.cff must contain a YAML mapping at its root."])

    parsed = normalize_dates(parsed)
    schema = load_citation_cff_schema()
    if schema is None:
        return _result(
            True,
            ["Could not load the Citation File Format schema for validation."],
            parsed,
        )
    issues = []
    for error in sorted(Draft7Validator(schema).iter_errors(parsed), key=lambda e: e.path):
        field_path = " -> ".join(str(part) for part in error.path)
        issues.append(f"{field_path}: {error.message}" if field_path else error.message)
    return _result(True, issues, parsed)
