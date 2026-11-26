# Estratégia de segurança

Sem Supabase, **não há RLS como rede de proteção automática**. A autorização passa a ser responsabilidade do código Django, com reforços no banco. Este documento diz onde cada garantia mora e como ela é testada.

> Estado: proposta. Nada foi executado. Itens de autenticação e dinheiro exigem confirmação sua antes de implementar (AGENTS.md §4).

## 1. Fronteiras de confiança
| Quem | Confiança | Regra |
|---|---|---|
| Navegador / frontend | **nenhuma** | Qualquer valor vindo dele (preço, saldo, id de dono, resultado de sorteio) é ignorado ou revalidado |
| API Django (serviços) | confiável | Única camada que escreve em tabelas de jogo |
| PostgreSQL | confiável | Última linha de defesa: constraints, triggers, privilégios |
| Dado do catálogo importado | semi-confiável | Validado no import (esquema, faixas); import só por comando administrativo |

## 2. Modelo de ameaças (resumo)
| Ameaça | Exemplo | Defesa principal | Teste |
|---|---|---|---|
| Duplicar dinheiro/item | Dois cliques simultâneos em "comprar" | `select_for_update` + `UNIQUE` parcial + idempotência | concorrência (N threads contra o mesmo anúncio: 1 vence) |
| Saldo negativo | Duas compras em paralelo com saldo para uma | lock da carteira + `CHECK balance >= 0` | concorrência |
| Comprar o próprio anúncio | `buyer = seller` para inflar estatística | `CHECK buyer<>seller` + validação no serviço | unidade + API |
| Vazamento entre usuários (IDOR) | Trocar o id do usuário, do grupo ou do item na URL para ler a carteira ou o inventário de quem não é amigo | *selector* escopado + **uma** permissão central de visibilidade (dono, amigo, membro do mesmo grupo) em todo endpoint | teste parametrizado: cada endpoint com usuário **sem relação** (ou bloqueado) deve dar 404. **Inventário implementado (PR 3.2b)**: `GET /inventory/<username>/` decide só por `friends.selectors.can_view`; sem relação, pedido pendente, bloqueio nos dois sentidos e usuário inexistente dão o **mesmo 404** (status e corpo); a autorização vem **antes** de validar a query (um 400 só chega a quem já pode ver); o escopo do queryset é o dono resolvido, nunca um parâmetro |
| Multi-conta para farmar renda diária | Criar N contas para resgatar a diária N vezes (J4, agora dentro do escopo) | a janela de 24h e o `UNIQUE(user, claim_number)` impedem repetir por conta (sem fuso, nada a manipular); **não** impede várias contas. Mitigação futura: e-mail verificado obrigatório, limite por IP/dispositivo | hoje só o `UNIQUE`; o resto é risco aceito e registrado (RISCOS J4) |
| Mass assignment | `PATCH wallet {balance: 1e9}` | serializers com `fields` explícitos; carteiras e instâncias **sem** endpoint de escrita | API |
| Manipular sorteio | Cliente envia o "roll" | RNG só no servidor; cliente não envia nada além do id da caixa | API |
| Adulterar histórico | `UPDATE wallet_transactions` | `REVOKE` + trigger | teste de banco: UPDATE/DELETE falham |
| Convite adivinhado/vazado | Força bruta do código | ≥128 bits, hash, expiração, limite de usos, *rate limit* | unidade + API |
| Elevação de privilégio | Membro se promove a admin | só `owner`/`admin` alteram `role`; ninguém altera o próprio | API |
| Replay | Reenviar a mesma requisição | `Idempotency-Key` | API |
| Abuso/DoS | Spam de criar anúncios e salas | *throttling* DRF por usuário/IP; limites por sala (anúncios ativos, convites) | API |
| Contas falsas para farmar (futuro público) | Multi-contas | fora do escopo privado; ver RISCOS | - |

## 3. Autorização (substitui o RLS)
> **Revisão de 2026-11-19 (ADR 0010):** a economia é global por usuário. A pergunta de autorização deixa de ser "é membro da sala?" e passa a ser **"é o dono, amigo do dono ou membro do mesmo grupo?"**, conforme o recurso. O app `rooms` (PR 2.1) mantém o seu escopo por grupo; carteira e inventário usam a regra nova.

Camadas, da mais externa à mais interna:
1. **Permissão DRF** em toda view: `IsAuthenticated` + a permissão do recurso (`IsRoomMember`/`IsRoomAdmin` para grupos; **permissão central de visibilidade** para carteira e inventário). Padrão **negar por omissão**: `DEFAULT_PERMISSION_CLASSES = [IsAuthenticated]` e teste que falha se existir view de `rooms` sem permissão explícita (já existe).
2. **Selector escopado:** leitura de dados de jogo só por selectors que recebem o usuário (como `rooms.selectors.rooms_for_user`); **proibido** `Model.objects` solto em view. A regra "quem vê o quê" vive em **um** lugar (`friends`), nunca em `if amigo` espalhado: esquecê-la é o análogo do "filtro esquecido" de quem não tem RLS.
3. **Camada de serviço revalida:** `buy_listing(user, listing_id, key)` carrega o anúncio **dentro** da transação e confere status, dono e saldo. Nunca confia no que a view já checou.
4. **Banco:** FK simples ao dono, `CHECK`s e índices únicos parciais (um dono ativo por grupo, uma carteira por usuário, uma `system` global, uma relação de amizade por par). Mesmo um bug de serviço não cria item sem dono nem carteira sem usuário.
5. **Privilégios do banco:** o usuário da aplicação não é dono do esquema (migrations rodam com outro papel) e não tem `UPDATE/DELETE` nas tabelas append-only.

**Opção de reforço (decisão D4):** habilitar RLS do Postgres também, com `SET LOCAL app.user_id` por requisição. Dá defesa real contra o "filtro esquecido", mas aumenta complexidade, atrapalha pool de conexões em modo transação e exige disciplina nas migrations. Recomendação: **não agora**; avaliar antes de abrir ao público.

## 4. Autenticação
**Implementado na PR 1.3 (ADR 0008).**
- Não escrever auth: **django-allauth em modo headless** (só API JSON, cliente `browser`, sem telas HTML). Senha com o hasher padrão do Django (PBKDF2-SHA256), mínimo de 10 caracteres, validadores do Django. **Limite conhecido:** a lista de senhas comuns do Django é em inglês, então senhas fracas em português (ex.: `senha12345`) passam.
- Sessão por **cookie `HttpOnly` + `SameSite=Lax`** (+ `Secure` em produção) com **CSRF** (cookie `csrftoken` legível pelo frontend, que devolve o token no cabeçalho `X-CSRFToken`). O DRF aceita **só `SessionAuthentication`**: sem `BasicAuthentication`, sem token em cabeçalho. **Mesma origem exigida** (em dev, proxy do Vite). **D3 adiada**: o desenho de produção (proxy da Vercel + cookie, domínio próprio ou JWT) é decidido no deploy; sem domínio, cookie cross-site não funciona (`vercel.app` está na lista pública de sufixos).
- Login por **usuário ou e-mail**. Nome de usuário: `^[a-z0-9_]{3,20}$`, gravado em minúsculas, lista de nomes reservados (`admin`, `system`, `root`, `bahazar`...), imutável por enquanto. E-mail único sem distinguir maiúsculas (inclusive no banco).
- **Limite de tentativas de login** pelo allauth (`login_failed`), que usa o cache do Django: em produção, **cache em banco** (`DatabaseCache`), porque `LocMemCache` conta por processo. Exige `python manage.py createcachetable` antes do primeiro deploy.
- E-mail: verificação **opcional** por enquanto (sem provedor). **Bloqueio de deploy:** passar para `mandatory` e configurar provedor antes de qualquer produção; hoje em dev o e-mail sai no console.
- `ACCOUNT_PREVENT_ENUMERATION` (padrão do allauth) protege o e-mail; o nome de usuário "já existe" é enumerável por natureza (é público no jogo).
- Fora desta etapa: 2FA, login social, troca de e-mail/usuário, exclusão de conta (LGPD).

## 5. Convites
1. Gerar com `secrets.token_urlsafe(16)` (128 bits). Exibir **uma vez**; gravar só `sha256(código)`.
2. Resgate = função de serviço transacional: trava a linha do convite, confere expiração, revogação e `uses < max_uses`, cria `room_member` (a carteira **já existe**, é global e nasce no cadastro) e incrementa `uses`. Resgate repetido pelo mesmo usuário é idempotente. Convite entra em grupo; **não** concede dinheiro.
3. Comparação por hash do valor recebido (busca por índice único; sem comparação byte a byte vulnerável a timing, pois o segredo nunca é comparado em claro).
4. *Throttling* no endpoint de resgate para barrar força bruta.

## 6. Dinheiro e concorrência
- **Transação única** por operação: `transaction.atomic()` envolve checagens, lançamentos no ledger, troca de dono e atualização de status.
- Nível de isolamento `READ COMMITTED` (padrão) **com travas explícitas** (`select_for_update`): ordem fixa **jogadores → anúncio ou oferta → instâncias → carteiras, cada grupo por id crescente** (ADR 0016; a redação antiga, "anúncio → instância → carteiras", nunca foi a do código). Ordem fixa evita deadlock; se ocorrer, a transação é repetida (limite de 3 tentativas).
- **Idempotência** por `Idempotency-Key` (ver MODELO §4.4).
- Toda operação grava `activity_log`/ledger na mesma transação (nada de "gravar log depois").
- Estados inválidos tornados irrepresentáveis pelo banco (índices parciais, `CHECK`).

## 7. RNG (caixas e trade-ups)
- Fonte: `secrets.randbelow()` (CSPRNG do SO), **no servidor**, dentro da transação de pagamento (pagar e sortear são atômicos: sem "sortear grátis e desistir").
- Probabilidades explícitas e **congeladas** na publicação da caixa; cada abertura grava `drops_snapshot` + `roll`. Um comando de auditoria reproduz: dado o `roll`, o item tem de ser o gravado.
- Opcional (decisão D5): *commit-reveal* (hash de uma semente publicado antes, revelada depois) para verificabilidade pelos jogadores. Em jogo privado entre amigos é dispensável; vira relevante se o jogo abrir ao público.

## 8. Validação de entrada
Serializers DRF com tipos estritos; limites explícitos (`price` entre mínimo e máximo, tamanhos de string, página máxima); rejeitar campos desconhecidos; IDs como UUID validado. Frontend valida só por UX, nunca por segurança.

## 9. Segredos, CI e operação
- Nenhum segredo no repo: `.env` ignorado; `.env.example` sem valores; produção usa variáveis do provedor. Chave secreta do Django, credenciais do banco e e-mail só no servidor.
- CORS restrito à origem do frontend; `SECURE_*`, HSTS, `DEBUG=False` em produção; `ALLOWED_HOSTS` explícito.
- CI (ver PLANO etapa 1): guard de segredos do workspace, `ruff`, `mypy`/`pyright`, `pip-audit`, `npm audit`, testes com Postgres real, `bandit`.
- **Ruleset da `main`** (`.github/ruleset-protect-main.json`, aplicado pela API): PR obrigatório, sem force push, sem apagar, e três checks obrigatórios (`guard`, `Python (lint, types and tests)`, `Frontend (lint, types, tests and build)`). Os nomes são o `name:` dos jobs do `ci.yml`: **renomear um job sem atualizar o JSON e o ruleset trava todo merge** (o check nunca reporta). Para reaplicar: `gh api -X PUT repos/masterlxz/bahazar/rulesets/27571902 --input .github/ruleset-protect-main.json`.
- Logs sem senha, token, código de convite ou `Idempotency-Key` completa. Monitoramento de erros (decisão de ferramenta pendente).
- Backup do Postgres com **teste de restauração** documentado.

## 10. Plano de testes de segurança (obrigatórios por funcionalidade)
| Área | Casos mínimos |
|---|---|
| Autorização | Para **cada endpoint**: anônimo → 401; usuário sem relação com o dono/grupo (ou bloqueado) → 404; membro comum em rota de admin do grupo → 403 |
| Carteira | Saldo nunca negativo; transferência soma zero; valor ≤ 0, enorme (> bigint) e não numérico rejeitados; **nenhum endpoint de escrita** em carteira |
| Renda diária | Resgate 2x no mesmo dia (inclusive em paralelo) → um crédito só; valor vem do servidor, nunca do corpo |
| Amizade | Auto-pedido, pedido duplicado e pedido a quem bloqueou recusados; bloqueado não vê nada |
| Ledger | UPDATE/DELETE bloqueados; `SUM(amount)` de todo o ledger = 0; `balance` = soma do extrato após carga aleatória |
| Marketplace | 2 compradores simultâneos → 1 sucesso; comprar o próprio anúncio falha; anunciar item alheio/consumido/já anunciado falha; cancelar durante compra |
| Idempotência | Mesma chave 2x → mesmo resultado, 1 débito; mesma chave com corpo diferente → 422 |
| Convites | Expirado, revogado, esgotado, código errado, resgate concorrente com `max_uses=1` |
| Caixas | Distribuição estatística (qui-quadrado, N grande) coerente com os pesos; pagamento e item atômicos; sem endpoint aceitando "roll" |
| Trade-up | Entradas de outro usuário/sala, já consumidas, anunciadas ou em quantidade errada falham; float de saída dentro da faixa |
| Propriedade (property-based) | Hypothesis: sequência aleatória de operações mantém as invariantes (soma zero, saldo ≥ 0, um dono por item, um anúncio ativo por item) |

Mutação deliberada (AGENTS.md §3 D): trocar `>=` por `>` no check de saldo, remover o `select_for_update` e remover o `UNIQUE` parcial; **algum teste tem de falhar** em cada caso.
