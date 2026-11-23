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
| 2 | Base social e economia global (grupos, carteira, amigos, convites) | **em andamento**: 2.1 (grupos), 2.2 (economia), 2.3 (amigos) e 2.4 (convites) feitas; 2.5 (telas) em 3 PRs: 2.5a carteira, 2.5b amigos e 2.5c grupos |
| 3 | Catálogo, preço real e inventário | não iniciada (começa medindo a fonte de preços, D11) |
| 4 | Economia e trocas (simulação, trocas, marketplace) | não iniciada |
| 5 | Progressão e caixas (caixas, batalha, trade-ups, ranking) | não iniciada |
| 6 | Polimento (tempo real, segurança, deploy) | não iniciada |

Detalhe em [PLANO.md](PLANO.md).
