import os
from datetime import date
from pathlib import Path

from flask import current_app


def _default_library_root_for_templates(*, modality: str) -> Path:
    candidate = _global_survey_library_root()
    if candidate:
        return candidate
    return (Path(current_app.root_path) / "survey_library").resolve()


def _safe_expand_path(path_str: str) -> Path:
    """Safely expand path, handling network drives."""
    try:
        candidate = Path(path_str)
        if "~" in path_str:
            candidate = candidate.expanduser()
        return candidate
    except (OSError, ValueError):
        return Path(path_str)


def _global_survey_library_root() -> Path | None:
    """Get the global survey library path from configuration."""
    base_dir = Path(current_app.root_path)

    official_candidates = [
        base_dir / "official" / "library",
        base_dir.parent / "official" / "library",
    ]
    for candidate in official_candidates:
        try:
            candidate = candidate.resolve()
            if candidate.exists() and candidate.is_dir():
                return candidate
        except (OSError, ValueError):
            if candidate.exists() and candidate.is_dir():
                return candidate

    from src.config import get_effective_library_paths

    lib_paths = get_effective_library_paths(app_root=str(base_dir))

    if lib_paths["global_library_path"]:
        candidate = _safe_expand_path(lib_paths["global_library_path"])
        if not candidate.is_absolute():
            try:
                candidate = (base_dir / candidate).resolve()
            except (OSError, ValueError):
                candidate = base_dir / candidate
        if candidate.exists() and candidate.is_dir():
            return candidate

    preferred = base_dir / "library" / "survey_i18n"
    try:
        preferred = preferred.resolve()
    except (OSError, ValueError):
        pass
    if preferred.exists() and any(preferred.glob("survey-*.json")):
        return preferred

    fallback = base_dir / "survey_library"
    try:
        fallback = fallback.resolve()
    except (OSError, ValueError):
        pass
    return fallback if fallback.exists() else None


def _global_recipes_root() -> Path | None:
    """Get the global recipes path from configuration."""
    base_dir = Path(current_app.root_path)
    from src.config import get_effective_library_paths

    lib_paths = get_effective_library_paths(app_root=str(base_dir))

    if lib_paths["global_recipe_path"]:
        candidate = _safe_expand_path(lib_paths["global_recipe_path"])
        if not candidate.is_absolute():
            try:
                candidate = (base_dir / candidate).resolve()
            except (OSError, ValueError):
                candidate = base_dir / candidate
        if candidate.exists() and candidate.is_dir():
            return candidate
    return None


def _resolve_library_root(library_path: str | None) -> Path:
    if library_path:
        path = _safe_expand_path(library_path)
        try:
            path = path.resolve()
        except (OSError, ValueError):
            pass
        if path.exists() and path.is_dir():
            return path
        raise FileNotFoundError(f"Invalid library folder: {library_path}")

    default_root = _default_library_root_for_templates(modality="survey")
    if default_root:
        try:
            return default_root.resolve()
        except (OSError, ValueError):
            return default_root
    raise FileNotFoundError("No default library root found")


def _template_dir(*, modality: str, library_root: Path) -> Path:
    candidate = library_root / modality
    if candidate.is_dir():
        return candidate
    return library_root


def _project_library_root() -> Path:
    from src.web.blueprints.projects import get_current_project

    project = get_current_project()
    project_path = project.get("path")
    if not project_path:
        raise RuntimeError(
            "Select a project first; the template editor only saves into the project's custom library."
        )
    project_root = Path(project_path).expanduser().resolve()
    target = project_root / "code" / "library"
    target.mkdir(parents=True, exist_ok=True)
    return target


def _project_template_folder(*, modality: str) -> Path:
    library_root = _project_library_root()
    folder = library_root / modality
    folder.mkdir(parents=True, exist_ok=True)
    return folder


def _load_prism_schema(*, modality: str, schema_version: str | None) -> dict:
    from src.schema_manager import load_schema

    schema_dir = os.path.join(current_app.root_path, "schemas")
    schema = load_schema(modality, schema_dir=schema_dir, version=schema_version)
    if not schema:
        raise FileNotFoundError(
            f"No schema found for modality={modality} version={schema_version}"
        )
    return schema


def _pick_enum_value(values: list) -> object:
    for value in values:
        if value != "":
            return value
    return values[0] if values else ""


def _schema_example(schema: dict) -> object:
    if not isinstance(schema, dict):
        return None

    if isinstance(schema.get("examples"), list) and schema.get("examples"):
        return schema["examples"][0]
    if "default" in schema:
        return schema.get("default")
    if isinstance(schema.get("enum"), list) and schema.get("enum"):
        return _pick_enum_value(schema["enum"])

    schema_type = schema.get("type")
    if isinstance(schema_type, list):
        for preferred in (
            "object",
            "array",
            "string",
            "integer",
            "number",
            "boolean",
            "null",
        ):
            if preferred in schema_type:
                schema_type = preferred
                break
        else:
            schema_type = schema_type[0] if schema_type else None

    if schema_type == "object" or (schema_type is None and "properties" in schema):
        out: dict[str, object] = {}
        properties = schema.get("properties") or {}
        if isinstance(properties, dict):
            for key, value in properties.items():
                out[key] = _schema_example(value if isinstance(value, dict) else {})
        return out

    if schema_type == "array":
        item_schema = schema.get("items") if isinstance(schema.get("items"), dict) else {}
        return [_schema_example(item_schema)]

    if schema_type == "integer":
        return 0
    if schema_type == "number":
        return 0
    if schema_type == "boolean":
        return False
    if schema_type == "null":
        return None

    return ""


def _deep_merge(base: object, override: object) -> object:
    if isinstance(base, dict) and isinstance(override, dict):
        out = dict(base)
        for key, value in override.items():
            if key in out:
                out[key] = _deep_merge(out[key], value)
            else:
                out[key] = value
        return out
    return override


def _new_template_from_schema(*, modality: str, schema_version: str | None) -> dict:
    schema = _load_prism_schema(modality=modality, schema_version=schema_version)
    out: dict[str, object] = {}

    properties = schema.get("properties") if isinstance(schema.get("properties"), dict) else {}
    for key, value in properties.items():
        out[key] = _schema_example(value if isinstance(value, dict) else {})

    schema_semver = schema.get("version")
    if isinstance(out.get("Metadata"), dict):
        metadata = dict(out["Metadata"])
        if isinstance(schema_semver, str):
            metadata["SchemaVersion"] = schema_semver
        metadata.setdefault("CreationDate", date.today().isoformat())
        out["Metadata"] = metadata

    if modality == "survey":
        if isinstance(out.get("Technical"), dict):
            out["Technical"]["StimulusType"] = (
                out["Technical"].get("StimulusType") or "Questionnaire"
            )
            out["Technical"]["FileFormat"] = out["Technical"].get("FileFormat") or "tsv"

    if modality == "biometrics":
        if isinstance(out.get("Technical"), dict):
            out["Technical"]["FileFormat"] = out["Technical"].get("FileFormat") or "tsv"

    return out


def _validate_against_schema(*, instance: object, schema: dict) -> list[dict]:
    from jsonschema import Draft7Validator

    validator = Draft7Validator(schema)
    errors = []
    for err in sorted(validator.iter_errors(instance), key=lambda e: list(e.path)):
        path = "/".join(str(p) for p in err.path)
        errors.append({"path": path, "message": err.message})

    if isinstance(instance, dict) and "Technical" in instance:
        technical = instance["Technical"]
        if isinstance(technical, dict):
            platform = technical.get("SoftwarePlatform", "").strip()
            version = technical.get("SoftwareVersion", "").strip()
            if platform and platform != "Paper and Pencil" and not version:
                errors.append(
                    {
                        "path": "Technical/SoftwareVersion",
                        "message": f"SoftwareVersion is required when SoftwarePlatform is '{platform}'",
                    }
                )

    return errors


def _strip_template_editor_internal_keys(template: dict) -> dict:
    """Remove editor-internal metadata keys that are not part of PRISM schemas."""
    if not isinstance(template, dict):
        return template

    cleaned = dict(template)
    cleaned.pop("_aliases", None)
    cleaned.pop("_reverse_aliases", None)
    return cleaned
