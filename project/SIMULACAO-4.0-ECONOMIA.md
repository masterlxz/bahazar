# Simulação da economia (PR 4.0, D7)

**Data:** 2026-11-24. **Quem rodou:** o dono, no PC dele; eu vi a saída colada, não rodei o script (ADR 0017).
**Reproduzir:** `python3 project/simulacao/economia.py` (só biblioteca padrão; importa `apps.economy.rules`). Entrada: `backend/data/precos_percentis.json`, gerado do banco local e **fora do repo** (o repo é público e os termos da Skinport não foram lidos). Semente 2026; 500 jogadores sorteados no perfil casual. `verificações: OK` na saída: a fórmula da diária do modelo é igual à de `rules.daily_amount` nos dias 1 a 60 (com os valores que `rules.py` tem hoje) e a conta de US$ 4.650 em 30 dias dos valores provisórios fecha.

**Atualização (2026-11-25):** o dono decidiu a D7 com base neste relatório ([ADR 0013](adr/0013-parametros-economicos-iniciais.md)) e a PR 4.0b aplicou a candidata em `rules.py`. **As tabelas abaixo são a foto de 2026-11-24 e usam os valores provisórios antigos** (saldo US$ 100, diária US$ 10 × dia até o dia 30), que o script mantém fixos em literais para continuar reproduzível; `rules.py` hoje tem outros valores.

**A decisão da D7 foi do dono.** O texto abaixo foi escrito antes dela: "nenhum valor do código foi alterado" vale para a PR 4.0; os valores escolhidos entraram na PR 4.0b (`rules.py` e testes).

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

## Combinações candidatas (os 3 perfis; escolhidas por mim para discussão)
Renda e regime em US$; p90, p99 e "mais cara" em dias até poder comprar (poupando tudo).

| perfil | passo da diária | outros | renda 30 d | renda 180 d | p90 | p99 | mais cara | regime/dia |
|---|---|---|---|---|---|---|---|---|
| casual | atual (`rules.py`) | - | 730 | 4.485 | 0 | 37 | >180 | - |
| casual | US$ 1,00 | teto 30 | 163 | 538,50 | 0 | >180 | >180 | - |
| casual | US$ 1,00 | teto 30, saldo 25 | 88 | 463,50 | 19 | >180 | >180 | - |
| casual | US$ 0,50 | teto 30, saldo 25 | 56,50 | 244,25 | 34 | >180 | >180 | - |
| casual | US$ 2,50 | teto 14, saldo 25 | 182,50 | 1.120 | 9 | 141 | >180 | - |
| ativo | atual (`rules.py`) | - | 4.780 | 49.930 | 0 | 12 | 31 | 301 |
| ativo | US$ 1,00 | teto 30 | 595 | 5.245 | 0 | 39 | 166 | 31 |
| ativo | US$ 1,00 | teto 30, saldo 25 | 520 | 5.170 | 7 | 42 | 169 | 31 |
| ativo | US$ 0,50 | teto 30, saldo 25 | 287,50 | 2.687,50 | 10 | 67 | >180 | 16 |
| ativo | US$ 2,50 | teto 14, saldo 25 | 877,50 | 6.277,50 | 5 | 30 | 140 | 36 |
| ávido | atual (`rules.py`) | - | 4.900 | 50.650 | 0 | 12 | 30 | 305 |
| ávido | US$ 1,00 | teto 30 | 715 | 5.965 | 0 | 35 | 147 | 35 |
| ávido | US$ 1,00 | teto 30, saldo 25 | 640 | 5.890 | 5 | 37 | 150 | 35 |
| ávido | US$ 0,50 | teto 30, saldo 25 | 407,50 | 3.407,50 | 6 | 54 | >180 | 20 |
| ávido | US$ 2,50 | teto 14, saldo 25 | 997,50 | 6.997,50 | 4 | 27 | 126 | 40 |

### Leitura
1. **O casual fica de 5 a 11 vezes abaixo do ativo em renda de 180 dias** (valores atuais: US$ 4.485 contra US$ 49.930, 11 vezes; passo US$ 1,00: 538 contra 5.245, 10 vezes; passo US$ 2,50 com teto no dia 14: 1.120 contra 6.277, 5,6 vezes). A diferença vem da regra da sequência: qualquer dia sem resgate zera a sequência, e a diária cresce com a sequência. Com o casual do modelo (resgata em ~71% dos dias, de forma independente), a sequência média é curta.
2. **Passo de US$ 1,00 deixa o casual sem a skin p99 no horizonte** (US$ 538 em 180 dias contra ~US$ 870). O ativo a alcança em 39 a 42 dias.
3. **Passo de US$ 0,50 é lento para todos**: o ativo leva 67 dias para a p99 e a mais cara passa de 180 dias.
4. **A única candidata em que o casual chega à p99 antes de 180 dias é a de passo US$ 2,50 com teto no dia 14 e saldo US$ 25** (141 dias; ativo 30, ávido 27). A mais cara sai em 140 dias (ativo) e 126 (ávido); o casual não chega a ela em 180.
5. **O saldo de US$ 25 em lugar de US$ 100** tira o p90 do dia 0: 9 dias (casual), 5 (ativo), 4 (ávido).
6. A renda de regime cai de ~US$ 300 para US$ 36 a 40 por dia nessa candidata (ativo e ávido): uma ordem de grandeza menor, ainda acima do que os sumidouros plausíveis queimam, mas bem mais perto (queimá-la inteira exigiria ~US$ 360 por dia em caixas com margem de 10%, ou ~US$ 720 por dia no mercado com taxa de 5%, contas feitas à mão sobre a renda do ativo).

## Candidata para a 4.0b (ponto de partida, não verdade)
**Diária de US$ 2,50 × dia até o dia 14 (teto US$ 35) e saldo inicial de US$ 25**, mantendo a janela de 24 h e a quebra em 48 h. É a única das cinco testadas em que **os três perfis** chegam à skin p99 dentro de 180 dias (casual 141, ativo 30, ávido 27). Antes disso eu havia sugerido passo US$ 1,00; a revisão mostrou que isso só olhava o perfil ativo, e a tabela acima desmente: o casual não chega à p99.

**O que esta candidata não prova:**
- **O horizonte de 180 dias é um parâmetro da simulação**, não uma meta do produto. "Cabe em 180 dias" é só um critério de comparação entre as cinco.
- **A meta de progressão é decisão de produto sua** (quanto tempo "deve" levar para o casual e para o ativo). Se a meta for outra, o passo e o teto mudam.
- **A regra da sequência é a causa da diferença entre os perfis** e não foi simulada em variantes (por exemplo, não zerar a sequência numa falta, ou reduzi-la). Vale decidir isso junto com o passo, porque ela dá o fator ~10 entre casual e ativo.
- **Anúncio:** não simulei o anúncio com o passo novo. O ávido (5 anúncios por dia de US$ 1) ganharia ~US$ 5 por dia contra ~US$ 40 de diária de regime. **O valor do anúncio precisa ficar bem abaixo da diária** e decidir antes de existir anúncio (D12).
- **Margem das caixas e taxa do mercado** seguem hipóteses: não há caixa nem mercado ainda, e nenhuma queima foi simulada com o passo novo além da tabela "Queima observada" do script.
- **O tempo anda em dias inteiros:** a janela de 24 h nunca bloqueia um resgate no modelo e não há deslize de horário.
- **O perfil casual é pessimista:** resgates independentes, sem padrão semanal; um jogador real que resgata nos mesmos dias da semana teria sequências mais longas.

## Como regenerar a entrada
O arquivo `backend/data/precos_percentis.json` (fora do repo) tem o esquema `{"TODAS": {"n": 1455, "percentis_centavos": {"0.1": ..., "0.5": ..., "0.9": ..., "0.99": ...}}, "Contraband": {...}, ...}`, em centavos de USD, uma chave por raridade e uma `TODAS`. Foi gerado, no PC do dono, com o `reference_price` das skins ativas:

```bash
cd backend && python manage.py shell <<'EOF'
import json
from django.db import connection
from apps.catalog.models import Skin

PCTS = [0.10, 0.25, 0.50, 0.75, 0.90, 0.99]
sql = f"""
SELECT COALESCE(rarity, 'TODAS'), count(*),
       percentile_cont(%s) WITHIN GROUP (ORDER BY reference_price)
FROM {Skin._meta.db_table} WHERE active
GROUP BY ROLLUP(rarity) ORDER BY 1
"""
with connection.cursor() as cur:
    cur.execute(sql, [PCTS])
    linhas = cur.fetchall()
saida = {
    r: {"n": n, "percentis_centavos": dict(zip(map(str, PCTS), map(round, p)))}
    for r, n, p in linhas
}
with open("data/precos_percentis.json", "w") as f:
    json.dump(saida, f, indent=2, ensure_ascii=False)
EOF
```

## O que NÃO foi verificado
Comportamento de jogadores reais; os valores de caixa; a taxa e o anúncio (não existem no código); a execução do script por mim; os termos da Skinport (bloqueiam publicar o jogo).
