# Pendências

Critério: só entra o que está **em aberto** e depende de decisão ou ação. Decisões de produto e infraestrutura: ver `RISCOS.md` (D1-D10).

## Aguardando o dono
- [x] Arquitetura e ADRs 0001-0009 **aprovados** pelo dono em 2026-11-19. D8 confirmada: Django 5.2 LTS.
- [ ] Responder D3 (antes do deploy), D7 (na PR 4.0, com simulação), D2 (depois da etapa 2), **D11** (fonte de preços em USD, na PR 3.0: **decidida em 2026-11-24: Skinport por snapshot manual**, medida em `MEDICAO-3.0-FONTE-DE-PRECOS.md` (cobre 99,94%); **falta o dono ler os termos da Skinport (`skinport.com/terms`) antes de publicar o jogo**) e **D12** (anúncio real, etapa 6).
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
- [x] PR 2.5b telas de amigos (e `GET /api/v1/blocks/`): ver `SESSIONS.md` (Sessão 15).
- [x] PR 2.5c1 telas de grupos e membros (e `GET /api/v1/rooms/<id>/members/`): ver `SESSIONS.md` (Sessão 16).
- [x] PR 2.5c2 telas de convites (gerar, listar, revogar; `status` do convite calculado no backend; código só em estado do componente): ver `SESSIONS.md` (Sessão 17). **Fecha a Etapa 2.**
- [ ] **Validação manual do dono, no navegador, de toda a Etapa 2** (carteira, amigos, grupos e convites, com 2 contas): nada foi visto em tela até aqui, só testado no CI. Roteiros nos PRs #39, #44, #51 e no da 2.5c2.
- [ ] As mensagens dos convites repetem os tetos do backend (1 a 30 dias, 1 a 50 usos, 10 convites ativos), como a de "5 grupos": se `rules.py` mudar, ajustar a tela (ou passar os limites pela API).
- [ ] A mensagem "Você já é dono de 5 grupos." do frontend repete o teto `MAX_ROOMS_AS_OWNER` do backend; se o limite mudar, ajustar a tela (ou passar o limite pela API).
- [ ] **Convites, limites conhecidos:** o limite de tentativas de resgate mora no cache do Django (local em dev; em produção exige o cache em banco, já em "Bloqueios de deploy"); não há expulsar nem banir membro (o resgate só respeita o `banned` que já existir); convite não pode ser para um usuário específico.
- [ ] **`friends`, limites conhecidos:** sem teto de amigos nem de pedidos pendentes (anti-spam); um jogador com username `requests` não tem perfil acessível em `/friends/requests/` (colide com a rota literal; resolver reservando o nome no cadastro); `can_view` ainda não cobre "grupo" (entra com o primeiro recurso visível a grupo).
- [ ] **Valores da economia são provisórios** (saldo US$ 100, diária US$ 10 × dia até US$ 300): um jogador sem falhas ganha ~US$ 4.650 em 30 dias. Decisão de verdade na simulação da PR 4.0 (D7).
- [ ] **Ideia do dono, fora do escopo:** advertência e banimento temporário (3 advertências) para quem tentar fraudar. É um módulo de moderação próprio; a janela de 24h removeu a necessidade para a diária. Registrar quando houver o que punir.
- [ ] **Ponto quente:** toda operação de dinheiro trava a carteira `system` global, então tudo serializa nela. Aceitável nesta escala; medir antes de abrir ao público (se pesar, repartir a `system`).
- [ ] Usuários criados **antes** da PR 2.2 (ex.: contas de teste locais) não têm carteira até a primeira consulta: `ensure_wallet` a abre sozinho (auto-cura). Não há migração de dados.
- [ ] Revisar `room_id` das tabelas 3.3 a 3.6 e do §5 do `MODELO-DE-DADOS.md` na PR que implementar cada uma (hoje há um aviso no topo do §3).
- [ ] `REVOKE UPDATE/DELETE` do ledger com dois papéis de banco (dono das migrations x aplicação): fica para o deploy; até lá só o trigger protege.
- [x] Teste concorrente do limite de 5 salas: PR #93 (`tests/rooms/test_rooms_concurrency.py`); a mutação (tirar o `select_for_update`) derruba 3 dos 4 casos. Os casos de corrida e o da trava segurada dependem de agendamento/tempo; ver o texto do arquivo.
- [ ] Teste de que `PATCH` por `admin` (não só `owner`) funciona, quando existir forma de promover alguém a `admin`.

## Etapa 3 (aberta pela PR 3.0)
- [ ] **Rodar `python manage.py migrate` sem `--skip-checks`** num banco do dono depois do PR #102 (índice de amizades renomeado): deve terminar sem erro; se o banco já tinha a `0001`, o índice aparece com o nome novo. O `migrate` nunca tinha rodado de verdade até a Sessão 23.
- [ ] **Ver as telas do inventário no navegador** (PR 3.3, #95): `/inventario` com a conta A (depois do `grant_skin`), `/inventario/<A>` com uma amiga B e com uma C sem amizade (mesma tela de "não encontrado" de um usuário inexistente). Nada foi visto em tela, só CI.
- [ ] **3.4: coleção/catálogo e imagens (D1).** Não há endpoint de catálogo (`apps/catalog` sem urls/views) e "coleção" não está definida em nenhum doc; definir antes. Raridade e arma no filtro do inventário são texto livre por falta desse endpoint (ou de facetas).
- [ ] Inventário (frontend), limites conhecidos da revisão do #95: a chave de cache "mine" não inclui o id do usuário (mesmo padrão de carteira, amigos e grupos; a limpeza só roda no botão "Sair"); o texto "Tente novamente" não tem botão; `request<T>` faz cast sem validar o corpo; `maxLength` dos campos repetem o serializer; o formulário de filtros perde o rascunho ao paginar; o `retry` global do `QueryClient` (`main.tsx`) faz as outras telas esperarem ~7 s em 4xx; sem teste do link de amigos em `FriendsPage.test.tsx`; sem teste de erro de rede, 401 e 403 no inventário.
- [ ] **Rodar o `grant_skin` no PC do dono** (depois do import real): `python manage.py migrate` e `python manage.py grant_skin --user <seu_usuario> --skin <external_id de uma skin importada>`; conferir a instância e o desgaste impresso (PR 3.2a). `--float` fora da faixa da skin deve ser recusado.
- [ ] **Confirmar os cortes do desgaste** (0,07 / 0,15 / 0,38 / 0,45) e que o limite **inferior é inclusivo** (0,07 já é Minimal Wear): vêm do `MODELO-DE-DADOS`, a inclusividade é hipótese; conferir na fonte da Valve antes de mostrar o desgaste ao jogador (3.2b).
- [ ] **Validar a visibilidade do inventário com 2 contas no PC do dono** (PR 3.2b): contas A e B amigas, `grant_skin` para A; B vê o item em `/api/v1/inventory/<A>/`; uma conta C sem amizade recebe 404, igual ao de um usuário que não existe.
- [ ] **Etapa 4: toda ação sobre uma instância deve checar o dono.** O `id` da instância (UUID) passa a ser visível a amigos pela 3.2b; saber o id não pode dar poder nenhum.
- [ ] O `can_view` ainda não cobre "membro do mesmo grupo"; o inventário só é visível ao dono e a amigos aceitos. Entra com o primeiro recurso visível a grupo.
- [ ] Sem teste de concorrência da visibilidade (amizade desfeita no meio da requisição): a resposta reflete o instante da checagem.
- [ ] Se o import mudar a faixa (`min_float`/`max_float`) de uma skin que já tem instâncias, o trigger só confere na gravação: instâncias antigas podem ficar fora da nova faixa. Decidir o que fazer quando isso acontecer.
- [ ] **Rodar o `import_catalog` com os arquivos reais** no PC do dono (Postgres local): `python manage.py import_catalog --catalog backend/data/skins.json --prices backend/data/skinport.json`; conferir ~1.455 criadas e, na 2ª execução, 0 criadas e 0 atualizadas (PR 3.1).
- [ ] **Termos da Skinport** (`skinport.com/terms`): uso em jogo, exibição, guardar o dado, crédito. Bloqueia **publicar** o jogo, não o import local.
- [ ] **D1 (imagens)** na PR 3.3, com os termos da Valve lidos. A PR 3.1 não importa imagens.
- [ ] 4 variantes e 1 skin Restricted sem preço na Skinport (causa não confirmada: nome diferente ou item inexistente no mercado).
- [ ] Facas e luvas (`★`), StatTrak e Souvenir ficaram fora do catálogo; decidir se entram numa fase futura.
- [ ] Atualizar preços exige baixar o JSON da Skinport pelo navegador (o Cloudflare barra script); sem automação por ora.

## Verificações pendentes (antes da etapa 1)
- Licença do repo-fonte do catálogo de skins e termos das imagens.
- Licenças, datas de release e avisos de segurança das dependências (pré-triagem em DEPENDENCIAS).
- Criar modelo de CI para Python em `padrao/workflows/` do workspace (hoje só há Rust).
