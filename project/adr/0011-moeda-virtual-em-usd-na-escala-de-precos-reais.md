# 0011: Moeda virtual em USD, na escala de preços reais

**Data:** 2026-11-19

## Contexto
O dono quer que "a moeda seja real": os preços das skins no jogo devem refletir os preços reais. O escopo do projeto proíbe dinheiro real, depósito, saque e aposta (OVERVIEW, RISCOS J2). "Real" aqui significa **escala**, não conversão.

## Decisão
1. A moeda do jogo é **virtual**. A unidade do ledger é **1 centavo de dólar (USD)**: uma skin de referência US$ 12,34 vale `1234`. Continua `bigint` (ADR 0007).
2. O preço de uma skin vem de `skins.reference_price` (dado **nosso**, atualizado por import), em centavos de USD.
3. **Não há conversão para dinheiro real**: sem depósito, saque, compra de moeda ou transferência para fora. A fronteira de pagamento, se um dia existir, é uma decisão separada com análise jurídica.
4. Moeda nova entra **só pela carteira `system`**: saldo inicial, recompensa diária e recompensa por anúncio. Anúncio é **simulado** nesta fase (sem SDK, receita nem rastreamento).
5. Os valores de saldo inicial, diária e recompensa são **provisórios** e saem de uma simulação antes de abrir caixas (D7).

## Alternativas descartadas
- **BRL como referência:** exige converter preços de fontes em dólar e decidir a frequência de atualização do câmbio; mais uma fonte de erro.
- **Moeda em escala arbitrária (1 skin = N "gemas"):** o dono quis a escala real; evita explicar a conversão ao jogador.
- **Dinheiro real de verdade:** contradiz o escopo "fora para sempre"; batalha de caixa com valor real é jogo de azar (risco J2) e envolve licença, regulação e a política da Valve. Não implementar sem decisão separada.

## Consequências
- **Premissa não verificada:** que existe uma fonte de preços em USD com licença e limites utilizáveis (RISCOS R8 e D11). Precisa ser **medida antes** do catálogo; este ADR não promete a fonte.
- Skins muito caras cabem em `bigint` com folga (uma skin de US$ 1 milhão = 10^8 centavos), mas o preço de referência de itens raros pode ser instável ou ausente.
- A renda diária e o saldo inicial precisam ser pequenos frente aos preços reais para a economia não inflar; por isso a D7 vem antes das caixas.
- **Custo de reverter:** baixo agora; alto depois de haver saldos e preços gravados.
