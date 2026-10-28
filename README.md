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

## Monitoramento

O Prometheus recolhe métricas HTTP da API em `/metrics` e métricas do
PostgreSQL através do `postgres-exporter`. Para validar a integração, abra
<http://localhost:9091/targets> e confirme que os jobs `fastapi` e `postgres`
estão com estado `UP`. Também pode consultar diretamente
<http://localhost:8001/metrics> ou pesquisar métricas como
`http_requests_total`, `http_request_duration_seconds`,
`http_requests_in_progress` e `http_exceptions_total` na interface do
Prometheus.

Antes de executar, pode copiar `.env.example` para `.env` e substituir os
valores de exemplo. O Compose usa `POSTGRES_USER`, `POSTGRES_PASSWORD` e
`POSTGRES_DB`; o `.env` local é ignorado pelo Git, enquanto `.env.example` é
versionado. Nunca use valores de exemplo ou credenciais de desenvolvimento em
produção.