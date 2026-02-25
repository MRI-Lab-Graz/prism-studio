"""Tests for item registry (collision detection during import)."""

import pytest
import json

from src.converters.item_registry import ItemRegistry, ItemCollisionError


class TestItemRegistry:
    """Test suite for ItemRegistry collision detection."""

    def test_empty_registry(self):
        """Test creating an empty registry."""
        registry = ItemRegistry()
        assert registry.get_item_count() == 0

    def test_register_single_item(self):
        """Test registering a single item."""
        registry = ItemRegistry()
        registry.register_item(
            item_id="PHQ9_01",
            template_name="survey-phq9",
            description="Little interest or pleasure",
        )
        assert registry.get_item_count() == 1

    def test_duplicate_in_import_raises_error(self):
        """Test that duplicate item IDs in the same import raise an error."""
        registry = ItemRegistry()

        # First registration succeeds
        registry.register_item(
            item_id="PHQ9_01",
            template_name="survey-phq9",
            description="Little interest or pleasure",
        )

        # Duplicate should fail
        with pytest.raises(ItemCollisionError) as exc_info:
            registry.register_item(
                item_id="PHQ9_01",
                template_name="survey-phq9",
                description="Duplicate question",
            )

        assert "Duplicate item ID 'PHQ9_01'" in str(exc_info.value)

    def test_load_from_libraries(self, tmp_path):
        """Test loading items from local and official libraries."""
        # Create mock local library
        local_lib = tmp_path / "local" / "survey"
        local_lib.mkdir(parents=True)

        local_template = {
            "Technical": {"StimulusType": "Questionnaire"},
            "Study": {"TaskName": "phq9", "OriginalName": "PHQ-9"},
            "Metadata": {"SchemaVersion": "1.1.1", "CreationDate": "2024-01-01"},
            "PHQ9_01": {"Description": "Little interest"},
            "PHQ9_02": {"Description": "Feeling down"},
        }

        (local_lib / "survey-phq9.json").write_text(json.dumps(local_template))

        # Create mock official library
        official_lib = tmp_path / "official" / "survey"
        official_lib.mkdir(parents=True)

        official_template = {
            "Technical": {"StimulusType": "Questionnaire"},
            "Study": {"TaskName": "gad7", "OriginalName": "GAD-7"},
            "Metadata": {"SchemaVersion": "1.1.1", "CreationDate": "2024-01-01"},
            "GAD7_01": {"Description": "Feeling nervous"},
            "GAD7_02": {"Description": "Unable to stop worrying"},
        }

        (official_lib / "survey-gad7.json").write_text(json.dumps(official_template))

        # Load registry
        registry = ItemRegistry.from_libraries(
            local_library=local_lib, official_library=official_lib
        )

        # Should have 4 items (2 from local, 2 from official)
        assert registry.get_item_count() == 4

    def test_collision_with_local_library(self, tmp_path):
        """Test that importing an item that exists in local library raises error."""
        # Create mock local library
        local_lib = tmp_path / "local" / "survey"
        local_lib.mkdir(parents=True)

        local_template = {
            "Technical": {"StimulusType": "Questionnaire"},
            "Study": {"TaskName": "phq9", "OriginalName": "PHQ-9"},
            "Metadata": {"SchemaVersion": "1.1.1", "CreationDate": "2024-01-01"},
            "PHQ9_01": {"Description": "Little interest"},
        }

        (local_lib / "survey-phq9.json").write_text(json.dumps(local_template))

        # Load registry
        registry = ItemRegistry.from_libraries(local_library=local_lib)

        # Try to import duplicate
        with pytest.raises(ItemCollisionError) as exc_info:
            registry.register_item(
                item_id="PHQ9_01",
                template_name="survey-phq9-new",
                description="Duplicate from import",
            )

        assert "already exists in local library" in str(exc_info.value)

    def test_collision_with_official_library(self, tmp_path):
        """Test that importing an item that exists in official library raises error."""
        # Create mock official library
        official_lib = tmp_path / "official" / "survey"
        official_lib.mkdir(parents=True)

        official_template = {
            "Technical": {"StimulusType": "Questionnaire"},
            "Study": {"TaskName": "gad7", "OriginalName": "GAD-7"},
            "Metadata": {"SchemaVersion": "1.1.1", "CreationDate": "2024-01-01"},
            "GAD7_01": {"Description": {"en": "Feeling nervous"}},
        }

        (official_lib / "survey-gad7.json").write_text(json.dumps(official_template))

        # Load registry
        registry = ItemRegistry.from_libraries(official_library=official_lib)

        # Try to import duplicate
        with pytest.raises(ItemCollisionError) as exc_info:
            registry.register_item(
                item_id="GAD7_01",
                template_name="survey-gad7-custom",
                description="Custom version",
            )

        assert "already exists in official library" in str(exc_info.value)

    def test_local_overrides_official(self, tmp_path):
        """Test that local library items take precedence over official."""
        # Create both libraries with same item ID
        local_lib = tmp_path / "local" / "survey"
        local_lib.mkdir(parents=True)

        local_template = {
            "Technical": {"StimulusType": "Questionnaire"},
            "Study": {"TaskName": "phq9", "OriginalName": "PHQ-9"},
            "Metadata": {"SchemaVersion": "1.1.1", "CreationDate": "2024-01-01"},
            "PHQ9_01": {"Description": "Local version"},
        }

        (local_lib / "survey-phq9.json").write_text(json.dumps(local_template))

        official_lib = tmp_path / "official" / "survey"
        official_lib.mkdir(parents=True)

        official_template = {
            "Technical": {"StimulusType": "Questionnaire"},
            "Study": {"TaskName": "phq9", "OriginalName": "PHQ-9 Official"},
            "Metadata": {"SchemaVersion": "1.1.1", "CreationDate": "2024-01-01"},
            "PHQ9_01": {"Description": "Official version"},
        }

        (official_lib / "survey-phq9.json").write_text(json.dumps(official_template))

        # Load registry (official first, then local)
        registry = ItemRegistry.from_libraries(
            local_library=local_lib, official_library=official_lib
        )

        # Should have 1 item (local overrides official)
        assert registry.get_item_count() == 1

        # Trying to import PHQ9_01 should still fail (local exists)
        with pytest.raises(ItemCollisionError):
            registry.register_item(
                item_id="PHQ9_01",
                template_name="survey-import",
                description="Import attempt",
            )

    def test_check_batch(self):
        """Test batch checking without registration."""
        registry = ItemRegistry()
        registry.register_item(
            item_id="PHQ9_01", template_name="survey-phq9", description="Existing item"
        )

        # Check a batch with one collision
        batch = {
            "PHQ9_01": {"Description": "Collision"},
            "PHQ9_02": {"Description": "New item"},
            "Study": {"TaskName": "phq9"},  # Should be ignored
        }

        errors = registry.check_batch(batch, template_name="survey-import")

        # Should have 1 error for PHQ9_01
        assert len(errors) == 1
        assert "PHQ9_01" in errors[0]

    def test_get_items_by_template(self):
        """Test retrieving items for a specific template."""
        registry = ItemRegistry()
        registry.register_item("PHQ9_01", "survey-phq9", "Q1")
        registry.register_item("PHQ9_02", "survey-phq9", "Q2")
        registry.register_item("GAD7_01", "survey-gad7", "Q1")

        phq9_items = registry.get_items_by_template("survey-phq9")
        assert len(phq9_items) == 2
        assert "PHQ9_01" in phq9_items
        assert "PHQ9_02" in phq9_items

        gad7_items = registry.get_items_by_template("survey-gad7")
        assert len(gad7_items) == 1
        assert "GAD7_01" in gad7_items
