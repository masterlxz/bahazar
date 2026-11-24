# Modelo de dados

PostgreSQL é a fonte da verdade. As garantias de integridade (FK, CHECK, UNIQUE, índices parciais, triggers) ficam **no banco**, não só no Django: um bug de aplicação não pode criar saldo negativo nem dois anúncios ativos do mesmo item.

> Estado: proposta para revisão. SQL **não executado**; nomes e tipos são o contrato de desenho, o Django os materializa em migrations.
>
> **Revisão de 2026-11-19 (ADR 0010 e 0011):** a economia é **global por usuário** e a moeda é virtual em **centavos de USD**. Sala virou **grupo**. As seções 1, 3.1, 3.2 e 4 abaixo já refletem isso. As tabelas das seções 3.3 a 3.6 e o §5 **ainda trazem `room_id` do desenho antigo**: ele sai (a posse é do usuário); cada tabela é corrigida na PR que a implementa, e este aviso vale até lá.

## 1. Convenções
1. PK `uuid` (v4, `gen_random_uuid()`) em todas as tabelas, exceto onde indicado.
2. `created_at timestamptz NOT NULL DEFAULT now()` em tudo; `updated_at` só onde há mutação legítima.
3. **Dinheiro = inteiro.** Unidade: `bigint` em "centavos" do jogo (1 unidade = 0,01 moeda virtual). Nunca `float`/`double`/`numeric` para saldo, preço ou taxa. Taxas em **basis points** (`int`, 100 = 1%), com arredondamento definido em um único lugar (função pura de serviço, com teste).
4. **Posse global, grupos por sala.** Carteira, inventário e ledger pertencem ao **usuário** (ADR 0010); não há `room_id` neles. A sala é só um grupo (membros, papéis, convite). O isolamento é por **dono**, **amizade** e **grupo**, decidido por uma permissão central (ver SEGURANCA §3).
5. Enums como `text` + `CHECK (col IN (...))` (migração mais simples que `ENUM` nativo).
6. Registros financeiros e de resultado (ledger, aberturas de caixa, trade-ups, transações de mercado) são **append-only**.
7. Nomes em inglês `snake_case` (convenção Django); documentação em português.

## 2. Diagrama (visão geral)
```mermaid
erDiagram
  users ||--o{ room_members : "participa"
  rooms ||--o{ room_members : ""
  rooms ||--o{ room_invites : ""
  users ||--|| wallets : "1 carteira por jogador (global)"
  users ||--o{ friendships : "amizade"
  users ||--o{ daily_claims : "resgate diário"
  wallets ||--o{ wallet_transactions : "ledger"
  skins ||--o{ skin_instances : "catálogo -> instância"
  users ||--o{ skin_instances : "inventário (dono)"
  skin_instances ||--o{ market_listings : ""
  market_listings ||--o| market_transactions : "venda"
  cases ||--o{ case_drops : ""
  skins ||--o{ case_drops : ""
  cases ||--o{ case_openings : ""
  tradeup_recipes ||--o{ tradeup_history : ""
  tradeup_history ||--o{ tradeup_inputs : ""
  achievements ||--o{ player_achievements : ""
  seasons ||--o{ rooms : "opcional"
```

## 3. Tabelas

### 3.1 Identidade e salas
| Tabela | Campos principais | Constraints e índices |
|---|---|---|
| `users` (`accounts.User`, **implementado na PR 1.3**) | `id` uuid, `username` varchar(20), `email`, `avatar` (chave de lista fixa), mais os campos padrão do `AbstractUser` (`password`, `is_active`, `is_staff`...) | `UNIQUE(username)`; **CHECK** `username ~ '^[a-z0-9_]{3,20}$'` (`user_username_format`); **UNIQUE** `lower(email)` onde `email <> ''` (`user_email_unique_ci`). **Substitui a tabela `profiles` prevista antes** (ADR 0008): o perfil hoje é só o avatar, então não há tabela 1:1. `xp` e `level` migram para o módulo `progression` (o núcleo não importa módulo) |
| `rooms` (**implementado na PR 2.1**; é um **grupo/lobby**) | `id`, `name`, `owner_id` → users, `visibility` (`private`\|`public`), `max_members`, `archived_at`, `created_at`, `updated_at`; `season_id` null reservado | `visibility='private'` por padrão (público só no futuro); `max_members >= 1`. **Sem** `starting_balance` nem `market_fee_bps`: moeda e taxa são **globais** (ADR 0010) |
| `friendships` (**PR 2.3, implementada**) | `id`, `requester_id`, `addressee_id` → users, `status` (`pending`\|`accepted`\|`blocked`), `created_at`, `responded_at` | `CHECK requester_id <> addressee_id`; **uma relação por par** (`UNIQUE` sobre o par não ordenado: `LEAST(a,b), GREATEST(a,b)`); índice `(addressee_id, status)` para "pedidos recebidos". Base de "só amigo vê meu inventário". **Bloqueio:** a linha é reescrita com `requester` = quem bloqueou e só ele desbloqueia (apaga a linha); bloquear derruba amizade e pedido. **Recusar e remover apagam a linha** (não há estado "recusado"). Bloqueado, inexistente e auto-pedido dão a mesma resposta ao pedir (anti-enumeração) |
| `room_members` | `id`, `room_id`, `user_id`, `role` (`owner`\|`admin`\|`member`), `joined_at`, `status` (`active`\|`left`\|`banned`) | `UNIQUE(room_id, user_id)`; índice `(user_id, room_id)` (consulta "minhas salas" e checagem de pertencimento); **exatamente um `owner` ativo por sala** (índice único parcial `WHERE role='owner' AND status='active'`) |
| `room_invites` (**PR 2.4, implementada**) | `id`, `room_id`, `created_by`, `code_hash` (bytea, sha256), `expires_at`, `max_uses`, `uses`, `revoked_at`, `created_at` | `UNIQUE(code_hash)`; `CHECK uses >= 0`, `uses <= max_uses`, `max_uses >= 1`; índice `(room_id, revoked_at)`; o código em claro **nunca** é gravado (ver SEGURANCA §5). Revogar preenche `revoked_at` (não apaga). Padrão 7 dias e 10 usos; tetos 30 dias e 50 usos; no máximo 10 convites ativos por sala (ativo = não revogado, não expirado, `uses < max_uses`). Resgate: trava convite e depois sala; já ser membro é sucesso sem gastar uso; quem saiu volta pela mesma linha de `room_members`; banido e código desconhecido dão 404, e convite válido mas inutilizável dá 409 com o motivo |

### 3.2 Economia (núcleo financeiro)
| Tabela | Campos principais | Constraints e índices |
|---|---|---|
| `wallets` (PR B) | `id`, `user_id` null, `kind` (`player`\|`system`), `balance` bigint (**centavos de USD**, ADR 0011), `version` | **`UNIQUE(user_id)`** (uma carteira por jogador); **uma única `system` global** (índice único parcial `WHERE kind='system'`); `CHECK (kind='system' OR balance >= 0)`; `CHECK ((kind='player') = (user_id IS NOT NULL))` |
| `wallet_transactions` (PR B) | `id`, `wallet_id`, `group_id` (uuid do lançamento), `amount` bigint (assinado, ≠ 0), `balance_after` bigint, `kind`, `ref_type`, `ref_id`, `idempotency_key`, `created_at` | **append-only** (ver §4); `UNIQUE(wallet_id, idempotency_key)`; índice `(wallet_id, created_at DESC, id)` (extrato paginado); índice `(group_id)`; `kind IN ('starting_grant','daily_reward','ad_reward','transfer','trade','market_sale','market_purchase','market_fee','case_open','case_reward','tradeup','quest_reward','adjustment')` |
| `daily_claims` (**PR 2.2, implementada**) | `id`, `user_id`, `claim_number` (1, 2, 3... por jogador), `claimed_at`, `streak_day`, `amount`, `ledger_group_id` | `UNIQUE(user_id, claim_number)`: dois resgates simultâneos tentam o mesmo número e só um entra (a 1ª defesa é a trava da carteira). **Janela de 24h por resgate, sem fuso** (decisão do dono, 2026-11-19): libera 24h depois do último; a sequência continua se o próximo vier entre 24h e 48h e zera depois. O valor é `US$ 10 × dia`, com teto no dia 30 (provisório, D7). Descartado: meia-noite local (manipulável pelo fuso) |

### 3.3 Catálogo (global) e inventário (por usuário; ver o aviso no topo sobre `room_id`)
| Tabela | Campos principais | Constraints e índices |
|---|---|---|
| `skins` | `id`, `external_id` (id do dado-fonte), `weapon`, `name`, `collection`, `rarity`, `min_float`, `max_float`, `reference_price` bigint, `image_url`, `image_source`, `active` | `UNIQUE(external_id)`; `0 <= min_float < max_float <= 1`; `reference_price > 0`; **global**, sem `room_id`; leitura por qualquer autenticado, escrita só por import administrativo. **Implementada na PR 3.1** (`apps/catalog`): `id` é UUID; `image_url` fica vazio e `image_source` = `none` até a D1; `collection` é a 1ª coleção do catálogo (vazia se não houver) |
| `skin_instances` | `id`, `room_id`, `skin_id`, `owner_id`, `float_value` numeric(10,9), `acquired_via`, `acquired_at`, `acquired_ref_id`, `consumed_at` null, `consumed_ref_id` null | cada instância tem **um** dono (`owner_id NOT NULL`); FK composta `(room_id, owner_id)` → `room_members`; CHECK do float dentro de `[skin.min_float, skin.max_float]` (trigger, pois cruza tabelas); índices `(room_id, owner_id)` e `(room_id, skin_id)` |

O **desgaste** (FN/MW/FT/WW/BS) não é coluna: é derivado de `float_value` por função pura (faixas padrão: 0-0,07-0,15-0,38-0,45-1). Evita inconsistência entre float e rótulo.

### 3.4 Marketplace
| Tabela | Campos principais | Constraints e índices |
|---|---|---|
| `market_listings` | `id`, `room_id`, `skin_instance_id`, `seller_id`, `price` bigint, `status` (`active`\|`sold`\|`cancelled`), `created_at`, `closed_at` | `price > 0`; **`UNIQUE(skin_instance_id) WHERE status='active'`** (uma skin, um anúncio ativo); índice `(room_id, status, created_at DESC)` para a vitrine; índice `(seller_id)` |
| `market_transactions` | `id`, `room_id`, `listing_id` (UNIQUE), `buyer_id`, `seller_id`, `price`, `fee`, `ledger_group_id`, `idempotency_key` | **append-only**; `buyer_id <> seller_id`; `UNIQUE(listing_id)` (um anúncio só vende uma vez); `UNIQUE(buyer_id, idempotency_key)` |

### 3.5 Caixas e trade-ups (módulos)
| Tabela | Campos principais | Constraints e índices |
|---|---|---|
| `cases` | `id`, `room_id` null (global ou da sala), `name`, `price` bigint, `status` (`draft`\|`published`\|`retired`) | `price >= 0`; **imutável após `published`** (drops e pesos congelados) |
| `case_drops` | `id`, `case_id`, `skin_id`, `weight` int (partes por milhão) | `weight > 0`; `UNIQUE(case_id, skin_id)`; soma dos pesos = 1 000 000 verificada **na publicação** (CHECK entre linhas não existe; validado no serviço + teste e conferido por query de auditoria) |
| `case_openings` | `id`, `room_id`, `case_id`, `user_id`, `price_paid`, `result_instance_id`, `result_skin_id`, `roll` int, `drops_snapshot` jsonb, `ledger_group_id`, `idempotency_key` | **append-only**; `drops_snapshot` guarda pesos usados e `roll`, permitindo **verificar** depois que o sorteio respeitou as probabilidades |
| `tradeup_recipes` | `id`, `name`, `input_rarity`, `input_count`, `output_rarity`, `rules` (colunas explícitas, não jsonb livre: ex. `same_collection_required`) | `input_count >= 2` |
| `tradeup_history` | `id`, `room_id`, `recipe_id`, `user_id`, `result_instance_id`, `outcome_snapshot` jsonb, `idempotency_key` | **append-only** |
| `tradeup_inputs` | `tradeup_id`, `skin_instance_id`, `float_value` | entradas consumidas; `UNIQUE(skin_instance_id)` (item só é consumido uma vez) |

### 3.5.1 Trade-up: consumo de itens
As instâncias consumidas **não são apagadas**: recebem `skin_instances.consumed_at` (e `consumed_ref_id`). Elas somem do inventário, do mercado e do ranking pelo filtro `consumed_at IS NULL`, mas permanecem para auditoria. Vale para qualquer "destruição" futura. Alternativa descartada: `DELETE` (perde histórico e quebra FK de `tradeup_inputs`).

### 3.6 Progressão e competição
| Tabela | Campos principais | Constraints e índices |
|---|---|---|
| `achievements` | `id`, `code` (UNIQUE), `name`, `description`, `reward` bigint, `xp` | catálogo global |
| `player_achievements` | `id`, `room_id`, `user_id`, `achievement_id`, `unlocked_at`, `ledger_group_id` null | `UNIQUE(room_id, user_id, achievement_id)` (não ganha duas vezes) |
| `seasons` | `id`, `name`, `starts_at`, `ends_at`, `status` | `ends_at > starts_at`; **só o esquema agora** |
| `quests`, `player_quests` | missões e progresso por jogador/sala | justificativa: o prompt exige "missões" (§5.9) mas não as lista em §6 |
| `activity_log` | `id`, `room_id`, `actor_id`, `action`, `target_type`, `target_id`, `data` jsonb, `created_at` | histórico de atividade do §5.1/5.2; índice `(room_id, created_at DESC)`; append-only |
| `idempotency_records` | `id`, `scope` (user/room), `key`, `request_hash`, `response_status`, `response_body`, `created_at` | `UNIQUE(scope, key)`; guarda a resposta da primeira execução para operações que não gravam `idempotency_key` na própria linha |

Rankings (patrimônio, saldo, valor do inventário, evolução) **não são tabelas-fonte**: são consultas (e, se pesarem, uma *materialized view* ou tabela `net_worth_snapshots` por sala/dia, decidida com medição; ver RISCOS).

## 4. Ledger financeiro

### 4.1 Forma
Partida dobrada simplificada: cada operação gera um **grupo** (`group_id`) de 2 ou mais linhas em `wallet_transactions` cuja soma de `amount` é **zero**. Todo dinheiro "criado" ou "destruído" passa pela carteira `system` global:

| Operação | Linhas (mesmo `group_id`) |
|---|---|
| Saldo inicial (no cadastro) | system `-S`, jogador `+S` |
| Recompensa diária / por anúncio (simulado) | system `-R`, jogador `+R` |
| Transferência A→B de X | A `-X`, B `+X` |
| Compra no mercado, preço P, taxa F | comprador `-P`, vendedor `+(P-F)`, system `+F` |
| Abrir caixa, preço C | jogador `-C`, system `+C` |
| Recompensa R | system `-R`, jogador `+R` |

**Invariante global (reconciliação):** `SUM(amount)` de **todo o ledger** = 0, e `wallets.balance = SUM(amount)` por carteira. Duas queries de auditoria rodam no CI e num comando periódico. Se qualquer uma falhar, há bug ou adulteração.

A carteira `system` pode ficar negativa (é a fonte do dinheiro); as de jogador, não (`CHECK balance >= 0`). **Oferta monetária do jogo** = `-system.balance`, métrica útil contra inflação (agora uma só, global).

### 4.2 Saldo: coluna em cache, não verdade
`wallets.balance` existe para leitura rápida e para o `CHECK >= 0`. É atualizado **somente** pela função de serviço, na mesma transação do lançamento, e conferido contra `SUM(amount)`. A verdade é o ledger. `balance_after` em cada linha permite achar o ponto exato de uma divergência.

### 4.3 Imutabilidade (defesa em profundidade)
1. O papel do banco usado pela aplicação **não tem `UPDATE` nem `DELETE`** em `wallet_transactions`, `market_transactions`, `case_openings`, `tradeup_history` (`REVOKE`).
2. Trigger `BEFORE UPDATE OR DELETE` que levanta exceção (cobre superusuário distraído e migração errada).
3. Correção de erro = **lançamento compensatório** (`kind='adjustment'`), nunca edição.
4. `TRUNCATE` revogado; backups testados (ver RISCOS).

### 4.4 Idempotência
Todo endpoint que move valor exige o header `Idempotency-Key` (UUID gerado pelo cliente por intenção do usuário). A chave é única por escopo; repetir a mesma chave devolve o resultado original; chave igual com corpo diferente → `422`. Detalhe em ARQUITETURA §5.

## 5. Índices para consultas frequentes (resumo)
| Consulta | Índice |
|---|---|
| "Minhas salas" / é membro? | `room_members(user_id, room_id)` |
| Vitrine do mercado | `market_listings(room_id, status, created_at DESC)` |
| Inventário filtrado | `skin_instances(room_id, owner_id)` + join `skins(weapon, rarity)` |
| Extrato | `wallet_transactions(wallet_id, created_at DESC, id)` (paginação por *keyset*, não OFFSET) |
| Ranking por patrimônio | agregação por sala; índice `skin_instances(room_id, owner_id) WHERE consumed_at IS NULL` |
| Convite por código | `room_invites(code_hash)` |

## 6. O que fica explicitamente fora do modelo agora
Stickers, StatTrak/Souvenir, padrões (pattern index), listas de preço externas em tempo real, ofertas diretas de troca 1:1 entre jogadores (o prompt fala em "negociações", mas só o marketplace está especificado: ver RISCOS, decisão D6).
