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

Antes de executar, pode copiar `.env.example` para `.env` e substituir os
valores de exemplo. O Compose usa `POSTGRES_USER`, `POSTGRES_PASSWORD` e
`POSTGRES_DB`; o `.env` local é ignorado pelo Git, enquanto `.env.example` é
versionado. Nunca use valores de exemplo ou credenciais de desenvolvimento em
produção.