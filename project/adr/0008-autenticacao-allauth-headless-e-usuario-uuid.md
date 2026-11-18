# 0008: Autenticação com django-allauth (headless) e usuário próprio com UUID

**Data:** 2026-11-18

## Contexto
O jogo precisa de cadastro, login, sessão e redefinição de senha, e de um perfil mínimo (avatar). Autenticação nunca é escrita do zero (AGENTS.md §4). Ainda não há domínio próprio, então o desenho de produção do navegador (D3) está em aberto.

## Decisão
- **django-allauth 65.22.1 em modo headless** (`HEADLESS_ONLY`, cliente `browser`): só endpoints JSON em `/_allauth/browser/v1/...`, sem telas HTML.
- **Sessão por cookie `HttpOnly` + CSRF**, mesma origem. O DRF aceita só `SessionAuthentication`. D3 (como isso funciona em produção sem domínio) fica **adiada** para o deploy.
- **Modelo de usuário próprio** (`accounts.User`, `AbstractUser`) com **UUID** como chave primária, definido antes da primeira migração. `username` com CHECK `^[a-z0-9_]{3,20}$` e e-mail único sem distinguir maiúsculas, no banco.
- **Sem tabela `profiles` separada:** o avatar (chave de uma lista fixa) mora no `User`. XP e nível irão para o módulo `progression`.
- Hash de senha padrão do Django (PBKDF2-SHA256), sem `argon2-cffi`.

## Alternativas descartadas
- **Auth própria em DRF:** código crítico de segurança escrito à mão.
- **dj-rest-auth:** sinais de manutenção fraca.
- **simplejwt / JWT:** força token no navegador; contraria a preferência por cookie `HttpOnly` e dependia do D3.
- **Tabela `profiles` 1:1:** um join e uma tabela a mais para um único campo; separa-se depois se o perfil crescer.
- **Avatar como URL livre:** abuso (conteúdo impróprio, rastreamento) e direitos de imagem.

## Consequências
- Trocar o modelo de usuário depois de haver dados é muito caro; por isso foi decidido agora, sem dados.
- O limite de tentativas depende do cache do Django: em produção usa `DatabaseCache` (`createcachetable` no deploy).
- **Não pode ir a produção** sem provedor de e-mail e verificação `mandatory` (ver `PENDING.md`).
- A senha fraca em português não é barrada (a lista de senhas comuns do Django é em inglês); avaliar validador próprio depois.
- **Custo de reverter:** alto para o modelo de usuário; baixo para a escolha do allauth.
