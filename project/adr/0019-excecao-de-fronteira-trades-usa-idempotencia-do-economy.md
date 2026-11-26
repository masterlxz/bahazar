# 0019: Exceção de fronteira: a view de `trades` usa a idempotência e as regras puras do `economy`

**Data:** 2026-11-26 (registra a decisão do dono de 2026-11-25, Sessão 28, A2)

## Contexto
`trades` é troca só de itens, sem dinheiro: pelo desenho (GUIDELINES 2 e 5) não conhece carteira nem ledger. Mas as 4 rotas de troca (`POST /trades/` e `accept|decline|cancel`) precisam do `Idempotency-Key` (ADR 0014), e quem o implementa é `economy.idempotency.run_once`, com `normalize_idempotency_key` e `request_fingerprint` em `economy.rules`. O teste de arquitetura proibia qualquer import de `economy` em `trades`.

## Decisão
**Só `trades/views.py`** pode importar `apps.economy.idempotency` e `apps.economy.rules`. Nenhum outro arquivo de `trades` (serviço, seletor, serializer, modelo, guarda) importa `economy`; `economy.models` e `economy.services` (carteira, ledger, saldo) seguem proibidos em todo `trades`. A view roda o serviço de troca DENTRO do `run_once`: o registro da chave e a troca confirmam na mesma transação, e um erro do serviço desfaz os dois (a chave não fica "queimada"). Quem impõe isto é `tests/trades/test_trades_arquitetura.py`.

## Alternativas descartadas
- **Mover a idempotência para um módulo neutro** (fora de `economy`): resolveria a fronteira, mas é refatoração de um módulo já provado em CI (ADR 0014) sem dor além desta exceção; reabrir se um terceiro app precisar dela.
- **Duplicar `run_once` em `trades`:** dois lugares com a mesma garantia de unicidade sob corrida; um deles envelheceria.
- **`trades` importar `economy.services`:** abre a carteira para um módulo que não deve mexer em dinheiro.

## Consequências
- A exceção é **por módulo** em `trades` (`economy.idempotency` e `economy.rules`), diferente do mercado, onde o teste confere também o NOME importado (ADR 0018 e Sessão 40). Se um dia pesar, o mesmo molde vale para `trades`.
- O mercado tem uma exceção parecida e mais larga (`economy.services` para o dinheiro da compra, ADR 0018).
- **Custo de reverter:** baixo (uma linha no teste e os imports da view).
