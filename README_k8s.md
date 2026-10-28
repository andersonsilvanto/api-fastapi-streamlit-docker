# app_v2 no Kubernetes com kind e Istio

O guia principal para criar o cluster, carregar imagens e aplicar os recursos
da aplicação está em [k8s/README.md](./k8s/README.md). Este documento descreve
a instalação da malha de serviços Istio, a injeção de sidecars, o roteamento
do frontend e a observabilidade com Kiali.

## Pré-requisitos

- Cluster kind criado conforme [`k8s/kind-cluster.yaml`](./k8s/kind-cluster.yaml).
- `kubectl`, Docker e `istioctl` instalados.
- Namespace `app` e Services `frontend` e `backend` aplicados.
- Memória suficiente para o perfil `demo`; em ambiente local reserve pelo
  menos 8 GiB para Docker Desktop, especialmente quando OpenSearch também
  estiver executando.

O Istio instala recursos de plano de controle e um ingress gateway no cluster.
Confirme o contexto ativo antes de instalar:

```powershell
kubectl config current-context
kind get clusters
kubectl get nodes
```

## Instalar Istio demo

Baixe uma versão do Istio compatível com a versão Kubernetes do cluster, e
adicione seu diretório `bin` ao `PATH` do terminal. Defina `ISTIO_HOME` para a
raiz da distribuição extraída para que o addon Kiali esteja disponível:

```powershell
$env:ISTIO_VERSION = "1.27.3"
$env:ISTIO_HOME = "$PWD\istio-$env:ISTIO_VERSION"
New-Item -ItemType Directory -Force -Path $env:ISTIO_HOME | Out-Null
Invoke-WebRequest "https://github.com/istio/istio/releases/download/$env:ISTIO_VERSION/istio-$env:ISTIO_VERSION-win.zip" -OutFile "$env:TEMP\istio-$env:ISTIO_VERSION-win.zip"
Expand-Archive "$env:TEMP\istio-$env:ISTIO_VERSION-win.zip" -DestinationPath $PWD -Force
$env:PATH = "$env:ISTIO_HOME\bin;$env:PATH"
istioctl version --remote=false
```

Instale o perfil `demo` usando a configuração versionada:

```powershell
istioctl install --set profile=demo -f k8s/istio/install-istio.yaml -y
kubectl get pods -n istio-system -w
kubectl rollout status deployment/istiod -n istio-system --timeout=300s
kubectl get pods -n istio-system
```

Espere `istiod` e `istio-ingressgateway` ficarem `Running` e prontos antes de
continuar.

## Injetar sidecars no namespace app

O label pode ser aplicado em [namespace.yaml](./k8s/namespace.yaml) antes da
criação do namespace ou diretamente no namespace existente. Os pods já criados
não recebem sidecars retroativamente; reinicie os Deployments depois de
configurar a injeção:

```powershell
kubectl label namespace app istio-injection=enabled --overwrite
kubectl rollout restart deployment -n app --all
kubectl rollout status deployment -n app --all --timeout=300s
kubectl get pods -n app
istioctl proxy-status
```

Os Pods que executam aplicações mesh-injected devem exibir `2/2` containers:
o container da aplicação e `istio-proxy`. `proxy-status` deve mostrar os
sidecars conectados ao `istiod`. Nem todos os Pods são reiniciados por esse
comando: StatefulSets, Jobs e Pods sem sidecar precisam de tratamento próprio.

## Instalar Kiali

Use o manifesto de addon que acompanha a **mesma versão** do Istio:

```powershell
kubectl apply -f "$env:ISTIO_HOME/samples/addons/kiali.yaml"
kubectl rollout status deployment/kiali -n istio-system --timeout=180s
```

Abra o dashboard com o comando da extensão `istioctl`:

```powershell
istioctl dashboard kiali
```

Ou exponha o serviço temporariamente em outro terminal:

```powershell
kubectl port-forward -n istio-system service/kiali 20001:20001
```

Depois, visite <http://localhost:20001>. Se o service graph estiver vazio,
gere tráfego no frontend/backend e selecione o namespace `app` e a janela de
tempo correta.

Os comandos também estão anotados em
[`k8s/istio/kiali-dashboard.yaml`](./k8s/istio/kiali-dashboard.yaml).

## Gateway e roteamento do frontend

O Gateway recebe HTTP na porta 80 do ingress gateway Istio. O VirtualService
encaminha pedidos para o Service frontend na porta 8501:

```powershell
kubectl apply -f k8s/istio/traffic-management.yaml
kubectl get gateway,virtualservice -n app
```

Para acesso local no kind, mantenha este port-forward em execução:

```powershell
kubectl port-forward -n istio-system service/istio-ingressgateway 8080:80
```

Abra <http://localhost:8080>. Para confirmar o caminho externo, execute:

```powershell
Invoke-WebRequest http://localhost:8080 -UseBasicParsing
```

## Troubleshooting

| Sintoma | Verificação | Ação |
|---|---|---|
| `istiod` não fica Ready | `kubectl describe pods -n istio-system` | Verifique recursos disponíveis e `kubectl logs -n istio-system deployment/istiod`. |
| Pods de `app` aparecem `1/1` | `kubectl get pods -n app` e `kubectl get namespace app --show-labels` | Defina `istio-injection=enabled` e reinicie o Deployment afetado. |
| Sidecar não conecta | `istioctl proxy-status`; `kubectl logs -n app <pod> -c istio-proxy` | Confira conectividade com `istiod`, eventos do pod e versão do proxy. |
| Gateway/VirtualService não encaminha | `kubectl describe gateway,virtualservice -n app`; `istioctl analyze -n app` | Confira selector `istio: ingressgateway`, host, namespace e porta `8501` do Service. |
| Ingress Gateway não acessível | `kubectl get svc,pods -n istio-system` | Use o port-forward indicado; kind não provisiona um LoadBalancer externo por padrão. |
| Kiali não mostra tráfego | `kubectl get pods,svc -n istio-system` | Instale o addon da mesma versão do Istio, gere tráfego e ajuste namespace/período no dashboard. |
| Problema de protocolo do Service | `kubectl get svc frontend -n app -o yaml` | A porta deve ter nome HTTP (por exemplo, `http`) e `targetPort: 8501`. |

Para inspecionar configuração de um proxy:

```powershell
istioctl proxy-config clusters -n app <pod>
istioctl proxy-config routes -n app <pod>
kubectl describe pod -n app <pod>
```

## Desinstalação

Remova primeiro os recursos de tráfego e o addon:

```powershell
kubectl delete -f k8s/istio/traffic-management.yaml
kubectl delete -f "$env:ISTIO_HOME/samples/addons/kiali.yaml"
istioctl uninstall --purge -y
kubectl delete namespace istio-system
kubectl label namespace app istio-injection-
```
