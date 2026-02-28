@echo off
setlocal

set SCRIPT_DIR=%~dp0
set REPO_ROOT=%SCRIPT_DIR%\..\..
pushd "%REPO_ROOT%"

if not exist ".venv" (
  echo [ERROR] Missing .venv in %CD%
  echo Run setup first: scripts\setup\setup-windows.bat
  popd
  exit /b 1
)

call .venv\Scripts\activate.bat
python tests\verify_repo.py --check entrypoints-smoke,import-boundaries,pytest --no-fix
set EXIT_CODE=%ERRORLEVEL%

popd
exit /b %EXIT_CODE%
