<#
.SYNOPSIS
    Test fresh installation scenarios for pyedflib on Windows
    
.DESCRIPTION
    This script simulates a fresh PRISM installation and tests:
    1. Regular pip installation of pyedflib
    2. Fallback to vendored pyedflib if pip fails
    3. Both scenarios in isolated virtual environments
    
.PARAMETER TestVendored
    If specified, only test the vendored pyedflib scenario
    
.PARAMETER TestPip
    If specified, only test the pip installation scenario
    
.EXAMPLE
    .\scripts\ci\test_fresh_install.ps1
    
.EXAMPLE
    .\scripts\ci\test_fresh_install.ps1 -TestVendored
#>

Param(
    [switch]$TestVendored,
    [switch]$TestPip
)

# If neither flag is specified, test both
if (-not $TestVendored -and -not $TestPip) {
    $TestVendored = $true
    $TestPip = $true
}

$ErrorActionPreference = "Stop"
$ScriptDir = Split-Path -Parent $PSCommandPath
$RepoRoot = Split-Path -Parent (Split-Path -Parent $ScriptDir)

function Write-TestHeader {
    param([string]$Message)
    Write-Host ""
    Write-Host "=========================================" -ForegroundColor Cyan
    Write-Host $Message -ForegroundColor Cyan
    Write-Host "=========================================" -ForegroundColor Cyan
}

function Write-TestStep {
    param([string]$Message)
    Write-Host "  → $Message" -ForegroundColor Yellow
}

function Write-TestSuccess {
    param([string]$Message)
    Write-Host "  ✅ $Message" -ForegroundColor Green
}

function Write-TestFailure {
    param([string]$Message)
    Write-Host "  ❌ $Message" -ForegroundColor Red
}

function Write-TestWarning {
    param([string]$Message)
    Write-Host "  ⚠️  $Message" -ForegroundColor Yellow
}

# Navigate to repo root
Set-Location $RepoRoot

Write-TestHeader "PRISM Fresh Installation Test"
Write-Host "Repository: $RepoRoot"
Write-Host "Python: $(python --version)"
Write-Host ""

# Test 1: Check if vendored pyedflib exists
Write-TestHeader "Test 1: Check Vendored pyedflib Structure"
Write-TestStep "Checking vendor/pyedflib directory..."

$VendorPyedflib = Join-Path $RepoRoot "vendor\pyedflib"
if (Test-Path $VendorPyedflib) {
    Write-TestSuccess "Vendored pyedflib found at: $VendorPyedflib"
    
    # Check for key files
    $InitFile = Join-Path $VendorPyedflib "__init__.py"
    $VersionFile = Join-Path $VendorPyedflib "version.py"
    
    if (Test-Path $InitFile) {
        Write-TestSuccess "Found __init__.py"
    } else {
        Write-TestFailure "Missing __init__.py"
    }
    
    if (Test-Path $VersionFile) {
        Write-TestSuccess "Found version.py"
    } else {
        Write-TestWarning "Missing version.py (may be optional)"
    }
    
    # List .pyd files (compiled Windows extensions)
    $PydFiles = Get-ChildItem -Path $VendorPyedflib -Filter "*.pyd" -Recurse
    if ($PydFiles.Count -gt 0) {
        Write-TestSuccess "Found $($PydFiles.Count) compiled .pyd file(s)"
        foreach ($pyd in $PydFiles) {
            Write-Host "      - $($pyd.Name)" -ForegroundColor DarkGray
        }
    } else {
        Write-TestFailure "No .pyd files found - vendored version may not work on Windows!"
    }
} else {
    Write-TestFailure "Vendored pyedflib NOT found at: $VendorPyedflib"
    Write-TestWarning "Vendored fallback will not be available"
}

# Test 2: Test vendored pyedflib import
if ($TestVendored) {
    Write-TestHeader "Test 2: Import Vendored pyedflib"
    Write-TestStep "Attempting to import pyedflib from vendor folder..."
    
    $TestScript = @"
import sys
from pathlib import Path

# Add vendor to path (as documented)
repo_root = Path(sys.argv[1]).resolve()
vendor_dir = repo_root / 'vendor'
sys.path.insert(0, str(vendor_dir))

try:
    import pyedflib
    print(f'SUCCESS: pyedflib version {pyedflib.__version__}')
    print(f'Location: {pyedflib.__file__}')
    if str(vendor_dir).lower() not in str(Path(pyedflib.__file__).resolve()).lower():
        raise RuntimeError('Imported pyedflib is not from vendor directory')
    
    # Test basic functionality
    print('Testing EdfReader class...', end=' ')
    assert hasattr(pyedflib, 'EdfReader')
    print('OK')
    
    print('Testing EdfWriter class...', end=' ')
    assert hasattr(pyedflib, 'EdfWriter')
    print('OK')
    
except ImportError as e:
    print(f'FAILED: Cannot import pyedflib: {e}')
    sys.exit(1)
except Exception as e:
    print(f'FAILED: Error testing pyedflib: {e}')
    sys.exit(1)
"@
    
    $TempTestFile = Join-Path $env:TEMP "test_vendored_pyedflib.py"
    Set-Content -Path $TempTestFile -Value $TestScript
    
    try {
        $output = & python $TempTestFile $RepoRoot 2>&1
        if ($LASTEXITCODE -eq 0) {
            Write-TestSuccess "Vendored pyedflib works!"
            Write-Host "      $output" -ForegroundColor DarkGray
        } else {
            Write-TestFailure "Vendored pyedflib import failed:"
            Write-Host "      $output" -ForegroundColor Red
        }
    } finally {
        Remove-Item -Path $TempTestFile -ErrorAction SilentlyContinue
    }
}

# Test 3: Test pip installation in fresh venv
if ($TestPip) {
    Write-TestHeader "Test 3: Fresh Virtual Environment with pip install"
    
    $TestVenvDir = Join-Path $env:TEMP "prism_test_venv_$(Get-Random)"
    Write-TestStep "Creating temporary venv at: $TestVenvDir"
    
    try {
        # Create venv
        & python -m venv $TestVenvDir
        if ($LASTEXITCODE -ne 0) {
            Write-TestFailure "Failed to create virtual environment"
        } else {
            Write-TestSuccess "Virtual environment created"
            
            # Try to install pyedflib
            Write-TestStep "Installing pyedflib via pip..."
            $PipExe = Join-Path $TestVenvDir "Scripts\pip.exe"
            $PythonExe = Join-Path $TestVenvDir "Scripts\python.exe"

            $pipStdout = Join-Path $env:TEMP "prism_pip_stdout_$(Get-Random).log"
            $pipStderr = Join-Path $env:TEMP "prism_pip_stderr_$(Get-Random).log"

            try {
                $pipProc = Start-Process -FilePath $PipExe -ArgumentList @("install", "pyedflib", "--disable-pip-version-check") -Wait -PassThru -NoNewWindow -RedirectStandardOutput $pipStdout -RedirectStandardError $pipStderr
                $installExitCode = $pipProc.ExitCode
                $installOutput = ""
                if (Test-Path $pipStdout) {
                    $installOutput += (Get-Content -Path $pipStdout -Raw)
                }
                if (Test-Path $pipStderr) {
                    if ($installOutput) {
                        $installOutput += "`n"
                    }
                    $installOutput += (Get-Content -Path $pipStderr -Raw)
                }
            } finally {
                if (Test-Path $pipStdout) {
                    Remove-Item -Path $pipStdout -ErrorAction SilentlyContinue
                }
                if (Test-Path $pipStderr) {
                    Remove-Item -Path $pipStderr -ErrorAction SilentlyContinue
                }
            }
            
            if ($installExitCode -eq 0) {
                Write-TestSuccess "pyedflib installed successfully via pip"
                
                # Test import
                Write-TestStep "Testing installed pyedflib..."
                $importTest = & $PythonExe -c "import pyedflib; print(f'Version: {pyedflib.__version__}')" 2>&1
                
                if ($LASTEXITCODE -eq 0) {
                    Write-TestSuccess "Import successful: $importTest"
                } else {
                    Write-TestFailure "Import failed: $importTest"
                }
            } else {
                Write-TestWarning "pip install failed (this is expected on some systems)"
                Write-Host "      Exit code: $installExitCode" -ForegroundColor DarkGray
                Write-Host "      Error: $installOutput" -ForegroundColor DarkGray
                Write-TestStep "Trying uv fallback in the same fresh venv..."

                if (Get-Command "uv" -ErrorAction SilentlyContinue) {
                    $uvStdout = Join-Path $env:TEMP "prism_uv_stdout_$(Get-Random).log"
                    $uvStderr = Join-Path $env:TEMP "prism_uv_stderr_$(Get-Random).log"
                    try {
                        $uvProc = Start-Process -FilePath "uv" -ArgumentList @("pip", "install", "--python", $PythonExe, "pyedflib") -Wait -PassThru -NoNewWindow -RedirectStandardOutput $uvStdout -RedirectStandardError $uvStderr
                        $uvExitCode = $uvProc.ExitCode
                        $uvOutput = ""
                        if (Test-Path $uvStdout) {
                            $uvOutput += (Get-Content -Path $uvStdout -Raw)
                        }
                        if (Test-Path $uvStderr) {
                            if ($uvOutput) {
                                $uvOutput += "`n"
                            }
                            $uvOutput += (Get-Content -Path $uvStderr -Raw)
                        }

                        if ($uvExitCode -eq 0) {
                            Write-TestSuccess "uv fallback installed pyedflib successfully"
                            $uvImportTest = & $PythonExe -c "import pyedflib; print(f'Version: {pyedflib.__version__}')" 2>&1
                            if ($LASTEXITCODE -eq 0) {
                                Write-TestSuccess "uv-installed import successful: $uvImportTest"
                            } else {
                                Write-TestFailure "uv install succeeded but import failed: $uvImportTest"
                            }
                        } else {
                            Write-TestWarning "uv fallback also failed"
                            Write-Host "      uv exit code: $uvExitCode" -ForegroundColor DarkGray
                            Write-Host "      uv output: $uvOutput" -ForegroundColor DarkGray
                            Write-TestStep "This is why we have the vendored version!"
                        }
                    } finally {
                        if (Test-Path $uvStdout) {
                            Remove-Item -Path $uvStdout -ErrorAction SilentlyContinue
                        }
                        if (Test-Path $uvStderr) {
                            Remove-Item -Path $uvStderr -ErrorAction SilentlyContinue
                        }
                    }
                } else {
                    Write-TestWarning "uv is not available in PATH"
                    Write-TestStep "This is why we have the vendored version!"
                }
            }
        }
    } finally {
        # Cleanup
        if (Test-Path $TestVenvDir) {
            Write-TestStep "Cleaning up test venv..."
            Remove-Item -Path $TestVenvDir -Recurse -Force -ErrorAction SilentlyContinue
        }
    }
}

# Test 4: Test current environment
Write-TestHeader "Test 4: Current Environment Status"
Write-TestStep "Checking current Python environment..."

# Test both system Python and venv Python
$systemTest = python -c "try:
    import pyedflib
    print(f'INSTALLED: pyedflib {pyedflib.__version__}')
    print(f'Location: {pyedflib.__file__}')
except ImportError:
    print('NOT INSTALLED')
" 2>&1

Write-Host "  System Python: $systemTest" -ForegroundColor Cyan

# Check venv Python if it exists
$VenvPython = Join-Path $RepoRoot ".venv\Scripts\python.exe"
if (Test-Path $VenvPython) {
    Write-TestStep "Checking .venv Python..."
    $venvTest = & $VenvPython -c "try:
    import pyedflib
    print(f'INSTALLED: pyedflib {pyedflib.__version__}')
    print(f'Location: {pyedflib.__file__}')
except ImportError:
    print('NOT INSTALLED')
" 2>&1
    Write-Host "  .venv Python: $venvTest" -ForegroundColor Green
} else {
    Write-TestWarning ".venv not found"
}

# Summary
Write-TestHeader "Summary"
Write-Host ""
Write-Host "✅ Vendored pyedflib: " -NoNewline
if (Test-Path $VendorPyedflib) {
    Write-Host "Available (Python 3.12 x64 only)" -ForegroundColor Yellow
} else {
    Write-Host "Missing" -ForegroundColor Red
}

Write-Host "✅ System Python: " -NoNewline
if ($systemTest -match "^INSTALLED:") {
    Write-Host "pyedflib is installed" -ForegroundColor Green
} else {
    Write-Host "pyedflib NOT installed" -ForegroundColor Yellow
}

if (Test-Path $VenvPython) {
    Write-Host "✅ .venv Python: " -NoNewline
    if ($venvTest -match "^INSTALLED:") {
        Write-Host "pyedflib is installed" -ForegroundColor Green
    } else {
        Write-Host "pyedflib NOT installed" -ForegroundColor Yellow
    }
}

Write-Host ""
Write-Host "Recommendations:" -ForegroundColor Cyan
Write-Host "  • Preferred: Install with 'uv pip install pyedflib' (works without C++ compiler)"
Write-Host "  • Alternative: Use regular pip if pre-built wheels available"
Write-Host "  • Always use the .venv Python: .venv\Scripts\python.exe"
Write-Host ""
