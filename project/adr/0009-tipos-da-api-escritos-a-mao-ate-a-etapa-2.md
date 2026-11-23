# 0009: Tipos da API escritos à mão até a Etapa 2

> **Atualizado pelo [ADR 0012](0012-tipos-da-api-continuam-a-mao-com-novo-gatilho.md) (2026-11-23):** o gatilho disparou, a medição foi refeita e os tipos seguem à mão, com novo gatilho.

**Data:** 2026-11-18

## Contexto
A ARQUITETURA §6 e o PLANO 1.4 previam um contrato OpenAPI gerado do backend, com tipos TypeScript gerados a partir dele. Na hora de fazer a PR 1.4, os dados medidos mostraram que o custo superava o ganho:
- A API própria tem **2 endpoints** (`/health/` e `/me/`). Login, cadastro e sessão são do **django-allauth**, que publica **outra** especificação OpenAPI; um gerador baseado só no `drf-spectacular` não cobriria o que o frontend mais usa.
- `openapi-typescript` 7.13.0 declara `typescript ^5.x` como peer; o projeto usa TypeScript 6.0.3 (exigência do `typescript-eslint`, que declara `<6.1.0`), então o `npm` recusaria a instalação sem afrouxar a checagem de peers do projeto inteiro.
- `@hey-api/openapi-ts` 0.99.0 aceita TS 6, mas é pré-1.0, com 1 mantenedor e 10 dependências.
- `drf-spectacular` 0.30.0 teve 1 release nos últimos 12 meses e puxa `PyYAML`, `jsonschema`, `inflection` e `uritemplate`.

## Decisão
Os tipos da API vivem à mão em `frontend/src/types/api.ts` (só o que o frontend usa), e o cliente HTTP é um módulo próprio de ~50 linhas (`frontend/src/services/http.ts`). **A geração a partir do OpenAPI fica para a Etapa 2**, quando surgirem salas e carteiras (muitos endpoints próprios). Naquele momento, avaliar de novo geradores e `drf-spectacular` com dados atuais e gravar um novo ADR.

## Alternativas descartadas
- **drf-spectacular + `@hey-api/openapi-ts` agora:** 5 pacotes novos para 2 endpoints, e o allauth continuaria sem cobertura.
- **`openapi-typescript` com `legacy-peer-deps`:** desliga a checagem de compatibilidade do projeto todo.
- **`openapi-fetch`/`axios` como cliente:** o cliente só precisa de CSRF, JSON e erros.

## Consequências
- Risco de **divergência** entre o tipo escrito à mão e a resposta real. Mitigação: os testes do backend fixam o formato das respostas e os do frontend usam o mesmo formato (ver `src/test/fixtures.ts`); o risco cresce com o número de endpoints, que é o gatilho para migrar.
- Gatilho para reabrir: entrada do app `rooms` (Etapa 2), ou o terceiro recurso próprio da API.
- Menos dependências agora (nenhuma de geração).
- **Custo de reverter:** baixo (trocar `types/api.ts` por arquivo gerado).
