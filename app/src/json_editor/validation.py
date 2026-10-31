"""Check a BIDS sidecar JSON document against the BIDS schema: the one check behind the JSON Editor's validate and
save actions in Studio and `prism_tools json-editor validate|save`."""

from __future__ import annotations

from typing import Any

from src.json_editor.json_validator import JSONValidator
from src.json_editor.schema_loader import BIDSSchemaLoader


def validate_json_document(
    json_type: str, data: Any, *, validator: JSONValidator | None = None, schema_loader: BIDSSchemaLoader | None = None
) -> tuple[bool, list]:
    """(is_valid, errors) of data as a BIDS JSON file of json_type ('dataset_description', 'task-rest', ...).
    A loader that has already loaded the schema can be passed in."""
    if schema_loader is None:
        schema_loader = BIDSSchemaLoader()
        schema_loader.load_schema()
    return (validator or JSONValidator()).validate(json_type, data, schema_loader.get_schema_for_type(json_type))
