$ErrorActionPreference = "Stop"

$LabDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$ProjectRoot = Split-Path -Parent $LabDir
$BuildLab = Join-Path $LabDir "build_lab.py"

Set-Location $ProjectRoot

Write-Host "Validando laboratorio..."
python $BuildLab doctor
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }

python $BuildLab validate
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }

python $BuildLab package-status
exit $LASTEXITCODE
