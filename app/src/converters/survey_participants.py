"""Participant mapping/template helpers for survey conversion."""

from __future__ import annotations

from pathlib import Path

from ..utils.io import read_json as _read_json


def _load_participants_mapping(output_root: Path, log_fn=None) -> dict | None:
    """Load participants_mapping.json from the project."""
    project_root = output_root

    candidates = [
        project_root / "participants_mapping.json",
        project_root / "code" / "participants_mapping.json",
        project_root / "code" / "library" / "participants_mapping.json",
        project_root / "code" / "library" / "survey" / "participants_mapping.json",
    ]

    for p in candidates:
        if p.exists() and p.is_file():
            try:
                mapping = _read_json(p)
                if log_fn:
                    log_fn(f"Loaded participants_mapping.json from: {p}")
                return mapping
            except Exception as e:
                if log_fn:
                    log_fn(f"Warning: Failed to load {p}: {e}")
                continue

    if log_fn:
        log_fn("No participants_mapping.json found (using template columns only)")
    return None


def _get_mapped_columns(
    mapping: dict | None,
) -> tuple[set[str], dict[str, str], dict[str, dict]]:
    """Extract column information from participants mapping."""
    if not mapping or "mappings" not in mapping:
        return set(), {}, {}

    allowed_columns: set[str] = set()
    column_renames: dict[str, str] = {}
    value_mappings: dict[str, dict] = {}

    for var_name, spec in mapping.get("mappings", {}).items():
        if not isinstance(spec, dict):
            continue
        source_col = spec.get("source_column")
        standard_var = spec.get("standard_variable", var_name)

        if source_col:
            allowed_columns.add(source_col.lower())
            column_renames[source_col.lower()] = standard_var

            if "value_mapping" in spec:
                value_mappings[standard_var] = spec["value_mapping"]

    return allowed_columns, column_renames, value_mappings


def _load_participants_template(library_dir: Path) -> dict | None:
    """Load a participant template from the survey library, if present."""

    library_dir = library_dir.resolve()
    candidates: list[Path] = []
    if library_dir.name == "survey":
        candidates.append(library_dir.parent / "participants.json")

    candidates.extend(
        [
            library_dir / "participants.json",
            library_dir / "survey-participants.json",
            library_dir / "survey-participant.json",
        ]
    )

    for ancestor in library_dir.parents[:3]:
        candidates.append(ancestor / "participants.json")

    try:
        app_root = Path(__file__).parent.parent.parent.resolve()  # app/
        repo_root = app_root.parent.resolve()  # prism-studio/
        candidates.append(app_root / "official" / "participants.json")
        candidates.append(repo_root / "official" / "participants.json")
    except Exception:
        pass

    seen: set[Path] = set()
    for p in candidates:
        if p in seen:
            continue
        seen.add(p)
        if p.exists() and p.is_file():
            try:
                return _read_json(p)
            except Exception:
                return None
    return None


def _is_participant_template(path: Path) -> bool:
    stem = path.stem.lower()
    return stem in {"survey-participant", "survey-participants"}


def _normalize_participant_template_dict(template: dict | None) -> dict | None:
    """Extract column definitions from a participant template structure."""

    if not isinstance(template, dict):
        return None
    if "Columns" in template and isinstance(template.get("Columns"), dict):
        return template.get("Columns")
    return template


def _participants_json_from_template(
    *,
    columns: list[str],
    template: dict | None,
    extra_descriptions: dict[str, str] | None = None,
) -> dict:
    """Create a BIDS/NeuroBagel-compatible participants.json for TSV columns."""
    template = _normalize_participant_template_dict(template)
    extra_descriptions = extra_descriptions or {}
    out: dict[str, dict] = {}

    def _template_meta(col: str) -> dict:
        if not template:
            return {}
        if col not in template:
            return {}
        v = template.get(col)
        if not isinstance(v, dict):
            return {}
        meta: dict[str, object] = {}

        desc = v.get("Description")
        if desc:
            meta["Description"] = desc
        levels = v.get("Levels")
        if isinstance(levels, dict) and levels:
            meta["Levels"] = levels
        units = v.get("Units") or v.get("Unit")
        if units:
            meta["Units"] = units
        for key in ("DataType", "VariableType", "MinValue", "MaxValue", "Annotations"):
            if key in v:
                meta[key] = v[key]
        return meta

    for col in columns:
        if col == "participant_id":
            out[col] = {
                "Description": "Participant identifier (BIDS subject label)",
            }
            continue

        meta = _template_meta(col)

        if not meta:
            if col in extra_descriptions:
                meta = {"Description": extra_descriptions[col]}
            else:
                meta = {"Description": col}
                if col == "age":
                    meta["Description"] = "Age of participant"
                    meta["Units"] = "years"
                elif col == "sex":
                    meta["Description"] = "Biological sex"
                elif col == "gender":
                    meta["Description"] = "Gender identity"

        out[col] = dict(meta)

    return out
