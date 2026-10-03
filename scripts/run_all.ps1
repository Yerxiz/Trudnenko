#!/usr/bin/env pwsh
# Прогон эмулятора со всеми поддерживаемыми параметрами CLI.

$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$Root      = Resolve-Path (Join-Path $ScriptDir "..")
$Vfs       = Join-Path $Root "vfs"
$Py        = "python"

function Run-Case {
    param([string]$Title, [string[]]$Arguments)
    Write-Host ""
    Write-Host "=== $Title ===" -ForegroundColor Cyan
    & $Py (Join-Path $Root "src\shell.py") @Arguments
    Write-Host "Exit code: $LASTEXITCODE"
}

Run-Case "1. Только --vfs" @("--vfs", $Vfs)
Run-Case "2. --vfs + корректный стартовый скрипт" @(
    "--vfs", $Vfs, "--script", (Join-Path $ScriptDir "startup_demo.txt"))
Run-Case "3. --vfs + скрипт с ошибками" @(
    "--vfs", $Vfs, "--script", (Join-Path $ScriptDir "startup_with_errors.txt"))
Run-Case "4. Ошибка: несуществующий VFS" @(
    "--vfs", (Join-Path $Root "no_such_dir"))
Run-Case "5. Ошибка: несуществующий скрипт" @(
    "--vfs", $Vfs, "--script", (Join-Path $ScriptDir "no_such_script.txt"))