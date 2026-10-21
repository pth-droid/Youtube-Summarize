$ErrorActionPreference = 'Stop'
Set-Location -LiteralPath $PSScriptRoot
$appPython = Join-Path $PSScriptRoot '.venv\Scripts\python.exe'
if (-not (Test-Path -LiteralPath $appPython)) {
    & python -m venv .venv
    if ($LASTEXITCODE -ne 0) { throw 'Python could not create the app environment.' }
}
& $appPython -m pip install -r requirements-app.txt
if ($LASTEXITCODE -ne 0) { throw 'App dependencies could not be installed.' }
Write-Host 'Setup complete. Run start-app.ps1 to open Visual Learning.'
