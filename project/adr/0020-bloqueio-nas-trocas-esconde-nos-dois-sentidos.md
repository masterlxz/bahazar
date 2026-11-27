# 0020: Bloqueio nas trocas: esconde nos dois sentidos e cancela as pendentes

**Data:** 2026-11-27 (registra a decisão do dono da Sessão 45, PR #269; a doc de segurança é da Sessão 48)

## Contexto
`SEGURANCA.md` diz "bloqueado não vê nada". No mercado, o ADR 0017 já decidiu o contrário para uma
vitrine global: o bloqueio esconde só na vista de quem bloqueou, para o bloqueado não perceber. Uma
oferta de troca é outra coisa: tem dois donos (proponente e destinatário) e itens reservados. Antes
do PR #269, bloquear ou desfazer a amizade deixava a oferta pendente de pé: o bloqueado seguia
lendo-a, os itens ficavam presos no `offer_guard`, e o aceite falhava com `not_friends` sem
liberá-los.

## Decisão (dono, 2026-11-27)
1. **Nas trocas, o bloqueio esconde nos DOIS sentidos.** Lista, detalhe e as três ações
   (aceitar, recusar, cancelar) dão 404 para quem bloqueou e para quem foi bloqueado, em ofertas
   pendentes e resolvidas. Quem decide é `friends.selectors.pair_is_blocked`; `trades.selectors`
   a aplica em `_visiveis`.
2. **Bloquear ou desfazer a amizade cancela as ofertas pendentes do par** (nos dois sentidos) e
   solta os itens, na mesma transação. `friends` avisa por um gancho
   (`friends.hooks.notify_pair_ended`, chamado em `block` e `remove_friend` depois de gravar) e
   `trades` se registra em `AppConfig.ready()` (`cancel_pending_between`). `friends` não importa
   `trades`; `unblock` não restaura nada.
3. **Só o bloqueio esconde.** Um ex-amigo sem bloqueio continua lendo o histórico de ofertas do par:
   ele é a única trilha de posse (`acquired_via`/`acquired_ref_id` não registram a troca).
4. **Exceção consciente à regra do mercado:** o bloqueado percebe que foi bloqueado, porque as
   ofertas do par somem para ele.

## Alternativas descartadas
- **Esconder só na vista de quem bloqueou, como no mercado (ADR 0017):** o bloqueado seguiria
  lendo e agindo sobre ofertas do par, e cada oferta tem dois donos; a regra "bloqueado não vê
  nada" de `SEGURANCA.md` nasceu para inventário e trocas. (Motivo reconstruído pelo agente a
  partir do ADR 0017 e do código; o dono decidiu o efeito, não ditou esta justificativa.)
- **Não cancelar as pendentes (só esconder):** os itens ficariam presos para o mercado, e a
  oferta escondida não teria como ser resolvida pela interface. (Motivo reconstruído pelo agente,
  como o anterior; o problema dos itens presos é o do PENDING M1, resolvido no #269.)
- **Esconder também no fim da amizade sem bloqueio:** apagaria a única trilha de posse.
- **`friends` chamar `trades` direto:** cria ciclo (`trades` já importa `friends`) e quebra o teste
  de arquitetura que exige `friends` isolado; por isso o gancho.

## Consequências
- O bloqueado percebe o bloqueio comparando as ofertas antes e depois. É o custo aceito; no
  mercado o efeito é o oposto.
- **Dado antigo:** ofertas pendentes de pares já bloqueados ANTES do PR #269 ficam escondidas (404
  em tudo) e com os itens presos. O remédio é repetir `POST /friends/<u>/block/` (idempotente, avisa
  o gancho sempre). Não há remédio para um par que virou ex-amigo sem bloqueio: as pendentes seguem
  legíveis, o aceite dá `not_friends`, e recusar ou cancelar funciona por id. Sem migração de dados:
  não há produção (Etapa 6).
- Um gancho que levanta exceção desfaz o bloqueio inteiro: `cancel_pending_between` só consulta e
  grava linhas que acabou de travar.
- Throttle de 30/min (hipótese) em bloquear, desbloquear e remover amizade (Sessões 46 e 50),
  porque cada chamada trava também as ofertas do par.
- **Custo de reverter:** médio. Voltar ao "só quem bloqueou" muda `_visiveis` e os testes de
  `test_trades_bloqueio_esconde.py`; tirar o cancelamento exige tratar de novo os itens presos.
