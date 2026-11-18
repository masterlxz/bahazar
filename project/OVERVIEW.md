# bahazar: visão geral

## O que é
Jogo de navegador de **economia virtual, patrimônio, colecionismo e negociação** com skins de CS2. Cada jogador entra em **salas**; cada sala é uma economia independente (dinheiro, itens e mercado próprios). Não é um simulador de caixas: o centro é mercado, inventário e patrimônio.

## Escopo de produto
- Agora (privado): salas privadas por convite, carteira por sala, catálogo de ~100-200 skins, inventário, marketplace, caixas, trade-ups, ranking.
- Depois (preparado, não implementado): salas públicas, comunidades, rankings globais, temporadas, moderação.
- Fora para sempre deste escopo: dinheiro real, depósitos, saques, apostas, movimentação de itens reais da Steam.

## Stack (proposta)
| Camada | Escolha | Observação |
|---|---|---|
| Frontend | React + TypeScript + Vite + Tailwind + shadcn/ui | Vercel |
| Backend | Python + Django + Django REST framework | **Substitui** Supabase do prompt original (decisão do dono: sem BaaS) |
| Banco | PostgreSQL | Fonte da verdade e das garantias de integridade |
| Contrato | OpenAPI gerado do backend → tipos TS | evita divergência |
| Tempo real | começar com polling; SSE depois | ver ARQUITETURA §7 |

## Status das fases
| Etapa | Descrição | Estado |
|---|---|---|
| 0 | Arquitetura e revisão | **em revisão** (esta entrega) |
| 1 | Fundação (apps, auth, perfis, CI) | não iniciada |
| 2 | Multiplayer (salas, convites, carteiras) | não iniciada |
| 3 | Catálogo e inventário | não iniciada |
| 4 | Economia (ledger, marketplace) | não iniciada |
| 5 | Progressão (caixas, trade-ups, ranking, conquistas) | não iniciada |
| 6 | Polimento (tempo real, segurança, deploy) | não iniciada |

Detalhe em [PLANO.md](PLANO.md).
