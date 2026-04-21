"""Tests for src/converters/item_registry.py — survey item ID deduplication."""

import json
import sys
import os
import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from src.converters.item_registry import ItemRegistry, ItemCollisionError


# ---------------------------------------------------------------------------
# Basic registration
# ---------------------------------------------------------------------------

class TestItemRegistryBasic:
    def test_empty_registry(self):
        reg = ItemRegistry()
        assert reg.get_item_count() == 0

    def test_register_item(self):
        reg = ItemRegistry()
        reg.register_item("PHQ9_01", "survey-phq9", description="Feeling down")
        assert reg.get_item_count() == 1

    def test_duplicate_raises(self):
        reg = ItemRegistry()
        reg.register_item("PHQ9_01", "survey-phq9")
        with pytest.raises(ItemCollisionError) as exc_info:
            reg.register_item("PHQ9_01", "survey-phq9-v2")
        assert exc_info.value.collision_type == "duplicate"

    def test_get_items_by_template(self):
        reg = ItemRegistry()
        reg.register_item("PHQ9_01", "survey-phq9")
        reg.register_item("PHQ9_02", "survey-phq9")
        reg.register_item("GAD7_01", "survey-gad7")
        result = reg.get_items_by_template("survey-phq9")
        assert set(result) == {"PHQ9_01", "PHQ9_02"}


# ---------------------------------------------------------------------------
# Collision types
# ---------------------------------------------------------------------------

class TestItemCollisionTypes:
    def test_local_collision_duplicate(self):
        reg = ItemRegistry()
        reg._items["PHQ9_01"] = {
            "source_template": "survey-phq9",
            "source_task": "phq9",
            "source_type": "local",
            "description": "Old",
        }
        with pytest.raises(ItemCollisionError) as exc_info:
            reg.register_item("PHQ9_01", "survey-phq9-new", description="New")
        # Non-version-candidate → duplicate
        assert exc_info.value.collision_type in ("duplicate", "version_candidate")

    def test_version_candidate_detected(self):
        reg = ItemRegistry()
        reg._items["PHQ9_01"] = {
            "source_template": "survey-phq9",
            "source_task": "phq9",
            "source_type": "local",
            "description": "Old",
        }
        with pytest.raises(ItemCollisionError) as exc_info:
            # Same base task name → version candidate
            reg.register_item("PHQ9_01", "survey-phq9short", description="Short")
        assert exc_info.value.collision_type == "version_candidate"

    def test_official_collision_raises(self):
        reg = ItemRegistry()
        reg._items["PHQ9_01"] = {
            "source_template": "survey-phq9",
            "source_task": "phq9",
            "source_type": "official",
            "description": "Official",
        }
        with pytest.raises(ItemCollisionError):
            reg.register_item("PHQ9_01", "survey-phq9-local", description="Local")

    def test_collision_error_has_meta(self):
        reg = ItemRegistry()
        reg.register_item("X_01", "survey-x")
        with pytest.raises(ItemCollisionError) as exc_info:
            reg.register_item("X_01", "survey-x2")
        err = exc_info.value
        assert err.existing_meta
        assert err.new_meta


# ---------------------------------------------------------------------------
# from_libraries
# ---------------------------------------------------------------------------

class TestFromLibraries:
    def _make_survey(self, path, name, items):
        data = {
            "Study": {"TaskName": name},
            **{item_id: {"Description": f"Question {item_id}"} for item_id in items},
        }
        path.write_text(json.dumps(data))

    def test_loads_official_library(self, tmp_path):
        lib = tmp_path / "official"
        lib.mkdir()
        self._make_survey(lib / "survey-phq9.json", "phq9", ["PHQ9_01", "PHQ9_02"])
        reg = ItemRegistry.from_libraries(official_library=lib)
        assert reg.get_item_count() == 2

    def test_loads_local_library(self, tmp_path):
        lib = tmp_path / "local"
        lib.mkdir()
        self._make_survey(lib / "survey-gad7.json", "gad7", ["GAD7_01"])
        reg = ItemRegistry.from_libraries(local_library=lib)
        assert reg.get_item_count() == 1

    def test_local_overrides_official(self, tmp_path):
        official = tmp_path / "official"
        official.mkdir()
        local = tmp_path / "local"
        local.mkdir()
        self._make_survey(official / "survey-phq9.json", "phq9", ["PHQ9_01"])
        self._make_survey(local / "survey-phq9.json", "phq9", ["PHQ9_01"])
        # Should not raise — local overrides official
        reg = ItemRegistry.from_libraries(local_library=local, official_library=official)
        assert reg.get_item_count() == 1

    def test_missing_paths_empty(self):
        reg = ItemRegistry.from_libraries()
        assert reg.get_item_count() == 0

    def test_participants_template_skipped(self, tmp_path):
        lib = tmp_path / "lib"
        lib.mkdir()
        self._make_survey(lib / "survey-participants.json", "participants", ["P_01"])
        reg = ItemRegistry.from_libraries(local_library=lib)
        assert reg.get_item_count() == 0


# ---------------------------------------------------------------------------
# check_batch
# ---------------------------------------------------------------------------

class TestCheckBatch:
    def test_no_collision(self):
        reg = ItemRegistry()
        reg.register_item("A_01", "survey-a")
        errors = reg.check_batch({"B_01": {"Description": "new"}}, "survey-b")
        assert errors == []

    def test_collision_returns_error(self):
        reg = ItemRegistry()
        reg.register_item("A_01", "survey-a")
        errors = reg.check_batch({"A_01": {"Description": "duplicate"}}, "survey-b")
        assert len(errors) == 1
        assert "A_01" in errors[0]

    def test_non_item_keys_skipped(self):
        reg = ItemRegistry()
        errors = reg.check_batch({"Technical": {"x": 1}, "Scoring": {}}, "survey-a")
        assert errors == []


# ---------------------------------------------------------------------------
# check_version_compatibility
# ---------------------------------------------------------------------------

class TestCheckVersionCompatibility:
    def test_same_description_compatible(self):
        reg = ItemRegistry()
        compatible, reason = reg.check_version_compatibility(
            "Q1",
            {"Description": "How are you?", "Levels": {"1": "Bad", "2": "Good"}},
            {"Description": "How are you?", "Levels": {"1": "Bad", "2": "Good"}},
        )
        assert compatible is True

    def test_different_descriptions_incompatible(self):
        reg = ItemRegistry()
        compatible, _ = reg.check_version_compatibility(
            "Q1",
            {"Description": "Question A"},
            {"Description": "Question B"},
        )
        assert compatible is False

    def test_missing_description_incompatible(self):
        reg = ItemRegistry()
        compatible, reason = reg.check_version_compatibility("Q1", {}, {})
        assert compatible is False

    def test_different_levels_incompatible(self):
        reg = ItemRegistry()
        compatible, _ = reg.check_version_compatibility(
            "Q1",
            {"Description": "same", "Levels": {"1": "a", "2": "b"}},
            {"Description": "same", "Levels": {"1": "a", "3": "c"}},
        )
        assert compatible is False


# ---------------------------------------------------------------------------
# _load_library_items - malformed JSON skipped (lines 109-110)
# ---------------------------------------------------------------------------

class TestLoadLibraryMalformedJson:
    def test_malformed_json_file_is_skipped(self, tmp_path):
        """Lines 109-110: Exception when reading a JSON file → item skipped."""
        lib_dir = tmp_path / "library"
        lib_dir.mkdir()
        bad = lib_dir / "survey-bad.json"
        bad.write_bytes(b"NOT JSON")
        # ItemRegistry.from_libraries should not raise even with malformed JSON
        reg = ItemRegistry.from_libraries(local_library=lib_dir)
        assert reg.get_item_count() == 0

    def test_non_dict_item_is_skipped(self, tmp_path):
        """Line 122: item_data that is not a dict should be skipped."""
        import json
        lib_dir = tmp_path / "library"
        lib_dir.mkdir()
        # A survey JSON with a top-level key that has a non-dict value
        sidecar = {"Study": {"TaskName": "test"}, "Q1": "not a dict", "Q2": {"Description": "ok"}}
        (lib_dir / "survey-test.json").write_text(json.dumps(sidecar))
        reg = ItemRegistry.from_libraries(local_library=lib_dir)
        # Q1 should be skipped, Q2 should be registered
        items = reg.get_items_by_template("survey-test")
        assert "Q2" in items
        assert "Q1" not in items


# ---------------------------------------------------------------------------
# Collision with local library (lines 199-205)
# ---------------------------------------------------------------------------

class TestLocalLibraryCollision:
    def test_local_duplicate_raises_collision_error(self, tmp_path):
        """Lines 199-205: duplicate collision with local library item."""
        import json
        from src.converters.item_registry import ItemCollisionError
        lib_dir = tmp_path / "library"
        lib_dir.mkdir()
        sidecar = {"Study": {"TaskName": "existing"}, "Q1": {"Description": "A question"}}
        (lib_dir / "survey-existing.json").write_text(json.dumps(sidecar))
        reg = ItemRegistry.from_libraries(local_library=lib_dir)
        # Registering the same Q1 from a different template should raise
        with pytest.raises(ItemCollisionError):
            reg.register_item("Q1", "survey-new", "A question", {"Description": "A question"})
