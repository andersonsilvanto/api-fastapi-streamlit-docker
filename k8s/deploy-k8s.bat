@echo off
setlocal
cd /d "%~dp0"

where kubectl >nul 2>&1
if errorlevel 1 (
    echo ERRO: kubectl nao foi encontrado no PATH.
    exit /b 1
)

echo Contexto Kubernetes ativo:
kubectl config current-context
if errorlevel 1 exit /b 1

kubectl apply -f namespace.yaml
if errorlevel 1 exit /b 1

for %%S in (postgres-credentials backend-auth grafana-admin) do (
    kubectl get secret %%S -n app >nul 2>&1
    if errorlevel 1 (
        echo ERRO: Secret %%S ausente no namespace app.
        echo Execute create-secrets.ps1 e tente novamente.
        exit /b 1
    )
)

echo Aplicando recursos internos da stack...
kubectl apply -k .
if errorlevel 1 (
    echo ERRO: kubectl apply falhou. Verifique o contexto e os manifestos.
    exit /b 1
)

echo.
echo Pods no namespace app:
kubectl get pods -n app -o wide
if errorlevel 1 exit /b 1

echo.
echo Servicos internos:
kubectl get services -n app
if errorlevel 1 exit /b 1

for /f "delims=" %%E in ('kubectl get secret backend-auth -n app -o jsonpath^="{.metadata.labels.environment}" 2^>nul') do set "APP_ENVIRONMENT=%%E"
if /i "%APP_ENVIRONMENT%"=="development" (
    echo.
    echo Ingress externo bloqueado: Secrets de desenvolvimento usam credenciais fracas.
    echo Crie Secrets de producao antes de publicar qualquer servico.
    exit /b 0
)

kubectl get secret agrotech-tls -n app >nul 2>&1
if errorlevel 1 (
    echo.
    echo Ingress externo nao aplicado: crie agrotech-tls e aplique ingress.yaml depois de configurar DNS.
    exit /b 0
)

echo.
echo Aplicando Ingress TLS...
kubectl apply -f ingress.yaml
if errorlevel 1 exit /b 1
kubectl get ingress -n app
exit /b %errorlevel%
