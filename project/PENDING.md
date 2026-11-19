# Pendências

Critério: só entra o que está **em aberto** e depende de decisão ou ação. Decisões de produto e infraestrutura: ver `RISCOS.md` (D1-D10).

## Aguardando o dono
- [x] Arquitetura e ADRs 0001-0009 **aprovados** pelo dono em 2026-11-19. D8 confirmada: Django 5.2 LTS.
- [ ] Responder D3 (antes do deploy), D7 (antes da etapa 4) e D2 (depois da etapa 2).
- [x] Nome (D9): **bahazar**, confirmado pelo dono em 2026-11-18. Repo (D10): `masterlxz/bahazar`, público, AGPL-3.0.

## Pendências do frontend (criadas pela PR 1.4)
- [ ] **Validar no navegador** (só você pode: esta máquina não sobe o backend): cadastro, entrar (com usuário e com e-mail), trocar avatar, sair. Passo a passo no `README.md`.
- [ ] Redefinição de senha e confirmação de e-mail (rotas `/account/...` que o backend já aponta), quando houver provedor de e-mail.
- [ ] Gerar tipos a partir do OpenAPI na Etapa 2 (gatilho do ADR 0009: entrada do app `rooms`).
- [x] Mensagem própria para "muitas tentativas de login": feita (PR #9), cobre `400 too_many_login_attempts` e `429`.
- [ ] Variável `VITE_BACKEND_URL` no proxy do Vite (hoje fixo em `localhost:8000`; exige `@types/node`).

## Bloqueios de deploy (criados pela PR 1.3)
- [ ] Provedor de e-mail transacional + `ACCOUNT_EMAIL_VERIFICATION = "mandatory"` (hoje `optional`, e-mail no console em dev). Sem isso o cadastro em produção falha ao enviar e-mail.
- [ ] `python manage.py createcachetable` antes do primeiro deploy (cache em banco do limite de tentativas).
- [ ] D3: como o navegador autentica em produção sem domínio (proxy da Vercel + cookie, domínio próprio ou JWT). Em dev funciona só na mesma origem.
- [ ] `DJANGO_CSRF_TRUSTED_ORIGINS` com a origem real do frontend.
- [ ] Validador de senha comum em português (a lista do Django é em inglês).
- [ ] Política de privacidade e exclusão de conta (LGPD) antes de abrir ao público.

## ADRs gravados em `project/adr/` (gravados em 2026-11-18, **aceitos** em 2026-11-19)
0001 Django + DRF no lugar de Supabase · 0002 Regras econômicas em services · 0003 Ledger de partida dobrada · 0004 Autorização no código (sem RLS) · 0005 Polling primeiro, SSE depois · 0006 Monólito modular · 0007 Dinheiro em centavos · 0008 Autenticação com allauth headless e usuário UUID · 0009 Tipos da API escritos à mão até a Etapa 2.

## Verificações pendentes (antes da etapa 1)
- Licença do repo-fonte do catálogo de skins e termos das imagens.
- Licenças, datas de release e avisos de segurança das dependências (pré-triagem em DEPENDENCIAS).
- Criar modelo de CI para Python em `padrao/workflows/` do workspace (hoje só há Rust).
