"""Tests for version merger functionality."""

import pytest
from pathlib import Path
import json
import tempfile

from src.converters.version_merger import (
    merge_survey_versions,
    save_merged_template,
    detect_version_name_from_import,
)


class TestVersionMerger:
    """Test suite for survey version merging."""

    def test_merge_short_to_long(self, tmp_path):
        """Test merging a short form into an existing long form."""
        # Create existing template (short form - 5 items)
        existing = {
            "Technical": {"StimulusType": "Questionnaire"},
            "Study": {"TaskName": "test", "OriginalName": "Test Scale"},
            "Metadata": {"SchemaVersion": "1.1.1", "CreationDate": "2024-01-01"},
            "TEST_01": {"Description": "Question 1", "Levels": {"1": "No", "5": "Yes"}},
            "TEST_02": {"Description": "Question 2", "Levels": {"1": "No", "5": "Yes"}},
            "TEST_03": {"Description": "Question 3", "Levels": {"1": "No", "5": "Yes"}},
            "TEST_04": {"Description": "Question 4", "Levels": {"1": "No", "5": "Yes"}},
            "TEST_05": {"Description": "Question 5", "Levels": {"1": "No", "5": "Yes"}},
        }
        
        existing_path = tmp_path / "survey-test.json"
        existing_path.write_text(json.dumps(existing))
        
        # New items (long form - 10 items, includes all short form items)
        new_items = {
            "TEST_01": {"Description": "Question 1", "Levels": {"1": "No", "5": "Yes"}},
            "TEST_02": {"Description": "Question 2", "Levels": {"1": "No", "5": "Yes"}},
            "TEST_03": {"Description": "Question 3", "Levels": {"1": "No", "5": "Yes"}},
            "TEST_04": {"Description": "Question 4", "Levels": {"1": "No", "5": "Yes"}},
            "TEST_05": {"Description": "Question 5", "Levels": {"1": "No", "5": "Yes"}},
            "TEST_06": {"Description": "Question 6", "Levels": {"1": "No", "5": "Yes"}},
            "TEST_07": {"Description": "Question 7", "Levels": {"1": "No", "5": "Yes"}},
            "TEST_08": {"Description": "Question 8", "Levels": {"1": "No", "5": "Yes"}},
            "TEST_09": {"Description": "Question 9", "Levels": {"1": "No", "5": "Yes"}},
            "TEST_10": {"Description": "Question 10", "Levels": {"1": "No", "5": "Yes"}},
        }
        
        # Merge
        merged = merge_survey_versions(
            existing_template_path=existing_path,
            new_items=new_items,
            new_version_name="long",
            existing_version_name="short"
        )
        
        # Check Study.Versions
        assert "Versions" in merged["Study"]
        assert "short" in merged["Study"]["Versions"]
        assert "long" in merged["Study"]["Versions"]
        
        # Check item count
        assert merged["Study"]["ItemCount"] == 10
        
        # Check overlapping items have both versions
        assert "ApplicableVersions" in merged["TEST_01"]
        assert "short" in merged["TEST_01"]["ApplicableVersions"]
        assert "long" in merged["TEST_01"]["ApplicableVersions"]
        
        # Check new items have only long version
        assert "ApplicableVersions" in merged["TEST_06"]
        assert merged["TEST_06"]["ApplicableVersions"] == ["long"]
        assert "TEST_10" in merged

    def test_merge_long_to_short(self, tmp_path):
        """Test merging a long form when short exists."""
        # Create existing template (long form - 20 items)
        existing = {
            "Technical": {"StimulusType": "Questionnaire"},
            "Study": {"TaskName": "bdi", "OriginalName": "Beck Depression Inventory"},
            "Metadata": {"SchemaVersion": "1.1.1", "CreationDate": "2024-01-01"},
        }
        
        # Add 20 items
        for i in range(1, 21):
            existing[f"BDI_{i:02d}"] = {
                "Description": f"Item {i}",
                "Levels": {"0": "Not at all", "3": "Very much"}
            }
        
        existing_path = tmp_path / "survey-bdi.json"
        existing_path.write_text(json.dumps(existing))
        
        # New items (short screening - 9 items)
        new_items = {}
        for i in range(1, 10):
            new_items[f"BDI_{i:02d}"] = {
                "Description": f"Item {i}",
                "Levels": {"0": "Not at all", "3": "Very much"}
            }
        
        # Merge
        merged = merge_survey_versions(
            existing_template_path=existing_path,
            new_items=new_items,
            new_version_name="screening",
            existing_version_name="full"
        )
        
        # Check versions
        assert "screening" in merged["Study"]["Versions"]
        assert "full" in merged["Study"]["Versions"]
        
        # Check overlapping items
        assert "screening" in merged["BDI_01"]["ApplicableVersions"]
        assert "full" in merged["BDI_01"]["ApplicableVersions"]
        
        # Check items only in full version
        assert "ApplicableVersions" in merged["BDI_15"]
        assert merged["BDI_15"]["ApplicableVersions"] == ["full"]
        assert "screening" not in merged["BDI_15"]["ApplicableVersions"]

    def test_auto_version_naming(self, tmp_path):
        """Test automatic version name detection."""
        # Existing short form
        existing = {
            "Study": {"TaskName": "phq"},
            "PHQ_01": {"Description": "Q1"},
            "PHQ_02": {"Description": "Q2"},
        }
        
        existing_path = tmp_path / "survey-phq-short.json"
        existing_path.write_text(json.dumps(existing))
        
        # Import longer form
        new_items = {f"PHQ_{i:02d}": {"Description": f"Q{i}"} for i in range(1, 10)}
        
        suggested_new, suggested_existing = detect_version_name_from_import(
            new_items, existing_path
        )
        
        # Should detect short/long based on item counts and filename
        assert suggested_new == "long"
        assert suggested_existing == "short"

    def test_preserve_existing_metadata(self, tmp_path):
        """Test that merging preserves all existing metadata."""
        # Create existing with rich metadata
        existing = {
            "Technical": {
                "StimulusType": "Questionnaire",
                "FileFormat": "tsv",
                "Language": "en",
            },
            "Study": {
                "TaskName": "test",
                "OriginalName": "Test Scale",
                "Authors": ["Smith, J.", "Doe, J."],
                "Citation": "Smith et al. 2020",
                "DOI": "10.1234/test",
                "LicenseID": "CC-BY-4.0",
            },
            "Metadata": {"SchemaVersion": "1.1.1", "CreationDate": "2024-01-01"},
            "TEST_01": {"Description": "Q1"},
        }
        
        existing_path = tmp_path / "survey-test.json"
        existing_path.write_text(json.dumps(existing))
        
        # Merge with new items
        new_items = {
            "TEST_01": {"Description": "Q1"},
            "TEST_02": {"Description": "Q2"},
        }
        
        merged = merge_survey_versions(
            existing_template_path=existing_path,
            new_items=new_items,
            new_version_name="extended"
        )
        
        # Check all metadata preserved
        assert merged["Study"]["Authors"] == ["Smith, J.", "Doe, J."]
        assert merged["Study"]["DOI"] == "10.1234/test"
        assert merged["Technical"]["Language"] == "en"

    def test_save_merged_template(self, tmp_path):
        """Test saving a merged template."""
        template = {
            "Study": {
                "TaskName": "test",
                "Versions": ["v1", "v2"]
            },
            "TEST_01": {
                "Description": "Question 1",
                "ApplicableVersions": ["v1", "v2"]
            }
        }
        
        output_path = tmp_path / "merged.json"
        save_merged_template(template, output_path)
        
        # Verify saved correctly
        assert output_path.exists()
        loaded = json.loads(output_path.read_text())
        assert loaded["Study"]["Versions"] == ["v1", "v2"]
        assert "v1" in loaded["TEST_01"]["ApplicableVersions"]
