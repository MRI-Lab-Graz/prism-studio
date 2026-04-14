#Requires -Version 5.1
<#
.SYNOPSIS
    Local Windows build — produces the same prism-studio-Windows.zip as the GitHub CI.

.USAGE
    .\build_local.ps1                    # standard build
    .\build_local.ps1 -SkipInstall       # skip pip install (if deps already installed)
    .\build_local.ps1 -OutputZip my.zip  # custom output filename
#>
param(
    [switch]$SkipInstall,
    [string]$OutputZip = 'prism-studio-Windows.zip'
)

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

$root = Split-Path $PSScriptRoot -Parent
if (-not (Test-Path (Join-Path $root 'app\prism-studio.py'))) {
    # Script is IN the repo root (not a subdirectory)
    $root = $PSScriptRoot
}

Set-Location $root
Write-Host ""
Write-Host "=== PRISM Studio Local Windows Build ===" -ForegroundColor Cyan
Write-Host "Repo root : $root"
Write-Host "Output ZIP: $OutputZip"
Write-Host ""

# ── 1. Activate venv ────────────────────────────────────────────────────────
$venvPython = Join-Path $root '.venv\Scripts\python.exe'
if (-not (Test-Path $venvPython)) {
    Write-Error ".venv not found. Run setup.ps1 first, or create it with: python -m venv .venv"
}
Write-Host "[1/4] Using Python: $venvPython" -ForegroundColor Green

# ── 2. Install build dependencies (same as CI) ───────────────────────────────
if (-not $SkipInstall) {
    Write-Host "[2/4] Installing runtime + build requirements..." -ForegroundColor Green
    & $venvPython -m pip install --upgrade pip --quiet
    & $venvPython -m pip install -r requirements-runtime.txt --quiet
    & $venvPython -m pip install -r requirements-build.txt --quiet
    if ($LASTEXITCODE -ne 0) { Write-Error "pip install failed" }
} else {
    Write-Host "[2/4] Skipping pip install (-SkipInstall)" -ForegroundColor Yellow
}

# ── 3. Ensure survey_library exists (CI creates it before build) ──────────────
if (-not (Test-Path 'survey_library')) {
    New-Item -ItemType Directory -Path 'survey_library' | Out-Null
}

# ── 4. Run PyInstaller build (same command as CI) ────────────────────────────
Write-Host "[3/4] Building with PyInstaller..." -ForegroundColor Green
& $venvPython scripts\build\build_app.py --name PrismStudio
if ($LASTEXITCODE -ne 0) { Write-Error "PyInstaller build failed" }

# ── 5. Package Windows ZIP (same as CI) ─────────────────────────────────────
Write-Host "[4/4] Creating Windows ZIP: $OutputZip" -ForegroundColor Green
if (Test-Path $OutputZip) {
    Remove-Item $OutputZip -Force
}
Compress-Archive -Path 'dist\PrismStudio' -DestinationPath $OutputZip

Write-Host ""
Write-Host "=== Build complete! ===" -ForegroundColor Cyan
Write-Host "  ZIP : $(Resolve-Path $OutputZip)"
Write-Host "  Dir : $(Resolve-Path 'dist\PrismStudio')"
Write-Host ""
Write-Host "To test the build immediately, run:" -ForegroundColor Yellow
Write-Host "  .\dist\PrismStudio\PrismStudio.exe" -ForegroundColor Yellow
