@echo off
REM Compatibility wrapper for moved script
REM Use scripts/ci/test_pyedflib.bat as the canonical location.

call "%~dp0ci\test_pyedflib.bat" %*
