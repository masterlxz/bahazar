# 0013: Parâmetros econômicos iniciais (saldo inicial e diária)

**Data:** 2026-11-25

## Contexto
O ADR 0011 (pt. 5) declarou provisórios o saldo inicial, a diária e a recompensa, e mandou decidi-los por simulação antes de abrir caixas (RISCOS D7). Os valores provisórios eram saldo de US$ 100 e diária de US$ 10 × dia da sequência até o dia 30 (US$ 300). A simulação da PR 4.0 (`SIMULACAO-4.0-ECONOMIA.md`, rodada pelo dono em 2026-11-24 com os preços reais do catálogo, mediana ~US$ 1,60 por skin) mostrou: o saldo de US$ 100 já compra o p90 do catálogo (~US$ 60) no dia 0; a renda de regime era ~US$ 300 por dia, cerca de 188 skins medianas por dia; e os sumidouros plausíveis (taxa do mercado, margem das caixas) queimariam só ~3% a ~10% disso (2,9%, 6,0% e 10,5% por perfil).

## Decisão
O dono decidiu em 2026-11-25:
1. **Saldo inicial de US$ 25,00** (`STARTING_BALANCE = 2_500`).
2. **Diária de US$ 2,50 × dia da sequência, com teto no dia 14, ou seja, US$ 35,00** (`DAILY_STEP = 250`, `DAILY_CAP_DAY = 14`).
3. **Regra da sequência mantida:** janela de 24 h e 48 h sem resgatar zera a sequência (`DAILY_WINDOW`, `STREAK_BREAK`).
4. **Anúncio: decidir depois**, com um teto de projeto: valor por anúncio de no máximo ~10% da diária de regime (~US$ 3,50) e limite diário de anúncios. Esta decisão não cria código de anúncio (D12 segue na Etapa 6).

Na simulação, essa combinação foi a única das cinco testadas em que os três perfis de jogador (casual, ativo, ávido) chegam à skin p99 (~US$ 870) em 180 dias: 141, 30 e 27 dias; o p90 sai em 9, 5 e 4 dias.

## Alternativas descartadas
- **Diária de US$ 1,00 com teto no dia 30 e saldo de US$ 25:** o casual (renda de ~US$ 460 em 180 dias) nunca chega à skin p99 no horizonte simulado; o ativo chega em 42 dias.
- **Diária de US$ 0,50:** lenta demais para todos (o ativo leva 67 dias para a p99 e a skin mais cara passa de 180 dias).
- **Manter US$ 100 e US$ 10 até o dia 30:** o saldo inicial compra 90% do catálogo no dia 0 e o ativo chega à p99 em 12 dias.
- **Mudar a regra da sequência** (por exemplo, uma falta reduz a sequência pela metade): não foi simulada; adiada. Ela explica a diferença de 5 a 11 vezes entre casual e ativo.

## Consequências
- **Só valem para carteiras novas e diárias futuras.** O ledger é append-only: o que já foi lançado não muda, e as contas de desenvolvimento que já têm carteira mantêm US$ 100 (uma conta sem carteira abre uma agora, com US$ 25). Se um dia houver jogadores reais, mudar estes valores cria desigualdade entre quem entrou antes e depois.
- **A economia ainda não tem como queimar a renda** (não há taxa de mercado nem caixa). Com a diária de regime de US$ 35 a US$ 40 por dia, queimá-la inteira exigiria ~US$ 360 por dia em caixas com margem de 10%, ou ~US$ 720 por dia no mercado com taxa de 5% (contas à mão sobre a renda do perfil ativo). Revisar quando existirem as trocas (4.2) e o mercado (4.3 e 4.4).
- **Hipóteses:** os perfis, a margem das caixas, a taxa e o valor do anúncio não foram medidos; o casual do modelo é pessimista (resgates independentes, sem padrão semanal).
- **Reabrir quando:** existirem taxa de mercado e caixas reais, ou quando houver dados de jogadores.
- **Custo de reverter:** baixo agora (3 constantes e os testes); alto depois de haver saldos reais.
