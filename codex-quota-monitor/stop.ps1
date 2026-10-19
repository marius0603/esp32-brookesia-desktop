$ErrorActionPreference = 'Stop'
$quotaRuntime = Join-Path $PSScriptRoot 'runtime'
New-Item -ItemType Directory -Path $quotaRuntime -Force | Out-Null
Set-Content -LiteralPath (Join-Path $quotaRuntime 'stop.request') -Value 'stop' -Encoding ascii
Write-Output 'Stop requested; the collector will exit after the active read completes (up to 35 seconds).'
