[CmdletBinding()]
param(
    [string]$DataRoot = 'D:\AI\Project_SHION',
    [switch]$NoBrowser
)

$ErrorActionPreference = 'Stop'
$repoRoot = $PSScriptRoot
$python = Join-Path $repoRoot 'training\.venv\Scripts\python.exe'
$serverScript = Join-Path $repoRoot 'app\server.py'
$statusUrl = 'http://127.0.0.1:8765/api/status'
$workspaceUrl = 'http://127.0.0.1:8765/#/chat'
$modelAlias = 'gemma4_12b_heretic_ja_v2_manual'

if (-not (Test-Path -LiteralPath $python -PathType Leaf)) { throw "SHION Python was not found: $python" }
if (-not (Test-Path -LiteralPath $serverScript -PathType Leaf)) { throw "SHION server was not found: $serverScript" }
if (-not [IO.Path]::IsPathRooted($DataRoot)) { throw 'SHION_DATA_ROOT must be an absolute path.' }

function Get-ShionStatus {
    # /api/status may spend up to two seconds probing the lazy Voice adapter.
    # Keep the launcher timeout above that boundary to avoid a false startup timeout.
    try { return Invoke-RestMethod -Uri $statusUrl -TimeoutSec 5 }
    catch { return $null }
}

$existing = Get-ShionStatus
if ($existing) {
    Write-Host "Project SHION is already running ($($existing.state), $($existing.model_alias))."
    if (-not $NoBrowser) { Start-Process $workspaceUrl }
    exit 0
}

$listener = Get-NetTCPConnection -LocalAddress 127.0.0.1 -LocalPort 8765 -State Listen -ErrorAction SilentlyContinue
if ($listener) {
    throw "Port 8765 is owned by PID $($listener.OwningProcess), but it did not answer as Project SHION. Nothing was stopped."
}

$logRoot = Join-Path $DataRoot 'logs'
New-Item -ItemType Directory -Path $logRoot -Force | Out-Null
$stdout = Join-Path $logRoot 'shion-workspace.stdout.log'
$stderr = Join-Path $logRoot 'shion-workspace.stderr.log'
$previousDataRoot = $env:SHION_DATA_ROOT
$env:SHION_DATA_ROOT = $DataRoot
try {
    $process = Start-Process -FilePath $python -ArgumentList @('app\server.py', '--model', $modelAlias) -WorkingDirectory $repoRoot -WindowStyle Hidden -RedirectStandardOutput $stdout -RedirectStandardError $stderr -PassThru
} finally {
    if ($null -eq $previousDataRoot) { Remove-Item Env:SHION_DATA_ROOT -ErrorAction SilentlyContinue }
    else { $env:SHION_DATA_ROOT = $previousDataRoot }
}

$deadline = (Get-Date).AddMinutes(3)
do {
    Start-Sleep -Milliseconds 750
    $status = Get-ShionStatus
    if ($status -and $status.state -eq 'Ready') { break }
    if ($process.HasExited) { throw "Project SHION exited during startup. See $stderr" }
} while ((Get-Date) -lt $deadline)

if (-not $status -or $status.state -ne 'Ready') {
    throw "Project SHION did not become Ready within 3 minutes. The process was left intact for diagnosis. See $stderr"
}

Write-Host "Project SHION is Ready ($($status.model_alias))."
Write-Host "History: $($status.history.state)"
Write-Host 'Voice remains lazy; Stable Diffusion was not started.'
if (-not $NoBrowser) { Start-Process $workspaceUrl }
