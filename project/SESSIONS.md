# Registro de sessões

Mais recente no topo.

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
