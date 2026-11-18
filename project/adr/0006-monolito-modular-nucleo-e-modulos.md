# 0006: Monólito modular, núcleo e módulos por app Django

**Data:** 2026-11-18

## Contexto
O produto tem muitas features (caixas, trade-ups, progressão, temporadas, comunidades) e deve crescer sem virar um bolo. Microserviços seriam prematuros.

## Decisão
Um backend Django com apps por feature. **Núcleo:** accounts, rooms, economy, catalog, inventory, marketplace. **Módulos:** cases, tradeups, progression, leaderboard, seasons, communities. O núcleo não importa módulo e módulo não importa módulo; reações entre eles passam por sinais/eventos do núcleo. Módulos ligam e desligam por configuração (`INSTALLED_APPS`) e o frontend consulta `GET /api/features/`. Sem sistema de plugins.

## Alternativas descartadas
- **Microserviços:** custo operacional sem necessidade.
- **Monólito sem fronteiras:** acoplamento e testes lentos.
- **Plugins instaláveis:** só com demanda real (`padrao/modularidade.md`).

## Consequências
- O CI roda o núcleo sem módulos e cada módulo isolado; um teste de arquitetura barra importação cruzada.
- Cada módulo custa contrato e matriz de teste; o app só vira módulo se alguém vive sem ele.
- **Custo de reverter:** baixo a médio.
