@echo off
setlocal

set "SCRIPT_DIR=%~dp0"
set "ROOT=%SCRIPT_DIR%.."
set "VFS=%ROOT%\vfs"
set "PY=python"

echo.
echo === 1. Минимальный VFS + полный стартовый скрипт ===
%PY% "%ROOT%\src\terminal.py" --vfs "%VFS%\minimal.json" --script "%SCRIPT_DIR%startup_vfs.txt"
echo Exit code: %ERRORLEVEL%

echo.
echo === 2. Обычный VFS + стартовый скрипт ===
%PY% "%ROOT%\src\terminal.py" --vfs "%VFS%\basic.json" --script "%SCRIPT_DIR%startup_vfs.txt"
echo Exit code: %ERRORLEVEL%

echo.
echo === 3. Глубокий VFS + стартовый скрипт ===
%PY% "%ROOT%\src\terminal.py" --vfs "%VFS%\deep.json" --script "%SCRIPT_DIR%startup_vfs.txt"
echo Exit code: %ERRORLEVEL%

echo.
echo === 4. VFS с base64-файлом ===
%PY% "%ROOT%\src\terminal.py" --vfs "%VFS%\binary.json" --script "%SCRIPT_DIR%startup_vfs.txt"
echo Exit code: %ERRORLEVEL%

echo.
echo === 5. Ошибка: VFS-файл не найден ===
%PY% "%ROOT%\src\terminal.py" --vfs "%VFS%\no_such.json"
echo Exit code: %ERRORLEVEL%

echo.
echo === 6. Ошибка: неверный JSON ===
%PY% "%ROOT%\src\terminal.py" --vfs "%VFS%\invalid.json"
echo Exit code: %ERRORLEVEL%

echo.
echo === 7. Ошибка: несуществующий стартовый скрипт ===
%PY% "%ROOT%\src\terminal.py" --vfs "%VFS%\basic.json" --script "%SCRIPT_DIR%no_such_script.txt"
echo Exit code: %ERRORLEVEL%

echo.
echo === 8. Полный тест команд этапа 4 ===
%PY% "%ROOT%\src\terminal.py" --vfs "%VFS%\basic.json" --script "%SCRIPT_DIR%startup_stage4.txt"
echo Exit code: %ERRORLEVEL%

echo.
echo === 9. Копирование cp (этап 5) ===
%PY% "%ROOT%\src\terminal.py" --vfs "%VFS%\basic.json" --script "%SCRIPT_DIR%startup_stage5.txt"
echo Exit code: %ERRORLEVEL%

echo.
echo === Все тесты завершены ===
pause >nul
endlocal