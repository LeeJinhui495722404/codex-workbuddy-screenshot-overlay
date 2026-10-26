# -*- coding: utf-8 -*-
[CmdletBinding()]
param(
    [ValidateSet('Codex', 'WorkBuddy', 'Both')]
    [string]$Target = 'Both',
    [string]$InstallRoot = (Join-Path $env:LOCALAPPDATA 'CodexScreenshotHelpers'),
    [string]$PythonPath = '',
    [switch]$NoAutostart,
    [switch]$ValidateOnly
)

$ErrorActionPreference = 'Stop'
$assetRoot = Join-Path (Split-Path -Parent $PSScriptRoot) 'assets\helper'

if (-not (Test-Path -LiteralPath $assetRoot -PathType Container)) {
    throw "缺少截图助手资源：$assetRoot"
}

function Resolve-PythonRunner {
    param([string]$Requested)
    $candidates = @()
    if ($Requested) { $candidates += $Requested }
    foreach ($name in 'pythonw.exe', 'python.exe') {
        $command = Get-Command $name -ErrorAction SilentlyContinue | Select-Object -First 1
        if ($command) { $candidates += $command.Source }
    }
    $candidates += 'C:\ProgramData\miniconda3\pythonw.exe', 'C:\ProgramData\miniconda3\python.exe',
                   'C:\ProgramData\anaconda3\pythonw.exe', 'C:\ProgramData\anaconda3\python.exe'
    foreach ($candidate in $candidates | Select-Object -Unique) {
        if (Test-Path -LiteralPath $candidate -PathType Leaf) {
            & $candidate -c 'import PIL' 2>$null
            if ($LASTEXITCODE -eq 0) { return (Resolve-Path -LiteralPath $candidate).Path }
        }
    }
    throw '未找到带 Pillow 的 Python。请安装 Python 与 Pillow，或使用 -PythonPath 指定 pythonw.exe / python.exe。'
}

function Write-Launcher {
    param([string]$Name, [string]$ScriptName, [string]$Runner, [string]$Root)
    $runnerLiteral = $Runner.Replace('"', '""')
    $scriptLiteral = (Join-Path $Root $ScriptName).Replace('"', '""')
    $content = @"
Option Explicit
Dim command
command = Chr(34) & "$runnerLiteral" & Chr(34) & " " & Chr(34) & "$scriptLiteral" & Chr(34)
CreateObject("WScript.Shell").Run command, 0, False
"@
    $path = Join-Path $Root $Name
    Set-Content -LiteralPath $path -Value $content -Encoding ascii
    return $path
}

function New-Shortcut {
    param([string]$Path, [string]$Launcher, [string]$Description)
    $shortcut = $script:shell.CreateShortcut($Path)
    $shortcut.TargetPath = "$env:WINDIR\System32\wscript.exe"
    $shortcut.Arguments = '"' + $Launcher + '"'
    $shortcut.WorkingDirectory = $script:installPath
    $shortcut.Description = $Description
    $shortcut.Save()
}

$python = Resolve-PythonRunner $PythonPath
if ($ValidateOnly) {
    Write-Output "验证通过：将使用 $python；资源目录为 $assetRoot"
    return
}
New-Item -ItemType Directory -Path $InstallRoot -Force | Out-Null
$installPath = (Resolve-Path -LiteralPath $InstallRoot).Path
Copy-Item -LiteralPath (Join-Path $assetRoot 'attach_capture.ps1') -Destination $installPath -Force
Get-ChildItem -LiteralPath $assetRoot -Filter '*.py' -File | Copy-Item -Destination $installPath -Force

$shell = New-Object -ComObject WScript.Shell
$targets = if ($Target -eq 'Both') { @('Codex', 'WorkBuddy') } else { @($Target) }
foreach ($item in $targets) {
    $scriptName = if ($item -eq 'Codex') { 'codex_screenshot_overlay.py' } else { 'workbuddy_screenshot_overlay.py' }
    $launcher = Write-Launcher "Start-$item-Screenshot.vbs" $scriptName $python $installPath
    $desktopName = "启动 $item 截图助手.lnk"
    New-Shortcut (Join-Path ([Environment]::GetFolderPath('Desktop')) $desktopName) $launcher "手动启动 $item 截图助手"
    New-Shortcut (Join-Path ([Environment]::GetFolderPath('Programs')) "$item 截图助手.lnk") $launcher "手动启动 $item 截图助手"
    if (-not $NoAutostart) {
        New-Shortcut (Join-Path ([Environment]::GetFolderPath('Startup')) "$item 截图助手.lnk") $launcher "登录后启动，等待 $item 打开"
    }
}

Write-Output "已安装 $($targets -join '、') 截图助手。安装目录：$installPath"
