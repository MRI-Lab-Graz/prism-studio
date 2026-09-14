#!/bin/bash
# Test if pyedflib is available (Unix/Mac/Linux)
# Usage: ./scripts/ci/test_pyedflib.sh

echo "========================================="
echo "PRISM - Testing pyedflib availability"
echo "========================================="
echo ""

if python -c "import pyedflib; print('SUCCESS: pyedflib is available'); print('Version:', pyedflib.__version__)" 2>/dev/null; then
    echo ""
    echo "✓ pyedflib is working correctly!"
    echo "✓ EDF/EDF+ files will be fully supported."
else
    echo ""
    echo "⚠ WARNING: pyedflib not found"
    echo "EDF/EDF+ metadata extraction will be skipped."
    echo ""
    echo "To enable EDF support, run: pip install pyedflib"
    echo ""
fi

echo ""
