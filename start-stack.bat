@echo off
setlocal
cd /d "%~dp0"

where docker >nul 2>&1
if errorlevel 1 (
    echo ERRO: Docker nao foi encontrado. Instale ou inicie o Docker Desktop.
    pause
    exit /b 1
)

docker compose version >nul 2>&1
if errorlevel 1 (
    echo ERRO: Docker Compose nao esta disponivel. Atualize o Docker Desktop.
    pause
    exit /b 1
)

docker info >nul 2>&1
if errorlevel 1 (
    echo ERRO: O Docker nao esta ativo. Inicie o Docker Desktop e tente novamente.
    pause
    exit /b 1
)

docker compose up -d
if errorlevel 1 (
    echo ERRO: Nao foi possivel iniciar a stack. Verifique a saida do Docker Compose.
    pause
    exit /b 1
)

echo.
echo Stack AgroTech Enterprise iniciada.
echo Frontend Streamlit: http://agrotech.local:8502
echo API FastAPI:        http://agrotech.local:8001/docs
echo Grafana:            http://grafana.local:3001
echo Prometheus:         http://prometheus.local:9091
echo.
pause
