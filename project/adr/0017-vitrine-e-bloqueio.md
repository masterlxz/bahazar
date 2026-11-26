# 0017: Vitrine do mercado e bloqueio

**Data:** 2026-11-26

## Contexto
A vitrine (`GET /api/v1/listings/` e `/listings/<id>/`) é global: todo usuário logado vê todos os anúncios ativos. `SEGURANCA.md` diz "bloqueado não vê nada", regra pensada para inventário e trocas, onde há um dono e uma relação. Num mercado global a frase não diz o que fazer. O `friends` guarda o bloqueio com `requester` = quem bloqueou, e `blocked_by(user)` devolve só quem `user` bloqueou, "NUNCA quem bloqueou `user`", de propósito: o bloqueado não pode aprender que foi bloqueado.

## Decisão (dono, 2026-11-26)
1. **A vitrine esconde só na vista de quem bloqueou.** Quem bloqueou não vê os anúncios de quem bloqueou, na lista e no detalhe (404 igual ao de anúncio inexistente). O bloqueado vê a vitrine inteira, igual a antes do bloqueio.
2. **Compra (4.4): o bloqueado pode comprar** o anúncio de quem o bloqueou. Anúncio é oferta pública; bloquear é "não quero ver", não "não vendo". Nada é implementado agora; a 4.4 herda esta regra.
3. **Fronteira:** `marketplace/views.py` importa `apps.friends.selectors.blocked_by` e passa os ids ao selector (`hide_sellers`). `selectors.py`, `services.py`, `serializers.py` e `models.py` continuam sem importar `friends`. Mesma forma da exceção de `trades/views.py` com `economy`. `tests/marketplace/test_marketplace_arquitetura.py` impõe: só `views.py`, só `apps.friends.selectors`.

## Alternativas descartadas
- **Esconder nos dois sentidos** (cumpriria "bloqueado não vê nada" ao pé da letra): o bloqueado percebe o bloqueio comparando com uma segunda conta ou com a vitrine de um amigo, o que o `friends` evita de propósito.
- **Recusar só a compra do bloqueado (404 genérico):** o detalhe do mesmo anúncio responderia 200 para ele, então o 404 da compra já entregaria o bloqueio, a menos que a vitrine também escondesse (a opção acima).
- **Vitrine pública, sem efeito do bloqueio:** mais simples, mas o bloqueador seguiria vendo os anúncios de quem bloqueou, sem como evitar.
- **`marketplace` lendo `friendships` direto:** acopla o mercado ao modelo interno do `friends` e quebra "só o selector do `friends` é a porta".

## Consequências
- O bloqueio não vaza pela vitrine: um teste compara a vitrine do bloqueado antes e depois, e outro garante que o bloqueio no sentido inverso não esconde nada.
- Uma consulta a mais por leitura da vitrine (a lista de ocultos, sem cache) e um `NOT IN` com a lista dos bloqueados. Sem teto de bloqueios hoje: revisar se a lista crescer.
- **O que a API expõe, sem campo novo:** `seller.id`, `seller.username` (público no jogo), `instance.id`, `float_value`, a skin (`id`, nome, arma, raridade), preço e datas. O id da instância é visível a qualquer autenticado; "saber o id não dá poder" vale porque toda ação confere o dono.
- Fora do escopo e ainda aberto: teto de anúncios ativos por vendedor.
- **Custo de reverter:** baixo (um parâmetro no selector, uma função na view e um teste de fronteira).
