#!/usr/bin/env pwsh
$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$Root      = Resolve-Path (Join-Path $ScriptDir "..")
$Vfs       = Join-Path $Root "vfs"
$Py        = "python"

function Run-Case {
    param([string]$Title, [string[]]$Arguments)
    Write-Host ""
    Write-Host "=== $Title ===" -ForegroundColor Cyan
    & $Py (Join-Path $Root "src\terminal.py") @Arguments
    Write-Host "Exit code: $LASTEXITCODE"
}

Run-Case "1. Минимальный VFS + полный стартовый скрипт" @(
    "--vfs", (Join-Path $Vfs "minimal.json"),
    "--script", (Join-Path $ScriptDir "startup_vfs.txt"))
Run-Case "2. Обычный VFS + стартовый скрипт" @(
    "--vfs", (Join-Path $Vfs "basic.json"),
    "--script", (Join-Path $ScriptDir "startup_vfs.txt"))
Run-Case "3. Глубокий VFS + стартовый скрипт" @(
    "--vfs", (Join-Path $Vfs "deep.json"),
    "--script", (Join-Path $ScriptDir "startup_vfs.txt"))
Run-Case "4. VFS с base64-файлом" @(
    "--vfs", (Join-Path $Vfs "binary.json"),
    "--script", (Join-Path $ScriptDir "startup_vfs.txt"))
Run-Case "5. Ошибка: VFS-файл не найден" @(
    "--vfs", (Join-Path $Vfs "no_such.json"))
Run-Case "6. Ошибка: неверный JSON" @(
    "--vfs", (Join-Path $Vfs "invalid.json"))
Run-Case "7. Ошибка: несуществующий стартовый скрипт" @(
    "--vfs", (Join-Path $Vfs "basic.json"),
    "--script", (Join-Path $ScriptDir "no_such_script.txt"))
Run-Case "8. Полный тест команд этапа 4" @(
    "--vfs", (Join-Path $Vfs "basic.json"),
    "--script", (Join-Path $ScriptDir "startup_stage4.txt"))