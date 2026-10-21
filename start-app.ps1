param([int]$Port = 8765, [switch]$NoBrowser)
$ErrorActionPreference = 'Stop'
Set-Location -LiteralPath $PSScriptRoot
$appPython = Join-Path $PSScriptRoot '.venv\Scripts\python.exe'
if (-not (Test-Path -LiteralPath $appPython)) {
    Write-Host 'Run setup-app.ps1 once before starting the app.'
    exit 1
}
$appArguments = @('-m', 'visual_learning', '--port', $Port)
if ($NoBrowser) { $appArguments += '--no-browser' }
& $appPython @appArguments
exit $LASTEXITCODE
