@echo off
setlocal
cd /d "%~dp0"

powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0setup.ps1"
if errorlevel 1 (
    echo.
    echo A instalacao nao foi concluida. Verifique a mensagem acima.
    pause
    exit /b 1
)

echo.
pause
