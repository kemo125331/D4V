$ErrorActionPreference = "Stop"

$repoRoot = Split-Path -Parent $PSScriptRoot
Set-Location $repoRoot
$desktopEntry = Join-Path $repoRoot "src\d4v\desktop.py"
$modelsDir = Join-Path $repoRoot "models"

Write-Host "Syncing build dependencies..."
uv sync --group build
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }

Write-Host "Building standalone Windows executable..."
uv run pyinstaller `
  --noconfirm `
  --clean `
  --onefile `
  --windowed `
  --name D4V `
  --specpath build\pyinstaller `
  --paths src `
  --collect-submodules winocr `
  --add-data "${modelsDir};models" `
  $desktopEntry
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }

Write-Host "Build complete: dist\\D4V.exe"
