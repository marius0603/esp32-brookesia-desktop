param([switch]$Flash, [string]$Port = '', [switch]$Reconfigure)
$ErrorActionPreference = 'Stop'
$quotaRoot = Split-Path -Parent $PSScriptRoot
$quotaPython = Join-Path $quotaRoot '.venv\Scripts\python.exe'
$quotaArguments = @((Join-Path $PSScriptRoot 'build_firmware.py'))
if ($Reconfigure) { $quotaArguments += '--reconfigure' }
if ($Flash) {
    if (-not $Port) { throw '-Flash requires an explicit -Port, such as COM9.' }
    $quotaArguments += @('--flash', '--port', $Port)
}
& $quotaPython @quotaArguments
exit $LASTEXITCODE
