# bahazar: índice do projeto

## Como Usar Este Arquivo
Mapa dos documentos de `project/`. Leia nesta ordem para revisar a primeira entrega (arquitetura, sem código).

| Ordem | Arquivo | O que responde |
|---|---|---|
| 1 | [OVERVIEW.md](OVERVIEW.md) | O que é, stack, fases e status |
| 2 | [ARQUITETURA.md](ARQUITETURA.md) | Camadas, módulos, fluxos ponta a ponta |
| 3 | [MODELO-DE-DADOS.md](MODELO-DE-DADOS.md) | Tabelas, constraints, índices, dinheiro, ledger |
| 4 | [SEGURANCA.md](SEGURANCA.md) | Ameaças, autorização (no lugar do RLS), testes de fraude |
| 5 | [PLANO.md](PLANO.md) | Etapas e PRs pequenos |
| 6 | [DEPENDENCIAS.md](DEPENDENCIAS.md) | Dependências e busca de "pronto antes de criar" |
| 7 | [RISCOS.md](RISCOS.md) | Riscos e decisões pendentes do dono |
| - | [PENDING.md](PENDING.md) | O que está em aberto |
| - | [GUIDELINES.md](GUIDELINES.md) | Regras de código do projeto (rascunho) |
| - | [SESSIONS.md](SESSIONS.md) | Registro de sessões (mais recente no topo) |

ADRs ficam em `project/adr/` (0001 a 0008, lista em [PENDING.md](PENDING.md)).

## Normas do workspace que valem aqui
`AGENTS.md` (fluxo), `padrao/arquitetura.md` (simplicidade primeiro), `padrao/modularidade.md` (núcleo + módulos), `padrao/dependencias-novas.md` (procurar pronto e avaliar dependência), ADR 0009 do workspace (build e teste só no CI).
