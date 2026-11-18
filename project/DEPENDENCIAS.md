# Dependências e "procurar pronto antes de criar"

Segue `padrao/dependencias-novas.md`. **Nada foi instalado.** Cada dependência abaixo só entra com seu aprovado, em PR próprio, com uma linha de registro (nome, versão, por quê, alternativa, veredito).

## Como ler a confiança
- **Medido (2026-11-18):** versão mais recente no PyPI (consulta direta à API do registro).
- **Não medido:** data de release, licença exata, avisos de segurança (OSV/GHSA), nº de mantenedores no registro, peso das transitivas. Isso é feito no PR de cada dependência (`pip-audit`, `npm audit`, `pip index`/`npm view`). **Os vereditos abaixo são, portanto, pré-triagem (confiança média).**
- A busca web foi feita com termos genéricos de categoria, sem citar o projeto.

## 1. Passo 0: o que existe pronto
| Necessidade | Onde procurei | Alternativas | Veredito | Por quê |
|---|---|---|---|---|
| Autenticação para API de SPA | PyPI, docs, discussões | **django-allauth (headless)**; dj-rest-auth; djangorestframework-simplejwt | **Adaptar: allauth headless** (confiança média) | Mais ativa nos resultados (release 65.22.1 no PyPI; notas de 2026); dj-rest-auth tem sinais de manutenção fraca em discussões (a conferir: PyPI mostra 7.2.0). simplejwt só se for token puro. Auth nunca é do zero (AGENTS.md §4) |
| Ledger/carteira | PyPI | django-hordak (2.0.0), django-double-entry (1.0.9), capone, django-ledger (contábil completo), kunshort-django-wallet (saldo mutável) | **Criar (ledger próprio e pequeno)**, com django-hordak como referência de desenho (confiança média-baixa; não li o código) | Nosso ledger é ~3 tabelas com invariantes específicas (carteira `system`, `kind`, idempotência, append-only por trigger). hordak/double-entry trazem plano de contas contábil e conceitos de "contas, legs, moedas" que sobram para um jogo e acoplariam o modelo. Dinheiro "do zero" exige justificativa: **(b/c)** o pronto não encaixa e integrar custa mais que construir. **Revisar:** se o dono preferir pronto, testar hordak num piloto descartável |
| Catálogo de skins | GitHub, PyPI | **ByMykel/CSGO-API** (JSON estático, multi-idioma; licença **MIT não confirmada**: só vi em listagem de terceiros); CS2Cap/CS2-API (reescrita, MIT); dump do Steam (`items_game`) | **Adaptar** um dump JSON versionado no repo, importado por comando (confiança baixa-média) | Evita scraping; não depende de API viva. **Pendente:** ler a LICENSE no repo-fonte e decidir imagens (D1). Os dados em si descrevem itens da Valve |
| Tempo real | docs Channels | **SSE** + `LISTEN/NOTIFY`; Django Channels 4.3.2; polling | **Polling agora; SSE na etapa 6** | Só servidor → cliente; ver ARQUITETURA §7 |
| OpenAPI | PyPI | **drf-spectacular** (0.30.0); django-rest-swagger (obsoleto) | **Adotar** | Padrão de fato para DRF |
| Rankings/estatísticas | - | views SQL/agregação | **Criar** (consulta) | Sem dependência |
| Frontend: componentes | npm | **shadcn/ui** (copia código para o repo); Radix direto; MUI | **Adotar shadcn/ui** (exigido pelo prompt) | Código fica no repo, sem runtime pesado |

## 2. Backend (Python)
| Pacote | Versão no registro (medido) | Uso | Escopo | Veredito (pré-triagem) |
|---|---|---|---|---|
| Django | 6.1.3 | framework | runtime | **Adotar com decisão pendente (D8):** a linha **LTS** vigente é a 5.2 (suporte longo); 6.1 é a mais nova. Para um jogo que pode virar público, **recomendo LTS** e fixar a versão exata no lockfile |
| djangorestframework | 3.18.3 | API REST | runtime | Adotar |
| psycopg (v3) | 3.3.9 | driver PostgreSQL | runtime | Adotar (com o extra `binary` só em dev/CI; em produção, avaliar compilar) |
| django-allauth | 65.22.1 | contas, e-mail, headless | runtime | Adotar com ressalva (superfície grande; ligar só o necessário; vigiar avisos) |
| argon2-cffi | 25.1.0 | hash de senha (se não usar o padrão) | runtime | Adotar (confirmar necessidade: o hasher padrão do Django já é aceitável) |
| drf-spectacular | 0.30.0 | OpenAPI | runtime/build | Adotar |
| django-cors-headers | 4.9.0 | CORS | runtime | Adotar (só se frontend e API ficarem em origens diferentes; D3) |
| django-filter | não medido | filtros de listagem | runtime | **Provável dispensável:** filtros simples cabem em `selectors.py`. Decidir no PR 3.2 |
| gunicorn + uvicorn | não medido | servidor ASGI | runtime | Adotar na etapa 6 (se SSE) |
| pytest, pytest-django | pytest-django 4.14.0 | testes | **dev** | Adotar |
| hypothesis | 6.170.15 | testes de propriedade | **dev** | Adotar (usos: invariantes do ledger) |
| ruff | não medido | lint/format | **dev** | Adotar (workspace já usa em outros projetos) |
| mypy ou pyright + django-stubs | não medido | tipos | **dev** | Adotar um só; decidir no PR 1.1 |
| pip-audit, bandit | não medido | segurança | **dev/CI** | Adotar |
| Redis, Celery | - | fila/cache | - | **Não adotar** (sem dor medida) |

## 3. Frontend
**Atualização (PR 1.2, 2026-11-18):** versões, datas e licenças medidas no registro do npm e fixadas em `frontend/package.json` + `package-lock.json` (283 pacotes; `npm audit`: 0 vulnerabilidades; único script de instalação: `fsevents`, opcional e só macOS). Escolhas que divergem da lista abaixo: **TypeScript 6.0.3** (o `typescript-eslint` 8.73 declara `typescript <6.1.0`, então a 7.0.2 não é suportada), `@radix-ui/react-slot` avulso em vez do pacote `radix-ui` (55 dependências), e `lucide-react`/`tw-animate-css` adiados até algum componente usá-los. A tabela abaixo é a pré-triagem original.

| Pacote | Uso | Veredito |
|---|---|---|
| react, react-dom, typescript, vite | base exigida pelo prompt | Adotar |
| tailwindcss | estilo (exigido) | Adotar |
| shadcn/ui (+ Radix, class-variance-authority, clsx, tailwind-merge, lucide-react) | componentes | Adotar (o CLI copia código; as transitivas são as do Radix) |
| @tanstack/react-query | estado de servidor, cache, refetch | Adotar |
| react-router | rotas | Adotar |
| openapi-typescript (ou orval) | tipos a partir do OpenAPI | Adotar um (decidir no PR 1.4) |
| recharts (ou visx) | gráficos de patrimônio | Adiar para a etapa 4-6; escolher então |
| vitest, @testing-library/react | testes | **dev**, Adotar |
| zod ou react-hook-form | formulários e validação de UX | Decidir quando houver formulário complexo; evitar os dois juntos sem necessidade |
| Zustand/Redux | estado global | **Não adotar** |

## 4. Infra e ferramentas externas (avaliação completa na etapa 6)
PaaS/VPS do backend e PostgreSQL gerenciado (D2), serviço de e-mail transacional (verificação/redefinição de senha), captura de erros. São "ferramenta externa" pelo `dependencias-novas.md` (privilégios, lock-in, custo, para onde vai o dado). Nenhuma escolhida.

## 5. Ações do GitHub Actions (CI)
Fixar por **SHA** de commit as ações de terceiros (supply chain). Usar o guard `ci-private-files.yml` do workspace. Modelo de CI para Python ainda não existe em `padrao/workflows/` (só Rust); proponho criar um e devolver ao workspace (sugestão de fluxo).
