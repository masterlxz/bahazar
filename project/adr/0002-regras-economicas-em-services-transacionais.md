# 0002: Regras econômicas em services transacionais

**Data:** 2026-11-18

## Contexto
Compra, transferência, abertura de caixa e trade-up movem dinheiro e itens. O cliente não é confiável; as operações precisam ser atômicas, idempotentes e testáveis, inclusive sob concorrência.

## Decisão
A regra fica em funções de serviço no Django (`services.py`), cada uma dentro de `transaction.atomic()`, com `select_for_update` em ordem fixa (anúncio → instância → carteiras por UUID; **ordem substituída pelo ADR 0016**: jogadores → anúncio ou oferta → instâncias → carteiras) e `Idempotency-Key`. A decisão pura (validações, divisão de preço e taxa) fica em `rules.py`, sem I/O. Views são finas; só `economy.services` altera saldo e só `inventory.services` altera dono de item.

## Alternativas descartadas
- **Procedures PL/pgSQL:** regra no banco, mais difícil de testar e versionar para quem vem de Django.
- **Lógica no cliente com permissões de tabela:** o cliente decidiria valores; inseguro.

## Consequências
- Regras testáveis sem HTTP; I/O testado com Postgres real no CI.
- A disciplina "só o service escreve" é convenção; o banco reforça com constraints e privilégios (ADR 0003).
- **Custo de reverter:** médio.
