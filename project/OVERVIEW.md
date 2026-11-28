# bahazar: visão geral

## O que é
Jogo de navegador de **economia virtual, patrimônio, colecionismo e negociação** com skins de CS2. A economia é **global por usuário** (uma carteira e um inventário por jogador, ADR 0010), em **moeda virtual na escala de preços reais** (centavos de USD, ADR 0011). O jogador tem **amigos**, troca itens com eles, vê o inventário deles e participa de **grupos** (as "salas") e de batalhas de caixa. Não é um simulador de caixas: o centro é inventário, mercado, trocas e patrimônio.

## Escopo de produto
- Agora: amigos, carteira global com saldo inicial, **renda diária** e recompensa por anúncio (simulada), catálogo de ~100-200 skins com preço de referência, inventário (visível a amigos), trocas entre amigos, marketplace, caixas e **batalha de caixa**, trade-ups, ranking. Grupos privados por convite.
- Depois (preparado, não implementado): salas públicas, comunidades, rankings globais, temporadas, moderação, **anúncio real**.
- Fora para sempre deste escopo: **dinheiro real, depósitos, saques, apostas**, movimentação de itens reais da Steam. "Moeda real" quer dizer **escala de preços**, não conversão para dinheiro (ADR 0011).

## Stack (proposta)
| Camada | Escolha | Observação |
|---|---|---|
| Frontend | React + TypeScript + Vite + Tailwind + shadcn/ui | Vercel |
| Backend | Python + Django + Django REST framework | **Substitui** Supabase do prompt original (decisão do dono: sem BaaS) |
| Banco | PostgreSQL | Fonte da verdade e das garantias de integridade |
| Contrato | tipos TS escritos à mão; OpenAPI reavaliado na PR 2.5a, segue à mão com novo gatilho | ADR 0012 (atualiza o 0009) |
| Tempo real | começar com polling; SSE depois | ver ARQUITETURA §7 |

## Status das fases
| Etapa | Descrição | Estado |
|---|---|---|
| 0 | Arquitetura e revisão | **aprovada pelo dono** (2026-11-19) |
| 1 | Fundação (apps, auth, perfis, CI) | **feita** (validada no navegador em 2026-11-19) |
| 2 | Base social e economia global (grupos, carteira, amigos, convites) | **feita** (código e testes; **falta a validação manual do dono no navegador**): 2.1 (grupos), 2.2 (economia), 2.3 (amigos), 2.4 (convites) e 2.5 (telas) em 4 PRs: 2.5a carteira, 2.5b amigos, 2.5c1 grupos, 2.5c2 convites |
| 3 | Catálogo, preço real e inventário | **em andamento**: 3.0 (fonte de preços), 3.1 (catálogo), 3.2a/3.2b (inventário e API) e 3.3 (telas do inventário, sem imagens) feitas; 3.4 feita **sem imagens** (API pública do catálogo, #164, e tela `/skins`, #165; imagens = placeholder, D1 para a Etapa 6); a atribuição visual da Skinport está no inventário e no catálogo (PRs #312 e #320); falta a validação do dono no navegador |
| 4 | Economia e trocas (simulação, trocas, marketplace) | **em andamento**: simulação, idempotência, trocas (4.2, com rotas) **4.3 (anúncios: criar, cancelar e listar, #162)** e **4.4a (compra atômica, taxa de 5% como hipótese, `market_transactions`, ADR 0018)** e **4.4b (`Idempotency-Key` em criar e cancelar anúncio, PR #229)** feitas; frontend das trocas só a **fatia 1 da 4.5** (tela `/trocas`: listar, aceitar, recusar, cancelar; sem criar oferta), sem frontend de mercado; 4.3 e 4.4a sem revisão adversária |
| 5 | Progressão e caixas (caixas, batalha, trade-ups, ranking) | não iniciada |
| 6 | Polimento (tempo real, segurança, deploy) | não iniciada |

Detalhe em [PLANO.md](PLANO.md).
