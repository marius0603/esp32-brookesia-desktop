param([switch]$Preview)
$ErrorActionPreference = 'Stop'
$quotaRoot = $PSScriptRoot
$quotaPython = Join-Path $quotaRoot '.venv\Scripts\pythonw.exe'
if (-not (Test-Path -LiteralPath $quotaPython)) { throw 'Project environment missing. Run setup.ps1 first.' }
if (Test-Path -LiteralPath (Join-Path $quotaRoot 'runtime\stop.request')) {
    Remove-Item -LiteralPath (Join-Path $quotaRoot 'runtime\stop.request')
}
# The Python lock prevents duplicate collectors, including simultaneous startup launches.
Start-Process -FilePath $quotaPython -ArgumentList @('-m', 'quota_monitor') -WorkingDirectory $quotaRoot -WindowStyle Hidden
if ($Preview) {
    Start-Process -FilePath $quotaPython -ArgumentList @('-m', 'quota_monitor', '--preview-only') -WorkingDirectory $quotaRoot
}
Write-Output 'Quota monitor started. Logs: runtime\monitor.log'
