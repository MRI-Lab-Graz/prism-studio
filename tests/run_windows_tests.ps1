# Run all Windows-specific tests for PRISM validator
# This script activates the virtual environment and runs the Windows test suite

param(
    [switch]$Verbose,
    [switch]$Individual,
    [string]$TestFile = ""
)

Write-Host "=" -NoNewline -ForegroundColor Cyan
Write-Host ("=" * 69) -ForegroundColor Cyan
Write-Host "🪟 PRISM Windows Test Suite" -ForegroundColor Cyan
Write-Host "=" -NoNewline -ForegroundColor Cyan
Write-Host ("=" * 69) -ForegroundColor Cyan

# Check if running on Windows
if (-not $IsWindows -and $PSVersionTable.Platform -ne "Win32NT") {
    Write-Host "⚠️  Warning: Not running on Windows!" -ForegroundColor Yellow
    Write-Host "Tests may behave differently on non-Windows platforms." -ForegroundColor Yellow
    Write-Host ""
}

# Get script directory and project root
$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$ProjectRoot = Split-Path -Parent $ScriptDir
$TestsDir = Join-Path $ProjectRoot "tests"
$VenvPath = Join-Path $ProjectRoot ".venv"
$VenvActivate = Join-Path $VenvPath "Scripts\Activate.ps1"

# Check for virtual environment
if (Test-Path $VenvActivate) {
    Write-Host "✅ Activating virtual environment..." -ForegroundColor Green
    & $VenvActivate
} else {
    Write-Host "⚠️  Virtual environment not found at: $VenvPath" -ForegroundColor Yellow
    Write-Host "   Using system Python. Run setup.ps1 to create venv." -ForegroundColor Yellow
}

Write-Host ""

# Define test files
$TestFiles = @(
    @{
        File = "test_windows_compatibility.py"
        Name = "Core Windows Compatibility"
        Desc = "Platform detection, path handling, filename validation"
    },
    @{
        File = "test_windows_paths.py"
        Name = "Windows Path & Filename Tests"
        Desc = "Drive letters, UNC paths, reserved names, special chars"
    },
    @{
        File = "test_windows_web_uploads.py"
        Name = "Windows Web Upload Tests"
        Desc = "Upload handling, session management, file security"
    },
    @{
        File = "test_windows_datasets.py"
        Name = "Windows Dataset Validation"
        Desc = "Case sensitivity, system files, BIDS compatibility"
    }
)

# Function to run a single test
function Run-Test {
    param($TestInfo)
    
    $TestPath = Join-Path $TestsDir $TestInfo.File
    
    if (-not (Test-Path $TestPath)) {
        Write-Host "❌ Test file not found: $($TestInfo.File)" -ForegroundColor Red
        return $false
    }
    
    Write-Host "📋 $($TestInfo.Name)" -ForegroundColor Cyan
    Write-Host "   $($TestInfo.Desc)" -ForegroundColor Gray
    Write-Host ""
    
    $Output = & python $TestPath 2>&1
    $ExitCode = $LASTEXITCODE
    
    if ($Verbose) {
        Write-Host $Output
    }
    
    if ($ExitCode -eq 0) {
        Write-Host "✅ PASS" -ForegroundColor Green
        return $true
    } else {
        Write-Host "❌ FAIL" -ForegroundColor Red
        if (-not $Verbose) {
            Write-Host $Output
        }
        return $false
    }
}

# Run tests
$Results = @{}

if ($TestFile) {
    # Run specific test file
    $TestInfo = $TestFiles | Where-Object { $_.File -eq $TestFile }
    if ($TestInfo) {
        $Success = Run-Test -TestInfo $TestInfo
        $Results[$TestInfo.Name] = $Success
    } else {
        Write-Host "❌ Unknown test file: $TestFile" -ForegroundColor Red
        Write-Host ""
        Write-Host "Available tests:" -ForegroundColor Yellow
        foreach ($Test in $TestFiles) {
            Write-Host "  - $($Test.File)" -ForegroundColor Gray
        }
        exit 1
    }
} elseif ($Individual) {
    # Run tests individually with detailed output
    Write-Host "Running tests individually..." -ForegroundColor Cyan
    Write-Host ""
    
    foreach ($TestInfo in $TestFiles) {
        Write-Host ""
        Write-Host "-" -NoNewline -ForegroundColor Gray
        Write-Host ("-" * 69) -ForegroundColor Gray
        $Success = Run-Test -TestInfo $TestInfo
        $Results[$TestInfo.Name] = $Success
        Write-Host ""
    }
} else {
    # Run all tests using master runner
    Write-Host "Running all tests via master runner..." -ForegroundColor Cyan
    Write-Host ""
    
    $RunnerPath = Join-Path $TestsDir "run_windows_tests.py"
    
    if (Test-Path $RunnerPath) {
        & python $RunnerPath
        $ExitCode = $LASTEXITCODE
        
        Write-Host ""
        if ($ExitCode -eq 0) {
            Write-Host "🎉 All Windows tests passed!" -ForegroundColor Green
        } else {
            Write-Host "❌ Some Windows tests failed" -ForegroundColor Red
        }
        
        exit $ExitCode
    } else {
        Write-Host "❌ Master runner not found: $RunnerPath" -ForegroundColor Red
        Write-Host "   Running tests individually instead..." -ForegroundColor Yellow
        Write-Host ""
        
        foreach ($TestInfo in $TestFiles) {
            $Success = Run-Test -TestInfo $TestInfo
            $Results[$TestInfo.Name] = $Success
            Write-Host ""
        }
    }
}

# Summary (if individual tests were run)
if ($Results.Count -gt 0) {
    Write-Host ""
    Write-Host "=" -NoNewline -ForegroundColor Cyan
    Write-Host ("=" * 69) -ForegroundColor Cyan
    Write-Host "📊 Test Summary" -ForegroundColor Cyan
    Write-Host "=" -NoNewline -ForegroundColor Cyan
    Write-Host ("=" * 69) -ForegroundColor Cyan
    
    $Passed = 0
    $Total = $Results.Count
    
    foreach ($Key in $Results.Keys) {
        $Success = $Results[$Key]
        if ($Success) {
            Write-Host "✅ PASS" -NoNewline -ForegroundColor Green
            $Passed++
        } else {
            Write-Host "❌ FAIL" -NoNewline -ForegroundColor Red
        }
        Write-Host " - $Key" -ForegroundColor White
    }
    
    Write-Host ""
    Write-Host "Result: $Passed/$Total test suites passed" -ForegroundColor $(if ($Passed -eq $Total) { "Green" } else { "Red" })
    
    if ($Passed -eq $Total) {
        exit 0
    } else {
        exit 1
    }
}
