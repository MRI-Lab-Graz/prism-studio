"""Version merger for handling multiple forms of the same instrument.

Allows importing different versions (short/long, screening/full) of the same
survey without item ID collisions by adding version metadata.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any
import json

_NON_ITEM_TOPLEVEL_KEYS = {
    "Technical",
    "Study",
    "Metadata",
    "Normative",
    "Scoring",
    "I18n",
    "LimeSurvey",
    "_aliases",
    "_reverse_aliases",
    "_prismmeta",
}


def merge_survey_versions(
    existing_template_path: Path,
    new_items: dict[str, Any],
    new_version_name: str,
    existing_version_name: str = None,
) -> dict[str, Any]:
    """Merge a new version into an existing survey template.

    Args:
        existing_template_path: Path to existing template JSON
        new_items: Dict of new item_id -> item_data to merge
        new_version_name: Name for the new version (e.g., "long", "extended")
        existing_version_name: Name for existing version (auto-detect if None)

    Returns:
        Updated template dict with version metadata
    """
    # Load existing template
    with open(existing_template_path, "r", encoding="utf-8") as f:
        template = json.load(f)

    # Get existing items
    existing_items = {
        k: v
        for k, v in template.items()
        if k not in _NON_ITEM_TOPLEVEL_KEYS and isinstance(v, dict)
    }

    # Determine existing version name
    if existing_version_name is None:
        # Try to infer from Study.Version or filename
        existing_version_name = template.get("Study", {}).get("Version", "")
        if isinstance(existing_version_name, dict):
            existing_version_name = existing_version_name.get("en", "")
        if not existing_version_name:
            # Default based on item count
            existing_version_name = f"{len(existing_items)}-item"

    # Initialize Versions array in Study section if not present
    if "Study" not in template:
        template["Study"] = {}

    versions_list = template["Study"].get("Versions", [])
    if not isinstance(versions_list, list):
        versions_list = []

    # Add existing version if not already there
    if existing_version_name and existing_version_name not in versions_list:
        versions_list.append(existing_version_name)

    # Add new version
    if new_version_name not in versions_list:
        versions_list.append(new_version_name)

    template["Study"]["Versions"] = versions_list

    # Identify overlapping vs new items
    new_item_ids = set(new_items.keys())
    existing_item_ids = set(existing_items.keys())
    overlapping_ids = new_item_ids & existing_item_ids
    new_only_ids = new_item_ids - existing_item_ids

    print("\n[PRISM] Version merge summary:")
    print(
        f"  Existing version: '{existing_version_name}' ({len(existing_item_ids)} items)"
    )
    print(f"  New version: '{new_version_name}' ({len(new_item_ids)} items)")
    print(f"  Overlapping: {len(overlapping_ids)} items")
    print(f"  New items: {len(new_only_ids)} items")

    # Update existing items with version info
    for item_id in existing_items:
        item = template[item_id]

        # Add ApplicableVersions
        applicable_versions = item.get("ApplicableVersions", [])
        if not isinstance(applicable_versions, list):
            applicable_versions = []

        # Add existing version if not there
        if existing_version_name and existing_version_name not in applicable_versions:
            applicable_versions.append(existing_version_name)

        # If this item is also in new version, add that too
        if item_id in overlapping_ids:
            if new_version_name not in applicable_versions:
                applicable_versions.append(new_version_name)

        item["ApplicableVersions"] = applicable_versions
        template[item_id] = item

    # Add new items
    for item_id in new_only_ids:
        new_item = new_items[item_id].copy()

        # Set ApplicableVersions for new items
        new_item["ApplicableVersions"] = [new_version_name]

        template[item_id] = new_item

    # Update Study.ItemCount to reflect total
    total_items = len(existing_item_ids | new_item_ids)
    if "Study" in template:
        template["Study"]["ItemCount"] = total_items

    return template


def save_merged_template(template: dict[str, Any], output_path: Path) -> None:
    """Save a merged template to disk.

    Args:
        template: Template dict with version metadata
        output_path: Where to save the JSON file
    """
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(template, f, indent=2, ensure_ascii=False)

    print(f"[PRISM] Saved merged template to {output_path}")


def detect_version_name_from_import(
    import_items: dict[str, Any], existing_template_path: Path
) -> tuple[str, str]:
    """Auto-detect likely version names from import context.

    Args:
        import_items: Items being imported
        existing_template_path: Path to existing template

    Returns:
        Tuple of (suggested_new_version, suggested_existing_version)
    """
    # Load existing
    with open(existing_template_path, "r", encoding="utf-8") as f:
        existing = json.load(f)

    existing_items = {
        k: v
        for k, v in existing.items()
        if k not in _NON_ITEM_TOPLEVEL_KEYS and isinstance(v, dict)
    }

    existing_count = len(existing_items)
    new_count = len(import_items)

    # Heuristics for version naming
    if new_count > existing_count:
        suggested_new = "long"
        suggested_existing = "short"
    elif new_count < existing_count:
        suggested_new = "short"
        suggested_existing = "long"
    else:
        # Same count - might be different forms
        suggested_new = "form-b"
        suggested_existing = "form-a"

    # Check filename for hints
    filename = existing_template_path.stem.lower()
    if "short" in filename:
        suggested_existing = "short"
        suggested_new = "long"
    elif "long" in filename:
        suggested_existing = "long"
        suggested_new = "short"
    elif "screening" in filename or "screen" in filename:
        suggested_existing = "screening"
        suggested_new = "full"

    return suggested_new, suggested_existing
