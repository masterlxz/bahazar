"""Simulação da economia do bahazar (PR 4.0, decide a D7 de RISCOS.md).

Pergunta: com os preços reais do catálogo, quanto tempo um jogador leva para poder comprar uma
skin barata, mediana, cara e a mais cara, e quanta moeda nova entra por dia contra o que os
sumidouros (taxa do mercado, margem das caixas) conseguem queimar?

Como rodar (só biblioteca padrão; roda no PC do dono, não na VM do agente):

    python project/simulacao/economia.py [--precos CAMINHO] [--seed N] [--jogadores N]

A entrada é um JSON de percentis de `reference_price` por raridade (em centavos de USD), gerado
no banco local e mantido FORA do repo (o repo é público e os termos da Skinport não foram lidos).

Limites que o leitor precisa saber:
- Os perfis de jogador e as frações de gasto são HIPÓTESES; nenhum jogador real foi observado.
- A margem das caixas e a taxa do mercado são HIPÓTESES: as caixas (5.1) ainda não têm tabela
  de drop. O anúncio (R centavos por anúncio) também não existe no código.
- Preço fixo (`reference_price`): não há descoberta de preço entre jogadores.
- Dinheiro é inteiro em centavos; o único `float` é a probabilidade de o jogador resgatar a
  diária num dia (sorteio, não dinheiro).
"""

import argparse
import json
import random
import statistics
import sys
from dataclasses import dataclass, replace
from datetime import timedelta
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(RAIZ / "backend"))

from apps.economy import rules  # noqa: E402  (regras puras: a diária vem do código real)

HORIZONTE = 180
MARCOS = (7, 30, 90, 180)
INF = float("inf")


@dataclass(frozen=True)
class Params:
    """Parâmetros da D7. Os três primeiros são os valores PROVISÓRIOS de `economy/rules.py`."""

    saldo_inicial: int = rules.STARTING_BALANCE
    passo_diaria: int = rules.DAILY_STEP
    dia_teto: int = rules.DAILY_CAP_DAY
    anuncio: int = 100  # centavos por anúncio: HIPÓTESE (o anúncio é simulado, sem valor no código)
    margem_caixa_bps: int = 1_000  # 10%: HIPÓTESE (não há caixa ainda)
    taxa_bps: int = 500  # 5%: HIPÓTESE (não há mercado ainda)


@dataclass(frozen=True)
class Perfil:
    nome: str
    p_resgate: float  # chance de resgatar a diária num dia
    anuncios_dia: int
    gasto_caixas_bps: int  # parte da renda do dia gasta em caixas (10_000 = 100%)
    giro_mercado_bps: int  # parte da renda do dia negociada no mercado (paga a taxa)


PERFIS = (
    Perfil("casual", 5 / 7, 0, 3_000, 0),
    Perfil("ativo", 1.0, 1, 5_000, 2_000),
    Perfil("ávido", 1.0, 5, 8_000, 5_000),
)


@dataclass(frozen=True)
class Resultado:
    renda_acum: list[int]  # renda acumulada (inclui o saldo inicial), por dia, de 0 a HORIZONTE
    patrimonio: list[int]  # carteira + estoque (ao preço de referência), por dia
    emitido: int
    queimado: int


def diaria(p: Params, dia_da_sequencia: int) -> int:
    """A diária do código real, com `passo` e `teto` parametrizáveis."""
    return p.passo_diaria * min(dia_da_sequencia, p.dia_teto)


def simular(perfil: Perfil, p: Params, rng: random.Random) -> Resultado:
    saldo, estoque = p.saldo_inicial, 0
    emitido, queimado = p.saldo_inicial, 0
    renda_acum, patrimonio = [emitido], [saldo]
    sequencia: int | None = None
    ultimo_resgate: int | None = None
    for dia in range(1, HORIZONTE + 1):
        decorrido = None if ultimo_resgate is None else timedelta(days=dia - ultimo_resgate)
        renda = perfil.anuncios_dia * p.anuncio
        if rng.random() < perfil.p_resgate and rules.can_claim(decorrido):
            sequencia = rules.next_streak_day(sequencia, decorrido)
            renda += diaria(p, sequencia)
            ultimo_resgate = dia
        saldo += renda
        emitido += renda

        gasto = renda * perfil.gasto_caixas_bps // 10_000
        perda_caixa = gasto * p.margem_caixa_bps // 10_000
        saldo -= gasto
        estoque += gasto - perda_caixa  # a caixa devolve, em média, o preço menos a margem
        queimado += perda_caixa

        giro = renda * perfil.giro_mercado_bps // 10_000
        taxa = giro * p.taxa_bps // 10_000
        saldo -= taxa
        queimado += taxa

        assert saldo >= 0, "saldo negativo"
        assert saldo + estoque == emitido - queimado, "a conservação do dinheiro falhou"
        renda_acum.append(renda_acum[-1] + renda)
        patrimonio.append(saldo + estoque)
    return Resultado(renda_acum, patrimonio, emitido, queimado)


def rodar(perfil: Perfil, p: Params, seed: int, jogadores: int) -> list[Resultado]:
    """Um jogador basta quando o perfil não sorteia nada; senão, `jogadores` com semente fixa."""
    n = 1 if perfil.p_resgate >= 1.0 else jogadores
    rng = random.Random(f"{seed}:{perfil.nome}")
    return [simular(perfil, p, rng) for _ in range(n)]


def dias_ate(resultados: list[Resultado], preco: int) -> float:
    """Mediana dos dias até a renda acumulada (poupando tudo) alcançar `preco`. INF se nunca."""
    chegou: list[float] = []
    for r in resultados:
        dia = next((d for d, acumulado in enumerate(r.renda_acum) if acumulado >= preco), None)
        chegou.append(INF if dia is None else dia)
    return statistics.median(chegou)


def mediana_em(resultados: list[Resultado], serie: str, dia: int) -> int:
    return int(statistics.median(getattr(r, serie)[dia] for r in resultados))


def renda_em_regime(perfil: Perfil, p: Params) -> int:
    """Renda por dia depois do teto da sequência, para quem resgata todo dia."""
    return diaria(p, p.dia_teto) + perfil.anuncios_dia * p.anuncio


def usd(centavos: int) -> str:
    return f"US$ {centavos // 100:,}.{centavos % 100:02d}"


def dias(valor: float) -> str:
    return f">{HORIZONTE}" if valor == INF else f"{int(valor)}"


def carregar_precos(caminho: Path) -> dict[str, int]:
    try:
        dados = json.loads(caminho.read_text(encoding="utf-8"))
        todas = dados["TODAS"]["percentis_centavos"]
        return {
            "barata (p10)": todas["0.1"],
            "mediana (p50)": todas["0.5"],
            "cara (p90)": todas["0.9"],
            "muito cara (p99)": todas["0.99"],
            "a mais cara (Contraband)": dados["Contraband"]["percentis_centavos"]["0.5"],
        }
    except (OSError, KeyError, ValueError) as erro:
        sys.exit(f"entrada inválida em {caminho}: {erro!r}")


def tabela(cabecalho: list[str], linhas: list[list[str]]) -> None:
    print("| " + " | ".join(cabecalho) + " |")
    print("|" + "|".join("---" for _ in cabecalho) + "|")
    for linha in linhas:
        print("| " + " | ".join(linha) + " |")
    print()


def verificar(seed: int) -> None:
    """O modelo concorda com o código real e com os números que o repo já documenta."""
    p = Params()
    assert (p.saldo_inicial, p.passo_diaria, p.dia_teto) == (10_000, 1_000, 30)
    for d in range(1, 61):
        assert diaria(p, d) == rules.daily_amount(d), f"a diária difere no dia {d}"
    sem_anuncio = Perfil("teste", 1.0, 0, 0, 0)
    r = simular(sem_anuncio, p, random.Random(0))
    # PENDING.md: "um jogador sem falhas ganha ~US$ 4.650 em 30 dias" (sem o saldo inicial).
    assert r.renda_acum[30] - p.saldo_inicial == 465_000, "a renda de 30 dias não bate (US$ 4.650)"
    assert r.queimado == 0 and r.patrimonio[30] == r.renda_acum[30], "sem gasto nada se queima"
    um = rodar(PERFIS[0], p, seed, 20)
    outro = rodar(PERFIS[0], p, seed, 20)
    assert [x.renda_acum for x in um] == [x.renda_acum for x in outro], "não é determinístico"
    print("verificações: OK\n")


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--precos", type=Path, default=RAIZ / "backend/data/precos_percentis.json")
    ap.add_argument("--seed", type=int, default=2026)
    ap.add_argument("--jogadores", type=int, default=500)
    args = ap.parse_args()

    verificar(args.seed)
    precos = carregar_precos(args.precos)
    base = Params()
    mediano = precos["mediana (p50)"]

    print("## Parâmetros\n")
    print(f"- saldo inicial {usd(base.saldo_inicial)}; diária {usd(base.passo_diaria)} x dia até o")
    print(f"  dia {base.dia_teto} (teto {usd(diaria(base, base.dia_teto))}); valores de rules.py")
    print(f"- HIPÓTESES: anúncio {usd(base.anuncio)}, margem das caixas "
          f"{base.margem_caixa_bps / 100:.0f}%, taxa do mercado {base.taxa_bps / 100:.0f}%")
    print(f"- {args.jogadores} jogadores sorteados no perfil casual; semente {args.seed}\n")

    print("## Preços de referência (catálogo ativo, entrada local)\n")
    tabela(["referência", "preço"], [[nome, usd(c)] for nome, c in precos.items()])

    res = {pf.nome: rodar(pf, base, args.seed, args.jogadores) for pf in PERFIS}

    print("## Dias até poder comprar (poupando tudo, valores de rules.py)\n")
    tabela(
        ["perfil", *precos],
        [[pf.nome, *(dias(dias_ate(res[pf.nome], c)) for c in precos.values())] for pf in PERFIS],
    )

    print("## Patrimônio (carteira + estoque ao preço de referência)\n")
    cab = ["perfil", *(f"dia {m}" for m in MARCOS)]
    linhas = []
    for pf in PERFIS:
        cel = []
        for m in MARCOS:
            v = mediana_em(res[pf.nome], "patrimonio", m)
            cel.append(f"{usd(v)} ({v // mediano:,} medianas)")
        linhas.append([pf.nome, *cel])
    tabela(cab, linhas)

    print("## Quanto precisa girar por dia para queimar toda a renda diária de regime\n")
    print("Renda de regime = diária no teto + anúncios (quem resgata todo dia).\n")
    linhas = []
    for pf in PERFIS[1:]:
        renda = renda_em_regime(pf, base)
        em_caixas = renda * 10_000 // base.margem_caixa_bps
        no_mercado = renda * 10_000 // base.taxa_bps
        linhas.append([pf.nome, usd(renda), usd(em_caixas), usd(no_mercado)])
    tabela(
        ["perfil", "renda/dia", "em caixas (a margem queima)", "no mercado (a taxa queima)"],
        linhas,
    )

    print("## Sensibilidade (perfil ativo, um parâmetro por vez)\n")
    ativo = next(pf for pf in PERFIS if pf.nome == "ativo")
    variacoes = [
        (nome, rotulo(v), replace(base, **{campo: v}))
        for nome, campo, rotulo, valores in (
            ("passo da diária", "passo_diaria", usd, (100, 250, 500, 1_000)),
            ("dia do teto", "dia_teto", str, (7, 14, 30)),
            ("saldo inicial", "saldo_inicial", usd, (1_000, 2_500, 10_000)),
            ("anúncio", "anuncio", usd, (0, 25, 100, 500)),
        )
        for v in valores
    ]
    cab = ["parâmetro", "valor", "renda 30 d", "renda 180 d", "p90", "p99", "mais cara"]
    cab.append("regime/dia")
    linhas = []
    for nome, rotulo, params in variacoes:
        r = rodar(ativo, params, args.seed, 1)
        linhas.append(
            [
                nome,
                rotulo,
                usd(r[0].renda_acum[30]),
                usd(r[0].renda_acum[180]),
                dias(dias_ate(r, precos["cara (p90)"])),
                dias(dias_ate(r, precos["muito cara (p99)"])),
                dias(dias_ate(r, precos["a mais cara (Contraband)"])),
                usd(renda_em_regime(ativo, params)),
            ]
        )
    tabela(cab, linhas)

    print("## Queima observada por perfil (valores de rules.py + hipóteses)\n")
    linhas = []
    for pf in PERFIS:
        e = int(statistics.median(r.emitido for r in res[pf.nome]))
        q = int(statistics.median(r.queimado for r in res[pf.nome]))
        linhas.append([pf.nome, usd(e), usd(q), f"{q * 100 / e:.1f}%"])
    tabela(["perfil", f"emitido em {HORIZONTE} d", "queimado", "queimado / emitido"], linhas)


if __name__ == "__main__":
    main()
