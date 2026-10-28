# Relatório técnico: autenticação e política de senhas

Este relatório consolida a implementação de autenticação, troca obrigatória da
senha inicial, regras de senha em desenvolvimento/produção, provisionamento de
Secrets em Kubernetes e respetiva validação.

## Índice

- [Visão geral](#visão-geral)
- [Componentes e referências cruzadas](#componentes-e-referências-cruzadas)
  - [Backend e ciclo de senha](#backend-e-ciclo-de-senha)
  - [Provisionamento Kubernetes](#provisionamento-kubernetes)
  - [Testes automatizados](#testes-automatizados)
- [Regras por ambiente](#regras-por-ambiente)
- [Validação executada](#validação-executada)
- [Comandos para reprodução](#comandos-para-reprodução)
- [Limitações e avisos operacionais](#limitações-e-avisos-operacionais)

## Visão geral

A aplicação usa JWT Bearer para proteger as rotas de itens. No primeiro acesso,
o utilizador inicial recebe um token marcado com `must_change_password=true`;
as rotas protegidas rejeitam esse token com HTTP `428` até que a senha seja
alterada. A interface Streamlit apresenta o fluxo de alteração e atualiza o
token após a resposta bem-sucedida da API.

A política curta de 4–8 caracteres aplica-se exclusivamente quando
`APP_ENV=development`. Produção mantém validação forte, sem impor um máximo de
8 caracteres.

## Componentes e referências cruzadas

### Backend e ciclo de senha

- [Validação e hashing de senhas](../backend/passwords.py): PBKDF2-HMAC-SHA256
  com salt aleatório e comparação constante; validação separada por ambiente.
- [Autenticação e bootstrap inicial](../backend/auth.py): cria o utilizador
  inicial, gera e valida JWTs e impede o uso de senhas fracas no bootstrap de
  produção.
- [Rotas FastAPI](../backend/main.py): `POST /auth/login`,
  `POST /auth/change-password`, e operações autenticadas de itens.
- [Schemas da API](../backend/schemas.py): modelos de entrada e saída para
  autenticação e troca de senha.
- [Interface Streamlit](../frontend/app.py): login, solicitação de mudança
  obrigatória e gestão do token na sessão.

### Provisionamento Kubernetes

- [Script de criação de Secrets](../k8s/create-secrets.ps1): modo local
  `-DevelopmentDefaults`, prompts protegidos, validação por ambiente e envio
  dos Secrets por stdin ao `kubectl`.
- [Deployment do backend](../k8s/backend/backend-deployment.yaml): injeta
  `APP_ENV`, credenciais de bootstrap e segredo JWT a partir do Secret
  `backend-auth`.
- [Template do Secret do backend](../k8s/backend/backend-auth-secret.yaml):
  valores de substituição para configuração; não representa credenciais
  operacionais.
- [Guia Kubernetes](../k8s/README.md): instruções de preparação e implantação.

### Testes automatizados

- [Testes de autenticação e política forte](../tests/test_auth.py): tokens,
  scopes, hashing, requisitos de senha e proteção do bootstrap em produção.
- [Testes dos limites em desenvolvimento](../tests/test_password_change_api.py):
  valores abaixo de 4, acima de 8 e dentro do intervalo permitido.
- [Smoke test da stack](../smoke-test.ps1): verificações de API, PostgreSQL,
  frontend, Prometheus, Grafana e configuração Kubernetes.

## Regras por ambiente

| Ambiente | Senha de alteração de conta | Bootstrap e infraestrutura |
|---|---|---|
| Desenvolvimento (`APP_ENV=development`) | Comprimento entre 4 e 8 caracteres; não exige classes de caracteres. | `create-secrets.ps1 -DevelopmentDefaults` permite entradas de 4–8 caracteres e usa `1234` como valor ao premir Enter nos prompts aplicáveis. |
| Produção | Mínimo de 8 caracteres, com maiúscula, minúscula, número e símbolo; sem limite superior de 8. | Senha PostgreSQL com mínimo de 16; senha inicial do admin satisfaz a política forte; chave JWT com mínimo de 32 caracteres. |

O modo de desenvolvimento no script Kubernetes é restrito a contextos locais
Kind, Minikube ou Docker Desktop e apresenta um aviso de segurança. Não exponha
esses serviços publicamente nem reutilize credenciais de teste.

## Validação executada

Na validação registada para esta implementação, os **16 testes unitários de
autenticação e senha passaram** no container do backend. A compilação dos
ficheiros Python também passou. O smoke test integrado passou em **12 de 12
verificações**, incluindo o estado `UP` dos targets FastAPI e PostgreSQL no
Prometheus.

## Comandos para reprodução

Execute a partir da pasta `app_v2`:

```powershell
docker compose exec -T backend_v2 python -m unittest -v tests.test_password_change_api tests.test_auth
docker compose exec -T backend_v2 python -m compileall -q backend tests
.\smoke-test.ps1
```

Para criar Secrets de teste em um cluster local compatível:

```powershell
.\k8s\create-secrets.ps1 -DevelopmentDefaults
```

Sem essa flag, o script segue os requisitos de produção.

## Limitações e avisos operacionais

- Valores de Kubernetes Secret codificados em Base64 não são encriptação.
  Configure controlo de acesso RBAC e encriptação de Secrets no cluster; prefira
  um gestor de segredos para produção.
- Substituir a senha de um Secret PostgreSQL não altera automaticamente a senha
  do utilizador numa base já inicializada. O script alerta para confirmar a
  rotação e a persistência antes de substituir Secrets.
- O segredo JWT de desenvolvimento é intencionalmente curto e só é permitido
  quando a aplicação está identificada como desenvolvimento.
- A faixa 4–8 é uma conveniência exclusiva para ambientes isolados de
  desenvolvimento/teste; não deve ser promovida para produção.
