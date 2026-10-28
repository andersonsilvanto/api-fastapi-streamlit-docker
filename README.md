# app_v2

Aplicação de exemplo com API FastAPI, interface Streamlit e PostgreSQL.

## Executar em desenvolvimento

Na pasta `app_v2`, execute:

```sh
docker compose up --build
```

O Compose monta a pasta do projeto nos containers da API e da interface para
permitir hot-reload. Endpoints disponíveis:

- Streamlit: <http://localhost:8502>
- FastAPI: <http://localhost:8001> (documentação em `/docs`)
- PostgreSQL: `localhost:5433`
- Prometheus: <http://localhost:9091>
- Grafana: <http://localhost:3001> (`admin` / `admin` por padrão)
- OpenSearch: <http://localhost:9201>
- OpenSearch Dashboards: <http://localhost:5602>

## Monitoramento

O Prometheus recolhe métricas HTTP da API em `/metrics` e métricas do
PostgreSQL através do `postgres-exporter`. Para validar a integração, abra
<http://localhost:9091/targets> e confirme que os jobs `fastapi` e `postgres`
estão com estado `UP`. Também pode consultar diretamente
<http://localhost:8001/metrics> ou pesquisar métricas como
`http_requests_total`, `http_request_duration_seconds`,
`http_requests_in_progress` e `http_exceptions_total` na interface do
Prometheus.

## Logs centralizados e dashboards

O backend escreve logs JSON no stdout com timestamp UTC, nível, logger,
mensagem, `request_id`, método, caminho, status, duração, IP do cliente e
User-Agent. O cabeçalho `X-Request-ID` é propagado ou gerado para cada
requisição. O envio ao índice `logs-app-v2` é assíncrono; se o OpenSearch
estiver indisponível, os logs continuam no stdout.

Consulte os logs locais com `docker compose logs -f backend_v2`. Para verificar
os documentos indexados, primeiro gere tráfego na API e consulte:

```powershell
Invoke-RestMethod http://localhost:9201/logs-app-v2/_count
Invoke-RestMethod 'http://localhost:9201/logs-app-v2/_search?q=path:%2Fitems&size=5'
```

O OpenSearch Dashboards está em <http://localhost:5602>. O Grafana está em
<http://localhost:3001>; entre com `admin` e a senha indicada por
`GRAFANA_ADMIN_PASSWORD` (o padrão `admin` é apenas para desenvolvimento).
O datasource Prometheus é provisionado e aponta para
`http://prometheus:9090`; confirme em Connections/Data sources e abra o
dashboard `app_v2 - API and PostgreSQL`.

As variáveis `OPENSEARCH_ENABLED`, `OPENSEARCH_HOST`, `OPENSEARCH_PORT`,
`OPENSEARCH_SCHEME`, `OPENSEARCH_USER`, `OPENSEARCH_PASSWORD` e
`OPENSEARCH_INDEX` controlam a integração de logs. Segurança do OpenSearch está
desabilitada apenas para este ambiente didático; em produção habilite
autenticação/TLS, proteja credenciais e restrinja o acesso às redes privadas.

Antes de executar, pode copiar `.env.example` para `.env` e substituir os
valores de exemplo. O Compose usa `POSTGRES_USER`, `POSTGRES_PASSWORD` e
`POSTGRES_DB`; o `.env` local é ignorado pelo Git, enquanto `.env.example` é
versionado. Nunca use valores de exemplo ou credenciais de desenvolvimento em
produção.