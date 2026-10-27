$ErrorActionPreference='Stop'
$speechRoot=$PSScriptRoot
$speechPidFile=Join-Path $speechRoot 'logs/server.pid'
if (-not (Test-Path -LiteralPath $speechPidFile)) { Write-Output 'Not running';exit }
$speechServerId=[int](Get-Content -LiteralPath $speechPidFile)
$speechServer=Get-CimInstance Win32_Process -Filter "ProcessId=$speechServerId"
if (-not $speechServer) { Write-Output 'Already stopped';exit }
if (-not $speechServer.CommandLine.Contains((Join-Path $speechRoot 'scripts/server.py'))) { throw 'Process identity changed; refusing to stop another application' }
$speechPythonPaths=@((Join-Path $speechRoot 'python/python.exe'),(Join-Path $speechRoot 'envs/tts/Scripts/python.exe'),(Join-Path $speechRoot 'envs/asr/Scripts/python.exe'))
# Windows virtual environments launch an additional Python process. Stop both
# levels so an in-progress generation cannot retain GPU memory after shutdown.
Get-CimInstance Win32_Process | Where-Object { $_.ExecutablePath -in $speechPythonPaths -and $_.CommandLine -and ($_.CommandLine.Contains((Join-Path $speechRoot 'scripts/worker.py')) -or $_.CommandLine.Contains((Join-Path $speechRoot 'scripts/engine_worker.py'))) } | ForEach-Object { Stop-Process -Id $_.ProcessId -ErrorAction SilentlyContinue }
Stop-Process -Id $speechServerId -ErrorAction Stop
Write-Output 'Stopped'
