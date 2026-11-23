# Pendências

Critério: só entra o que está **em aberto** e depende de decisão ou ação. Decisões de produto e infraestrutura: ver `RISCOS.md` (D1-D10).

## Aguardando o dono
- [x] Arquitetura e ADRs 0001-0009 **aprovados** pelo dono em 2026-11-19. D8 confirmada: Django 5.2 LTS.
- [ ] Responder D3 (antes do deploy), D7 (na PR 4.0, com simulação), D2 (depois da etapa 2), **D11** (fonte de preços em USD, na PR 3.0) e **D12** (anúncio real, etapa 6).
- [x] **Virada de produto** (2026-11-19): economia global por usuário, moeda virtual em USD na escala de preços reais, salas como grupos. ADR 0010 e 0011 gravados; 0003 e 0004 parcialmente substituídos. **Aguarda sua leitura/aprovação do PR**.
- [x] Nome (D9): **bahazar**, confirmado pelo dono em 2026-11-18. Repo (D10): `masterlxz/bahazar`, público, AGPL-3.0.

## Pendências do frontend (criadas pela PR 1.4)
- [x] **Validado no navegador** em 2026-11-19 (backend + Postgres 17 + Vite nesta máquina): cadastro, entrar, avatar, sair, `/perfil` deslogado, senha errada em sequência, cadastro duplicado. Ver `SESSIONS.md` (Sessão 8) para o que o log provou e o que foi só relato.
- [ ] Redefinição de senha e confirmação de e-mail (rotas `/account/...` que o backend já aponta), quando houver provedor de e-mail.
- [x] Gerar tipos a partir do OpenAPI: medido na PR 2.5a, **seguem à mão** (ADR 0012). Reabrir se: passar de ~25 rotas próprias, houver a primeira divergência real, ou `openapi-typescript` aceitar o TS do projeto.
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
0001 Django + DRF no lugar de Supabase · 0002 Regras econômicas em services · 0003 Ledger de partida dobrada (escopo "por sala" substituído pelo 0010) · 0004 Autorização no código (sem RLS; escopo "por sala" substituído pelo 0010) · 0005 Polling primeiro, SSE depois · 0006 Monólito modular · 0007 Dinheiro em centavos · 0008 Autenticação com allauth headless e usuário UUID · 0009 Tipos da API escritos à mão até a Etapa 2 · **0010 Economia global por usuário; salas como grupos** · **0011 Moeda virtual em USD na escala de preços reais** (0010 e 0011 gravados em 2026-11-19 e **aceitos** com o merge do PR #12).

## Etapa 2 (aberta pela PR 2.1; refeita pela virada de 2026-11-19)
- [x] PR 2.2 `economy` **global** (PR #13): carteira por usuário, `system` global, ledger com trigger, saldo inicial de US$ 100, diária em sequência (US$ 10 × dia até o dia 30, janela de 24h, **sem fuso**). Anúncio desativado.
- [x] PR 2.3 `friends` (pedido, aceite, recusa, remoção, bloqueio, `can_view`): ver `SESSIONS.md` (Sessão 12).
- [x] PR 2.4 convites de grupo (código de 128 bits só em hash, resgate idempotente e travado, limite de tentativas): ver `SESSIONS.md` (Sessão 13).
- [x] PR 2.5a (ADR 0012 e tela da carteira): ver `SESSIONS.md` (Sessão 14).
- [ ] PR 2.5b telas de amigos e PR 2.5c telas de grupos e convites. A 2.5c precisa de um endpoint de membros da sala (hoje a API não lista quem está na sala), que é backend.
- [ ] **Convites, limites conhecidos:** o limite de tentativas de resgate mora no cache do Django (local em dev; em produção exige o cache em banco, já em "Bloqueios de deploy"); não há expulsar nem banir membro (o resgate só respeita o `banned` que já existir); convite não pode ser para um usuário específico.
- [ ] **`friends`, limites conhecidos:** sem teto de amigos nem de pedidos pendentes (anti-spam); um jogador com username `requests` não tem perfil acessível em `/friends/requests/` (colide com a rota literal; resolver reservando o nome no cadastro); `can_view` ainda não cobre "grupo" (entra com o primeiro recurso visível a grupo).
- [ ] **Valores da economia são provisórios** (saldo US$ 100, diária US$ 10 × dia até US$ 300): um jogador sem falhas ganha ~US$ 4.650 em 30 dias. Decisão de verdade na simulação da PR 4.0 (D7).
- [ ] **Ideia do dono, fora do escopo:** advertência e banimento temporário (3 advertências) para quem tentar fraudar. É um módulo de moderação próprio; a janela de 24h removeu a necessidade para a diária. Registrar quando houver o que punir.
- [ ] **Ponto quente:** toda operação de dinheiro trava a carteira `system` global, então tudo serializa nela. Aceitável nesta escala; medir antes de abrir ao público (se pesar, repartir a `system`).
- [ ] Usuários criados **antes** da PR 2.2 (ex.: contas de teste locais) não têm carteira até a primeira consulta: `ensure_wallet` a abre sozinho (auto-cura). Não há migração de dados.
- [ ] Revisar `room_id` das tabelas 3.3 a 3.6 e do §5 do `MODELO-DE-DADOS.md` na PR que implementar cada uma (hoje há um aviso no topo do §3).
- [ ] `REVOKE UPDATE/DELETE` do ledger com dois papéis de banco (dono das migrations x aplicação): fica para o deploy; até lá só o trigger protege.
- [ ] Teste concorrente do limite de 5 salas (`create_room` trava o usuário, mas nenhum teste o exercita em paralelo).
- [ ] Teste de que `PATCH` por `admin` (não só `owner`) funciona, quando existir forma de promover alguém a `admin`.

## Verificações pendentes (antes da etapa 1)
- Licença do repo-fonte do catálogo de skins e termos das imagens.
- Licenças, datas de release e avisos de segurança das dependências (pré-triagem em DEPENDENCIAS).
- Criar modelo de CI para Python em `padrao/workflows/` do workspace (hoje só há Rust).
