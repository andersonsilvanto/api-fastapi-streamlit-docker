@echo off
setlocal
chcp 65001 >nul
cd /d "%~dp0"

where powershell.exe >nul 2>&1
if errorlevel 1 (
    echo ERRO: Windows PowerShell nao foi encontrado.
    pause
    exit /b 1
)

powershell.exe -NoLogo -NoProfile -ExecutionPolicy Bypass -File "%~dp0setup.ps1"
if errorlevel 1 (
    echo.
    echo A instalacao nao foi concluida. Verifique a mensagem acima.
    pause
    exit /b 1
)

echo.
pause
