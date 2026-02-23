"""Survey item registry for preventing duplicate item IDs across imports.

Ensures each survey item (question) has a unique ID across:
- The current import batch
- Existing local templates (project survey library)
- Official templates (global survey library)
"""

from __future__ import annotations

from pathlib import Path
from typing import Any
import json


def _read_json(path: Path) -> dict:
    """Simple JSON reader fallback."""
    with open(path, 'r', encoding='utf-8') as f:
        return json.load(f)


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


class ItemCollisionError(Exception):
    """Raised when an item ID collision is detected."""

    def __init__(self, message, collision_type="duplicate", existing_meta=None, new_meta=None):
        """Initialize collision error with metadata.
        
        Args:
            message: Error message
            collision_type: "duplicate", "version_candidate", or "incompatible"
            existing_meta: Metadata about existing item
            new_meta: Metadata about new item
        """
        super().__init__(message)
        self.collision_type = collision_type
        self.existing_meta = existing_meta or {}
        self.new_meta = new_meta or {}


class ItemRegistry:
    """Tracks item IDs to prevent duplicates during import.

    Typical usage:
        registry = ItemRegistry.from_libraries(local_dir, official_dir)
        registry.register_item("survey-phq9", "PHQ9_01", description="...")
        # Raises ItemCollisionError if PHQ9_01 already exists
    """

    def __init__(self):
        """Initialize empty registry."""
        # item_id -> {source_template, source_type, description}
        self._items: dict[str, dict[str, Any]] = {}

    @classmethod
    def from_libraries(
        cls, local_library: Path | None = None, official_library: Path | None = None
    ) -> ItemRegistry:
        """Create registry pre-populated with items from local + official libraries.

        Args:
            local_library: Path to project's survey library (e.g., code/library/survey)
            official_library: Path to official survey library (e.g., official/library/survey)

        Returns:
            ItemRegistry populated with all existing item IDs
        """
        registry = cls()

        # Load official library first (lower priority)
        if official_library and official_library.exists():
            registry._load_library(official_library, source_type="official")

        # Load local library second (higher priority, can override official)
        if local_library and local_library.exists():
            registry._load_library(local_library, source_type="local")

        return registry

    def _load_library(self, library_dir: Path, source_type: str):
        """Scan a library directory and register all items.

        Args:
            library_dir: Path to survey library directory
            source_type: "local", "official", or "import"
        """
        for json_path in sorted(library_dir.glob("survey-*.json")):
            # Skip participants templates
            if "participant" in json_path.stem.lower():
                continue

            try:
                sidecar = _read_json(json_path)
            except Exception:
                continue

            template_name = json_path.stem  # e.g., "survey-phq9"
            task_name = sidecar.get("Study", {}).get("TaskName") or template_name.replace(
                "survey-", ""
            )

            # Register each item key
            for item_id, item_data in sidecar.items():
                if item_id in _NON_ITEM_TOPLEVEL_KEYS:
                    continue
                if not isinstance(item_data, dict):
                    continue

                # Extract description for error messages
                desc = item_data.get("Description", "")
                if isinstance(desc, dict):
                    desc = desc.get("en") or desc.get("de") or next(iter(desc.values()), "")

                # Register (but allow local to override official)
                existing = self._items.get(item_id)
                if existing and existing["source_type"] == "official" and source_type == "local":
                    # Local override is OK
                    pass
                elif item_id not in self._items:
                    self._items[item_id] = {
                        "source_template": template_name,
                        "source_task": task_name,
                        "source_type": source_type,
                        "description": str(desc)[:100],  # Truncate for display
                    }

    def register_item(
        self,
        item_id: str,
        template_name: str,
        description: str = "",
        source_type: str = "import",
        item_data: dict = None,
    ) -> None:
        """Register a new item from an import.

        Args:
            item_id: Item identifier (e.g., "PHQ9_01")
            template_name: Template/survey name (e.g., "survey-phq9")
            description: Item description for error messages
            source_type: "import", "local", or "official"
            item_data: Full item data dict for compatibility checking (optional)

        Raises:
            ItemCollisionError: If item_id already exists
        """
        existing = self._items.get(item_id)

        if existing:
            existing_source = existing["source_type"]
            existing_template = existing["source_template"]
            existing_desc = existing["description"]

            # Check if this might be a version variant
            is_candidate = self.is_version_candidate(item_id, template_name, existing)
            
            # Build error message
            if existing_source == "import":
                msg = (
                    f"Duplicate item ID '{item_id}' in current import.\n"
                    f"  First: {existing_template} - {existing_desc}\n"
                    f"  Duplicate: {template_name} - {description}"
                )
                collision_type = "duplicate"
            elif existing_source == "local":
                if is_candidate:
                    msg = (
                        f"Item ID '{item_id}' already exists in local library.\n"
                        f"  Existing: {existing_template} ({existing_source}) - {existing_desc}\n"
                        f"  Import: {template_name} - {description}\n"
                        f"  → This looks like a version variant (e.g., short/long form).\n"
                        f"  → Consider merging as a new version."
                    )
                    collision_type = "version_candidate"
                else:
                    msg = (
                        f"Item ID '{item_id}' already exists in local library.\n"
                        f"  Existing: {existing_template} ({existing_source}) - {existing_desc}\n"
                        f"  Import: {template_name} - {description}\n"
                        f"  → Each survey item must have a globally unique ID."
                    )
                    collision_type = "duplicate"
            elif existing_source == "official":
                if is_candidate:
                    msg = (
                        f"Item ID '{item_id}' already exists in official library.\n"
                        f"  Existing: {existing_template} (official) - {existing_desc}\n"
                        f"  Import: {template_name} - {description}\n"
                        f"  → This looks like a version variant. You may be importing a different form."
                    )
                    collision_type = "version_candidate"
                else:
                    msg = (
                        f"Item ID '{item_id}' already exists in official library.\n"
                        f"  Existing: {existing_template} (official) - {existing_desc}\n"
                        f"  Import: {template_name} - {description}\n"
                        f"  → Use a different item ID or remove the conflicting local template."
                    )
                    collision_type = "duplicate"
            else:
                msg = f"Duplicate item ID '{item_id}' (source: {existing_source})"
                collision_type = "duplicate"

            raise ItemCollisionError(
                msg,
                collision_type=collision_type,
                existing_meta=existing,
                new_meta={
                    "item_id": item_id,
                    "template_name": template_name,
                    "description": description,
                    "item_data": item_data or {}
                }
            )

        # Register new item
        self._items[item_id] = {
            "source_template": template_name,
            "source_type": source_type,
            "description": description[:100],
        }

    def check_batch(self, items: dict[str, Any], template_name: str) -> list[str]:
        """Check a batch of items for collisions without registering.

        Args:
            items: Dict of item_id -> item_data
            template_name: Template name for error messages

        Returns:
            List of error messages (empty if no collisions)
        """
        errors = []
        for item_id, item_data in items.items():
            if item_id in _NON_ITEM_TOPLEVEL_KEYS:
                continue

            existing = self._items.get(item_id)
            if existing:
                # Extract description
                desc = item_data.get("Description", "")
                if isinstance(desc, dict):
                    desc = desc.get("en") or desc.get("de") or next(iter(desc.values()), "")

                existing_source = existing["source_type"]
                existing_template = existing["source_template"]
                existing_desc = existing["description"]

                errors.append(
                    f"Item '{item_id}' conflicts with {existing_source} template "
                    f"'{existing_template}': {existing_desc}"
                )

        return errors

    def get_item_count(self) -> int:
        """Return total number of registered items."""
        return len(self._items)

    def get_items_by_template(self, template_name: str) -> list[str]:
        """Get all item IDs for a specific template.

        Args:
            template_name: Template name (e.g., "survey-phq9")

        Returns:
            List of item IDs
        """
        return [
            item_id
            for item_id, meta in self._items.items()
            if meta["source_template"] == template_name
        ]

    def check_version_compatibility(
        self, item_id: str, new_item_data: dict, existing_item_data: dict
    ) -> tuple[bool, str]:
        """Check if two items with same ID are compatible as version variants.
        
        Args:
            item_id: The item identifier
            new_item_data: Item data from import
            existing_item_data: Item data from existing template
            
        Returns:
            Tuple of (is_compatible, reason)
        """
        # Extract descriptions
        def get_desc(data):
            desc = data.get("Description", "")
            if isinstance(desc, dict):
                # Get first non-empty language
                return next((v for v in desc.values() if v), "")
            return str(desc)
        
        new_desc = get_desc(new_item_data)
        existing_desc = get_desc(existing_item_data)
        
        # Normalize for comparison (strip whitespace, lowercase)
        new_desc_norm = new_desc.strip().lower()
        existing_desc_norm = existing_desc.strip().lower()
        
        if not new_desc_norm or not existing_desc_norm:
            return False, "Missing description"
        
        # Check if descriptions match (allowing for minor variations)
        if new_desc_norm != existing_desc_norm:
            # Check if one is substring of other (e.g., with/without instructions)
            if new_desc_norm not in existing_desc_norm and existing_desc_norm not in new_desc_norm:
                return False, f"Different descriptions"
        
        # Check Levels compatibility
        new_levels = new_item_data.get("Levels", {})
        existing_levels = existing_item_data.get("Levels", {})
        
        if new_levels or existing_levels:
            # Both should have levels if either does
            if bool(new_levels) != bool(existing_levels):
                return False, "One has Levels, other doesn't"
            
            # Check if level structures are compatible
            if isinstance(new_levels, dict) and isinstance(existing_levels, dict):
                # Check if keys match
                if set(new_levels.keys()) != set(existing_levels.keys()):
                    return False, "Different level values"
        
        # Items are compatible
        return True, "Compatible"

    def is_version_candidate(
        self, 
        item_id: str, 
        template_name: str, 
        existing_meta: dict
    ) -> bool:
        """Check if collision looks like a version variant scenario.
        
        Args:
            item_id: The colliding item ID
            template_name: Template being imported
            existing_meta: Metadata about existing item
            
        Returns:
            True if this looks like a version variant import
        """
        # Extract task names from template names
        # e.g., "survey-phq9" -> "phq9", "survey-bdi-short" -> "bdi-short"
        def extract_task(name):
            return name.replace("survey-", "").replace("-", "").lower()
        
        new_task = extract_task(template_name)
        existing_task = extract_task(existing_meta.get("source_template", ""))
        
        # If base task names are similar, might be version variant
        # e.g., "bdi" matches "bdi", "bdishort" matches "bdilong"
        if new_task.startswith(existing_task) or existing_task.startswith(new_task):
            return True
        
        # Also check if item ID prefix matches task
        # e.g., "BDI_01" starts with "BDI"
        item_prefix = item_id.split("_")[0].lower()
        if item_prefix in new_task and item_prefix in existing_task:
            return True
        
        return False
