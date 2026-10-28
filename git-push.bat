@echo off
setlocal
chcp 65001 >nul
cd /d "%~dp0"

where git >nul 2>&1
if errorlevel 1 (
    echo ERRO: Git nao foi encontrado no PATH.
    exit /b 1
)

git rev-parse --show-toplevel >nul 2>&1
if errorlevel 1 (
    echo ERRO: Esta pasta nao pertence a um repositorio Git.
    exit /b 1
)

git remote get-url origin >nul 2>&1
if errorlevel 1 (
    echo ERRO: O remoto origin nao esta configurado.
    exit /b 1
)

for /f "delims=" %%B in ('git branch --show-current') do set "BRANCH=%%B"
if not defined BRANCH (
    echo ERRO: Nao foi possivel identificar a branch atual.
    exit /b 1
)

echo Estado atual do repositorio:
git status
if errorlevel 1 exit /b 1

echo.
echo A adicionar ficheiros respeitando o .gitignore...
git add .
if errorlevel 1 exit /b 1

git diff --cached --quiet
if not errorlevel 1 (
    echo Nao ha alteracoes para commit. A publicar a branch %BRANCH%.
    git push -u origin "%BRANCH%"
    if errorlevel 1 exit /b 1
    exit /b 0
)

echo.
echo A criar commit...
git commit -m "feat: consolidação final da stack AgroTech Enterprise com observabilidade completa" -m "Co-authored-by: Copilot <223556219+Copilot@users.noreply.github.com>"
if errorlevel 1 exit /b 1

echo.
echo A publicar origin/%BRANCH%...
git push -u origin "%BRANCH%"
if errorlevel 1 (
    echo ERRO: O push falhou. O commit local foi preservado.
    exit /b 1
)

echo.
echo Commit e push concluidos para origin/%BRANCH%.
exit /b 0
