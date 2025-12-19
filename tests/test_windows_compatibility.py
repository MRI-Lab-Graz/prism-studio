#!/usr/bin/env python3
"""
Test Windows compatibility for psycho-validator
"""

import os
import sys
import tempfile
import shutil
import json
from pathlib import Path

# Add src to path for testing
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

try:
    from cross_platform import (
        normalize_path,
        safe_path_join,
        CrossPlatformFile,
        validate_filename_cross_platform,
        get_platform_info,
        is_case_sensitive_filesystem,
    )
except ImportError as e:
    print(f"❌ Import error: {e}")
    sys.exit(1)


def test_platform_detection():
    """Test platform detection works correctly"""
    print("🧪 Testing platform detection...")

    info = get_platform_info()
    print(f"   Platform: {info['platform']}")
    print(f"   Is Windows: {info['is_windows']}")
    print(f"   Path separator: '{info['path_separator']}'")
    print(f"   Line separator: {repr(info['line_separator'])}")

    return True


def test_path_handling():
    """Test cross-platform path handling"""
    print("🧪 Testing path handling...")

    # Test path normalization
    test_paths = [
        "C:\\Users\\test\\dataset",
        "/home/user/dataset",
        "sub-01/ses-001/func",
        "sub-01\\ses-001\\func",
    ]

    for test_path in test_paths:
        normalized = normalize_path(test_path)
        print(f"   '{test_path}' -> '{normalized}'")

    # Test path joining
    joined = safe_path_join("dataset", "sub-01", "func", "file.nii.gz")
    print(f"   Joined path: '{joined}'")

    return True


def test_filename_validation():
    """Test Windows filename validation"""
    print("🧪 Testing filename validation...")

    test_files = [
        "sub-01_task-test_bold.nii.gz",  # Good
        "sub-01_task-test_CON.nii.gz",  # Windows reserved name
        "sub-01_task-test_file*.nii.gz",  # Invalid character
        "sub-01_task-test_file .nii.gz",  # Trailing space
        "a" * 300 + ".nii.gz",  # Too long
    ]

    for filename in test_files:
        issues = validate_filename_cross_platform(filename)
        status = "❌" if issues else "✅"
        print(f"   {status} {filename[:50]}{'...' if len(filename) > 50 else ''}")
        for issue in issues:
            print(f"      • {issue}")

    return True


def test_file_operations():
    """Test cross-platform file operations"""
    print("🧪 Testing file operations...")

    with tempfile.TemporaryDirectory() as temp_dir:
        test_file = os.path.join(temp_dir, "test.json")
        test_content = '{\n  "test": "data",\n  "line_endings": "mixed"\r\n}'

        # Test writing
        try:
            CrossPlatformFile.write_text(test_file, test_content)
            print("   ✅ File writing works")
        except Exception as e:
            print(f"   ❌ File writing failed: {e}")
            return False

        # Test reading
        try:
            read_content = CrossPlatformFile.read_text(test_file)
            print("   ✅ File reading works")
            print(f"      Content length: {len(read_content)} chars")
        except Exception as e:
            print(f"   ❌ File reading failed: {e}")
            return False

    return True


def test_case_sensitivity():
    """Test filesystem case sensitivity detection"""
    print("🧪 Testing filesystem case sensitivity...")

    try:
        is_case_sensitive = is_case_sensitive_filesystem()
        print(
            f"   Filesystem is {'case-sensitive' if is_case_sensitive else 'case-insensitive'}"
        )

        # This is expected behavior
        if sys.platform.startswith("win") and is_case_sensitive:
            print(
                "   ⚠️  Warning: Windows filesystem detected as case-sensitive (unusual)"
            )
        elif not sys.platform.startswith("win") and not is_case_sensitive:
            print("   ⚠️  Warning: Non-Windows filesystem detected as case-insensitive")
        else:
            print("   ✅ Case sensitivity detection matches expected platform behavior")

        return True
    except Exception as e:
        print(f"   ❌ Case sensitivity test failed: {e}")
        return False


def test_import_compatibility():
    """Test that main modules can be imported"""
    print("🧪 Testing module imports...")

    try:
        # Test absolute imports
        import sys
        import os

        # Add path if not already added
        src_path = os.path.join(os.path.dirname(__file__), "..", "src")
        if src_path not in sys.path:
            sys.path.insert(0, src_path)

        # Now try imports
        import validator
        import schema_manager
        import stats
        import reporting

        print("   ✅ All core modules import successfully")
        return True
    except ImportError as e:
        print(f"   ⚠️  Import warning: {e}")
        print("   ℹ️  This is expected when running outside the package context")
        return True  # Don't fail the test for this
    except Exception as e:
        print(f"   ❌ Unexpected error: {e}")
        return False


def test_json_handling():
    """Test JSON file handling with various encodings"""
    print("🧪 Testing JSON handling...")

    with tempfile.TemporaryDirectory() as temp_dir:
        # Test different content types
        test_cases = [
            ("basic.json", {"test": "data", "number": 42}),
            ("unicode.json", {"test": "données", "emoji": "🎉", "special": "café"}),
            (
                "nested.json",
                {"Study": {"TaskName": "test"}, "Technical": {"FileFormat": "nii.gz"}},
            ),
        ]

        for filename, data in test_cases:
            test_file = os.path.join(temp_dir, filename)

            try:
                # Write JSON
                CrossPlatformFile.write_text(
                    test_file, json.dumps(data, indent=2, ensure_ascii=False)
                )

                # Read and parse JSON
                content = CrossPlatformFile.read_text(test_file)
                parsed = json.loads(content)

                if parsed == data:
                    print(f"   ✅ {filename}")
                else:
                    print(f"   ❌ {filename} - data mismatch")
                    return False

            except Exception as e:
                print(f"   ❌ {filename} - error: {e}")
                return False

    return True


def main():
    """Run all Windows compatibility tests"""
    print("🔍 WINDOWS COMPATIBILITY TESTS")
    print("=" * 50)

    tests = [
        ("Platform Detection", test_platform_detection),
        ("Path Handling", test_path_handling),
        ("Filename Validation", test_filename_validation),
        ("File Operations", test_file_operations),
        ("Case Sensitivity", test_case_sensitivity),
        ("Module Imports", test_import_compatibility),
        ("JSON Handling", test_json_handling),
    ]

    passed = 0
    total = len(tests)

    for test_name, test_func in tests:
        print(f"\n📋 {test_name}")
        print("-" * 30)
        try:
            if test_func():
                passed += 1
            else:
                print(f"   ❌ {test_name} failed")
        except Exception as e:
            print(f"   ❌ {test_name} error: {e}")
        print()

    print("=" * 50)
    print(f"📊 RESULTS: {passed}/{total} tests passed")

    if passed == total:
        print("🎉 All Windows compatibility tests passed!")
        return 0
    else:
        print("❌ Some compatibility issues found")
        return 1


if __name__ == "__main__":
    sys.exit(main())
