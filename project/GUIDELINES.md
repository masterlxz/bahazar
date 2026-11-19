# Guidelines de código (rascunho)

Valem os padrões do workspace (`AGENTS.md`, `padrao/arquitetura.md`, `padrao/modularidade.md`). Específico do projeto:

## Dinheiro e itens
1. Valor monetário é **inteiro** em centavos (`bigint`/`int`). Proibido `float` e `Decimal` para saldo, preço ou taxa.
2. Só `economy.services` altera saldo; só `inventory.services` altera dono de item. Nenhuma view, serializer ou admin escreve nessas tabelas.
3. Toda operação que move valor ou item: `transaction.atomic`, travas na ordem fixa, `Idempotency-Key`, lançamento no ledger na mesma transação.
4. Tabelas append-only nunca recebem `UPDATE`/`DELETE`; correção é lançamento compensatório.

## Estrutura
5. View fina; regra em `rules.py` (puro, sem Django) e I/O em `services.py`.
6. Leitura de dados de jogo só por `selectors` escopados ao usuário (dono, amigo ou grupo, ADR 0010). Proibido `Model.objects.all()` em view.
7. Módulo não importa módulo; núcleo não importa módulo. Teste de arquitetura no CI.
8. Serializers com `fields` explícito (nunca `__all__`), campos de escrita mínimos.

## Testes
9. Concorrência e ledger testam contra **PostgreSQL real**, no CI. Teste que "só passa" sem asserção de invariante não conta.
10. Mudança de comportamento tem teste que falha antes e passa depois; código crítico ganha mutação deliberada.

## Frontend
11. Sem regra de negócio em componentes. Valores monetários chegam como inteiros e são só formatados.
12. Tipos vêm do OpenAPI gerado; `any` só com comentário justificando.
