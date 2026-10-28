@echo off
setlocal
cd /d "%~dp0"

call "%~dp0k8s\deploy-k8s.bat"
exit /b %errorlevel%
