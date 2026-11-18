# 0003: Ledger de partida dobrada com carteira `system`

**Data:** 2026-11-18

## Contexto
O saldo não pode ser um número editável. É preciso auditoria, reconciliação e controle de inflação por sala.

## Decisão
`wallet_transactions` é append-only e agrupa lançamentos por `group_id` cuja soma é zero. Dinheiro criado ou destruído (saldo inicial, recompensas, taxas, preço de caixa) passa pela carteira `system` da sala. `wallets.balance` é cache atualizado só pelo service, com `CHECK balance >= 0` para jogadores. Imutabilidade por `REVOKE` de UPDATE/DELETE mais trigger; correção por lançamento compensatório.

## Alternativas descartadas
- **Saldo mutável sem histórico:** sem auditoria.
- **Ledger de entrada simples (sem contrapartida):** não permite reconciliar nem medir a oferta monetária.
- **Biblioteca contábil pronta (django-hordak, django-double-entry):** trazem plano de contas e conceitos que sobram; o encaixe com `system`, idempotência e append-only por trigger custaria mais que um ledger de ~3 tabelas. Revisar se o dono preferir pronto (piloto descartável).

## Consequências
- Invariantes verificáveis: soma por sala = 0 e `balance` = soma do extrato.
- Mais linhas por operação (2 a 3), irrelevante nesta escala.
- Dinheiro é inteiro em centavos (ADR 0007).
- **Custo de reverter:** alto depois de haver dados.
