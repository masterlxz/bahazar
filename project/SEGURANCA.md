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
| Vazamento entre salas (IDOR) | Trocar `room_id`/`listing_id` na URL | *manager* escopado + permissão por sala em todo endpoint | teste parametrizado: cada endpoint com usuário de **outra** sala deve dar 404 |
| Mass assignment | `PATCH wallet {balance: 1e9}` | serializers com `fields` explícitos; carteiras e instâncias **sem** endpoint de escrita | API |
| Manipular sorteio | Cliente envia o "roll" | RNG só no servidor; cliente não envia nada além do id da caixa | API |
| Adulterar histórico | `UPDATE wallet_transactions` | `REVOKE` + trigger | teste de banco: UPDATE/DELETE falham |
| Convite adivinhado/vazado | Força bruta do código | ≥128 bits, hash, expiração, limite de usos, *rate limit* | unidade + API |
| Elevação de privilégio | Membro se promove a admin | só `owner`/`admin` alteram `role`; ninguém altera o próprio | API |
| Replay | Reenviar a mesma requisição | `Idempotency-Key` | API |
| Abuso/DoS | Spam de criar anúncios e salas | *throttling* DRF por usuário/IP; limites por sala (anúncios ativos, convites) | API |
| Contas falsas para farmar (futuro público) | Multi-contas | fora do escopo privado; ver RISCOS | - |

## 3. Autorização (substitui o RLS)
Camadas, da mais externa à mais interna:
1. **Permissão DRF** em toda view: `IsAuthenticated` + `IsRoomMember` (e `IsRoomAdmin` onde aplicável). Padrão **negar por omissão**: `DEFAULT_PERMISSION_CLASSES = [IsAuthenticated]` e teste que falha se existir view sem permissão explícita.
2. **Manager escopado por sala:** modelos de jogo expõem `.for_room(room, user)` e **não** usam `objects` solto nas views (convenção + teste que lista os modelos com `room_id` e checa que as views usam o escopado). Um `.filter(room=...)` esquecido é o principal risco de ficar sem RLS.
3. **Camada de serviço revalida:** `buy_listing(user, listing_id, key)` carrega o anúncio **dentro** da transação e confere sala, status, dono e saldo. Nunca confia no que a view já checou.
4. **Banco:** FKs compostas `(room_id, user_id)` para membros, `CHECK`s e índices únicos parciais. Mesmo um bug de serviço não cria item sem dono ou carteira de não-membro.
5. **Privilégios do banco:** o usuário da aplicação não é dono do esquema (migrations rodam com outro papel) e não tem `UPDATE/DELETE` nas tabelas append-only.

**Opção de reforço (decisão D4):** habilitar RLS do Postgres também, com `SET LOCAL app.user_id` por requisição. Dá defesa real contra o "filtro esquecido", mas aumenta complexidade, atrapalha pool de conexões em modo transação e exige disciplina nas migrations. Recomendação: **não agora**; avaliar antes de abrir ao público.

## 4. Autenticação
- Não escrever auth: usar biblioteca madura (candidata: django-allauth em modo *headless*; ver DEPENDENCIAS). Senhas com Argon2 (`argon2-cffi`) ou o hasher padrão do Django; nunca guardar senha em claro.
- Sessão por **cookie HttpOnly + Secure + SameSite=Lax** com CSRF, **se** frontend e API ficarem sob o mesmo domínio registrável (ex.: `app.exemplo.com` e `api.exemplo.com`). Se ficarem em domínios distintos (ex.: `*.vercel.app` + API própria), cookie vira cross-site e a alternativa é token (JWT curto + refresh rotativo). Decisão D3, recomendação: mesmo domínio registrável.
- Verificação de e-mail, redefinição de senha e *rate limit* em login. 2FA fica para depois.
- Nome de usuário único, validado (ver modelo).

## 5. Convites
1. Gerar com `secrets.token_urlsafe(16)` (128 bits). Exibir **uma vez**; gravar só `sha256(código)`.
2. Resgate = função de serviço transacional: trava a linha do convite, confere expiração, revogação e `uses < max_uses`, cria `room_member` e a carteira (com saldo inicial via ledger) e incrementa `uses`. Resgate repetido pelo mesmo usuário é idempotente.
3. Comparação por hash do valor recebido (busca por índice único; sem comparação byte a byte vulnerável a timing, pois o segredo nunca é comparado em claro).
4. *Throttling* no endpoint de resgate para barrar força bruta.

## 6. Dinheiro e concorrência
- **Transação única** por operação: `transaction.atomic()` envolve checagens, lançamentos no ledger, troca de dono e atualização de status.
- Nível de isolamento `READ COMMITTED` (padrão) **com travas explícitas** (`select_for_update`): ordem fixa **anúncio → instância → carteiras ordenadas por UUID**. Ordem fixa evita deadlock; se ocorrer, a transação é repetida (limite de 3 tentativas).
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
- Logs sem senha, token, código de convite ou `Idempotency-Key` completa. Monitoramento de erros (decisão de ferramenta pendente).
- Backup do Postgres com **teste de restauração** documentado.

## 10. Plano de testes de segurança (obrigatórios por funcionalidade)
| Área | Casos mínimos |
|---|---|
| Autorização | Para **cada endpoint**: anônimo → 401; usuário de outra sala → 404; membro comum em rota de admin → 403 |
| Carteira | Saldo nunca negativo; transferência soma zero; valor ≤ 0, enorme (> bigint) e não numérico rejeitados |
| Ledger | UPDATE/DELETE bloqueados; `SUM(amount)` da sala = 0; `balance` = soma do extrato após carga aleatória |
| Marketplace | 2 compradores simultâneos → 1 sucesso; comprar o próprio anúncio falha; anunciar item alheio/consumido/já anunciado falha; cancelar durante compra |
| Idempotência | Mesma chave 2x → mesmo resultado, 1 débito; mesma chave com corpo diferente → 422 |
| Convites | Expirado, revogado, esgotado, código errado, resgate concorrente com `max_uses=1` |
| Caixas | Distribuição estatística (qui-quadrado, N grande) coerente com os pesos; pagamento e item atômicos; sem endpoint aceitando "roll" |
| Trade-up | Entradas de outro usuário/sala, já consumidas, anunciadas ou em quantidade errada falham; float de saída dentro da faixa |
| Propriedade (property-based) | Hypothesis: sequência aleatória de operações mantém as invariantes (soma zero, saldo ≥ 0, um dono por item, um anúncio ativo por item) |

Mutação deliberada (AGENTS.md §3 D): trocar `>=` por `>` no check de saldo, remover o `select_for_update` e remover o `UNIQUE` parcial; **algum teste tem de falhar** em cada caso.
