[CmdletBinding()]
param(
    [string]$DataRoot = 'D:\AI\Project_SHION'
)

$ErrorActionPreference = 'Stop'
$repoRoot = $PSScriptRoot
$python = Join-Path $repoRoot 'training\.venv\Scripts\pythonw.exe'
if (-not (Test-Path -LiteralPath $python -PathType Leaf)) {
    $python = Join-Path $repoRoot 'training\.venv\Scripts\python.exe'
}
if (-not (Test-Path -LiteralPath $python -PathType Leaf)) { throw "SHION Python was not found: $python" }
if (-not [IO.Path]::IsPathRooted($DataRoot)) { throw 'SHION_DATA_ROOT must be an absolute path.' }

$mutex = New-Object Threading.Mutex($false, 'Local\ProjectSHIONDesktopCompanion')
if (-not $mutex.WaitOne(0, $false)) {
    Write-Host 'SHION Desktop Companion is already running.'
    exit 0
}
$env:SHION_DATA_ROOT = $DataRoot
try {
    & $python -m desktop_companion.app --data-root $DataRoot
} finally {
    $mutex.ReleaseMutex()
    $mutex.Dispose()
}
