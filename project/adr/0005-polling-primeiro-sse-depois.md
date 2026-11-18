# 0005: Polling primeiro, SSE depois

**Data:** 2026-11-18

## Contexto
O mercado e o ranking se beneficiam de atualização ao vivo, mas o grupo inicial é pequeno e só há fluxo servidor → cliente.

## Decisão
Etapas 1 a 5: sem tempo real, com refetch (TanStack Query) ao focar a aba e a cada ~10-15 s na vitrine. Etapa 6: SSE por sala sobre ASGI, com `LISTEN/NOTIFY` do Postgres como barramento, só para `market_listings` e ranking.

## Alternativas descartadas
- **Django Channels/WebSocket desde o início:** infraestrutura (ASGI, camada de canais, em geral Redis) sem necessidade; a comunicação é unidirecional.
- **Redis pub/sub:** infra extra sem dor medida.

## Consequências
- Início mais simples; o polling já entrega valor.
- SSE com `LISTEN/NOTIFY` entre vários processos precisa de protótipo medido antes de adotar (RISCOS R7, confiança média). Fallback: manter o polling.
- **Custo de reverter:** baixo.
