# 0010: Economia global por usuário; salas como grupos

**Data:** 2026-11-19

## Contexto
O desenho inicial (ADR 0003, 0004; MODELO §1.4) isolava **toda** a economia por sala: cada sala tinha carteira, inventário e mercado próprios, e a fronteira de segurança era "o usuário é membro da sala?". O dono mudou a direção do produto: o jogo é uma **economia única**, com saldo inicial, renda diária, amigos, troca de itens, inventário visível a amigos, caixas e batalha de caixa. Economia por sala não serve a isso (um jogador precisaria de um patrimônio por sala e de trocas entre salas).

## Decisão
1. **Carteira e inventário pertencem ao usuário**, não à sala. Existe **uma carteira `system` global** (fonte e sumidouro de moeda).
2. **Sala vira grupo/lobby**: um conjunto de usuários (membros, papéis, convite) sobre a economia global. O app `rooms` da PR 2.1 continua; o que muda é o que a sala guarda (sem `starting_balance` nem `market_fee_bps` por sala; sem economia própria).
3. **Amizade** (`friendships`: pedido, aceite, bloqueio) é a nova relação de confiança. Regras de visibilidade ("quem vê o inventário de quem") ficam em **uma permissão central reutilizável**, nunca espalhadas por views.
4. A fronteira de autorização passa de "membro da sala" para **"dono do dado, amigo do dono, ou membro do mesmo grupo"**, conforme o recurso.
5. Invariantes do ledger valem **globalmente**: `SUM(amount)` de todo o ledger = 0 e `wallets.balance` = soma do extrato de cada carteira.

## Alternativas descartadas
- **Manter economia por sala e acrescentar amigos:** contradiz o pedido (economia global); cada recurso teria duas dimensões (usuário e sala).
- **Apagar `rooms`:** joga fora a PR 2.1 (membros, papéis, 404 por não-membro) sem ganho; "grupo/lobby" é exatamente o que a batalha de caixa e as trocas em grupo vão precisar.
- **Economias por sala sincronizadas por uma camada global:** complexidade sem uso.

## Consequências
- **Substitui parcialmente** os ADR 0003 (escopo "por sala" do ledger) e 0004 (escopo "por sala" da autorização). Todo o resto deles vale: partida dobrada, `system`, append-only, negar por omissão, service revalida.
- A defesa em profundidade muda: some a FK composta `(room_id, user_id)` na carteira; entra FK simples ao dono, índices únicos parciais e **uma** função de visibilidade testada exaustivamente. O risco principal passa a ser "se esqueci de aplicar a regra de visibilidade" (o análogo do filtro esquecido).
- **Inflação (R5) fica mais perigosa:** uma economia única com renda diária e recompensas por anúncio não tem o amortecedor de salas pequenas. A D7 (parâmetros) vira pré-requisito de caixas.
- **Multi-conta para farmar (J4)** deixa de ser "fora do escopo privado": renda diária por conta é incentivo a criar contas.
- **Custo de reverter:** médio agora (só a PR 2.1 existe); alto depois de haver carteiras e inventários.
