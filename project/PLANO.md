# Plano de implementação

Regra do fluxo: tarefa grande vira PRs pequenos; **testes primeiro** (AGENTS.md §3 D); build e teste **só no CI** (ADR 0009 do workspace); um PR = uma intenção. Cada etapa abaixo termina com critério de pronto verificável. Etapas 1, 4 e 5 tocam auth, dinheiro e RNG: **confirmação explícita antes de implementar** (AGENTS.md §4).

> Nenhuma etapa começa antes da sua aprovação desta arquitetura.

## Etapa 1 · Fundação
| PR | Conteúdo | Pronto quando |
|---|---|---|
| 1.1 | Esqueleto `backend/` (Django, DRF, settings por ambiente, Postgres) + CI (lint, tipos, testes com Postgres, guard de segredos, `pip-audit`) | CI verde numa branch com 1 teste trivial |
| 1.2 | Esqueleto `frontend/` (Vite, TS, Tailwind, shadcn/ui, tema escuro) + CI (lint, tsc, build, testes) | CI verde |
| 1.3 | Autenticação (biblioteca escolhida em DEPENDENCIAS) + `profiles` (username único, avatar) + testes de permissão | cadastro/login/logout/perfil funcionam; endpoint sem auth → 401 |
| 1.4 | Contrato OpenAPI → tipos TS gerados; tela de login/perfil | tipos regenerados sem diff no CI |

## Etapa 2 · Multiplayer
| PR | Conteúdo | Pronto quando |
|---|---|---|
| 2.1 | `rooms`, `room_members`, permissões (`IsRoomMember`, `IsRoomAdmin`), manager escopado | teste de IDOR parametrizado cobre todo endpoint da etapa |
| 2.2 | `room_invites` (hash, expiração, usos, revogação) + resgate | testes de convite (SEGURANCA §10) |
| 2.3 | `economy`: `wallets` + `wallet_transactions` + `post_entries` + saldo inicial + triggers/REVOKE | invariantes de soma zero e imutabilidade testadas |
| 2.4 | Telas de sala, convite, participantes, configuração | fluxo manual descrito no PR |

## Etapa 3 · Catálogo e inventário
| PR | Conteúdo | Pronto quando |
|---|---|---|
| 3.1 | `skins` + comando de import a partir de dado aberto (fonte e licença verificadas; decisão sobre imagens, D1) | 100-200 skins importadas, reexecutar é idempotente |
| 3.2 | `skin_instances`, float, desgaste derivado, inventário (filtros, ordenação, paginação) | testes de propriedade e de float dentro da faixa |
| 3.3 | Tela de inventário e coleção | revisão visual |

## Etapa 4 · Economia
| PR | Conteúdo | Pronto quando |
|---|---|---|
| 4.1 | Idempotência (`idempotency_records`) + transferência entre jogadores | testes de concorrência e replay |
| 4.2 | `market_listings`: criar/cancelar/listar; índice único parcial | uma skin, um anúncio ativo (testado sob concorrência) |
| 4.3 | Compra atômica + taxa + `market_transactions` | N compradores simultâneos: 1 sucesso; reconciliação OK |
| 4.4 | Extrato, patrimônio, telas do mercado | revisão visual |
| 4.5 | Teste de propriedade (Hypothesis) das invariantes + mutação deliberada | mutações derrubam testes |

## Etapa 5 · Progressão
| PR | Conteúdo | Pronto quando |
|---|---|---|
| 5.1 | Caixas (`cases`, `case_drops`, `case_openings`) + RNG servidor + snapshot | qui-quadrado + atomicidade |
| 5.2 | Trade-ups | validações e float de saída |
| 5.3 | XP, níveis, missões, conquistas (por evento do núcleo) | sem importação cruzada entre módulos (teste de arquitetura) |
| 5.4 | Rankings (patrimônio, saldo, inventário, evolução) | consultas paginadas; medir antes de materializar |

## Etapa 6 · Polimento
Tempo real (SSE), refinamento visual e mobile, testes de segurança e carga, observabilidade, backup com restauração testada, deploy (staging → prod), README e runbook.

## Fora do plano inicial
Salas públicas, comunidades, temporadas ativas, moderação, economias personalizadas: só o esquema e as fronteiras ficam preparados.

## O que preciso de você para começar a Etapa 1
Respostas às decisões D1-D8 em [RISCOS.md](RISCOS.md) (principalmente D2, D3 e D7).
