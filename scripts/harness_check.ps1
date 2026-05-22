$ErrorActionPreference = "Stop"

$Root = Split-Path -Parent $PSScriptRoot
Set-Location $Root

Write-Host "=== Harness check ==="
Write-Host "Project: $Root"

$requiredPaths = @(
    "agents.md",
    "README.md",
    "ESTANDARES_ADOPTADOS.md",
    "HARNESS_DESARROLLO.md",
    "extract_compliance.py",
    "tenable_sc_phase1",
    "tests"
)

foreach ($path in $requiredPaths) {
    if (-not (Test-Path $path)) {
        throw "Missing required path: $path"
    }
}

$pythonCandidates = @(
    "C:\Users\Alberto\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe",
    "python",
    "py"
)

$python = $null
foreach ($candidate in $pythonCandidates) {
    try {
        $cmd = Get-Command $candidate -ErrorAction Stop
        $python = $cmd.Source
        break
    }
    catch {
        if (Test-Path $candidate) {
            $python = $candidate
            break
        }
    }
}

if (-not $python) {
    throw "Python executable not found"
}

Write-Host "Python: $python"

Write-Host "Running unit tests..."
& $python -m unittest discover -s tests
if ($LASTEXITCODE -ne 0) {
    throw "Unit tests failed"
}

Write-Host "Checking CLI help..."
& $python extract_compliance.py --help | Out-Null
if ($LASTEXITCODE -ne 0) {
    throw "CLI help failed"
}

Write-Host "=== Harness check OK ==="
