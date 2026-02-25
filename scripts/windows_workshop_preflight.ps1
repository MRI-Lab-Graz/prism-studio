param(
    [switch]$SkipSetup,
    [switch]$SkipTests,
    [switch]$VerboseTests
)

$ErrorActionPreference = "Stop"

function Write-Section {
    param([string]$Message)
    Write-Host ""
    Write-Host "============================================================" -ForegroundColor Cyan
    Write-Host $Message -ForegroundColor Cyan
    Write-Host "============================================================" -ForegroundColor Cyan
}

function Run-Step {
    param(
        [string]$Name,
        [scriptblock]$Action
    )

    Write-Host "[STEP] $Name" -ForegroundColor Yellow
    try {
        & $Action
        Write-Host "[ OK ] $Name" -ForegroundColor Green
    }
    catch {
        Write-Host "[FAIL] $Name" -ForegroundColor Red
        Write-Host $_.Exception.Message -ForegroundColor Red
        exit 1
    }
}

Write-Section "PRISM Windows Workshop Preflight"

# Resolve repo root from script location
$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$RepoRoot = Split-Path -Parent $ScriptDir
Set-Location $RepoRoot

Write-Host "Repo root: $RepoRoot" -ForegroundColor Gray

$VenvPython = Join-Path $RepoRoot ".venv\Scripts\python.exe"
$SetupBat = Join-Path $RepoRoot "scripts\setup\setup-windows.bat"
$WindowsRunner = Join-Path $RepoRoot "tests\run_windows_tests.py"

Run-Step "Check Python availability" {
    python --version | Out-Host
}

if (-not $SkipSetup) {
    Run-Step "Ensure virtual environment exists" {
        if (-not (Test-Path $VenvPython)) {
            if (-not (Test-Path $SetupBat)) {
                throw "Setup script not found: $SetupBat"
            }
            Write-Host "No .venv detected. Running setup script..." -ForegroundColor Gray
            cmd /c "`"$SetupBat`""
            if ($LASTEXITCODE -ne 0) {
                throw "Setup script failed with exit code $LASTEXITCODE"
            }
        }
    }
}

Run-Step "Verify venv Python" {
    if (-not (Test-Path $VenvPython)) {
        throw "Virtual environment Python not found: $VenvPython"
    }
    & $VenvPython --version | Out-Host
}

Run-Step "Critical import checks" {
    & $VenvPython -c "import sys; sys.path.insert(0, 'app'); from src.participants_converter import ParticipantsConverter; from src.web.blueprints.conversion import api_participants_convert; print('import checks ok')" | Out-Host
    if ($LASTEXITCODE -ne 0) {
        throw "Critical import check failed"
    }
}

Run-Step "App entrypoint smoke import" {
    $code = @"
import importlib.util
from pathlib import Path

p = Path('app/prism-studio.py').resolve()
spec = importlib.util.spec_from_file_location('prism_studio_app', p)
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)
print('app startup import ok')
"@
    & $VenvPython -c $code | Out-Host
    if ($LASTEXITCODE -ne 0) {
        throw "App startup smoke import failed"
    }
}

if (-not $SkipTests) {
    Run-Step "Run Windows test suite" {
        if (-not (Test-Path $WindowsRunner)) {
            throw "Windows test runner not found: $WindowsRunner"
        }

        if ($VerboseTests) {
            & $VenvPython $WindowsRunner
        }
        else {
            & $VenvPython $WindowsRunner | Out-Host
        }

        if ($LASTEXITCODE -ne 0) {
            throw "Windows tests failed with exit code $LASTEXITCODE"
        }
    }
}

Write-Section "Preflight Passed"
Write-Host "Windows workshop checks completed successfully." -ForegroundColor Green
Write-Host ""
Write-Host "Next command to run app:" -ForegroundColor Gray
Write-Host "  .\.venv\Scripts\python.exe app\prism-studio.py" -ForegroundColor White
