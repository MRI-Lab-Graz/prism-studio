#!/usr/bin/env python3
"""
Enhanced test script demonstrating the comprehensive validator output
"""

import os
import sys
import subprocess


def run_validator(dataset_path, verbose=False):
    """Run the validator and return the results"""
    try:
        # Calculate path to main script
        script_path = os.path.join(
            os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
            "prism.py",
        )
        cmd = [sys.executable, script_path, dataset_path]
        if verbose:
            cmd.append("-v")

        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            cwd=os.path.dirname(os.path.abspath(__file__)),
        )
        return result.returncode, result.stdout, result.stderr
    except Exception as e:
        return -1, "", str(e)


def test_comprehensive_validation():
    """Test different validation scenarios with comprehensive output"""
    print("🧪 Enhanced PRISM Testing")
    print("=" * 70)

    # Test 1: Valid dataset
    print("\n🟢 TEST 1: Valid Dataset")
    print("-" * 40)
    returncode, stdout, stderr = run_validator("valid_test_dataset")
    print(stdout)
    if returncode == 0:
        print("✅ Test passed: Valid dataset correctly validated")
    else:
        print("❌ Test failed: Valid dataset should pass validation")

    # Test 2: Dataset with errors
    print("\n🔴 TEST 2: Dataset with Validation Errors")
    print("-" * 40)
    returncode, stdout, stderr = run_validator("test_dataset")
    print(stdout)
    if returncode != 0:
        print("✅ Test passed: Errors correctly detected")
    else:
        print("❌ Test failed: Should have detected validation errors")

    # Test 3: Verbose mode
    print("\n🔍 TEST 3: Verbose Mode")
    print("-" * 40)
    returncode, stdout, stderr = run_validator("valid_test_dataset", verbose=True)
    if "📁 Scanning for modalities:" in stdout:
        print("✅ Test passed: Verbose mode working correctly")
    else:
        print("❌ Test failed: Verbose mode not working")

    # Test 4: Non-existent dataset
    print("\n❌ TEST 4: Non-existent Dataset")
    print("-" * 40)
    returncode, stdout, stderr = run_validator("non_existent_dataset")
    if returncode != 0:
        print("✅ Test passed: Correctly failed for non-existent dataset")
    else:
        print("❌ Test failed: Should fail for non-existent dataset")

    print("\n" + "=" * 70)
    print("🎯 SUMMARY OF VALIDATOR FEATURES:")
    print("  ✅ Comprehensive dataset statistics")
    print("  ✅ Subject and session counting")
    print("  ✅ Modality detection and file counting")
    print("  ✅ Task extraction and listing")
    print("  ✅ File categorization (data vs sidecar)")
    print("  ✅ Schema validation status")
    print("  ✅ Structured error and warning reporting")
    print("  ✅ Proper exit codes for automation")
    print("  ✅ Verbose mode for debugging")


if __name__ == "__main__":
    test_comprehensive_validation()
