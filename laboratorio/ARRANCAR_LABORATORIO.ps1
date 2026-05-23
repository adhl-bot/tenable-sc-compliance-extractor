$ErrorActionPreference = "Stop"

$LabDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$ProjectRoot = Split-Path -Parent $LabDir
$BuildLab = Join-Path $LabDir "build_lab.py"

Set-Location $ProjectRoot

Write-Host "Arrancando laboratorio..."
python $BuildLab up
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }

python $BuildLab doctor
exit $LASTEXITCODE
