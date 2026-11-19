# Registro de sessões

Mais recente no topo.

### 2026-11-19 — Sessão 8 (validação no navegador)

- **Pedido**: validar o fluxo de autenticação (PR 1.3 e 1.4) num navegador real. Foram instalados nesta máquina, via `winget`, Python 3.13.17 e PostgreSQL 17.12 (mesma versão major do CI); banco e usuário `bahazar` criados, `migrate` OK, backend em `:8000` e Vite em `:5173`.
- **Provado pelo log e pelo banco**: cadastro (`signup` 200, usuário no banco, e-mail de confirmação no console), sair (`session` 401 depois do `DELETE`), dois logins 200, avatar `verdant` gravado, sessão mantida após F5, e senha errada: 5 respostas `400` de 173 bytes (credencial) e, da 6ª em diante, `400` de 143 bytes (limite do allauth), 25 no total.
- **Só relato do dono** (o log não prova): `/perfil` deslogado redireciona para `/entrar`; cadastro duplicado recusado; qual identificador (usuário ou e-mail) foi usado em cada login.
- **Erro do roteiro**: o roteiro citava `/profile`, mas a rota é `/perfil` (`/profile` cai no `*` e vai à Home). Não era bug do app.
- **Achado**: a tela mostra "Usuário ou senha incorretos" também no limite de tentativas (pendência já conhecida; PR própria em seguida).
- **Não verificado**: formato do corpo da resposta de limite (só os tamanhos, 173 e 143 bytes); o e-mail de confirmação não foi clicado; deploy e D3 seguem abertos.
- **Fica**: PR da mensagem de "muitas tentativas"; Etapa 2 (plano antes de codar, toca carteiras: confirmação explícita); D3, D7, D2.

### 2026-11-19 — Sessão 7 (aprovação da arquitetura)

- **Pedido**: o dono escolheu aprovar a arquitetura e confirmar a D8, sem reler os documentos nesta sessão.
- **Feito** (só docs): Etapa 0 marcada como aprovada no `OVERVIEW.md`; ADRs 0001-0009 como aceitos e D8 resolvida (Django 5.2 LTS) em `PENDING.md` e `RISCOS.md`.
- **Não verificado**: nenhuma conferência de código; a aprovação cobre o desenho, que as etapas 1.1 a 1.4 já seguem.
- **Fica**: D3 (antes do deploy), D7 (antes da etapa 4), D2 (depois da etapa 2); validação no navegador; Etapa 2.

### 2026-11-18 — Sessão 6 (etapa 1.4: telas de autenticação)

- **Pedido**: PR 1.4. Plano aprovado antes de codar. O dono escolheu **tipos escritos à mão agora e geração na Etapa 2** (ADR 0009), contrariando o PLANO 1.4 e a ARQUITETURA §6 quanto ao "quando".
- **Feito** (branch `etapa-1-4-telas-de-autenticacao`, PR #6): cliente HTTP com CSRF (`services/http.ts`), serviços de auth e perfil, `useSession` (TanStack Query), telas Entrar, Cadastrar e Perfil (avatar), `RequireAuth`, `Header`, proxy do Vite, `react-router` 8.5.1 e `@tanstack/react-query` 5.107.0, README com como rodar. Auto-merge **não** ligado neste PR (toca sessão/CSRF no cliente).
- **Desvios do plano**: (1) **Sair** não navega mais para `/`: um `navigate("/")` explícito disputava com o redirecionamento do `RequireAuth` (transição de baixa prioridade contra atualização urgente do cache) e o último vencia; agora a sessão decide (de uma página protegida vai ao login). (2) O proxy do Vite tem o alvo fixo `localhost:8000` (ler variável de ambiente exigiria `@types/node`).
- **Testes**: 30 no frontend (era 8). 3 mutações válidas (token CSRF não enviado: `5 failed`; login sempre `username`: `1 failed`; `RequireAuth` invertido: `7 failed`). **Duas das cinco tentativas iniciais eram inválidas** (deixaram código sem uso e falharam no lint antes dos testes); foram refeitas.
- **CI**: ver o PR #6.
- **Não verificado**: **nada foi visto num navegador** e o fluxo real com backend + frontend (proxy, `Origin`/`Host`, cookie) nunca rodou; o formato dos erros do allauth veio da especificação, não de um teste real.
- **Fica**: o dono validar no navegador (README); PR da Etapa 2 (salas, convites, carteiras) e, com ela, geração de tipos.

### 2026-11-18 — Sessão 5 (ruleset exige os checks de CI)

- **Pedido**: exigir no ruleset da `main` os dois checks de CI (hoje só o `guard`).
- **Decisão do dono**: "faz a PR do ruleset primeiro".
- **Feito** (branch `ruleset-exige-checks-de-ci`, PR #5): o ruleset passa a ser versionado em `.github/ruleset-protect-main.json` (3 checks: `guard`, `Python (lint, types and tests)`, `Frontend (lint, types, tests and build)`). O PR sozinho **não** altera o ruleset (ele vive na API do GitHub): depois do merge, o JSON é aplicado com `gh api -X PUT repos/masterlxz/bahazar/rulesets/27571902 --input .github/ruleset-protect-main.json` e lido de volta.
- **CI**: ver o PR #5.
- **Não verificado**: o efeito do ruleset novo num PR real (o primeiro PR depois dele é o teste).
- **Fica**: aplicar o JSON na API após o merge; só então considerar auto-merge (ADR 0012); PR 1.4.

### 2026-11-18 — Sessão 4 (etapa 1.3: autenticação e perfil)

- **Pedido**: PR 1.3 (cadastro, login, perfil). Sem domínio próprio, o dono **adiou o D3** e escolheu: e-mail opcional agora e obrigatório antes do deploy; login por usuário ou e-mail; avatar por chave de lista fixa. Plano aprovado antes de codar (toca autenticação, AGENTS.md §4).
- **Feito** (branch `etapa-1-3-autenticacao`, PR #4): allauth headless (sessão + CSRF), `accounts.User` com UUID e constraints no banco, `/api/v1/me/` (GET/PATCH só do avatar), cache em banco em produção, ADR 0008, `profiles` fundido no `User` no modelo de dados.
- **Testes**: 43 novos (50 no backend). Rodada vermelha só com testes: `41 failed, 9 passed`. 3 mutações deliberadas (CSRF desligado, `fields="__all__"`, regex frouxa) derrubaram os testes certos em branches descartáveis (`workflow_dispatch`).
- **CI**: visto com `gh run`: `Python`, `Frontend` e `guard` verdes.
- **Não verificado**: nada num navegador; e-mail real nunca enviado; CSRF testado só com o cliente de teste do DRF (o fluxo `browser` do allauth não foi lido na doc, foi provado por teste); limite de tentativas só com `LocMemCache`, o `DatabaseCache` de produção nunca rodou; migração escrita à mão (validada pelo `makemigrations --check`).
- **Fica**: PR 1.4 (OpenAPI → tipos TS, telas de login e perfil, proxy do Vite); bloqueios de deploy em `PENDING.md`; exigir os checks `Python` e `Frontend` no ruleset.

### 2026-11-18 — Sessão 3 (etapa 1.2: esqueleto do frontend)

- **Pedido**: começar a PR 1.2 (Vite, React, TypeScript, Tailwind, shadcn/ui, tema escuro).
- **Decisão do dono**: aprovou a lista de dependências medida; Node LTS instalado por ele só para gerar o lockfile (`npm install --package-lock-only`).
- **Feito** (branch `etapa-1-2-esqueleto-frontend`, PR #3): `frontend/` com 8 testes (`cn`, `Button`, `App`), job de CI `Frontend (lint, types, tests and build)`. Mutação deliberada (`bg-primary` → `bg-secondary`) derrubou o teste certo; revertida.
- **CI**: visto com `gh run`: lint, tipos, `npm audit`, 8 testes e build verdes, e o job Python segue verde.
- **Não verificado**: nada rodou local (só o lock foi gerado com Node local); aparência no navegador não foi vista (só build e testes em jsdom); o CI usa Node 24 e o lock foi gerado com Node 26/npm 11.
- **Fica**: PR 1.3 (auth; confirmação explícita e decisão D3), PR 1.4 (OpenAPI → tipos TS), `frontend/` fora do deploy da Vercel até D2; exigir os dois checks no ruleset.

### 2026-11-18 — Sessão 2 (etapa 1.1 e renomeação)

- **Pedido**: aprovar a arquitetura, começar a etapa 1 e trocar o nome do projeto para `bahazar`.
- **Decisão do dono**: arquitetura aprovada; nome final **bahazar** (o nome de trabalho era `bazaar`; as entradas abaixo e o histórico do git mantêm o nome antigo de propósito, como registro).
- **Feito**: PR #1 (etapa 1.1: esqueleto Django + CI, 7 testes, mutação deliberada confirmada), mesclado como `f71e978`. Repo renomeado no GitHub para `masterlxz/bahazar` (o nome antigo redireciona). Este PR troca o nome nos docs, no `README` e nos valores padrão do banco (`DB_NAME`/`DB_USER`).
- **CI**: PR #1 com `Python (lint, types and tests)` e `guard` verdes (visto com `gh pr view`).
- **Não verificado**: lockfile das transitivas não existe; `prod.py` só testado por import.
- **Fica**: PR 1.2 (frontend), PR 1.3 (auth: pede confirmação explícita, AGENTS.md §4; depende de D3), PR 1.4 (OpenAPI → tipos). Exigir o check `Python (lint, types and tests)` no ruleset (já reportou verde na `main`).

### 2026-11-18 — Sessão 1 (arquitetura inicial)

- **Pedido**: abrir o projeto e entregar só a documentação de arquitetura do jogo (sem implementar).
- **Decisão do dono**: sem BaaS (Supabase fora); backend em Python + Django + DRF; docs no repo novo em `project/`; imagens de skins ficam como decisão pendente; nome `bazaar`.
- **Feito** (commit inicial direto na `main`, necessário para o guard existir antes do ruleset; ver `padrao/README.md`): docs (INDEX, OVERVIEW, ARQUITETURA, MODELO-DE-DADOS, SEGURANCA, PLANO, DEPENDENCIAS, RISCOS, PENDING, GUIDELINES), 7 ADRs, template de PR e guard do workspace.
- **CI**: ver resultado real do `guard` na `main` abaixo, na seção "Fica".
- **Não verificado**: nenhum SQL ou código executado; licenças/avisos de dependências; licença do dado de skins; preços de hospedagem.
- **Licença e visibilidade** (decisão do dono): AGPL-3.0 (`LICENSE` baixado do endpoint de licenças do GitHub) e repo `masterlxz/bazaar` tornado **público**. Commit da licença direto na `main` porque o ruleset ainda não existia (setup inicial); a partir do ruleset, tudo por PR. O plano gratuito não oferece ruleset nem secret scanning em repo privado, o que motivou também a abertura.
- **Fica**: revisão do dono; decisões D1-D10 em `RISCOS.md`; ADRs propostos em `PENDING.md`; criar repo no GitHub e aplicar o ruleset na ordem de `padrao/README.md`.
