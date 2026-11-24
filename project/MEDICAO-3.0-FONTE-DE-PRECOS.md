# Medição 3.0: fonte de preços em USD (relatório parcial)

**Data:** 2026-11-24 · **Origem das medições:** a VM de desenvolvimento (IP de datacenter), poucas chamadas GET sem chave nem cadastro, com User-Agent genérico. **Estado: parcial.** O catálogo foi medido; **nenhuma fonte de preço respondeu a um script**, então a cobertura de preços **não foi medida**. A D11 segue aberta.

## Resultado em uma tabela
| Fonte | Papel | O que medi | Estado |
|---|---|---|---|
| ByMykel/CSGO-API (`public/api/en/skins.json`) | catálogo | HTTP 200, 4,9 MB, **2.246 entradas**; `LICENSE` do repo lida: **MIT**, "Copyright (c) 2023 ByMykel" | **Usável como catálogo**; não traz preço |
| ByMykel `prices.json` | preço | HTTP 404 (o arquivo não existe) | descartada |
| Skinport `GET /v1/items` | preço | **HTTP 403**, `cf-mitigated: challenge` (desafio do Cloudflare, HTML) | **Bloqueada para script**; não contornei o desafio |
| Steam Community Market `priceoverview` | preço | 1ª chamada: 200, `{"lowest_price":"$27.38","volume":"87","median_price":"$27.00"}`. Depois, **19 chamadas espaçadas de 4 s: todas HTTP 429** | **Inviável para import em massa** (limite agressivo, endpoint não documentado) |
| CSGOTrader (`prices.csgotrader.app`) | preço | todas as rotas dão **301** para uma página HTML (`csgotrader.app/prices/`) que cita `latests.json`; não achei arquivo de dados acessível; repo de preços sem `LICENSE` na URL que tentei (404) | **Não acessível hoje**; licença **não confirmada** |
| CSFloat `GET /api/v1/listings` | preço | HTTP 403: `"You need to be logged in to search listings"` | exige conta; descartada sem decisão sua |
| Termos da Steam Web API (`steamcommunity.com/dev/apiterms`) | licença | lidos: citam limite de 100.000 chamadas/dia para a Web API com chave | **Não cobrem** o `priceoverview` (endpoint de mercado sem chave); uso de preços do mercado em jogo **não confirmado** |

## O que o catálogo ensina (vale para a PR 3.1)
- 2.246 entradas, **uma por skin**, não por variante de mercado. Campos: `id`, `name`, `weapon`, `category`, `pattern`, `min_float`, `max_float`, `rarity`, `stattrak`, `souvenir`, `wears`, `collections`, `crates`, `image`, entre outros. Tudo que o `MODELO-DE-DADOS` pede em `skins` (menos preço) está lá.
- As flags `stattrak` e `souvenir` significam "**pode existir** nessa variante", não "é essa variante": das 2.246, 1.456 têm `souvenir: true` e 1.394 têm `stattrak: true`, e 698 têm as duas. Não filtre por elas; filtre pelo prefixo do nome (`StatTrak™`, `Souvenir`, `★`).
- Excluindo StatTrak/Souvenir/facas (`★`): **1.456** skins, por raridade: Consumer 200, Industrial 204, Mil-Spec 446, Restricted 311, Classified 183, Covert 111, Contraband 1. Os 100 a 200 do plano cabem num subconjunto.
- 208 entradas não têm todos os campos (os outros 2.038 têm o conjunto completo): o import precisa tolerar campo ausente.
- Um preço de mercado é por **skin + desgaste** (`AK-47 | Redline (Field-Tested)`), não por skin. O `reference_price` por skin exige regra (ex.: desgaste de referência), ainda não decidida.

## O que NÃO foi verificado
- **Cobertura de preço** de qualquer fonte (quantas das skins têm preço, mediana, outliers, itens sem preço). Sem número, não recomendo fonte.
- Limites e termos do Skinport (a página de termos não foi lida; só a API foi barrada).
- Se o bloqueio do Cloudflare e o 429 do Steam são por **IP de datacenter**: do IP residencial do dono pode ser diferente. É hipótese.
- Licença do dado de preço de qualquer fonte. Não sou jurídico; os termos da Valve sobre itens, nomes e imagens seguem em D1 e J1.

## Como destravar (decisão do dono)
1. **Medir do PC do dono:** dois `curl` com `-o` (Skinport e CSGOTrader), e o arquivo vem para eu cruzar com o catálogo.
2. **Fonte com chave de API** (plano grátis), com cadastro e termos lidos pelo dono; a chave vai por variável de ambiente.
3. **Preço próprio/curado** (R8 já prevê `reference_price` como dado nosso): tabela por raridade e desgaste, sem fonte externa. Perde a premissa de "preço real" do ADR 0011.

## Reproduzir
`curl -sS -A <UA genérico> -o <arquivo> <URL>` para cada linha da tabela; a contagem do catálogo é `len(json)` do `skins.json` e a filtragem acima é por prefixo do nome. Os arquivos ficaram no scratchpad da sessão e **não entram no repo**.
