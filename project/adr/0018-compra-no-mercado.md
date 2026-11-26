# 0018: Compra no mercado: taxa, ponte com `economy` e o que a venda grava

**Data:** 2026-11-26

## Contexto
A 4.3 deixou anunciar, cancelar e listar. A compra é a primeira operação que move **posse e dinheiro na mesma transação**: o comprador paga, o vendedor recebe menos a taxa, a carteira `system` queima a taxa, o item troca de dono e o anúncio vira `sold`. Já estavam decididas a ordem de trava (ADR 0016), a regra do bloqueio (ADR 0017) e a idempotência na mesma transação (ADR 0014). Faltava decidir a taxa, onde `marketplace` fala com `economy` (um teste de arquitetura o proibia) e o que a compra grava.

## Decisão (dono, 2026-11-26)
1. **Taxa de 5% (`MARKET_FEE_BPS = 500`), arredondada para baixo.** `taxa = preço * 500 // 10000`; o vendedor recebe `preço - taxa` e nunca zero. Preço até 19 centavos paga taxa 0 e o ledger leva só duas linhas. **O 5% é hipótese**: vem da simulação 4.0 (ADR 0013), nada foi medido. Reabrir com dados reais ou quando existirem caixas.
2. **A ponte com `economy` fica só em `marketplace/services.py`**, e só nos módulos `economy.services`, `economy.idempotency` e `economy.rules`. O serviço roda o `run_once` por dentro, como `economy.transfer`. Views, selectors, models e serializers continuam sem `economy`, e nenhum módulo importa `economy.models`. O erro de saldo, a chave repetida e a chave inválida são traduzidos para erros do mercado dentro do serviço. O teste de arquitetura (`_EXCECOES`) impõe isto.
3. **`POST /api/v1/listings/<id>/buy/`** com `Idempotency-Key` (UUID). Devolve 201 com `id`, `listing_id`, `price`, `fee` e `ledger_group_id` (a repetição também). O corpo é ignorado: preço, dono e taxa nunca vêm do cliente. Anúncio escondido pelo bloqueio do comprador dá o mesmo 404 de anúncio inexistente. O bloqueado compra normalmente (ADR 0017). Throttle `market_listing_buy`, 30/min (hipótese).
4. **O que a compra faz, nesta ordem** (a ordem de trava é a do ADR 0016): lê o anúncio sem trava só para achar o vendedor, abre as carteiras fora da transação, e dentro do `run_once` trava jogadores por `pk`, o anúncio e a instância, reconferindo estado, dono e consumo sob a trava. Depois muda o dono (`change_owner` com `authorized_by` = id do anúncio), grava o ledger, marca o anúncio `sold` e grava a venda. O `change_owner` vem **antes** do lançamento porque trava a instância de novo, e a instância tem de ser travada antes das carteiras.
5. **Ledger:** três linhas em um grupo (comprador `-P`, vendedor `+(P-taxa)`, `system` `+taxa`; a da taxa é omitida se for 0), cada uma com o seu tipo (`market_purchase`, `market_sale`, `market_fee`) e `ref_id` = id do anúncio. `economy.services.Entry` ganhou o campo opcional `kind`; sem ele a linha leva o tipo do lançamento.
6. **`MarketTransaction`** (append-only): `listing` único, `buyer`, `seller`, `price`, `fee`, `ledger_group_id`. Constraints: comprador diferente do vendedor e `0 <= taxa < preço` (que já garante preço positivo). Trigger `BEFORE UPDATE OR DELETE` na migração `0003`, escrita à mão como a do ledger. Todas as FKs são `PROTECT`. **Não há coluna `idempotency_key`**: a chave de negócio que sobrevive à expiração do registro de idempotência é o `UNIQUE(listing)`, mais o estado `sold` do anúncio.

## Alternativas descartadas
- **Taxa arredondada para cima:** todo preço pagaria pelo menos 1 centavo, mas o preço de 1 centavo deixaria o vendedor com zero, e o ledger recusa valor nulo; exigiria piso de preço.
- **Ponte com `economy` na view (como `trades`):** `trades` não paga nada, e o serviço da compra precisa de `post_entries` de qualquer jeito; a ponte do dinheiro teria de ir para a view ou para um módulo novo.
- **`marketplace` lendo `Wallet` direto:** acopla o mercado ao modelo interno do `economy` e fura "só `economy.services` altera saldo".
- **Um tipo de ledger para as três linhas (`market_purchase`):** o extrato do vendedor mostraria "Compra no mercado" para uma venda.
- **Coluna `idempotency_key` na venda (o desenho de `MODELO-DE-DADOS`):** a idempotência já vive em `idempotency_records` e no ledger; `UNIQUE(listing)` é mais forte (vale mesmo com chaves diferentes).
- **Anúncio primeiro na trava:** já descartado no ADR 0016.
- **Chave do ledger montada com a chave do cliente** (`market_buy:<comprador>:<chave>`, a 1ª versão): o `UNIQUE(carteira, chave)` do ledger estourava (500) quando o mesmo cliente reusava a chave num anúncio diferente depois de expirar o registro de idempotência. Achado da revisão da Sessão 35; hoje a chave é `market_buy:<id do anúncio>`.

## Ajustes depois da revisão adversária e da auditoria (Sessão 35)
- **A chave de idempotência das linhas do ledger é `market_buy:<id do anúncio>`**, independente da do cliente. Depois de expirar o registro, a mesma chave num OUTRO anúncio é uma compra nova; no MESMO anúncio dá 409 `listing_not_active` (a guarda durável é o estado `sold` e o `UNIQUE(listing)`), sem mover nada. Quem perdeu a resposta de uma compra feita há mais de 7 dias recebe 409, não o recibo.
- **Erros do `inventory` na troca de dono** (`NotOwner`, `ConsumedInstance`, `ItemLocked`) e o `ValueError` de `split_price` (preço gravado direto no banco acima do teto) viram `409 listing_unavailable`. Isso também deixa de revelar, por `item_locked`, que o item está numa oferta de troca pendente.
- **A chave é validada antes do bloqueio:** a ordem das checagens não pode revelar a quem bloqueou. O serviço recebe `hide_sellers` (a view os lê do `friends`). O replay de uma compra de um vendedor que o comprador bloqueou depois dá 404, não o recibo.
- **O 409 da compra de anúncio fechado revela que o id já existiu** (o `GET` dá 404). Aceito: o UUID não é adivinhável e o anúncio já foi público.

## Adendo da 4.4b: `Idempotency-Key` em criar e cancelar (Sessão 37, dono, 2026-11-26)
- **Obrigatória** nas duas rotas (400 `invalid_idempotency_key` sem ela), como na compra e em `trades`. A ponte com `economy.idempotency` segue só em `services.py`: `create_listing` e `cancel_listing` rodam dentro do `run_once` (escopo `user:<id>`, impressão digital `market_create`/`market_cancel` com jogador e alvo) e devolvem `ListingOutcome(body, status, replayed)`.
- **A repetição devolve o corpo gravado** (um retrato): o replay do criar de um anúncio já cancelado mostra `active`. Cancelar repetido com a MESMA chave dá 200 (antes 409); com OUTRA chave num anúncio fechado continua 409. Mesma chave com outro item, preço ou operação: 422.
- **O corpo repetido é um retrato, em qualquer estado:** o replay do criar devolve `status: active` também depois da VENDA e o item de antes da troca; nunca use o corpo repetido como estado atual (use `GET /listings/<id>/`). Fixado por `test_replay_do_criar_depois_da_venda_devolve_o_retrato_active_nao_o_estado_atual`. O `jsonb` do PostgreSQL também reordena as chaves do corpo repetido (inofensivo para JSON).
- **Sem guarda durável do criar (aceito):** depois que o registro expira (7 dias) um criar antigo reenviado recria o anúncio; o teste `test_a_chave_do_criar_expirada_deixa_criar_de_novo_limite_aceito` documenta. **Descartada:** coluna `idempotency_key` com `UNIQUE(vendedor, chave)` (migração em tabela de posse; o ADR já recusou a coluna na venda). Reabrir se o risco pesar.

## Consequências
- Quem criar outra operação que mexa em dinheiro e posse segue a mesma regra: a ponte fica no serviço, e o caso entra em `tests/test_lock_order.py`.
- A `system` é um ponto quente: toda compra com taxa trava a carteira global (já no PENDING). Aceito nesta escala.
- **O que os testes provam:** a corrida de 8 compradores no mesmo anúncio (1 sucesso, 7 recusas, ledger fechado), a ordem de trava (por SQL emitido e por `pg_locks` contra criar anúncio e trocas) e que cada reconferência sob trava é necessária (11 mutações, todas caem em teste).
- **O que não provam:** a taxa de 5% e o limite de 30 compras por minuto são hipóteses; a corrida real depende do PostgreSQL 17 do CI (poucas execuções); nada rodou fora do CI; não há frontend.
- **Custo de reverter:** médio. A migração só cria uma tabela e um trigger (reverter = `migrate marketplace 0002`); a ponte com `economy` é um arquivo e uma exceção de teste.
