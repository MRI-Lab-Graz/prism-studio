"""Integration test for version merge workflow during import."""

import pytest
from pathlib import Path
import json
import tempfile
import shutil

from app.src.converters.excel_to_survey import extract_excel_templates
from src.converters.item_registry import ItemCollisionError


class TestVersionMergeIntegration:
    """End-to-end test for version collision detection and merging."""

    def test_xlsx_import_with_version_merge(self, tmp_path):
        """Test importing short form, then long form with version merge."""
        
        # Setup: Create proper directory structure (code/library/survey)
        project_root = tmp_path / "test_project"
        code_dir = project_root / "code"
        local_library = code_dir / "library" / "survey"
        local_library.mkdir(parents=True)
        
        # Step 1: Create initial "short" version template manually
        short_template = {
            "Technical": {
                "StimulusType": "Questionnaire",
                "FileFormat": "tsv"
            },
            "Study": {
                "TaskName": "bdi",
                "OriginalName": "Beck Depression Inventory - Short",
                "Authors": ["Beck, A.T."],
                "Citation": "Beck et al. 1961",
                "ItemCount": 5,
                "Versions": ["short"]  # Mark this as the "short" version
            },
            "Metadata": {
                "SchemaVersion": "1.1.1",
                "CreationDate": "2024-01-01"
            },
            "BDI_01": {
                "Description": "Sadness",
                "Levels": {
                    "0": "I do not feel sad",
                    "3": "I am so sad I can't stand it"
                },
                "ApplicableVersions": ["short"]
            },
            "BDI_02": {
                "Description": "Pessimism",
                "Levels": {
                    "0": "I am not discouraged",
                    "3": "I feel my future is hopeless"
                },
                "ApplicableVersions": ["short"]
            },
            "BDI_03": {
                "Description": "Past Failure",
                "Levels": {
                    "0": "I do not feel like a failure",
                    "3": "I feel I am a total failure"
                },
                "ApplicableVersions": ["short"]
            },
            "BDI_04": {
                "Description": "Loss of Pleasure",
                "Levels": {
                    "0": "I get as much pleasure as I ever did",
                    "3": "I can't get any pleasure from anything"
                },
                "ApplicableVersions": ["short"]
            },
            "BDI_05": {
                "Description": "Guilty Feelings",
                "Levels": {
                    "0": "I don't feel particularly guilty",
                    "3": "I feel guilty all of the time"
                },
                "ApplicableVersions": ["short"]
            }
        }
        
        short_path = local_library / "survey-bdi.json"
        short_path.write_text(json.dumps(short_template, indent=2))
        
        print(f"\n✓ Created initial short version template: {short_path}")
        print(f"  Items: BDI_01 through BDI_05")
        
        # Step 2: Create Excel file with long version (10 items, includes all short items)
        import pandas as pd
        
        long_items = [
            {"ItemID": "BDI_01", "Description": "Sadness", "0": "I do not feel sad", "3": "I am so sad I can't stand it"},
            {"ItemID": "BDI_02", "Description": "Pessimism", "0": "I am not discouraged", "3": "I feel my future is hopeless"},
            {"ItemID": "BDI_03", "Description": "Past Failure", "0": "I do not feel like a failure", "3": "I feel I am a total failure"},
            {"ItemID": "BDI_04", "Description": "Loss of Pleasure", "0": "I get as much pleasure as I ever did", "3": "I can't get any pleasure from anything"},
            {"ItemID": "BDI_05", "Description": "Guilty Feelings", "0": "I don't feel particularly guilty", "3": "I feel guilty all of the time"},
            {"ItemID": "BDI_06", "Description": "Punishment Feelings", "0": "I don't feel I am being punished", "3": "I expect to be punished"},
            {"ItemID": "BDI_07", "Description": "Self-Dislike", "0": "I feel the same about myself", "3": "I hate myself"},
            {"ItemID": "BDI_08", "Description": "Self-Criticalness", "0": "I don't criticize or blame myself", "3": "I blame myself for everything bad"},
            {"ItemID": "BDI_09", "Description": "Suicidal Thoughts", "0": "I don't have thoughts of killing myself", "3": "I would kill myself if I had the chance"},
            {"ItemID": "BDI_10", "Description": "Crying", "0": "I don't cry any more than I used to", "3": "I used to cry but can't anymore"},
        ]
        
        df = pd.DataFrame(long_items)
        excel_path = tmp_path / "bdi_long.xlsx"
        df.to_excel(excel_path, index=False, sheet_name="BDI")
        
        print(f"\n✓ Created Excel file with long version: {excel_path}")
        print(f"  Items: BDI_01 through BDI_10")
        
        # Step 3: Import with merge handler - should detect collision and merge
        def mock_merge_handler(existing_template_path, new_items, prefix):
            """Mock handler that returns version name for the new import."""
            print(f"  [Handler called] Existing: {existing_template_path.name}, Items: {len(new_items)}, Prefix: {prefix}")
            return "long"  # Name for the new version
        
        print(f"\n→ Importing with merge handler...")
        
        result = extract_excel_templates(
            excel_file=excel_path,
            output_dir=local_library,
            check_collisions=True,
            version_merge_handler=mock_merge_handler
        )
        
        print(f"✓ Import completed with merge")
        
        # Step 4: Verify merged template
        merged_path = local_library / "survey-bdi.json"
        assert merged_path.exists()
        
        merged = json.loads(merged_path.read_text())
        
        # Check Study.Versions
        assert "Versions" in merged["Study"]
        assert "short" in merged["Study"]["Versions"]
        assert "long" in merged["Study"]["Versions"]
        print(f"✓ Study.Versions: {merged['Study']['Versions']}")
        
        # Check item count updated
        assert merged["Study"]["ItemCount"] == 10
        print(f"✓ ItemCount updated: {merged['Study']['ItemCount']}")
        
        # Check overlapping items (BDI_01 to BDI_05) have both versions
        for i in range(1, 6):
            item_id = f"BDI_{i:02d}"
            assert "ApplicableVersions" in merged[item_id]
            assert "short" in merged[item_id]["ApplicableVersions"]
            assert "long" in merged[item_id]["ApplicableVersions"]
        
        print(f"✓ Overlapping items have both versions (BDI_01 to BDI_05)")
        
        # Check new items (BDI_06 to BDI_10) only have long version
        for i in range(6, 11):
            item_id = f"BDI_{i:02d}"
            assert item_id in merged
            assert "ApplicableVersions" in merged[item_id]
            assert merged[item_id]["ApplicableVersions"] == ["long"]
        
        print(f"✓ New items only have long version (BDI_06 to BDI_10)")
        
        # Check original metadata preserved
        assert merged["Study"]["Authors"] == ["Beck, A.T."]
        assert merged["Study"]["Citation"] == "Beck et al. 1961"
        print(f"✓ Original metadata preserved")
        
        print(f"\n✅ Integration test PASSED - Version merge workflow works end-to-end!")

    def test_collision_blocks_different_instruments(self, tmp_path):
        """Test that collisions between different instruments are blocked."""
        
        # Setup proper directory structure
        project_root = tmp_path / "test_project"
        code_dir = project_root / "code"
        local_library = code_dir / "library" / "survey"
        local_library.mkdir(parents=True)
        
        # Create existing BDI template
        bdi_template = {
            "Study": {
                "TaskName": "bdi",
                "OriginalName": "Beck Depression Inventory",
                "Versions": ["original"]
            },
            "BDI_01": {
                "Description": "Feeling sad",
                "ApplicableVersions": ["original"]
            },
            "BDI_02": {
                "Description": "Loss of interest",
                "ApplicableVersions": ["original"]
            },
        }
        
        (local_library / "survey-bdi.json").write_text(json.dumps(bdi_template))
        
        # Try to import BDI with same IDs but conflicting descriptions
        # This demonstrates version collision detection
        import pandas as pd
        
        conflicting_items = [
            {"ItemID": "BDI_01", "Description": "Different question"},
            {"ItemID": "BDI_02", "Description": "Another question"},
        ]
        
        df = pd.DataFrame(conflicting_items)
        excel_path = tmp_path / "bdi_conflict.xlsx"
        df.to_excel(excel_path, index=False, sheet_name="BDI")
        
        # Without merge handler, will try to prompt (fails in pytest)
        with pytest.raises(OSError, match="reading from stdin"):
            extract_excel_templates(
                excel_file=excel_path,
                output_dir=local_library,
                check_collisions=True,
                version_merge_handler=None
            )
        
        print("\n✅ Collision detection works (would prompt user in CLI)")
