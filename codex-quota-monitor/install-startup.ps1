param([switch]$Remove)
$ErrorActionPreference = 'Stop'
$quotaShortcut = Join-Path ([Environment]::GetFolderPath('Startup')) 'Codex Quota Monitor.lnk'
if ($Remove) {
    if (Test-Path -LiteralPath $quotaShortcut) { Remove-Item -LiteralPath $quotaShortcut }
    Write-Output 'Quota monitor startup entry removed.'
    exit
}
$quotaShell = New-Object -ComObject WScript.Shell
$quotaLink = $quotaShell.CreateShortcut($quotaShortcut)
$quotaLink.TargetPath = Join-Path $PSScriptRoot '.venv\Scripts\pythonw.exe'
$quotaLink.Arguments = '-m quota_monitor'
$quotaLink.WorkingDirectory = $PSScriptRoot
$quotaLink.Description = 'Read Codex quota and send it to the ESP32 display'
$quotaLink.WindowStyle = 7
$quotaLink.Save()
Write-Output 'Quota monitor will start at the next Windows sign-in.'
