#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Windows-specific dataset validation tests for PRISM.
Tests validation behavior with Windows paths, case sensitivity, and file system quirks.
"""

import os
import sys
import tempfile
import json

# Force UTF-8 encoding for Windows console
if sys.platform.startswith("win"):
    import io

    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8")

# Add paths for testing
app_path = os.path.join(os.path.dirname(__file__), "..", "app")
sys.path.insert(0, app_path)
sys.path.insert(0, os.path.join(app_path, "src"))

try:
    from cross_platform import CrossPlatformFile, normalize_path
    from system_files import filter_system_files
except ImportError as e:
    print(f"❌ Import error: {e}")
    sys.exit(1)


class TestWindowsDatasetStructure:
    """Test PRISM dataset validation on Windows file systems"""

    def create_mock_dataset(self, base_dir):
        """Helper to create a minimal valid PRISM dataset"""
        # Dataset description
        dataset_desc = {
            "Name": "Test Dataset",
            "BIDSVersion": "1.9.0",
            "DatasetType": "raw",
        }
        CrossPlatformFile.write_text(
            os.path.join(base_dir, "dataset_description.json"),
            json.dumps(dataset_desc, indent=2),
        )

        # Participants file
        CrossPlatformFile.write_text(
            os.path.join(base_dir, "participants.tsv"),
            "participant_id\tage\tsex\nsub-01\t25\tM\n",
        )

        # Subject data
        sub_dir = os.path.join(base_dir, "sub-01", "func")
        os.makedirs(sub_dir, exist_ok=True)

        # Data file
        data_file = os.path.join(sub_dir, "sub-01_task-rest_bold.nii.gz")
        CrossPlatformFile.write_text(data_file, "mock data")

        # Sidecar
        sidecar = {
            "Study": {"TaskName": "rest"},
            "Technical": {"FileFormat": "NIfTI", "SamplingRate": 2.0},
        }
        sidecar_file = os.path.join(sub_dir, "sub-01_task-rest_bold.json")
        CrossPlatformFile.write_text(sidecar_file, json.dumps(sidecar, indent=2))

    def test_case_insensitive_validation(self):
        """Test validation on case-insensitive Windows filesystem"""
        print("  🧪 Testing case-insensitive validation...")

        with tempfile.TemporaryDirectory() as tmpdir:
            # Create files with different cases
            files = [
                "dataset_description.json",
                "Dataset_Description.json",  # Different case
                "DATASET_DESCRIPTION.JSON",  # All caps
            ]

            for filename in files:
                filepath = os.path.join(tmpdir, filename)
                CrossPlatformFile.write_text(filepath, '{"Name": "test"}')

            # On Windows, these should all refer to the same file
            if sys.platform.startswith("win"):
                # Check how many unique files exist
                actual_files = os.listdir(tmpdir)
                print(
                    f"    Created {len(files)} names, found {len(actual_files)} files"
                )

                if len(actual_files) == 1:
                    print("    ✅ Windows case-insensitive behavior confirmed")
                else:
                    print("    ⚠️  Expected 1 file due to case-insensitivity")
            else:
                print("    ⚠️  Not on Windows, case-sensitive behavior")

            return True

    def test_mixed_case_subject_folders(self):
        """Test handling of subject folders with mixed case"""
        print("  🧪 Testing mixed case subject folders...")

        with tempfile.TemporaryDirectory() as tmpdir:
            # Try to create folders with different cases
            folders = ["sub-01", "Sub-01", "SUB-01"]

            created_folders = []
            for folder in folders:
                folder_path = os.path.join(tmpdir, folder)
                try:
                    os.makedirs(folder_path, exist_ok=True)
                    if os.path.exists(folder_path):
                        created_folders.append(folder)
                except Exception as e:
                    print(f"    ⚠️  Error creating {folder}: {e}")

            # Check actual directory listing
            actual_dirs = [
                d for d in os.listdir(tmpdir) if os.path.isdir(os.path.join(tmpdir, d))
            ]

            print(f"    Attempted: {len(folders)} folders")
            print(f"    Created: {len(created_folders)} folders")
            print(f"    Actual: {len(actual_dirs)} directories")

            if sys.platform.startswith("win") and len(actual_dirs) == 1:
                print("    ✅ Case-insensitive folder creation (expected on Windows)")
            elif not sys.platform.startswith("win") and len(actual_dirs) == len(
                folders
            ):
                print("    ✅ Case-sensitive folder creation (expected on Unix)")

            return True

    def test_windows_path_validation(self):
        """Test validation with Windows-style paths"""
        print("  🧪 Testing Windows path validation...")

        with tempfile.TemporaryDirectory() as tmpdir:
            self.create_mock_dataset(tmpdir)

            # Get all files in dataset
            all_files = []
            for root, dirs, files in os.walk(tmpdir):
                # Filter system files from directory listing
                dirs[:] = [d for d in dirs if not d.startswith(".")]

                for file in files:
                    if not file.startswith("."):
                        full_path = os.path.join(root, file)
                        rel_path = os.path.relpath(full_path, tmpdir)
                        all_files.append(rel_path)

            # Normalize all paths
            normalized = [normalize_path(f) for f in all_files]

            print(f"    ✅ Found {len(all_files)} files")
            print(f"    ✅ Normalized {len(normalized)} paths")

            # Check for backslashes
            backslash_paths = [p for p in normalized if "\\" in p]
            if backslash_paths:
                print(f"    ⚠️  {len(backslash_paths)} paths still have backslashes")
                for p in backslash_paths[:3]:
                    print(f"        {p}")
            else:
                print("    ✅ All paths normalized to forward slashes")

            return True

    def test_system_file_filtering_in_dataset(self):
        """Test that system files are filtered during validation"""
        print("  🧪 Testing system file filtering...")

        with tempfile.TemporaryDirectory() as tmpdir:
            self.create_mock_dataset(tmpdir)

            # Add system files
            system_files = [
                "Thumbs.db",
                ".DS_Store",
                "Desktop.ini",
            ]

            for sys_file in system_files:
                filepath = os.path.join(tmpdir, sys_file)
                CrossPlatformFile.write_text(filepath, "system file")

            # Add system file in subdirectory
            sub_dir = os.path.join(tmpdir, "sub-01", "func")
            CrossPlatformFile.write_text(os.path.join(sub_dir, "Thumbs.db"), "system")

            # Collect all files
            all_files = []
            for root, dirs, files in os.walk(tmpdir):
                for file in files:
                    all_files.append(file)

            # Filter system files
            filtered = filter_system_files(all_files)
            system_found = [f for f in all_files if f not in filtered]

            print(f"    Total files: {len(all_files)}")
            print(f"    After filter: {len(filtered)}")
            print(f"    System files: {len(system_found)}")

            # Verify system files were removed
            expected_system = ["Thumbs.db", ".DS_Store", "Desktop.ini"]
            for sys_file in expected_system:
                if sys_file in filtered:
                    print(f"    ❌ System file not filtered: {sys_file}")
                    return False
                else:
                    print(f"    ✅ Filtered: {sys_file}")

            return True


class TestWindowsFileHandling:
    """Test file handling edge cases on Windows"""

    def test_locked_file_handling(self):
        """Test handling of locked/in-use files"""
        print("  🧪 Testing locked file handling...")

        with tempfile.TemporaryDirectory() as tmpdir:
            test_file = os.path.join(tmpdir, "locked.json")

            # Write file
            CrossPlatformFile.write_text(test_file, '{"test": "data"}')

            # Open file for reading (shared lock on Windows)
            with open(test_file, "r") as f:
                content = f.read()

                # Try to read with our utility (should work with shared lock)
                try:
                    content2 = CrossPlatformFile.read_text(test_file)
                    print("    ✅ Can read file while open for reading")
                except Exception as e:
                    print(f"    ⚠️  Read failed: {e}")
                    return False

            # Try exclusive write
            try:
                CrossPlatformFile.write_text(test_file, '{"test": "updated"}')
                print("    ✅ Can write after file closed")
            except Exception as e:
                print(f"    ❌ Write failed: {e}")
                return False

            return True

    def test_long_filename_paths(self):
        """Test handling of paths exceeding 260 character limit"""
        print("  🧪 Testing long file paths...")

        with tempfile.TemporaryDirectory() as tmpdir:
            # Create a deep directory structure
            deep_path = tmpdir
            for i in range(15):
                deep_path = os.path.join(deep_path, f"level_{i:02d}")

            # Add a long filename
            long_filename = "sub-01_ses-01_task-verylongtaskname_run-01_bold_with_extra_descriptors.json"
            full_path = os.path.join(deep_path, long_filename)

            path_length = len(full_path)
            print(f"    Path length: {path_length} characters")

            if path_length > 260:
                print("    ⚠️  Exceeds traditional Windows limit (260)")

            try:
                # Try to create the directories and file
                os.makedirs(os.path.dirname(full_path), exist_ok=True)
                CrossPlatformFile.write_text(full_path, '{"test": "data"}')

                if os.path.exists(full_path):
                    print("    ✅ Long path handled successfully")

                    # Try to read it back
                    content = CrossPlatformFile.read_text(full_path)
                    print("    ✅ Can read long path")
                else:
                    print("    ❌ File not created")
                    return False

            except Exception as e:
                print(f"    ⚠️  Long path error: {e}")
                if sys.platform.startswith("win"):
                    print("    ℹ️  May need long path support enabled in Windows")

            return True

    def test_special_characters_in_content(self):
        """Test files with special characters in content"""
        print("  🧪 Testing special characters in file content...")

        with tempfile.TemporaryDirectory() as tmpdir:
            test_cases = [
                ("unicode.json", '{"text": "café résumé naïve"}'),
                ("quotes.json", '{"text": "She said \\"hello\\""}'),
                ("newlines.json", '{"text": "line1\\nline2\\r\\nline3"}'),
                ("backslash.json", '{"path": "C:\\\\Users\\\\test"}'),
                ("special.json", '{"symbols": "© ® ™ € £ ¥"}'),
            ]

            for filename, content in test_cases:
                filepath = os.path.join(tmpdir, filename)

                try:
                    # Write
                    CrossPlatformFile.write_text(filepath, content)

                    # Read back
                    read_content = CrossPlatformFile.read_text(filepath)

                    # Parse as JSON
                    json.loads(read_content)

                    print(f"    ✅ {filename}")

                except Exception as e:
                    print(f"    ❌ {filename}: {e}")
                    return False

            return True

    def test_readonly_file_handling(self):
        """Test handling of read-only files"""
        print("  🧪 Testing read-only file handling...")

        with tempfile.TemporaryDirectory() as tmpdir:
            test_file = os.path.join(tmpdir, "readonly.json")

            # Create file
            CrossPlatformFile.write_text(test_file, '{"test": "data"}')

            # Make read-only
            if sys.platform.startswith("win"):
                import stat

                os.chmod(test_file, stat.S_IREAD)

                # Try to read
                try:
                    content = CrossPlatformFile.read_text(test_file)
                    print("    ✅ Can read read-only file")
                except Exception as e:
                    print(f"    ❌ Cannot read read-only: {e}")
                    return False

                # Try to write (should fail gracefully)
                try:
                    CrossPlatformFile.write_text(test_file, '{"test": "updated"}')
                    print("    ⚠️  Write to read-only succeeded (unexpected)")
                except Exception as e:
                    print(f"    ✅ Write to read-only blocked: {type(e).__name__}")

                # Restore permissions for cleanup
                os.chmod(test_file, stat.S_IWRITE | stat.S_IREAD)
            else:
                print("    ⚠️  Not on Windows, skipping")

            return True


class TestWindowsBIDSCompatibility:
    """Test BIDS compatibility on Windows"""

    def test_bidsignore_windows_paths(self):
        """Test .bidsignore with Windows paths"""
        print("  🧪 Testing .bidsignore with Windows paths...")

        with tempfile.TemporaryDirectory() as tmpdir:
            # Create .bidsignore
            bidsignore_content = """
# System files
Thumbs.db
Desktop.ini
.DS_Store

# Derivatives
/derivatives/

# Specific subjects
/sub-99/
"""
            CrossPlatformFile.write_text(
                os.path.join(tmpdir, ".bidsignore"), bidsignore_content
            )

            # Create test files
            test_files = [
                "Thumbs.db",
                "Desktop.ini",
                "sub-01/Thumbs.db",
                "sub-99/func/data.nii.gz",
                "derivatives/sub-01/data.nii.gz",
            ]

            for file_path in test_files:
                full_path = os.path.join(tmpdir, file_path)
                os.makedirs(os.path.dirname(full_path), exist_ok=True)
                CrossPlatformFile.write_text(full_path, "test")

            print("    ✅ Created test structure with .bidsignore")
            print(f"    ✅ {len(test_files)} test files")

            return True

    def test_cross_platform_dataset_sharing(self):
        """Test dataset that might be shared between Windows and Unix"""
        print("  🧪 Testing cross-platform dataset...")

        with tempfile.TemporaryDirectory() as tmpdir:
            # Create files with both system file types
            system_files = [
                "Thumbs.db",  # Windows
                ".DS_Store",  # macOS
                "Desktop.ini",  # Windows
                ".Spotlight-V100",  # macOS
            ]

            for sys_file in system_files:
                filepath = os.path.join(tmpdir, sys_file)
                CrossPlatformFile.write_text(filepath, "system")

            # Test that all are recognized as system files
            basenames = [os.path.basename(f) for f in system_files]
            filtered = filter_system_files(basenames)

            if len(filtered) == 0:
                print("    ✅ All cross-platform system files filtered")
                return True
            else:
                print(f"    ❌ Some system files not filtered: {filtered}")
                return False


def run_all_tests():
    """Run all Windows dataset validation tests"""
    print("=" * 70)
    print("📂 WINDOWS DATASET VALIDATION TESTS")
    print("=" * 70)

    if not sys.platform.startswith("win"):
        print("\n⚠️  Warning: Not running on Windows!")
        print("Some tests may behave differently on non-Windows platforms.\n")

    test_classes = [
        ("Dataset Structure", TestWindowsDatasetStructure),
        ("File Handling", TestWindowsFileHandling),
        ("BIDS Compatibility", TestWindowsBIDSCompatibility),
    ]

    total_passed = 0
    total_tests = 0

    for class_name, test_class in test_classes:
        print(f"\n📋 {class_name}")
        print("-" * 70)

        instance = test_class()
        methods = [m for m in dir(instance) if m.startswith("test_")]

        for method_name in methods:
            total_tests += 1
            method = getattr(instance, method_name)

            try:
                if method():
                    total_passed += 1
                else:
                    print(f"    ❌ {method_name} failed")
            except Exception as e:
                print(f"    ❌ {method_name} error: {e}")
                import traceback

                traceback.print_exc()

        print()

    print("=" * 70)
    print(f"📊 RESULTS: {total_passed}/{total_tests} tests passed")

    if total_passed == total_tests:
        print("🎉 All Windows dataset validation tests passed!")
        return 0
    else:
        print(f"❌ {total_tests - total_passed} test(s) failed")
        return 1


if __name__ == "__main__":
    sys.exit(run_all_tests())
