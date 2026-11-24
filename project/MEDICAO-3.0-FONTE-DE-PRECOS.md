# Medição 3.0: fonte de preços em USD

**Data:** 2026-11-24 · **Origem:** (a) a VM de desenvolvimento, poucas chamadas GET sem chave nem cadastro, com User-Agent genérico; (b) o PC Windows do dono (PowerShell 5.1, `curl.exe` e o navegador). **Estado: cobertura medida para a Skinport; D11 aguarda a decisão do dono.** Nenhuma fonte de preço respondeu a um script, nem da VM nem do PC do dono; a Skinport só entregou o arquivo pelo **navegador**.

## Resultado: cobertura da Skinport sobre o catálogo (medida no PC do dono)
Um único snapshot (`updated_at` com 1 valor distinto no arquivo todo), 37.316 itens, 15,5 MB. Cruzamento por nome exato `"<name do catálogo> (<desgaste>)"` com as 1.456 skins sem StatTrak, Souvenir, faca nem luva.

| Medida | Valor |
|---|---|
| Variantes (skin x desgaste) do catálogo | 6.825 |
| Achadas no arquivo da Skinport | 6.821 (99,94%) |
| Com `suggested_price` | 6.821 (as achadas, 100%) |
| Com anúncio ativo (`quantity > 0`) | 6.504 (95,3% das 6.825) |
| Skins com ao menos um desgaste com preço | 1.455 de 1.456; só 1 Restricted fica sem |
| `suggested_price` das skins do catálogo | mediana US$ 2,13; mínimo US$ 0,02; máximo US$ 13.683,72 |
| Cobertura por raridade | 100% em Consumer, Industrial, Mil-Spec, Classified, Covert e Contraband; Restricted 310 de 311 |
| Não achadas (amostra de 4 de 4) | `MP5-SD | Lab Rats` em FN, MW e FT; `Negev | Mjölnir (Well-Worn)` |

- O **`suggested_price`** é a estimativa da própria Skinport e existe mesmo sem anúncio; `min/max/mean/median_price` ficam `null` quando `quantity` é 0 (visto num trecho do arquivo). No Talon Knife Fade (FN) o sugerido era 717,90 contra mediana 766,36 de anúncios: **o sugerido não é preço de venda**. Qual campo vira `reference_price` é decisão de produto, não medida.
- Facas e luvas (`★`) ficaram **fora** desta medição (o catálogo tem entradas por fase de Doppler, e o script guardou uma por nome).
- As 4 variantes não achadas parecem nome diferente ou item inexistente no mercado; **não confirmei qual**.

## O que impede de automatizar
O `curl` recebe **403 com desafio do Cloudflare** também no IP residencial (o bloqueio não é do datacenter, ao contrário da minha hipótese anterior). O navegador passa, depois de um captcha. **O backend do jogo não consegue buscar sozinho.** O desenho que sobra é um **snapshot manual** (o dono baixa o JSON no navegador; um comando de import o carrega), compatível com `reference_price` como dado nosso (R8).

## Resultado em uma tabela
| Fonte | Papel | O que medi | Estado |
|---|---|---|---|
| ByMykel/CSGO-API (`public/api/en/skins.json`) | catálogo | HTTP 200, 4,9 MB, **2.246 entradas**; `LICENSE` do repo lida: **MIT**, "Copyright (c) 2023 ByMykel" | **Usável como catálogo**; não traz preço |
| ByMykel `prices.json` | preço | HTTP 404 (o arquivo não existe) | descartada |
| Skinport `GET /v1/items` | preço | **HTTP 403**, `cf-mitigated: challenge` (desafio do Cloudflare, HTML), na VM e no PC do dono; **no navegador, após captcha, o JSON completo veio** (cobertura acima) | **Só por navegador**; não contornei o desafio; termos de uso **não lidos** |
| Steam Community Market `priceoverview` | preço | 1ª chamada: 200, `{"lowest_price":"$27.38","volume":"87","median_price":"$27.00"}`. Depois, **19 chamadas espaçadas de 4 s: todas HTTP 429** | **Inviável para import em massa** (limite agressivo, endpoint não documentado) |
| CSGOTrader (`prices.csgotrader.app`) | preço | na VM, todas as rotas dão **301** para HTML; no PC do dono, `prices_v6.json` deu 200 com os **mesmos 36.709 bytes de HTML**; repo de preços sem `LICENSE` na URL que tentei (404) | **Não serve dados nas URLs que tentei**; licença **não confirmada** |
| CSFloat `GET /api/v1/listings` | preço | HTTP 403: `"You need to be logged in to search listings"` | exige conta; descartada sem decisão sua |
| Termos da Steam Web API (`steamcommunity.com/dev/apiterms`) | licença | lidos: citam limite de 100.000 chamadas/dia para a Web API com chave | **Não cobrem** o `priceoverview` (endpoint de mercado sem chave); uso de preços do mercado em jogo **não confirmado** |

## O que o catálogo ensina (vale para a PR 3.1)
- 2.246 entradas, **uma por skin**, não por variante de mercado. Campos: `id`, `name`, `weapon`, `category`, `pattern`, `min_float`, `max_float`, `rarity`, `stattrak`, `souvenir`, `wears`, `collections`, `crates`, `image`, entre outros. Tudo que o `MODELO-DE-DADOS` pede em `skins` (menos preço) está lá.
- As flags `stattrak` e `souvenir` significam "**pode existir** nessa variante", não "é essa variante": das 2.246, 1.456 têm `souvenir: true` e 1.394 têm `stattrak: true`, e 698 têm as duas. Não filtre por elas; filtre pelo prefixo do nome (`StatTrak™`, `Souvenir`, `★`).
- Excluindo StatTrak/Souvenir/facas (`★`): **1.456** skins, por raridade: Consumer 200, Industrial 204, Mil-Spec 446, Restricted 311, Classified 183, Covert 111, Contraband 1. Os 100 a 200 do plano cabem num subconjunto.
- 208 entradas não têm todos os campos (os outros 2.038 têm o conjunto completo): o import precisa tolerar campo ausente.
- Um preço de mercado é por **skin + desgaste** (`AK-47 | Redline (Field-Tested)`), não por skin. O `reference_price` por skin exige regra (ex.: desgaste de referência), ainda não decidida.

## O que NÃO foi verificado
- **Termos de uso da Skinport** (uso em jogo, redistribuição, limites de requisição): não lidos. **Sem isso, não recomendo adotar a fonte**; o dono deve ler `skinport.com/terms` e `docs.skinport.com`. Não sou jurídico.
- **Estabilidade no tempo:** um só snapshot (2026-11-24). Não medi quanto o `suggested_price` oscila entre dias, nem outliers por skin.
- Facas e luvas (fora desta medição) e as 4 variantes não achadas (causa não confirmada).
- A cobertura foi medida pelo **script do PC do dono**, não por mim; eu vi só as linhas de saída coladas, não o arquivo. Reprodutível pelo bloco abaixo.
- Licença do dado de preço de qualquer outra fonte; termos da Valve sobre itens, nomes e imagens seguem em D1 e J1.

## Decisão do dono (D11)
1. **Skinport por snapshot manual** (cobertura 99,94% das variantes), **depois de ler os termos**. Perde a automação; um import por comando carrega o arquivo.
2. **Fonte com chave de API** (plano grátis), com cadastro e termos lidos pelo dono; a chave vai por variável de ambiente. Não medida.
3. **Preço próprio/curado** (R8 já prevê `reference_price` como dado nosso): tabela por raridade e desgaste, sem fonte externa. Perde a premissa de "preço real" do ADR 0011.
Recomendação: **1, condicionada aos termos**; reserva: 3. Também a decidir na PR 3.1: qual campo vira `reference_price` (`suggested_price` cobre tudo; `median_price` só os 95,3% com anúncio) e qual desgaste representa a skin.

## Reproduzir
- VM: `curl -sS -A <UA genérico> -o <arquivo> <URL>` para cada linha da tabela. O catálogo: `len(json)` do `skins.json`.
- PC do dono (PowerShell 5.1): salvar a URL da Skinport pelo navegador como `skinport.json`; baixar `catalogo.json` do mesmo caminho do catálogo; casar `"<name> (<wear>)"` do catálogo com `market_hash_name`, ignorando nomes que começam com `★`. Os arquivos **não entram no repo**.
