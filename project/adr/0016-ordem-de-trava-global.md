# 0016: Ordem de trava global das operações transacionais

**Data:** 2026-11-26

## Contexto
`SEGURANCA.md` §6, `RISCOS.md` R3 e o ADR 0002 diziam "anúncio → instância → carteiras por UUID". O código nunca seguiu isso: `trades` trava jogadores, depois a oferta, depois as instâncias; `marketplace.create_listing` trava o vendedor e depois a instância; `economy.post_entries` trava carteiras por id. A 4.4 (compra) junta tudo na mesma transação, e duas ordens diferentes entre operações são deadlock.

O deadlock já aconteceu, e foi medido: na Sessão 31, `create_listing` travava a instância antes do vendedor. O `INSERT` do anúncio toma `KEY SHARE` na linha do vendedor (a FK), que conflita com o `FOR UPDATE` que `trades` segura nos jogadores. As duas transações esperavam uma pela outra, e o PostgreSQL 17 do CI abortou uma (`deadlock detected`).

## Decisão
Toda transação que trava mais de uma linha segue esta ordem, e só pega um trecho dela, sem voltar atrás:

1. **jogadores**, por `pk` crescente;
2. **anúncio ou oferta** (`marketplace_marketlisting` ou `trades_tradeoffer`; nenhuma operação trava os dois);
3. **instâncias**, por `pk` crescente;
4. **carteiras**, por `id` crescente (`economy.post_entries` já faz).

A compra (4.4) lê o anúncio sem trava só para achar vendedor e instância (como `accept_offer` faz com a oferta), trava comprador e vendedor por `pk`, trava o anúncio e reconfere o estado, trava a instância e deixa o `post_entries` travar as carteiras.

`tests/test_lock_order.py` fixa a ordem lendo o `SELECT ... FOR UPDATE` que cada serviço emite. A compra entra na tabela de casos quando existir.

## Alternativas descartadas
- **Anúncio primeiro (a redação antiga):** o anúncio não existe quando `create_listing` começa, então não há o que travar antes; e `trades` (dois módulos já provados em CI) teria de mudar de ordem sem ganho.
- **Só a instância como âncora (sem jogadores):** não cobre a FK. `KEY SHARE` no jogador conflita com `FOR UPDATE` dos jogadores em `trades`, e foi esse o ciclo medido.
- **Deixar o PostgreSQL resolver (retry em deadlock):** `SEGURANCA.md` já prevê retry de 3 tentativas, mas o deadlock custa 1 s (`deadlock_timeout`) e devolve 500 se esgotar. O retry é rede de segurança, não a defesa.

## Consequências
- `SEGURANCA.md` §6, `RISCOS.md` R3 e o ADR 0002 passam a remeter a este ADR; o texto antigo fica só como histórico.
- Quem criar uma operação nova que trave jogadores e instâncias escreve o caso dela em `test_lock_order.py`.
- `inventory.services.change_owner` sozinho continua perigoso fora de `trades` (docstring dele): quem o chamar trava antes os jogadores, depois a instância.
- **O que o teste não prova:** ausência de deadlock em corrida real. Isso fica com os testes de `pg_locks` (`test_marketplace_locks.py`, `test_trades_concurrency.py`), que a 4.4 precisa estender para compra × criar × aceitar.
- **Primeira consequência medida (Sessão 36):** a diária (`claim_daily`) travava a carteira do jogador e só depois chamava `post_entries`. A compra, que trava `system` e a carteira do jogador por `id`, formava um ciclo com ela quando `system.id < carteira.id`. O CI reproduziu o `deadlock detected`. A diária passou a travar o USUÁRIO e deixar o `post_entries` travar as carteiras: regra geral, **nenhuma operação trava uma carteira à mão antes de chamar `post_entries`**. O `test_lock_order` compara tabelas e não pega esse tipo de ciclo (as duas travas são da mesma tabela); quem pega é o teste de `pg_locks` da diária.
- **Custo de reverter:** baixo (documento e um teste); trocar a ordem depois de a compra existir custa uma reescrita de três serviços.
