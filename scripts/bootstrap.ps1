param([switch]$InstallDependencies)
$ErrorActionPreference = 'Stop'
$kitRoot = Split-Path -Parent $PSScriptRoot
Set-Location -LiteralPath $kitRoot
if (-not (Get-Command python -ErrorAction SilentlyContinue)) {
    throw 'Python is required. Install Python 3.10+ with PATH enabled, then reopen Codex.'
}
if (-not (Test-Path -LiteralPath '.venv/Scripts/python.exe')) {
    & python -m venv .venv
    if ($LASTEXITCODE -ne 0) { throw 'Unable to create the local Python environment.' }
}
$kitPython = Join-Path $kitRoot '.venv/Scripts/python.exe'
if ($InstallDependencies) {
    & $kitPython -m pip install -r requirements.txt
    if ($LASTEXITCODE -ne 0) { throw 'Dependency installation failed; no automatic retry.' }
}
& $kitPython -B scripts/vocab.py init
if ($LASTEXITCODE -ne 0) { throw 'Initialization failed.' }
& $kitPython -B scripts/vocab.py doctor
if ($LASTEXITCODE -ne 0) { throw 'Environment check failed.' }
