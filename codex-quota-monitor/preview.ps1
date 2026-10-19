$ErrorActionPreference = 'Stop'
Start-Process -FilePath (Join-Path $PSScriptRoot '.venv\Scripts\pythonw.exe') -ArgumentList @('-m', 'quota_monitor', '--preview-only') -WorkingDirectory $PSScriptRoot
