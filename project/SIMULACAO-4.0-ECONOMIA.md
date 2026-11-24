# Simulação da economia (PR 4.0, D7)

**Data:** 2026-11-24. **Quem rodou:** o dono, no PC dele; eu vi a saída colada, não rodei o script (ADR 0017).
**Reproduzir:** `python3 project/simulacao/economia.py` (só biblioteca padrão; importa `apps.economy.rules`). Entrada: `backend/data/precos_percentis.json`, gerado do banco local e **fora do repo** (o repo é público e os termos da Skinport não foram lidos). Semente 2026; 500 jogadores sorteados no perfil casual. `verificações: OK` na saída: o modelo reproduz `rules.daily_amount` nos dias 1 a 60 e a conta de US$ 4.650 em 30 dias do `PENDING.md`.

**A decisão da D7 continua sendo do dono.** Este relatório traz números e uma recomendação; nenhum valor do código foi alterado. Os valores escolhidos entram na PR 4.0b (`rules.py` e testes), que mexe em dinheiro (AGENTS §4) e pede confirmação própria.

## O que o modelo é, e o que não é
- **Vem do código:** saldo inicial (US$ 100), diária (US$ 10 × dia, teto no dia 30), janela de 24 h e quebra da sequência em 48 h (`economy/rules.py`).
- **São hipóteses minhas, não medidas:** os 3 perfis de jogador; as frações de gasto; o anúncio (US$ 1 cada, 0/1/5 por dia: o anúncio nem existe no código); a margem das caixas (10%, as caixas da 5.1 não têm tabela de drop); a taxa do mercado (5%).
- **Preço fixo** (`reference_price`): sem descoberta de preço entre jogadores.
- **"Poder comprar" não é "conseguir a skin".** Hoje skins só entram por `grant_skin`; depois, só por caixa ou pela oferta de outro jogador. O modelo mede poder de compra, não oferta.
- Nenhum jogador real foi observado.

## Preços de referência do catálogo (1.455 skins ativas, valores arredondados)
| referência | preço |
|---|---|
| barata (p10) | ~US$ 0,04 |
| mediana (p50) | ~US$ 1,60 |
| cara (p90) | ~US$ 60 |
| muito cara (p99) | ~US$ 870 |
| a mais cara (Contraband, 1 skin) | ~US$ 4.800 |

(A mediana da Sessão 18, ~US$ 2,13, era sobre as variantes de desgaste; aqui conta o `reference_price` por skin.)

## Resultado com os valores atuais (provisórios)
**Dias até poder comprar**, poupando tudo:

| perfil | p10 | p50 | p90 | p99 | a mais cara |
|---|---|---|---|---|---|
| casual (5 de 7 dias) | 0 | 0 | 0 | 37 | >180 |
| ativo (todo dia, 1 anúncio) | 0 | 0 | 0 | 12 | 31 |
| ávido (todo dia, 5 anúncios) | 0 | 0 | 0 | 12 | 30 |

**Patrimônio** (carteira + estoque ao preço de referência): ativo US$ 370 no dia 7, US$ 4.500 no dia 30, US$ 21.500 no dia 90 e US$ 46.900 no dia 180 (cerca de 29 mil skins medianas). Casual: US$ 4.350 no dia 180.

**Quanto girar por dia para queimar toda a renda de regime** (US$ 301 por dia no ativo): cerca de **US$ 3.010 em caixas** (com margem de 10%) ou **US$ 6.020 no mercado** (taxa de 5%). Sob as hipóteses de gasto, o jogador queima só 2,9% (casual), 6,0% (ativo) e 10,5% (ávido) do que recebe em 180 dias.

### Leitura
1. **O saldo inicial de US$ 100 já compra o p90 do catálogo no dia 0.** Nenhum perfil tem progressão nos primeiros dias.
2. **A renda de regime (US$ 300 por dia) vale ~188 skins medianas por dia.** Em 180 dias entram ~US$ 50 mil por jogador ativo.
3. **Os sumidouros plausíveis não alcançam essa renda.** O patrimônio cresce em linha reta, sem equilíbrio.
4. **O que mais mexe nos números é o passo da diária (e o teto).** O saldo inicial só mexe nos primeiros dias; o anúncio de US$ 1 por dia muda ~0,4% da renda de 180 dias com o passo atual (US$ 49.750 sem anúncio contra US$ 49.930).

## Sensibilidade (perfil ativo, um parâmetro por vez, os outros nos valores atuais)
| parâmetro | valor | renda 30 d | renda 180 d | p90 | p99 | mais cara | regime/dia |
|---|---|---|---|---|---|---|---|
| passo da diária | US$ 1,00 | 595 | 5.245 | 0 | 39 | 166 | 31 |
| passo da diária | US$ 2,50 | 1.292,50 | 12.692,50 | 0 | 24 | 77 | 76 |
| passo da diária | US$ 5,00 | 2.455 | 25.105 | 0 | 17 | 46 | 151 |
| passo da diária | US$ 10,00 | 4.780 | 49.930 | 0 | 12 | 31 | 301 |
| dia do teto | 7 | 2.020 | 12.670 | 0 | 14 | 70 | 71 |
| dia do teto | 14 | 3.420 | 24.570 | 0 | 12 | 40 | 141 |
| dia do teto | 30 | 4.780 | 49.930 | 0 | 12 | 31 | 301 |
| saldo inicial | US$ 10 | 4.690 | 49.840 | 3 | 13 | 31 | 301 |
| saldo inicial | US$ 25 | 4.705 | 49.855 | 3 | 13 | 31 | 301 |
| saldo inicial | US$ 100 | 4.780 | 49.930 | 0 | 12 | 31 | 301 |
| anúncio | US$ 0 | 4.750 | 49.750 | 0 | 12 | 31 | 300 |
| anúncio | US$ 0,25 | 4.757,50 | 49.795 | 0 | 12 | 31 | 300,25 |
| anúncio | US$ 1 | 4.780 | 49.930 | 0 | 12 | 31 | 301 |
| anúncio | US$ 5 | 4.900 | 50.650 | 0 | 12 | 30 | 305 |

(Valores em US$ nas colunas de renda e regime; p90, p99 e "mais cara" em dias.)

## Combinações candidatas (perfil ativo; escolhidas por mim para discussão)
| passo da diária | outros | renda 30 d | renda 180 d | p90 | p99 | mais cara | regime/dia |
|---|---|---|---|---|---|---|---|
| atual (`rules.py`) | - | 4.780 | 49.930 | 0 | 12 | 31 | 301 |
| US$ 1,00 | teto 30 | 595 | 5.245 | 0 | 39 | 166 | 31 |
| US$ 1,00 | teto 30, saldo 25 | 520 | 5.170 | 7 | 42 | 169 | 31 |
| US$ 0,50 | teto 30, saldo 25 | 287,50 | 2.687,50 | 10 | 67 | >180 | 16 |
| US$ 2,50 | teto 14 | 952,50 | 6.352,50 | 0 | 28 | 138 | 36 |

## Recomendação (ponto de partida, não verdade)
**Diária de US$ 1,00 × dia até o dia 30 (teto US$ 30) e saldo inicial de US$ 25**, mantendo a janela de 24 h e a quebra em 48 h. Motivos, só com o que a tabela mostra:
- Com saldo de US$ 25 a skin p90 leva ~1 semana; com US$ 100 era o dia 0.
- A skin p99 sai em ~6 semanas e a mais cara em ~5,5 meses (169 dias): a progressão cabe no horizonte simulado de 180 dias.
- A renda de regime cai de US$ 301 para US$ 31 por dia. Ainda é muito para o sumidouro queimar (cerca de US$ 310 por dia em caixas ou US$ 620 por dia no mercado), mas uma ordem de grandeza menor, e é aí que a margem das caixas e a taxa passam a pesar.
- O passo de US$ 0,50 é lento demais: a mais cara passa de 180 dias. O de US$ 2,50 com teto no dia 14 tem renda de regime parecida (US$ 36 por dia), p99 em 28 dias e a mais cara em 138; é a alternativa mais próxima, e a diferença é só de ritmo.

**O que esta recomendação não prova:**
- Não simulei o anúncio junto do passo novo. Com a diária de US$ 1,00 no início, um anúncio de US$ 1 vale tanto quanto o primeiro dia; o ávido (5 anúncios por dia) ganharia ~US$ 5 por dia de anúncio contra ~US$ 31 de diária. **O valor do anúncio precisa ficar bem abaixo da diária** e decidir antes de existir anúncio (D12).
- Não há caixa nem mercado: margem e taxa seguem hipóteses.
- A meta de progressão (quanto tempo "deve" levar) é decisão de produto sua. Se a meta for outra, o passo muda.

## O que NÃO foi verificado
Comportamento de jogadores reais; os valores de caixa; a taxa e o anúncio (não existem no código); a execução do script por mim; os termos da Skinport (bloqueiam publicar o jogo).
