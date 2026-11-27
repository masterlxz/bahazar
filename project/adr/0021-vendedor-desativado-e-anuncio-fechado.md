# 0021: Mercado: vendedor desativado conta como anúncio fechado

**Data:** 2026-11-27 (registra a decisão do dono da Sessão 55, PR #346; completa a regra "só ao agir" da Sessão 54, PR #327)

## Contexto
`is_active=False` (conta desativada) é recusado ao agir em trocas, compras e `transfer` (Sessão 54,
`PlayerUnavailable`, 409 genérico). No mercado isso deixou dois problemas:
- a vitrine continuava listando anúncios de vendedor desativado, que nunca poderiam ser comprados
  (a compra dava 409 `player_unavailable`: a vitrine virava um oráculo de "esta conta foi desativada");
- a 1ª versão da correção da Sessão 55 escondia o anúncio e dava **404** na compra, "igual ao de
  inexistente". O revisor mostrou que isso não protege o que importa: quem raspou a vitrine guarda
  o `id`; depois que o anúncio some, 404 na compra = desativado e 409 = fechado.

## Decisão (dono, 2026-11-27)
1. **Vitrine e detalhe filtram `seller__is_active=True`** (404 para o anúncio de vendedor
   desativado). O filtro mora em `marketplace/selectors.py:_vendaveis`, ponto único dos dois.
2. **A compra de anúncio de vendedor desativado dá `ListingNotActive` (409 `listing_not_active`)**,
   a mesma resposta de um anúncio vendido ou cancelado, em qualquer estado do anúncio. Em
   `marketplace/services.py:buy_listing`, a leitura de `is_active` é do banco, depois de travar os
   jogadores (`_travar_jogadores`, depois `_ativos`).
3. **A checagem do vendedor vem antes da do comprador.** Comprador desativado segue com
   `PlayerUnavailable`: ele é o ator, e a resposta só fala dele.
4. **Regra de uma frase:** o mercado trata vendedor desativado como anúncio fechado.

## Alternativas descartadas
- **Aceitar o 409 `player_unavailable` na compra de vendedor desativado (e não filtrar a vitrine):**
  descartada pelo dono; deixa a vitrine mostrar o que não pode ser comprado e vaza o estado da conta.
- **Esconder da vitrine e manter o 404 na compra:** descartada depois da revisão; o `id` visto
  distingue "desativado" (404) de "fechado" (409).
- **404 para todo anúncio não ativo (vendido, cancelado, desativado):** igualaria as respostas, mas
  mudaria o contrato dos outros estados, e o frontend não foi conferido (hoje ele nem tem tela de
  mercado). (Motivo registrado na Sessão 55; o dono escolheu o 409 sem ditar mais que isso.)
- **Pré-checar o vendedor antes do `run_once`:** quebraria o replay do recibo (Sessão 55).

## Consequências
- **Canal residual aceito:** `IdempotencyKeyReused` (422) só ocorre para anúncio que existe,
  inclusive o escondido. Vale para qualquer anúncio e só para um `id` já visto.
- **Não medido:** timing e número de consultas do caminho "vendedor desativado" contra o
  "inexistente" (diferentes). Se o timing virar ameaça, este ADR não o cobre.
- **Anúncios de quem foi desativado seguem segurando os itens** (não há expiração de anúncios nem
  gancho de desativação; `PENDING.md`, "Jogador desativado" (b)).
- **Etapa 5 (caixas, trade-ups):** quem mover posse tem de checar `is_active` (`change_owner` não
  checa; `PENDING.md` (d)).
- **Custo de reverter:** baixo a médio: `_vendaveis`, a checagem em `buy_listing` e os testes de
  `test_marketplace_inativo.py` e `test_lock_order.py` (a leitura de `is_active` tem de estar no `WHERE`).
- Relacionados: ADR 0017 (vitrine e bloqueio), 0018 (compra), 0016 (ordem de trava).
