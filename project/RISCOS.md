# Riscos e decisões pendentes

## Decisões pendentes (suas)
| # | Decisão | Opções | Recomendação | Bloqueia |
|---|---|---|---|---|
| D1 | **Imagens das skins** (propriedade da Valve) | hotlink do CDN da Steam; placeholders próprios; pacote próprio | Já decidido por você: **pendente**. O modelo tem `image_url` + `image_source`. Decidir antes da etapa 3 | PR 3.1 |
| D2 | **Onde hospedar backend e Postgres** | Fly.io, Railway, Render, VPS próprio com Postgres gerenciado (Neon/RDS) | Escolher após a etapa 2; compare custo, backup, região (latência BR) e lock-in. **Não medi preços nem limites atuais** | Etapa 6 (staging na 2) |
| D3 | **Domínio e modelo de sessão** (2026-11-18: **adiada**; a PR 1.3 implementou sessão por cookie na mesma origem; sem domínio, cookie cross-site não funciona porque `vercel.app` está na lista pública de sufixos; opções vivas: proxy da Vercel + cookie, domínio próprio, JWT) | (a) frontend e API sob o mesmo domínio registrável + cookie de sessão; (b) domínios distintos + token JWT | (a): cookie HttpOnly + CSRF é mais seguro que token no navegador | PR 1.3 |
| D4 | **RLS do Postgres além da autorização no código** | não agora; ou desde já com `SET LOCAL` | Não agora; reavaliar antes de abrir ao público | - |
| D5 | **RNG verificável (commit-reveal)** | só snapshot+roll; ou commit-reveal | Snapshot+roll agora; commit-reveal se abrir ao público | PR 5.1 |
| D6 | **Negociação direta (oferta/troca 1:1)** além do marketplace | só marketplace; ou incluir trocas | Só marketplace na v1. O prompt cita "negociações" mas só especifica o mercado | Escopo |
| D7 | **Parâmetros econômicos**: saldo inicial padrão, taxa do mercado (sumidouro), fontes de dinheiro (recompensas, missões), preço base das caixas vs. valor esperado | a definir com números | Taxa de 5%-10% como sumidouro; **a taxa e o valor esperado das caixas decidem se a economia infla**. Proponho uma planilha de simulação antes da etapa 5 | Etapas 4-5 |
| D8 | **Versão do Django**: LTS (5.2) ou mais nova (6.1) | | LTS | PR 1.1 |
| D9 | **Nome** | | **Resolvida:** `bahazar` (2026-11-18) | - |
| D10 | **Repo no GitHub**: organização, visibilidade (privado) | `masterlxz` ou `Arven-Labs` | Privado, até decidir D1 | Ruleset e CI |

## Riscos técnicos
| # | Risco | Impacto | Mitigação |
|---|---|---|---|
| R1 | **Sem RLS**: um `.filter(room=...)` esquecido vaza dados entre salas | Alto | Manager escopado, permissão padrão negar, teste de IDOR parametrizado por endpoint, FKs compostas no banco |
| R2 | Condição de corrida em compra, saldo ou convite | Alto | Travas na ordem fixa, `CHECK`s, índices únicos parciais, testes de concorrência **contra Postgres real** (SQLite não serve: ele não reproduz o comportamento de `FOR UPDATE`) |
| R3 | Deadlock por ordem de lock inconsistente | Médio | Ordem fixa (anúncio → instância → carteiras por UUID) + retry limitado |
| R4 | Divergência entre `wallets.balance` e o ledger | Alto | Uma única função grava ambos; auditoria periódica; `balance_after` para achar o ponto |
| R5 | Economia desbalanceada (inflação por caixas/recompensas, "máquina de dinheiro" com trade-up) | Alto (produto) | Carteira `system` mede a oferta monetária; sumidouros (taxa); simular antes de lançar (D7) |
| R6 | RNG enviesado ou manipulável | Alto (confiança dos jogadores) | CSPRNG no servidor, snapshot, teste qui-quadrado |
| R7 | Tempo real via SSE + `LISTEN/NOTIFY` entre múltiplos processos | Médio | Protótipo medido na etapa 6; fallback: polling (já funciona) |
| R8 | Preço de referência desatualizado ou ausente no dado-fonte | Médio | `reference_price` é dado nosso, ajustável por import; não depender de API de preço em tempo real |
| R9 | Operar o próprio backend (deploy, patches, TLS, backup, e-mail) | Médio | PaaS gerenciado, backups com restauração testada, runbook na etapa 6; é o preço de não usar BaaS |
| R10 | Testes pesados só no CI (ADR 0009) tornam o ciclo mais lento | Baixo | PRs pequenos, CI rápido, só o leve local (ruff/tsc) |
| R11 | Rankings por patrimônio ficam caros com muitos itens | Baixo agora | Consulta com índice; medir antes de materializar (`net_worth_snapshots`) |

## Riscos jurídicos e de produto
| # | Risco | Mitigação |
|---|---|---|
| J1 | **Propriedade intelectual da Valve** (imagens, nomes, a marca Counter-Strike) | Nome do projeto neutro; D1 pendente; jogo privado; checar termos antes de qualquer abertura pública. **Não sou jurídico**: recomendo conferir os termos vigentes da Valve/Steam |
| J2 | Moeda virtual com **caixas pagas** pode lembrar jogos de azar | Sem dinheiro real e sem conversão (decisão do prompt). Reavaliar regulação (loot boxes) ao abrir ao público e se algum dia houver monetização |
| J3 | Dados pessoais (e-mail, nome de usuário) | Coletar o mínimo; política de privacidade antes de abrir ao público (LGPD); exclusão de conta |
| J4 | Abuso/multi-contas no modo público | Fora do escopo privado; moderação e antifraude na fase pública |

## O que **não** foi verificado nesta entrega
- Nenhum SQL, migration ou código foi executado; modelos e invariantes são desenho.
- Licença e versão de cada dependência (só versões do PyPI foram medidas) e avisos de segurança.
- Licença do dado de skins (ByMykel/CSGO-API) e termos de uso das imagens.
- Preços/limites de hospedagem.
- Que `LISTEN/NOTIFY` + SSE se comporte bem sob o servidor ASGI escolhido.
