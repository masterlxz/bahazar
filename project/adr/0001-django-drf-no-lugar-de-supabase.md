# 0001: Django + DRF no lugar de Supabase

**Data:** 2026-11-18

## Contexto
O prompt original previa Supabase (Auth, RLS, Realtime, Edge Functions). O dono prefere codar o backend e não usar BaaS. O projeto lida com saldo e propriedade de itens, onde integridade e testabilidade pesam mais que velocidade de início.

## Decisão
Backend próprio em Python com Django e Django REST framework, sobre PostgreSQL. Frontend segue React + TypeScript + Vite + Tailwind + shadcn/ui na Vercel.

## Alternativas descartadas
- **Supabase:** rejeitado pelo dono (BaaS).
- **FastAPI + SQLAlchemy:** mais peças para montar (auth, migrations, admin) sem ganho para este domínio.
- **Rust (axum + sqlx):** mais lento de escrever; o gargalo do jogo é regra de negócio, não desempenho.
- **TypeScript (Fastify/NestJS):** o dono tem menos base em Node; ORM e migrations menos maduros que os do Django.

## Consequências
- O que o Supabase dava pronto (RLS, Realtime, Auth, hospedagem) passa a ser nosso: ver ADR 0004 (autorização) e 0005 (tempo real). Auth vem de biblioteca madura, nunca caseira.
- Operar o backend (deploy, backup, TLS) vira responsabilidade do projeto (RISCOS R9, D2).
- **Custo de reverter:** alto depois da etapa 2; barato agora.
