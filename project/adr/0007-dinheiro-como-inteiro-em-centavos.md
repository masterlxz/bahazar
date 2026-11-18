# 0007: Dinheiro como inteiro em centavos

**Data:** 2026-11-18

## Contexto
Saldos, preços e taxas precisam ser exatos e auditáveis. Ponto flutuante causa erro de arredondamento.

## Decisão
Todo valor monetário é `bigint` em centavos do jogo (1 unidade = 0,01 moeda virtual). Taxas em basis points (`int`, 100 = 1%), com o arredondamento definido num único lugar (função pura em `rules.py`, testada). Proibido `float` e `Decimal` para saldo, preço e taxa. O frontend só formata (`Intl.NumberFormat` sobre inteiros).

## Alternativas descartadas
- **`numeric(p,s)`/`Decimal`:** exato, mas convida a misturar escalas e exige cuidado extra em cada conversão; inteiro é mais simples e rápido.
- **`float`:** inexato.

## Consequências
- Divisões (taxa, taxa sobre preço pequeno) precisam de regra de arredondamento explícita e teste de borda (preço 1, taxa 1%).
- Valor máximo limitado a `bigint`; validar entrada contra o limite.
- **Custo de reverter:** alto depois de haver dados.
