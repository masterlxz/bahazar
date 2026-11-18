# Pendências

Critério: só entra o que está **em aberto** e depende de decisão ou ação. Decisões de produto e infraestrutura: ver `RISCOS.md` (D1-D10).

## Aguardando o dono
- [ ] Aprovar (ou pedir mudanças em) a arquitetura desta entrega.
- [ ] Responder D2, D3, D7, D8 (bloqueiam a etapa 1 e 4).
- [x] Nome (D9): **bahazar**, confirmado pelo dono em 2026-11-18. Repo (D10): `masterlxz/bahazar`, público, AGPL-3.0.

## Bloqueios de deploy (criados pela PR 1.3)
- [ ] Provedor de e-mail transacional + `ACCOUNT_EMAIL_VERIFICATION = "mandatory"` (hoje `optional`, e-mail no console em dev). Sem isso o cadastro em produção falha ao enviar e-mail.
- [ ] `python manage.py createcachetable` antes do primeiro deploy (cache em banco do limite de tentativas).
- [ ] D3: como o navegador autentica em produção sem domínio (proxy da Vercel + cookie, domínio próprio ou JWT). Em dev funciona só na mesma origem.
- [ ] `DJANGO_CSRF_TRUSTED_ORIGINS` com a origem real do frontend.
- [ ] Validador de senha comum em português (a lista do Django é em inglês).
- [ ] Política de privacidade e exclusão de conta (LGPD) antes de abrir ao público.

## ADRs gravados em `project/adr/` (2026-11-18, status: propostos até a aprovação da arquitetura)
0001 Django + DRF no lugar de Supabase · 0002 Regras econômicas em services · 0003 Ledger de partida dobrada · 0004 Autorização no código (sem RLS) · 0005 Polling primeiro, SSE depois · 0006 Monólito modular · 0007 Dinheiro em centavos · 0008 Autenticação com allauth headless e usuário UUID.

## Verificações pendentes (antes da etapa 1)
- Licença do repo-fonte do catálogo de skins e termos das imagens.
- Licenças, datas de release e avisos de segurança das dependências (pré-triagem em DEPENDENCIAS).
- Criar modelo de CI para Python em `padrao/workflows/` do workspace (hoje só há Rust).
