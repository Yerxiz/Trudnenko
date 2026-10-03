@echo off
REM Прогон эмулятора со всеми поддерживаемыми параметрами CLI.
setlocal enabledelayedexpansion

set SCRIPT_DIR=%~dp0
set ROOT=%SCRIPT_DIR%..
set VFS=%ROOT%\vfs
set PY=python

echo.
echo === 1. Только --vfs ===
%PY% "%ROOT%\terminal.py" --vfs "%VFS%"
echo Exit code: %ERRORLEVEL%

echo.
echo === 2. --vfs + корректный стартовый скрипт ===
%PY% "%ROOT%\terminal.py" --vfs "%VFS%" --script "%SCRIPT_DIR%startup_demo.txt"
echo Exit code: %ERRORLEVEL%

echo.
echo === 3. --vfs + скрипт с ошибками ===
%PY% "%ROOT%\terminal.py" --vfs "%VFS%" --script "%SCRIPT_DIR%startup_with_errors.txt"
echo Exit code: %ERRORLEVEL%

echo.
echo === 4. Ошибка: несуществующий VFS ===
%PY% "%ROOT%\terminal.py" --vfs "%ROOT%\no_such_dir"
echo Exit code: %ERRORLEVEL%

echo.
echo === 5. Ошибка: несуществующий скрипт ===
%PY% "%ROOT%\terminal.py" --vfs "%VFS%" --script "%SCRIPT_DIR%\no_such_script.txt"
echo Exit code: %ERRORLEVEL%

echo.
echo === Все тесты завершены. Нажмите любую клавишу для выхода ===

pause >nul
endlocal