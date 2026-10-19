param([string]$PythonPath = '')
$ErrorActionPreference = 'Stop'
if (-not $PythonPath) {
    $quotaBundledPython = Join-Path $env:USERPROFILE '.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe'
    if (Test-Path -LiteralPath $quotaBundledPython) { $PythonPath = $quotaBundledPython }
    else { $PythonPath = (Get-Command python -ErrorAction Stop).Source }
}
Push-Location $PSScriptRoot
try {
    if (-not (Test-Path -LiteralPath '.venv\Scripts\python.exe')) {
        & $PythonPath -m venv .venv
        if ($LASTEXITCODE -ne 0) { throw 'Could not create Python environment' }
    }
    & '.\.venv\Scripts\python.exe' -m pip install -r requirements.txt
    if ($LASTEXITCODE -ne 0) { throw 'Could not install Python dependencies' }
    & '.\.venv\Scripts\python.exe' -m quota_monitor --once
    if ($LASTEXITCODE -ne 0) { throw 'Quota probe failed. Check Codex login and runtime\monitor.log.' }
} finally { Pop-Location }
