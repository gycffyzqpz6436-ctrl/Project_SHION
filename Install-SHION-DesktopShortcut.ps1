[CmdletBinding()]
param()

$ErrorActionPreference = 'Stop'
$launcher = Join-Path $PSScriptRoot 'Start-SHION.ps1'
if (-not (Test-Path -LiteralPath $launcher -PathType Leaf)) { throw "Launcher not found: $launcher" }

$desktop = [Environment]::GetFolderPath([Environment+SpecialFolder]::DesktopDirectory)
$shortcutPath = Join-Path $desktop 'Project SHION.lnk'
$powerShell = Join-Path $PSHOME 'powershell.exe'
$shell = New-Object -ComObject WScript.Shell
$shortcut = $shell.CreateShortcut($shortcutPath)
$shortcut.TargetPath = $powerShell
$shortcut.Arguments = "-NoProfile -ExecutionPolicy Bypass -File `"$launcher`""
$shortcut.WorkingDirectory = $PSScriptRoot
$shortcut.Description = 'Open Project SHION Workspace'
$shortcut.Save()
Write-Host "Created: $shortcutPath"
