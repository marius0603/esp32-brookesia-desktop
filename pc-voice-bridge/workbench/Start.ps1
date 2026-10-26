param([switch]$NoBrowser)
$ErrorActionPreference='Stop'
$speechRoot=$PSScriptRoot
$speechUrl='http://127.0.0.1:7860'
try { $speechHealth=Invoke-RestMethod "$speechUrl/api/health" -TimeoutSec 2 } catch { $speechHealth=$null }
if ($speechHealth -and $speechHealth.app -ne 'qwen-speech-local') { throw 'Port 7860 is being used by another application' }
if (-not $speechHealth) {
    $env:TEMP=Join-Path $speechRoot 'temp'
    $env:TMP=$env:TEMP
    $env:PYTHONUTF8='1'
    Start-Process -FilePath (Join-Path $speechRoot 'envs/tts/Scripts/python.exe') -ArgumentList @('-X','utf8',(Join-Path $speechRoot 'scripts/server.py')) -WorkingDirectory $speechRoot -WindowStyle Hidden -RedirectStandardOutput (Join-Path $speechRoot 'logs/server.log') -RedirectStandardError (Join-Path $speechRoot 'logs/server-error.log') | Out-Null
    $speechReady=$false
    for ($speechTry=0;$speechTry -lt 20;$speechTry++) {
        Start-Sleep -Milliseconds 500
        try { $speechHealth=Invoke-RestMethod "$speechUrl/api/health" -TimeoutSec 2; if ($speechHealth.app -eq 'qwen-speech-local') { $speechReady=$true;break } } catch {}
    }
    if (-not $speechReady) { throw 'Could not start; see logs/server-error.log' }
}
Write-Output "Ready: $speechUrl"
if (-not $NoBrowser) { Start-Process "$speechUrl/assistant" }
