# app_v2 no Kubernetes local (kind)

Este conjunto de manifestos executa FastAPI, Streamlit, PostgreSQL,
Prometheus, Grafana, Postgres Exporter, OpenSearch, OpenSearch Dashboards e
um Job opcional de k6 no namespace `app`.

## Pré-requisitos

- Docker Desktop em execução (no Windows, com integração WSL2 habilitada).
- `kind` e `kubectl` instalados e disponíveis no `PATH`.
- Recursos de memória suficientes para o OpenSearch (recomendado: pelo menos
  8 GiB atribuídos ao Docker Desktop).
- O host Linux do Docker precisa de `vm.max_map_count` igual ou superior a
  `262144` para o OpenSearch. Em Docker Desktop/WSL2, configure esse parâmetro
  no ambiente Linux usado pelo Docker se os logs do OpenSearch indicarem
  falha de `vm.max_map_count`.

O OpenSearch desativa o plugin de segurança apenas neste cluster didático.
As credenciais e imagens locais deste guia não devem ser reutilizadas em
produção.

## Criar o cluster

Na raiz de `app_v2`, crie o cluster usando [`kind-cluster.yaml`](./kind-cluster.yaml):

```powershell
kind create cluster --config k8s/kind-cluster.yaml
kubectl cluster-info --context kind-app-v2
kubectl get nodes
```

## Construir e carregar as imagens da aplicação

Os deployments usam imagens locais com `imagePullPolicy: Never`. Sempre que
alterar o código, reconstrua e carregue as imagens no cluster:

```powershell
docker build -t app-v2-backend:local -f Dockerfile .
docker build -t app-v2-frontend:local -f Dockerfile.frontend .
kind load docker-image app-v2-backend:local app-v2-frontend:local --name app-v2
```

## Aplicar os manifestos

Execute os comandos abaixo na raiz do projeto. Os recursos são aplicados em
ordem para criar primeiro o namespace e as dependências:

```powershell
kubectl apply -f k8s/namespace.yaml
kubectl apply -f k8s/config/
kubectl apply -f k8s/postgres/
kubectl apply -f k8s/logging/
kubectl apply -f k8s/backend/
kubectl apply -f k8s/frontend/
kubectl apply -f k8s/monitoring/
```

Antes de aplicar em qualquer ambiente, substitua
`REPLACE_WITH_STRONG_PASSWORD` em `k8s/config/grafana-secret.yaml` por uma
palavra-passe forte. O valor versionado é apenas um marcador, não uma
credencial utilizável.

O Secret do PostgreSQL é criado junto com `postgres.yaml`; ele contém
credenciais de laboratório em texto no manifesto. Em ambientes reais, use um
gestor de segredos e configure criptografia de Secrets no control plane.

Espere os workloads principais ficarem prontos e inspecione o estado:

```powershell
kubectl wait --namespace app --for=condition=Ready pod -l app=postgres --timeout=180s
kubectl rollout status --namespace app statefulset/postgres --timeout=180s
kubectl rollout status --namespace app deployment/backend --timeout=180s
kubectl rollout status --namespace app deployment/frontend --timeout=180s
kubectl rollout status --namespace app deployment/prometheus --timeout=180s
kubectl rollout status --namespace app deployment/grafana --timeout=180s
kubectl rollout status --namespace app deployment/postgres-exporter --timeout=180s
kubectl get pods,services,pvc -n app
```

O backend aguarda o PostgreSQL via init container. As tabelas são criadas pelo
aplicativo no startup. O OpenSearch pode levar mais tempo para inicializar:

```powershell
kubectl rollout status --namespace app statefulset/opensearch --timeout=300s
kubectl rollout status --namespace app deployment/opensearch-dashboards --timeout=300s
kubectl get pods -n app
```

## Istio e Kiali

Consulte também o guia [README_k8s.md](../README_k8s.md). Os passos abaixo
instalam o perfil `demo` do Istio no cluster kind e ativam a injeção automática
de sidecar no namespace `app`. O namespace precisa receber o label antes de
recriar os pods:

```powershell
istioctl install --set profile=demo -f k8s/istio/install-istio.yaml -y
kubectl label namespace app istio-injection=enabled --overwrite
kubectl rollout restart deployment -n app --all
kubectl rollout status deployment -n app --all --timeout=300s
kubectl get pods -n app
```

Confirme que os pods de aplicação têm `2/2` containers. Jobs e StatefulSets
não são deployments e não são reiniciados pelo comando acima. Para verificar
os proxies:

```powershell
istioctl proxy-status
```

Instale o addon Kiali da mesma distribuição baixada do Istio:

```powershell
kubectl apply -f "$env:ISTIO_HOME/samples/addons/kiali.yaml"
kubectl rollout status deployment/kiali -n istio-system --timeout=180s
istioctl dashboard kiali
```

O manifesto [kiali-dashboard.yaml](./istio/kiali-dashboard.yaml) também
documenta os comandos alternativos de port-forward. O painel fica em
<http://localhost:20001>.

Aplique o gateway e a rota para o frontend:

```powershell
kubectl apply -f k8s/istio/traffic-management.yaml
kubectl get gateway,virtualservice -n app
```

Para aceder ao Ingress Gateway em um terminal separado:

```powershell
kubectl port-forward -n istio-system service/istio-ingressgateway 8080:80
```

Abra <http://localhost:8080>. O Gateway encaminha para
`frontend.app.svc.cluster.local:8501`. No kind, esse port-forward evita
depender de um LoadBalancer ou de NodePorts.

## Port-forward e validações

Abra um terminal PowerShell para cada comando de port-forward e mantenha-o em
execução (interrompa com `Ctrl+C`):

```powershell
kubectl port-forward -n app service/frontend 8501:8501
kubectl port-forward -n app service/backend 8000:8000
kubectl port-forward -n app service/prometheus 9090:9090
kubectl port-forward -n app service/grafana 3000:3000
kubectl port-forward -n app service/opensearch 9200:9200
kubectl port-forward -n app service/opensearch-dashboards 5601:5601
```

Acesse:

- Streamlit: <http://localhost:8501>
- FastAPI e documentação: <http://localhost:8000> e <http://localhost:8000/docs>
- Métricas FastAPI: <http://localhost:8000/metrics>
- Prometheus: <http://localhost:9090/targets>
- Grafana: <http://localhost:3000> (`admin` / `admin` neste ambiente local)
- OpenSearch: <http://localhost:9200>
- OpenSearch Dashboards: <http://localhost:5601>

O Prometheus recolhe métricas do backend e do Postgres Exporter; a recepção de
Remote Write está habilitada para o k6. O Grafana provisiona automaticamente o
datasource Prometheus e o dashboard `app_v2 - Kubernetes and k6`.

Para inspecionar logs e estados de falha:

```powershell
kubectl logs -n app deployment/backend
kubectl logs -n app statefulset/postgres
kubectl describe pods -n app
```

## Executar o teste k6

Depois que backend e Prometheus estiverem prontos, crie o ConfigMap do script e
execute o Job:

```powershell
kubectl apply -f k8s/loadtest/k6-job.yaml
kubectl wait --namespace app --for=condition=complete job/k6-load-test --timeout=300s
kubectl logs -n app job/k6-load-test
```

O teste sobe gradualmente até 5 VUs, verifica `GET /`, exige p95 inferior a
500 ms e taxa de falhas inferior a 1%. As métricas são enviadas a
`http://prometheus:9090/api/v1/write`. Consulte `k6_vus` e
`k6_http_reqs_total` em
Prometheus (`/graph`) ou Grafana (Explore e dashboard provisionado). Para
executar novamente, remova o Job anterior e reaplique o manifesto:

```powershell
kubectl delete job -n app k6-load-test
kubectl apply -f k8s/loadtest/k6-job.yaml
```

## Remover os recursos

```powershell
kubectl delete namespace app
kind delete cluster --name app-v2
```
