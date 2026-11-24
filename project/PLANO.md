# Plano de implementação

Regra do fluxo: tarefa grande vira PRs pequenos; **testes primeiro** (AGENTS.md §3 D); build e teste **só no CI** (ADR 0009 do workspace); um PR = uma intenção. Cada etapa abaixo termina com critério de pronto verificável. Etapas 1, 2, 4 e 5 tocam auth, dinheiro, privacidade e RNG: **confirmação explícita antes de implementar** (AGENTS.md §4).

> **Revisão de 2026-11-19 (ADR 0010 e 0011):** a economia é **global por usuário**, a moeda é virtual em **centavos de USD** e a sala é um **grupo**. As Etapas 2 a 5 foram refeitas. A Etapa 1 e a PR 2.1 (grupos) já estão em `main` e não mudam.

## Etapa 1 · Fundação (feita)
| PR | Conteúdo | Pronto quando |
|---|---|---|
| 1.1 | Esqueleto `backend/` (Django, DRF, settings por ambiente, Postgres) + CI (lint, tipos, testes com Postgres, guard de segredos, `pip-audit`) | CI verde numa branch com 1 teste trivial |
| 1.2 | Esqueleto `frontend/` (Vite, TS, Tailwind, shadcn/ui, tema escuro) + CI (lint, tsc, build, testes) | CI verde |
| 1.3 | Autenticação (allauth headless) + usuário com avatar + testes de permissão | cadastro/login/logout/perfil funcionam; endpoint sem auth → 401 |
| 1.4 | Telas de login, cadastro e perfil (tipos à mão, ADR 0009) | validado no navegador |

## Etapa 2 · Base social e economia global
| PR | Conteúdo | Pronto quando |
|---|---|---|
| 2.1 (**feita**) | `rooms` como **grupo**: membros, papéis, `rooms_for_user`, permissões, limite de 5 salas como dono | CI verde; IDOR 404; mutações provadas |
| 2.2 `economy` global | `wallets` por usuário + `system` global, `wallet_transactions` append-only (trigger), `post_entries`, carteira e **saldo inicial no cadastro**, **resgate diário em sequência** (`daily_claims`, janela de 24h por resgate, `UNIQUE(user, claim_number)`, US$ 10 × dia até o dia 30); **anúncio desativado** por ora | soma do ledger = 0, saldo = extrato, UPDATE/DELETE falham, diária 1x mesmo em paralelo |
| 2.3 `friends` (**implementada**) | `friendships` (pedido, aceite, bloqueio), **permissão central de visibilidade** (`selectors.can_view`: dono e amigo; o caso "grupo" entra na PR que tiver recurso visível a grupo, para `friends` não importar `rooms`) | amigo vê, não-amigo/bloqueado recebe 404; auto-pedido e duplicado recusados no banco |
| 2.4 convites de grupo (**implementada**) | `room_invites` (hash, expiração, usos, revogação) + resgate (entra no grupo; sem dinheiro); padrão 7 dias e 10 usos, tetos 30 dias e 50 usos, 10 convites ativos por sala, resgate limitado a 10 por minuto por usuário | testes de convite (SEGURANCA §10) |
| 2.5a telas: carteira (**implementada**) | ADR 0012 (tipos OpenAPI medidos: seguem à mão, com novo gatilho) + tela `/carteira` com saldo e resgate da diária | fluxo manual descrito no PR |
| 2.5b telas: amigos (**implementada**) | `/amigos`: lista, pedidos recebidos e enviados, enviar por username, aceitar, recusar, remover e bloquear (com confirmação), desbloquear; backend ganha `GET /api/v1/blocks/` (só quem eu bloqueei). Sem página de perfil do amigo (só `username` e `avatar`, já na lista) | fluxo manual descrito no PR |
| 2.5c1 telas: grupos e membros (**implementada**) | `/grupos` (listar, criar, entrar por código) e `/grupos/:roomId` (membros, renomear, sair); backend ganha `GET /api/v1/rooms/<id>/members/` (qualquer membro ativo) | fluxo manual descrito no PR |
| 2.5c2 telas: convites (**implementada; fecha a Etapa 2**) | gerar (validade e usos, padrão 7 dias e 10 usos), listar (com `status` calculado pelo backend) e revogar convite dentro do detalhe do grupo; código mostrado uma vez, só em estado do componente, sem link com o código na URL | fluxo manual descrito no PR |

## Etapa 3 · Catálogo, preço real e inventário
| PR | Conteúdo | Pronto quando |
|---|---|---|
| 3.0 (**medição**) | Medir a **fonte de preços em USD** (licença, limites, cobertura, itens sem preço): RISCOS D11 e R8. Resultado: relatório, sem código | decisão do dono sobre a fonte |
| 3.1 | App `catalog` (`skins`) + comando `import_catalog` (catálogo ByMykel, MIT, e snapshot da Skinport, ambos por arquivo local fora do repo) com `reference_price` em centavos de USD. **Sem imagens** (D1 na 3.3) | ~1.455 skins importadas (todas com preço; antes eram 100-200), reexecutar é idempotente |
| 3.2a (**implementada**) | App `inventory`: `skin_instances` (dono = usuário), float dentro da faixa da skin (trigger), desgaste derivado (`rules.wear_for`), `services.create_instance` e o comando `grant_skin` (única forma de dar uma skin por ora). **Sem API** | trigger e CHECKs provados contra PostgreSQL; varredura do desgaste; mutações pegas |
| 3.2b (**implementada**) | API do inventário (`/inventory/` e `/inventory/<username>/`), filtros (`rarity`, `weapon`, `wear`, `q`), ordenação, paginação e **ver o inventário de um amigo** pela permissão central (`friends.selectors.can_view`). Toca autorização: plano e confirmação próprios | não-amigo, pendente, bloqueado e usuário inexistente recebem o mesmo 404 |
| 3.3 | Telas de inventário e coleção | revisão visual |

## Etapa 4 · Economia e trocas
| PR | Conteúdo | Pronto quando |
|---|---|---|
| 4.0 (**simulação**) | Planilha de simulação da economia (saldo inicial, diária, anúncio, taxa, valor esperado das caixas): decide a D7 com números | decisão do dono |
| 4.1 | Idempotência (`idempotency_records`) + transferência entre jogadores | testes de concorrência e replay |
| 4.2 | **Troca de itens entre amigos** (oferta, aceite atômico, cancelamento) | uma skin, uma oferta ativa (sob concorrência) |
| 4.3 | `market_listings` global: criar/cancelar/listar; índice único parcial | uma skin, um anúncio ativo |
| 4.4 | Compra atômica + taxa + `market_transactions` | N compradores simultâneos: 1 sucesso; reconciliação OK |
| 4.5 | Extrato, patrimônio, telas do mercado e das trocas | revisão visual |
| 4.6 | Teste de propriedade (Hypothesis) das invariantes + mutação deliberada | mutações derrubam testes |

## Etapa 5 · Progressão e caixas
| PR | Conteúdo | Pronto quando |
|---|---|---|
| 5.1 | Caixas (`cases`, `case_drops`, `case_openings`) + RNG servidor + snapshot | qui-quadrado + atomicidade |
| 5.2 | **Batalha de caixa** (`battles`, módulo): lobby (reaproveita grupos), entrada paga, abertura simultânea, pagamento do vencedor | pagamento soma zero; sem "roll" vindo do cliente; atomicidade |
| 5.3 | Trade-ups | validações e float de saída |
| 5.4 | XP, níveis, missões, conquistas (por evento do núcleo) | sem importação cruzada entre módulos (teste de arquitetura) |
| 5.5 | Rankings (patrimônio, saldo, inventário, evolução) | consultas paginadas; medir antes de materializar |

## Etapa 6 · Polimento
Tempo real (SSE), refinamento visual e mobile, testes de segurança e carga, observabilidade, backup com restauração testada, **anúncio real** (decisão D12: SDK, receita, LGPD), deploy (staging → prod), README e runbook.

## Fora do plano inicial
Salas públicas, comunidades, temporadas ativas, moderação, economias personalizadas: só o esquema e as fronteiras ficam preparados. **Dinheiro real, depósito, saque e aposta: fora para sempre** (ADR 0011).

## O que preciso de você
Respostas às decisões abertas em [RISCOS.md](RISCOS.md): D3 (antes do deploy), D7 (na PR 4.0), D2 (depois da Etapa 2), D11 (fonte de preços, PR 3.0) e D12 (anúncio real, Etapa 6).
