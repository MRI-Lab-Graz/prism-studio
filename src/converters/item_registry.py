"""Survey item registry for preventing duplicate item IDs across imports.

Ensures each survey item (question) has a unique ID across:
- The current import batch
- Existing local templates (project survey library)
- Official templates (global survey library)
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from src.utils.io import read_json as _read_json

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

    def __init__(
        self, message, collision_type="duplicate", existing_meta=None, new_meta=None
    ):
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

    def __init__(self) -> None:
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
            task_name = sidecar.get("Study", {}).get(
                "TaskName"
            ) or template_name.replace("survey-", "")

            # Register each item key
            for item_id, item_data in sidecar.items():
                if item_id in _NON_ITEM_TOPLEVEL_KEYS:
                    continue
                if not isinstance(item_data, dict):
                    continue

                # Extract description for error messages
                desc = item_data.get("Description", "")
                if isinstance(desc, dict):
                    desc = (
                        desc.get("en")
                        or desc.get("de")
                        or next(iter(desc.values()), "")
                    )

                # Register (but allow local to override official)
                existing = self._items.get(item_id)
                if (
                    existing
                    and existing["source_type"] == "official"
                    and source_type == "local"
                ):
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
        item_data: dict | None = None,
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
                    "item_data": item_data or {},
                },
            )

        # Register new item
        self._items[item_id] = {
            "source_template": template_name,
            "source_type": source_type,
            "description": description[:100],
        }

    def get_item_count(self) -> int:
        """Return total number of registered items."""
        return len(self._items)

    def is_version_candidate(
        self, item_id: str, template_name: str, existing_meta: dict
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
