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

As credenciais e o nome padrão do banco são `postgres`, `postgres` e
`devops_v2_db`. Podem ser substituídos por variáveis de ambiente ou por um
arquivo `.env` local.