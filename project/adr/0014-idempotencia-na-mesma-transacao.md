# 0014: Idempotência na mesma transação da operação

**Data:** 2026-11-25

## Contexto
`ARQUITETURA.md` §5 descrevia a idempotência com um estado "em andamento": inserir `idempotency_records` com `ON CONFLICT DO NOTHING`, e, se o registro existisse sem resposta, devolver `409 Retry-After`. A PR 4.1 implementou a idempotência e a primeira operação que move dinheiro entre dois jogadores (`economy.services.transfer`, só serviço interno, sem rota HTTP: decisão do dono de 2026-11-25, risco J4 de várias contas).

## Decisão
1. `economy.idempotency.run_once(scope, key, request_hash, operation)` insere o registro `(scope, key)` **na mesma transação da operação**, num savepoint; executa a operação; grava a resposta no registro; confirma tudo junto.
2. Chave já usada com o mesmo `request_hash`: devolve a resposta gravada **sem executar**. Com outro `request_hash`: `IdempotencyKeyReused`.
3. **Não existe o estado "em andamento" nem o `409`.** Um pedido simultâneo com a mesma chave espera, no `INSERT`, a primeira transação terminar (o PostgreSQL bloqueia a segunda inserção no índice único até o commit ou o rollback da primeira) e então falha por unicidade, de onde lê a resposta pronta. Se a primeira desfaz, a segunda insere e executa.
4. Operação que falha **desfaz o registro junto**: a chave não fica "queimada" (um retry depois de um erro, como saldo insuficiente, é avaliado de novo).
5. A chave é um **UUID** (`rules.normalize_idempotency_key`; forma canônica em minúsculas). O hash do pedido é o SHA-256 de uma lista JSON canônica (`rules.request_fingerprint`); na transferência entram operação, remetente, destinatário e valor.
6. O escopo na transferência é `user:<remetente>`. A chave do **ledger** leva o remetente no nome (`transfer:<remetente>:<chave>`): o `UNIQUE(wallet, idempotency_key)` olha só a carteira e a chave, e a chave vem do cliente, então duas pessoas com a mesma chave para o mesmo destinatário colidiriam.

## Alternativas descartadas
- **Estado "em andamento" com `409 Retry-After`** (o desenho original): exigiria gravar o registro numa transação própria antes da operação, e então uma falha da operação deixaria a chave queimada ou exigiria um segundo passo para limpá-la. A transação única resolve os dois casos com menos estados.
- **`bulk_create(ignore_conflicts=True)`:** não informa se inseriu; o savepoint com `IntegrityError` informa.
- **Transferência com rota HTTP agora:** descartada (J4); as trocas (4.2) e o mercado (4.3, 4.4) usam o serviço.
- **Chave de texto livre:** descartada; UUID fecha chave gigante e caracteres estranhos em log.

## Consequências
- Um pedido duplicado concorrente **espera** em vez de receber erro; o tempo de espera é o da operação (curta).
- O registro nunca existe sem a operação confirmada: não há limpeza de "órfãos".
- **Pendências:** expiração dos registros (hoje crescem sem fim); o header `Idempotency-Key` e o mapeamento para `422` entram com a primeira rota que usar `run_once` (4.2).
- **Custo de reverter:** baixo agora (uma tabela e um módulo, sem rota).
