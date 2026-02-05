#!/usr/bin/env python3
"""
Verify that vendored pyedflib is properly structured.
Run this after copying pyedflib from Windows VM.
"""

import sys
from pathlib import Path

def check_vendor_structure():
    """Check if vendor directory is properly structured."""
    
    print("=" * 60)
    print("PRISM - Vendor Package Verification")
    print("=" * 60)
    print()
    
    vendor_dir = Path(__file__).parent
    pyedflib_dir = vendor_dir / "pyedflib"
    
    issues = []
    warnings = []
    
    # Check if pyedflib directory exists
    if not pyedflib_dir.exists():
        issues.append("❌ pyedflib directory not found")
        issues.append(f"   Expected: {pyedflib_dir}")
        issues.append("   → Copy pyedflib folder from Windows VM")
    else:
        print(f"✓ Found: {pyedflib_dir}")
        
        # Check for essential files
        init_file = pyedflib_dir / "__init__.py"
        if not init_file.exists():
            issues.append("❌ Missing __init__.py in pyedflib/")
        else:
            print(f"✓ Found: __init__.py")
        
        # Check for .pyd files (Windows compiled extensions)
        pyd_files = list(pyedflib_dir.rglob("*.pyd"))
        if not pyd_files:
            warnings.append("⚠ No .pyd files found")
            warnings.append("  These are needed for Windows support")
            warnings.append("  Make sure you copied from Windows, not Mac/Linux")
        else:
            print(f"✓ Found {len(pyd_files)} .pyd file(s):")
            for pyd in pyd_files:
                print(f"  - {pyd.relative_to(pyedflib_dir)}")
        
        # Check for Python files
        py_files = list(pyedflib_dir.glob("*.py"))
        if py_files:
            print(f"✓ Found {len(py_files)} Python file(s)")
        
        # Try to import (will only work if on Windows or if pure Python fallback exists)
        print()
        print("Testing import...")
        sys.path.insert(0, str(vendor_dir))
        try:
            import pyedflib
            print(f"✓ Import successful!")
            print(f"  Version: {getattr(pyedflib, '__version__', 'unknown')}")
            print(f"  Location: {pyedflib.__file__}")
        except ImportError as e:
            if pyd_files:
                warnings.append("⚠ Import failed")
                warnings.append("  This can happen on non-Windows systems or when")
                warnings.append("  the wheel Python version does not match the runtime")
                warnings.append("  Windows users with the matching Python version will be able to import it")
                warnings.append(f"  Import error: {e}")
            else:
                issues.append(f"❌ Import failed: {e}")
    
    print()
    print("=" * 60)
    
    # Report issues
    if issues:
        print("ISSUES FOUND:")
        print()
        for issue in issues:
            print(issue)
        print()
        print("See vendor/STEP_BY_STEP.md for instructions")
        return False
    
    # Report warnings
    if warnings:
        print("WARNINGS:")
        print()
        for warning in warnings:
            print(warning)
        print()
    
    # Success message
    if not issues:
        print("✅ VENDOR STRUCTURE LOOKS GOOD!")
        print()
        if warnings:
            print("Warnings are expected when verifying on Mac/Linux.")
            print("The bundled package will work for Windows users.")
        print()
        print("Next steps:")
        print("  1. git add vendor/pyedflib/")
        print("  2. git commit -m 'Bundle pre-compiled pyedflib'")
        print("  3. git push")
        return True
    
    print()
    return False


if __name__ == "__main__":
    success = check_vendor_structure()
    sys.exit(0 if success else 1)
