<#
.SYNOPSIS
    Setup script for prism on Windows.
    
.DESCRIPTION
    This script will:
    1. Check if 'uv' is installed.
    2. Create a virtual environment in .\.venv
    3. Install dependencies from requirements.txt into the virtual environment.
    4. Optional: Install build and/or developer dependencies.
    5. Install the project in development mode.

.PARAMETER Build
    Include dependencies required for building the standalone executable.

.PARAMETER Dev
    Include dependencies required for development and testing.

.EXAMPLE
    .\setup.ps1
    
.EXAMPLE
    .\setup.ps1 -Build -Dev
#>

Param(
    [switch]$Build,
    [switch]$Dev
)

# --- Configuration ---
$VenvDir = ".venv"
$RequirementsFile = "requirements.txt"
$BuildRequirementsFile = "requirements-build.txt"
$DevRequirementsFile = "requirements-dev.txt"

# --- Functions ---
function Write-Info {
    param([string]$Message)
    Write-Host "INFO: $Message" -ForegroundColor Cyan
}

function Write-Error {
    param([string]$Message)
    Write-Host "ERROR: $Message" -ForegroundColor Red
}

function Write-Success {
    param([string]$Message)
    Write-Host "✅ $Message" -ForegroundColor Green
}

# --- Main Script ---
Write-Info "Starting project setup for prism (Windows)..."

# 1. Check for uv
if (-not (Get-Command "uv" -ErrorAction SilentlyContinue)) {
    Write-Info "'uv' command not found."
    $InstallUv = Read-Host "Would you like to install 'uv' now? (Highly recommended for speed) [Y/N]"
    if ($InstallUv -match "^[Yy]$") {
        Write-Info "Installing uv..."
        powershell -ExecutionPolicy ByPass -c "irm https://astral.sh/uv/install.ps1 | iex"
        
        # Refresh Path for current session
        $env:Path = "$env:USERPROFILE\.cargo\bin;$env:Path"
        
        if (-not (Get-Command "uv" -ErrorAction SilentlyContinue)) {
            Write-Error "Failed to install uv or it's not in the path."
            Write-Info "Falling back to standard python/pip..." $true
            $UseUv = $false
        } else {
            Write-Success "uv installed successfully."
            $UseUv = $true
        }
    } else {
        Write-Info "Skipping uv installation. Falling back to standard python/pip..."
        $UseUv = $false
    }
} else {
    Write-Info "'uv' is installed."
    $UseUv = $true
}

# --- Common logic for using uv or python ---
function Invoke-PythonCommand {
    param([string]$Command, [string]$UvArgs)
    if ($UseUv) {
        Invoke-Expression "uv $UvArgs"
    } else {
        Invoke-Expression "$Command"
    }
}

# 2. Check for Deno (Required for BIDS validation)
if (-not (Get-Command "deno" -ErrorAction SilentlyContinue)) {
    Write-Info "Deno not found (required for BIDS validation). Installing..."
    try {
        irm https://deno.land/install.ps1 | iex
        
        # Add to path for current session
        $env:DENO_INSTALL = "$HOME\.deno"
        $env:Path = "$env:DENO_INSTALL\bin;$env:Path"
        
        Write-Success "Deno installed."
    } catch {
        Write-Host "WARNING: Failed to install Deno. BIDS validation may not work." -ForegroundColor Yellow
    }
} else {
    Write-Info "Deno is already installed."
}

# 3. Check for requirements.txt
if (-not (Test-Path "$RequirementsFile")) {
    Write-Error "'$RequirementsFile' not found."
    Write-Info "Please make sure the requirements file exists in the project root."
    exit 1
}
Write-Info "'$RequirementsFile' found."

# 4. Create virtual environment
if (Test-Path "$VenvDir") {
    Write-Info "Virtual environment already exists in '$VenvDir' - reusing it."
} else {
    Write-Info "Creating virtual environment in '$VenvDir'..."
    if ($UseUv) {
        & uv venv $VenvDir
    } else {
        & python -m venv $VenvDir
    }
    
    if ($LASTEXITCODE -ne 0) {
        Write-Error "Failed to create virtual environment."
        exit 1
    }
    Write-Success "Virtual environment created."
}

# 5. Install dependencies
Write-Info "Installing dependencies from '$RequirementsFile'..."

if ($UseUv) {
    & uv pip install -r $RequirementsFile
} else {
    & $VenvDir\Scripts\python.exe -m pip install --upgrade pip
    & $VenvDir\Scripts\pip.exe install -r $RequirementsFile
}

if ($LASTEXITCODE -ne 0) {
    Write-Error "Failed to install dependencies."
    exit 1
}

if ($Build) {
    if (-not (Test-Path "$BuildRequirementsFile")) {
        Write-Error "'$BuildRequirementsFile' not found."
        exit 1
    }
    Write-Info "Installing build dependencies from '$BuildRequirementsFile'..."
    if ($UseUv) {
        & uv pip install -r $BuildRequirementsFile
    } else {
        & $VenvDir\Scripts\pip.exe install -r $BuildRequirementsFile
    }
    if ($LASTEXITCODE -ne 0) {
        Write-Error "Failed to install build dependencies."
        exit 1
    }
    Write-Success "Build dependencies installed successfully."
}

if ($Dev) {
    if (-not (Test-Path "$DevRequirementsFile")) {
        Write-Error "'$DevRequirementsFile' not found."
        exit 1
    }
    Write-Info "Installing development dependencies from '$DevRequirementsFile'..."
    if ($UseUv) {
        & uv pip install -r $DevRequirementsFile
    } else {
        & $VenvDir\Scripts\pip.exe install -r $DevRequirementsFile
    }
    if ($LASTEXITCODE -ne 0) {
        Write-Error "Failed to install development dependencies."
        exit 1
    }
    Write-Success "Development dependencies installed successfully."
}

# 6. Install the project in development mode (editable install)
Write-Info "Installing prism in development mode..."
if ($UseUv) {
    & uv pip install -e .
} else {
    & $VenvDir\Scripts\pip.exe install -e .
}
if ($LASTEXITCODE -ne 0) {
    Write-Host "WARNING: Failed to install prism package in editable mode. Check if setup.py exists." -ForegroundColor Yellow
}

Write-Success "Dependencies installed successfully."

# --- Final Instructions ---
Write-Host ""
Write-Host "--------------------------------------------------" -ForegroundColor Cyan
Write-Host "Setup complete!" -ForegroundColor Green
Write-Host "To activate the virtual environment, run:" -ForegroundColor Cyan
Write-Host ".\$VenvDir\Scripts\Activate.ps1" -ForegroundColor Yellow
Write-Host "--------------------------------------------------" -ForegroundColor Cyan
