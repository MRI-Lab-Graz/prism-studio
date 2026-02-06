@echo off
REM Test if pyedflib is available (Windows batch script)
REM Usage: scripts\test_pyedflib.bat

echo =========================================
echo PRISM - Testing pyedflib availability
echo =========================================
echo.

python -c "import sys; sys.path.insert(0, 'vendor'); import pyedflib; print('SUCCESS: pyedflib is available'); print('Version:', pyedflib.__version__)" 2>nul

if %errorlevel% equ 0 (
    echo.
    echo pyedflib is working correctly!
    echo EDF/EDF+ files will be fully supported.
) else (
    echo.
    echo WARNING: pyedflib not found
    echo EDF/EDF+ metadata extraction will be skipped.
    echo.
    echo To enable EDF support, you can:
    echo   1. Try: pip install vendor\wheels\pyedflib-*.whl
    echo   2. Or: pip install pyedflib
    echo.
)

echo.
pause
