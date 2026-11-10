param([switch]$InstallShortcut)
$ErrorActionPreference = 'Stop'
$quotaRoot = $PSScriptRoot
$quotaPython = Join-Path $quotaRoot '.venv\Scripts\pythonw.exe'
if (-not (Test-Path -LiteralPath $quotaPython)) { throw 'Run setup.ps1 to create this project Python environment first.' }
$quotaPackage = Get-AppxPackage -Name OpenAI.Codex
if (-not $quotaPackage) { throw 'The Codex desktop Store package was not found.' }
$quotaManifest = Get-AppxPackageManifest $quotaPackage
$quotaApp = $quotaManifest.SelectSingleNode("//*[local-name()='Application' and @Id='App']")
if (-not $quotaApp) { throw 'Cannot find the Codex desktop application entry.' }
if ($InstallShortcut) {
    $quotaShortcut = Join-Path ([Environment]::GetFolderPath('Desktop')) 'Codex (device sync).lnk'
    $quotaShell = New-Object -ComObject WScript.Shell
    $quotaLink = $quotaShell.CreateShortcut($quotaShortcut)
    $quotaLink.TargetPath = Join-Path $env:SystemRoot 'System32\WindowsPowerShell\v1.0\powershell.exe'
    $quotaLink.Arguments = '-NoProfile -ExecutionPolicy Bypass -WindowStyle Hidden -File "' + $PSCommandPath + '"'
    $quotaLink.WorkingDirectory = $quotaRoot
    $quotaLink.Description = 'Open Codex and listen for ESP32 quota requests until Codex exits'
    $quotaExecutable = Join-Path $quotaPackage.InstallLocation ($quotaApp.GetAttribute('Executable'))
    $quotaLink.IconLocation = $quotaExecutable + ',0'
    $quotaLink.WindowStyle = 7
    $quotaLink.Save()
    Write-Output "Created: $quotaShortcut"
    exit
}
# Package-family activation remains valid when the desktop app is updated.
Start-Process -FilePath explorer.exe -ArgumentList ('shell:AppsFolder\' + $quotaPackage.PackageFamilyName + '!' + $quotaApp.GetAttribute('Id'))
Start-Process -FilePath $quotaPython -ArgumentList @('-m', 'quota_monitor', '--wait-for-codex') -WorkingDirectory $quotaRoot -WindowStyle Hidden
