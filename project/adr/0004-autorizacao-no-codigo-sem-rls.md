# 0004: Autorização no código, sem RLS do Postgres por ora

**Data:** 2026-11-18

## Contexto
Sem Supabase, não há RLS automático. O principal risco passa a ser um filtro por sala esquecido numa view, vazando dados entre economias.

## Decisão
Autorização em camadas: permissão DRF padrão negar (`IsAuthenticated` + `IsRoomMember`/`IsRoomAdmin`), manager/selector escopado por sala (proibido `objects.all()` em view), revalidação dentro do service, FKs compostas `(room_id, user_id)` e CHECKs no banco, e usuário do banco sem dono do esquema e sem UPDATE/DELETE nas tabelas append-only. Teste parametrizado: todo endpoint com usuário de outra sala responde 404.

## Alternativas descartadas
- **RLS do Postgres com `SET LOCAL app.user_id` por requisição:** defesa real contra o filtro esquecido, mas aumenta a complexidade, atrapalha pool de conexões em modo transação e exige disciplina nas migrations. Reavaliar antes de abrir ao público.

## Consequências
- A segurança depende de convenção e de testes; um endpoint novo sem teste de acesso cruzado é o ponto fraco. O CI deve falhar se existir view sem permissão explícita.
- **Custo de reverter (adotar RLS depois):** médio.
