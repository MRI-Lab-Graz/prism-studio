#!/usr/bin/env python3
"""
Comprehensive demonstration of the psycho-validator with schema versioning
"""

import subprocess
import os
import sys

def run_command(cmd, description):
    """Run a command and display its output with formatting"""
    print(f"\n{'='*80}")
    print(f"🚀 {description}")
    print(f"{'='*80}")
    print(f"💻 Command: {cmd}")
    print(f"{'-'*80}")
    
    result = subprocess.run(cmd, shell=True, capture_output=True, text=True)
    print(result.stdout)
    if result.stderr:
        print("STDERR:", result.stderr)
    
    print(f"{'-'*80}")
    print(f"📊 Exit code: {result.returncode}")
    return result.returncode

def main():
    print("🎯 PSYCHO-VALIDATOR SCHEMA VERSIONING SHOWCASE")
    print("=" * 80)
    
    # Ensure we're in the right directory
    if not os.path.exists('psycho-validator.py'):
        print("❌ Error: Please run from the psycho-validator directory")
        sys.exit(1)
    
    # Demo 1: List all schema versions
    run_command(
        "python psycho-validator.py --list-versions",
        "DEMO 1: List Available Schema Versions"
    )
    
    # Demo 2: Schema info with version details
    run_command(
        "python psycho-validator.py --schema-info image",
        "DEMO 2: Detailed Schema Information (Image Schema)"
    )
    
    # Demo 3: Version compatibility checking
    run_command(
        "python psycho-validator.py --check-compatibility 1.0.0 1.0.0",
        "DEMO 3A: Version Compatibility - Exact Match (Should Pass)"
    )
    
    run_command(
        "python psycho-validator.py --check-compatibility 1.0.1 1.0.0",
        "DEMO 3B: Version Compatibility - Patch Update (Should Pass)"
    )
    
    run_command(
        "python psycho-validator.py --check-compatibility 1.1.0 1.0.0",
        "DEMO 3C: Version Compatibility - Minor Update (Should Fail)"
    )
    
    run_command(
        "python psycho-validator.py --check-compatibility 2.0.0 1.0.0",
        "DEMO 3D: Version Compatibility - Major Update (Should Fail)"
    )
    
    # Demo 4: Full validation with schema versioning
    run_command(
        "python psycho-validator.py consistent_test_dataset/ -v",
        "DEMO 4: Full Dataset Validation with Schema Versioning"
    )
    
    # Demo 5: Validate valid test dataset
    run_command(
        "python psycho-validator.py valid_test_dataset/",
        "DEMO 5: Validation of Valid Test Dataset"
    )
    
    print(f"\n{'='*80}")
    print("🎉 SHOWCASE COMPLETE!")
    print("💡 Key Schema Versioning Features Demonstrated:")
    print("   ✅ Semantic versioning (MAJOR.MINOR.PATCH)")
    print("   ✅ Version compatibility checking")
    print("   ✅ Schema metadata with version information")
    print("   ✅ Automatic version validation during dataset validation")
    print("   ✅ Future-proofing for schema evolution")
    print(f"{'='*80}")

if __name__ == "__main__":
    main()
