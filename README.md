# app_v2

Aplicação de exemplo com API FastAPI, interface Streamlit e PostgreSQL.

## Instalação no Windows

Para instalar e iniciar a stack no Windows, abra `app_v2` no Explorador de
Ficheiros e execute `setup.ps1` (ou `install.bat`, se preferir iniciar o
PowerShell a partir de um clique). O instalador verifica o Docker Desktop e o
Docker Compose, cria `.env` a partir de `.env.example` se ainda não existir,
adiciona os endereços locais ao ficheiro hosts e constrói/inicia os serviços.
O Windows solicitará permissão de administrador para editar o ficheiro hosts.
As entradas são mantidas numa secção identificada; outras entradas existentes
nunca são substituídas. Se o Docker Desktop não estiver ativo, inicie-o e
execute o instalador novamente.

Também pode iniciar uma stack já configurada com `start-stack.bat`, que executa
`docker compose up -d` na pasta correta. Para iniciar manualmente ou acompanhar
a saída durante o desenvolvimento:

```sh
docker compose up --build
```

O Compose monta a pasta do projeto nos containers da API e da interface para
permitir hot-reload. Endereços locais configurados pelo instalador:

- Streamlit: <http://agrotech.local:8502>
- FastAPI: <http://agrotech.local:8001> (documentação em `/docs`)
- PostgreSQL: `localhost:5433`
- Prometheus: <http://prometheus.local:9091>
- Grafana: <http://grafana.local:3001> (`admin` / palavra-passe definida em
  `.env`; por padrão, `admin`)

As portas publicadas preservam a coexistência com outras stacks locais. O
instalador apenas configura nomes para `127.0.0.1`; os serviços continuam
acessíveis pelas portas publicadas no Compose. O `.env` é ignorado pelo Git:
revise os valores de desenvolvimento e substitua as palavras-passe de exemplo
antes de qualquer utilização fora da máquina local.

## Executar em desenvolvimento

Na pasta `app_v2`, execute `docker compose up --build` para reconstruir as
imagens e acompanhar os logs no terminal.

Serviços adicionais disponíveis:

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

### Métricas AgroTech Enterprise (demonstração)

A API também publica `agro_http_requests_total` e
`agro_http_request_duration_seconds` com labels de rota/status. O endpoint
existente `GET /items/` alimenta `agro_land_portfolio_queries_total` e o gauge
`agro_ma_land_queries_active` como um exemplo de consulta a portfólio de
terras. Como este repositório não contém serviços M&A ou agentes IoT reais,
`agro_edge_nodes`, `agro_edge_node_cpu_utilization_ratio` e
`agro_edge_node_memory_utilization_ratio` são valores estáticos de demonstração
para São Paulo e Mato Grosso, não medições de dispositivos físicos.

O dashboard provisionado `AgroTech Enterprise - API and Edge` pode ser aberto
no Grafana do `app_v2` em <http://localhost:3001>. Para popular as séries de
requisições, gere tráfego com `python scripts/generate_traffic.py` e aguarde
um scrape. Consultas de exemplo:

```promql
sum by (endpoint, status_code) (rate(agro_http_requests_total[5m]))
histogram_quantile(0.95, sum by (le, endpoint) (rate(agro_http_request_duration_seconds_bucket[5m])))
sum by (outcome) (rate(agro_land_portfolio_queries_total[5m]))
agro_edge_node_cpu_utilization_ratio
agro_edge_node_memory_utilization_ratio
agro_edge_nodes
```

### Teste de carga com k6

Execute o teste de carga no perfil `k6` (a API e o Prometheus são iniciados
automaticamente como dependências):

```powershell
docker compose --profile k6 up --build k6
```

O teste aumenta gradualmente até 5 VUs, verifica `GET /` e aplica thresholds
de p95 abaixo de 500 ms e menos de 1% de falhas. Por padrão usa
`http://backend:8000`; pode substituir a URL com `API_BASE`, por exemplo:

```powershell
$env:API_BASE = "http://host.docker.internal:8001"
docker compose --profile k6 up --build k6
Remove-Item Env:API_BASE
```

O k6 envia métricas pelo Prometheus Remote Write, recebido em
`/api/v1/write`. Após o teste, consulte métricas com o prefixo `k6_` em
<http://localhost:9091/graph> (por exemplo, pesquise `k6_vus` ou
`k6_http_reqs_total`). No Grafana, abra <http://localhost:3001>, acesse Explore,
selecione o datasource Prometheus e execute as mesmas consultas. Métricas do
teste ficam disponíveis após os primeiros envios Remote Write e durante a
retenção TSDB configurada no Prometheus.

### Gerar tráfego HTTP para métricas

O script Python envia lotes concorrentes e limitados para a API durante três
minutos por padrão. Ele alterna chamadas `GET /`, `GET /items/`, criação de
itens e respostas de erro seguras (`422` por validação e `404` em rota
inexistente). Interrompa a qualquer momento com `Ctrl+C`.

Na raiz `app_v2`, instale a dependência e execute em PowerShell:

```powershell
python -m pip install -r scripts/requirements.txt
python scripts/generate_traffic.py
```

A API do Compose é publicada em `localhost:8001` (a porta interna do
container é `8000`). Também pode parametrizar destino, duração, intervalo e
concorrência:

```powershell
python scripts/generate_traffic.py --base-url http://localhost:8001 --duration-seconds 180 --interval-seconds 1 --workers 4
```

Para carga rápida com Remote Write, use o perfil k6. O alias `backend` na rede
Compose aponta para o serviço FastAPI:

```powershell
docker compose --profile k6 up --build k6
```

Após executar tráfego, aguarde pelo menos um intervalo de scrape (15 segundos)
e consulte no Prometheus (`http://localhost:9091/graph`):

```promql
sum(rate(http_requests_total[1m]))
sum by (status_code) (rate(http_requests_total[1m]))
histogram_quantile(0.95, sum by (le) (rate(http_request_duration_seconds_bucket[1m])))
http_requests_in_progress
k6_vus
rate(k6_http_reqs_total[1m])
```

O `http_exceptions_total` conta exceções não tratadas; o script não força
respostas 5xx, para não provocar indisponibilidade artificial. Os erros de
validação e rota inexistente aparecem em `http_requests_total` com status 422
e 404. Depois de confirmar séries no Prometheus, abra o Grafana em
<http://localhost:3001> (a porta 3000 pertence à stack app_v1 neste ambiente),
vá a Explore e selecione o datasource Prometheus.

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

## CI e healthchecks

O workflow [CI](./.github/workflows/ci.yml) é executado em `push` e
`pull_request` direcionados às branches `main` e `develop`. Ele verifica a
sintaxe Python, executa o Flake8, roda os testes Python se houver uma suíte
`tests/` e constrói as imagens Docker do backend e do frontend. O workflow
apenas valida/constrói as imagens; não publica imagens nem faz deploy.

No Docker Compose, o PostgreSQL precisa passar `pg_isready` antes do backend
iniciar. O backend aguarda também o healthcheck HTTP do OpenSearch. API e
frontend têm healthchecks HTTP próprios; o estado pode ser consultado com:

```powershell
docker compose ps
docker inspect --format='{{.State.Health.Status}}' fastapi_app_v2
```

No Kubernetes, os Deployments de backend, frontend, Prometheus, Grafana,
Postgres Exporter, OpenSearch e OpenSearch Dashboards têm probes de readiness
e liveness. A readiness probe só encaminha tráfego para pods prontos; a
liveness probe permite ao Kubernetes reiniciar processos sem saúde. Consulte
os detalhes com `kubectl describe pod -n app <pod>`.

## Kubernetes local

Para criar um cluster kind e executar os serviços com manifests Kubernetes,
consulte o [guia de Kubernetes local](./k8s/README.md) e o
[guia de Istio/Kiali](./README_k8s.md).