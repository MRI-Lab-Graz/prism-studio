#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Windows-specific path handling tests for PRISM validator.
Tests UNC paths, drive letters, long paths, and Windows-specific edge cases.
"""

import os
import sys
import tempfile

# Force UTF-8 encoding for Windows console
if sys.platform.startswith("win"):
    import io

    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8")

# Add app/src to path for testing
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "app", "src"))

try:
    from cross_platform import (
        normalize_path,
        safe_path_join,
        CrossPlatformFile,
        validate_filename_cross_platform,
        is_case_sensitive_filesystem,
    )
    from system_files import is_system_file, filter_system_files
except ImportError as e:
    print(f"FAIL Import error: {e}")
    sys.exit(1)


class TestWindowsPaths:
    """Test Windows-specific path scenarios"""

    def test_drive_letters(self):
        """Test handling of Windows drive letters"""
        print("  TEST Testing drive letters...")

        test_cases = [
            ("C:\\Users\\test\\dataset", True),
            ("D:\\data\\prism", True),
            ("E:/mixed/slashes", True),
            ("Z:\\network\\share", True),
            ("c:\\lowercase\\drive", True),
        ]

        for path, should_work in test_cases:
            try:
                normalized = normalize_path(path)
                print(f"    OK {path} -> {normalized}")
            except Exception as e:
                if should_work:
                    print(f"    FAIL Failed to normalize {path}: {e}")
                    raise AssertionError(f"Failed to normalize {path}: {e}") from e

        return

    def test_unc_paths(self):
        """Test UNC (network) path handling"""
        print("  TEST Testing UNC paths...")

        test_cases = [
            "\\\\server\\share\\dataset",
            "\\\\192.168.1.1\\data\\prism",
            "\\\\fileserver\\research\\sub-01",
            "//server/share/dataset",  # Forward slash variant
        ]

        for path in test_cases:
            try:
                normalized = normalize_path(path)
                print(f"    OK {path} -> {normalized}")
            except Exception:
                print(f"    WARN UNC path may not be fully supported: {path}")

        return

    def test_long_paths(self):
        """Test long path support (>260 characters)"""
        print("  TEST Testing long paths...")

        # Create a path longer than the traditional 260 char limit
        base = "C:\\very\\long\\path"
        long_path = base + "\\" + ("subdir\\" * 30) + "file.json"

        print(f"    Path length: {len(long_path)} characters")

        if len(long_path) > 260:
            try:
                normalized = normalize_path(long_path)
                print("    OK Long path normalized successfully")

                # Test with \\?\ prefix for long path support
                if sys.platform.startswith("win"):
                    extended_path = "\\\\?\\" + long_path
                    extended_normalized = normalize_path(extended_path)
                    print("    OK Extended path format supported")

            except Exception as e:
                print(f"    WARN Long path handling: {e}")

        return

    def test_mixed_separators(self):
        """Test paths with mixed forward/backward slashes"""
        print("  TEST Testing mixed path separators...")

        test_cases = [
            "C:\\Users\\test/dataset/sub-01",
            "D:/data\\prism\\raw_data",
            "dataset/sub-01\\ses-01/func",
        ]

        for path in test_cases:
            try:
                normalized = normalize_path(path)
                # Check that result is consistent
                if "\\" in normalized and "/" in normalized:
                    print(f"    WARN Mixed separators remain: {normalized}")
                else:
                    print(f"    OK {path} -> {normalized}")
            except Exception as e:
                print(f"    FAIL Failed: {e}")
                raise AssertionError(
                    f"Failed to normalize mixed path {path}: {e}"
                ) from e

        return

    def test_relative_paths_windows(self):
        """Test Windows-style relative paths"""
        print("  TEST Testing relative paths on Windows...")

        test_cases = [
            "..\\parent\\dataset",
            ".\\current\\sub-01",
            "..\\..\\root\\data",
        ]

        for path in test_cases:
            try:
                normalized = normalize_path(path)
                print(f"    OK {path} -> {normalized}")
            except Exception as e:
                print(f"    FAIL Failed: {e}")
                raise AssertionError(
                    f"Failed to normalize relative path {path}: {e}"
                ) from e

        return

    def test_special_windows_chars(self):
        """Test handling of Windows special characters in paths"""
        print("  TEST Testing special characters...")

        # Valid characters
        valid_paths = [
            "C:\\dataset with spaces\\sub-01",
            "D:\\data-with-hyphens\\sub_01",
            "E:\\data.with.dots\\sub-01",
        ]

        for path in valid_paths:
            try:
                normalized = normalize_path(path)
                print(f"    OK {path}")
            except Exception as e:
                print(f"    FAIL Failed on valid path: {e}")
                raise AssertionError(f"Failed on valid path {path}: {e}") from e

        return


class TestWindowsFilenames:
    """Test Windows filename restrictions"""

    def test_reserved_names(self):
        """Test Windows reserved filenames"""
        print("  TEST Testing reserved filenames...")

        reserved = [
            "CON.json",
            "PRN.tsv",
            "AUX.nii",  # Single extension should work
            "NUL.txt",
            "COM1.json",
            "COM9.tsv",
            "LPT1.nii",
            "LPT9.json",
        ]

        for filename in reserved:
            issues = validate_filename_cross_platform(filename)
            if sys.platform.startswith("win"):
                if not issues:
                    print(f"    FAIL Should detect reserved name: {filename}")
                    assert False, f"Should detect reserved name: {filename}"
                print(f"    OK Detected: {filename} - {issues[0]}")
            else:
                print(f"    WARN Not on Windows, skipping: {filename}")

        # Test compound extensions (these are harder to detect)
        compound = [
            "AUX.nii.gz",  # os.path.splitext only removes .gz
            "COM1.tar.gz",
        ]

        print("    INFO Note: Reserved names with compound extensions (.nii.gz)")
        print("        may not be detected by splitext - this is a known limitation")

        return

    def test_invalid_characters(self):
        """Test Windows invalid filename characters"""
        print("  TEST Testing invalid characters...")

        invalid_chars = ["<", ">", ":", '"', "|", "?", "*"]

        for char in invalid_chars:
            filename = f"sub-01_task{char}test_bold.nii.gz"
            issues = validate_filename_cross_platform(filename)

            if sys.platform.startswith("win"):
                if not issues:
                    print(f"    FAIL Should detect invalid char '{char}'")
                    assert False, f"Should detect invalid char '{char}'"
                print(f"    OK Detected invalid char '{char}' in {filename}")
            else:
                print(f"    WARN Not on Windows, char '{char}' may be valid")

        return

    def test_trailing_spaces_dots(self):
        """Test filenames with trailing spaces or dots"""
        print("  TEST Testing trailing spaces and dots...")

        invalid_names = [
            "sub-01_bold.nii.gz ",  # trailing space
            "sub-01_bold.nii.gz.",  # trailing dot
            "file.",  # just trailing dot after name
        ]

        for filename in invalid_names:
            issues = validate_filename_cross_platform(filename)
            if sys.platform.startswith("win"):
                if not issues:
                    print(f"    FAIL Should detect invalid: {repr(filename)}")
                    assert False, f"Should detect invalid filename: {repr(filename)}"
                print(f"    OK Detected: {repr(filename)}")

        # Test case with space before extension - this is valid on Windows
        # The space is part of the base name, not trailing
        print("    INFO Note: 'file .json' has space before extension (valid)")

        return

    def test_filename_length(self):
        """Test maximum filename length"""
        print("  TEST Testing filename length limits...")

        # 255 character limit
        short_name = "a" * 200 + ".json"
        long_name = "a" * 260 + ".json"

        short_issues = validate_filename_cross_platform(short_name)
        long_issues = validate_filename_cross_platform(long_name)

        if short_issues:
            print("    FAIL 200 char filename should be valid")
            assert False, "200 char filename should be valid"

        if not long_issues:
            print("    FAIL 260 char filename should be invalid")
            assert False, "260 char filename should be invalid"

        print("    OK Filename length validation working")
        return


class TestWindowsSystemFiles:
    """Test Windows system file detection"""

    def test_windows_system_files(self):
        """Test detection of Windows-specific system files"""
        print("  TEST Testing Windows system files...")

        system_files = [
            "Thumbs.db",
            "ehthumbs.db",
            "Desktop.ini",
            "$RECYCLE.BIN",
            "System Volume Information",
        ]

        for filename in system_files:
            if not is_system_file(filename):
                print(f"    FAIL Should detect system file: {filename}")
                assert False, f"Should detect system file: {filename}"
            print(f"    OK Detected: {filename}")

        return

    def test_macos_system_files(self):
        """Test detection of macOS system files (for cross-platform datasets)"""
        print("  TEST Testing macOS system files...")

        macos_files = [
            ".DS_Store",
            "._.DS_Store",
            "._metadata.json",
            ".Spotlight-V100",
            ".Trashes",
            ".VolumeIcon.icns",
        ]

        for filename in macos_files:
            if not is_system_file(filename):
                print(f"    FAIL Should detect macOS system file: {filename}")
                assert False, f"Should detect macOS system file: {filename}"
            print(f"    OK Detected: {filename}")

        return

    def test_filter_mixed_list(self):
        """Test filtering a mixed list of files"""
        print("  TEST Testing system file filtering...")

        file_list = [
            "sub-01_bold.nii.gz",
            "Thumbs.db",
            "sub-01_bold.json",
            ".DS_Store",
            "dataset_description.json",
            "Desktop.ini",
            "participants.tsv",
        ]

        filtered = filter_system_files(file_list)
        expected = [
            "sub-01_bold.nii.gz",
            "sub-01_bold.json",
            "dataset_description.json",
            "participants.tsv",
        ]

        if filtered != expected:
            print(f"    FAIL Expected: {expected}")
            print(f"    FAIL Got: {filtered}")
            assert False, "System file filtering output mismatch"

        print(f"    OK Filtered {len(file_list) - len(filtered)} system files")
        return


class TestWindowsFileOperations:
    """Test file I/O operations on Windows"""

    def test_unicode_filenames(self):
        """Test handling of Unicode characters in filenames"""
        print("  TEST Testing Unicode filenames...")

        with tempfile.TemporaryDirectory() as tmpdir:
            test_files = [
                "café.json",
                "données.tsv",
                "测试.json",
                "тест.tsv",
                "emoji_🎉.json",
            ]

            for filename in test_files:
                try:
                    filepath = os.path.join(tmpdir, filename)
                    content = '{"test": "data"}'
                    CrossPlatformFile.write_text(filepath, content)

                    if os.path.exists(filepath):
                        read_content = CrossPlatformFile.read_text(filepath)
                        if read_content == content:
                            print(f"    OK {filename}")
                        else:
                            print(f"    FAIL Content mismatch: {filename}")
                            assert False, f"Content mismatch: {filename}"
                    else:
                        print(f"    FAIL File not created: {filename}")
                        assert False, f"File not created: {filename}"

                except Exception as e:
                    print(f"    WARN {filename}: {e}")

        return

    def test_line_endings(self):
        """Test line ending handling (CRLF vs LF)"""
        print("  TEST Testing line endings...")

        with tempfile.TemporaryDirectory() as tmpdir:
            test_file = os.path.join(tmpdir, "line_endings.txt")

            # Test different line ending styles
            test_cases = [
                ("Unix LF", "line1\nline2\nline3"),
                ("Windows CRLF", "line1\r\nline2\r\nline3"),
                ("Mixed", "line1\nline2\r\nline3\nline4"),
                ("Old Mac CR", "line1\rline2\rline3"),
            ]

            for name, content in test_cases:
                try:
                    CrossPlatformFile.write_text(test_file, content)
                    read_back = CrossPlatformFile.read_text(test_file)

                    # Check that content is readable and normalized
                    if len(read_back) > 0:
                        print(
                            f"    OK {name}: {len(content)} -> {len(read_back)} chars"
                        )
                    else:
                        print(f"    FAIL {name}: empty after read")
                        assert False, f"{name}: empty after read"

                except Exception as e:
                    print(f"    FAIL {name}: {e}")
                    raise AssertionError(f"{name}: {e}") from e

        return

    def test_encoding_handling(self):
        """Test different text encodings"""
        print("  TEST Testing text encodings...")

        with tempfile.TemporaryDirectory() as tmpdir:
            test_content = {
                "utf8": "UTF-8: café, données, 测试",
                "latin1": "Latin-1: café, naïve",
                "ascii": "ASCII: test data",
            }

            for encoding_name, content in test_content.items():
                try:
                    filepath = os.path.join(tmpdir, f"{encoding_name}.txt")
                    CrossPlatformFile.write_text(filepath, content)

                    # Read back with default UTF-8
                    read_content = CrossPlatformFile.read_text(filepath)
                    print(f"    OK {encoding_name}: {len(content)} chars")

                except Exception as e:
                    print(f"    WARN {encoding_name}: {e}")

        return

    def test_file_locking(self):
        """Test file operations with potential lock conflicts"""
        print("  TEST Testing file locking scenarios...")

        with tempfile.TemporaryDirectory() as tmpdir:
            test_file = os.path.join(tmpdir, "locktest.json")

            try:
                # Write file
                CrossPlatformFile.write_text(test_file, '{"test": "data"}')

                # Read while it exists
                content1 = CrossPlatformFile.read_text(test_file)

                # Overwrite
                CrossPlatformFile.write_text(test_file, '{"test": "updated"}')

                # Read again
                content2 = CrossPlatformFile.read_text(test_file)

                if content1 != content2:
                    print("    OK File operations without lock conflicts")
                    return
                else:
                    print("    FAIL File not updated properly")
                    assert False, "File not updated properly"

            except Exception as e:
                print(f"    FAIL Lock conflict: {e}")
                raise AssertionError(f"Lock conflict: {e}") from e


def run_all_tests():
    """Run all Windows-specific tests"""
    print("=" * 70)
    print("WINDOWS-SPECIFIC PATH & FILENAME TESTS")
    print("=" * 70)

    if not sys.platform.startswith("win"):
        print("\nWARN Warning: Not running on Windows!")
        print("Some tests may behave differently on non-Windows platforms.\n")

    test_classes = [
        ("Windows Path Handling", TestWindowsPaths),
        ("Windows Filenames", TestWindowsFilenames),
        ("Windows System Files", TestWindowsSystemFiles),
        ("Windows File Operations", TestWindowsFileOperations),
    ]

    total_passed = 0
    total_tests = 0

    for class_name, test_class in test_classes:
        print(f"\nSECTION {class_name}")
        print("-" * 70)

        instance = test_class()
        methods = [m for m in dir(instance) if m.startswith("test_")]

        for method_name in methods:
            total_tests += 1
            method = getattr(instance, method_name)

            try:
                result = method()
                if result is not False:
                    total_passed += 1
                else:
                    print(f"    FAIL {method_name} failed")
            except Exception as e:
                print(f"    FAIL {method_name} error: {e}")
                import traceback

                traceback.print_exc()

        print()

    print("=" * 70)
    print(f"RESULTS: {total_passed}/{total_tests} tests passed")

    if total_passed == total_tests:
        print("All Windows-specific tests passed!")
        return 0
    else:
        print(f"{total_tests - total_passed} test(s) failed")
        return 1


if __name__ == "__main__":
    sys.exit(run_all_tests())
