"""Instrument registry: stable identity (TaskName/Version/DOI) over the survey library.

Roadmap Phase 4 ("Instrument registry & variable semantics"). Reuses the
same identity fields already threaded through filenames, item_registry.py's
in-memory dedup, and the phenotype export bridge: Study.TaskName as the
stable slug (falling back to the filename stem), and Study.VariantDefinitions
for concrete variants - no new ID scheme is introduced here.

The generated index conforms to
app/schemas/stable/instrument-registry.schema.json.
"""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from typing import Any
import json


def _read_json(path: Path) -> dict:
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def _write_json(path: Path, obj: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(obj, f, indent=2, ensure_ascii=False)
        f.write("\n")


def _extract_variants(study: dict) -> list[dict[str, Any]]:
    variants = []
    for entry in study.get("VariantDefinitions") or []:
        if not isinstance(entry, dict) or not entry.get("VariantID"):
            continue
        variants.append(
            {
                "VariantID": entry["VariantID"],
                "ItemCount": entry.get("ItemCount"),
                "ScaleType": entry.get("ScaleType", ""),
            }
        )
    return variants


def build_registry_index(library_dir: Path) -> dict[str, Any]:
    """Build an instrument registry index over a survey template library.

    Args:
        library_dir: Directory containing survey-*.json instrument templates
            (typically official/library/survey).

    Returns:
        A dict matching instrument-registry.schema.json.
    """
    instruments: dict[str, Any] = {}
    for json_path in sorted(library_dir.glob("survey-*.json")):
        if "participant" in json_path.stem.lower():
            continue
        try:
            template = _read_json(json_path)
        except (OSError, json.JSONDecodeError):
            continue

        study = template.get("Study")
        if not isinstance(study, dict):
            study = {}

        task_name = study.get("TaskName") or json_path.stem.replace("survey-", "")

        instruments[task_name] = {
            "TaskName": task_name,
            "SourceFile": json_path.name,
            "ShortName": study.get("ShortName"),
            "OriginalName": study.get("OriginalName"),
            "DOI": study.get("DOI", ""),
            "Citation": study.get("Citation", ""),
            "Version": study.get("Version"),
            "Versions": [str(v) for v in (study.get("Versions") or [])],
            "Variants": _extract_variants(study),
            "Vocabulary": None,
        }

    return {
        "GeneratedOn": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "SourceLibrary": "official/library/survey",
        "Instruments": instruments,
    }


def write_registry_index(library_dir: Path, index_path: Path) -> dict[str, Any]:
    """Build and persist the registry index. Returns the built index."""
    index = build_registry_index(library_dir)
    _write_json(index_path, index)
    return index


_registry_cache: dict[Path, dict[str, Any]] = {}


def load_registry_index(index_path: Path) -> dict[str, Any]:
    """Load a previously generated registry index, caching by path."""
    cached = _registry_cache.get(index_path)
    if cached is not None:
        return cached
    index = _read_json(index_path)
    _registry_cache[index_path] = index
    return index


def get_instrument_identity(
    index: dict[str, Any], task_name: str, variant_id: str | None = None
) -> dict[str, Any]:
    """Resolve the stampable identity fields for a (TaskName, VariantID) pair.

    Returns a dict with "Version" and "DOI" keys (values may be empty/None
    when the registry has nothing on file), suitable for merging into a
    survey sidecar's Study block.
    """
    entry = (index.get("Instruments") or {}).get(task_name)
    if not entry:
        return {}

    version = entry.get("Version")
    if not version and variant_id:
        # No single Study.Version on file - fall back to the variant slug
        # itself, since it already appears in the sidecar filename (acq-).
        version = variant_id

    return {"Version": version, "DOI": entry.get("DOI") or None}
