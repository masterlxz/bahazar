# Riscos e decisões pendentes

## Decisões pendentes (suas)
| # | Decisão | Opções | Recomendação | Bloqueia |
|---|---|---|---|---|
| D1 | **Imagens das skins** (propriedade da Valve) | hotlink do CDN da Steam; placeholders próprios; pacote próprio | Já decidido por você: **pendente**. O modelo tem `image_url` + `image_source`. Decidir antes da etapa 3 | PR 3.1 |
| D2 | **Onde hospedar backend e Postgres** | Fly.io, Railway, Render, VPS próprio com Postgres gerenciado (Neon/RDS) | Escolher após a etapa 2; compare custo, backup, região (latência BR) e lock-in. **Não medi preços nem limites atuais** | Etapa 6 (staging na 2) |
| D3 | **Domínio e modelo de sessão** (2026-11-18: **adiada**; a PR 1.3 implementou sessão por cookie na mesma origem; sem domínio, cookie cross-site não funciona porque `vercel.app` está na lista pública de sufixos; opções vivas: proxy da Vercel + cookie, domínio próprio, JWT) | (a) frontend e API sob o mesmo domínio registrável + cookie de sessão; (b) domínios distintos + token JWT | (a): cookie HttpOnly + CSRF é mais seguro que token no navegador | PR 1.3 |
| D4 | **RLS do Postgres além da autorização no código** | não agora; ou desde já com `SET LOCAL` | Não agora; reavaliar antes de abrir ao público | - |
| D5 | **RNG verificável (commit-reveal)** | só snapshot+roll; ou commit-reveal | Snapshot+roll agora; commit-reveal se abrir ao público | PR 5.1 |
| D6 | **Negociação direta (oferta/troca 1:1)** além do marketplace | só marketplace; ou incluir trocas | **Resolvida (2026-11-19, ADR 0010):** trocas entre amigos **entram** no escopo (Etapa 4.2), junto de ver o inventário do amigo | - |
| D7 | **Parâmetros econômicos** (agora **globais**): saldo inicial, valor da diária, recompensa por anúncio, taxa do mercado e da troca (sumidouros), preço base das caixas vs. valor esperado | a definir com números | **Os valores da PR 2.2 são provisórios e declarados como tais.** A decisão de verdade sai de uma planilha de simulação (PR 4.0), antes de abrir caixas: renda diária e anúncio numa economia única inflam rápido | PR 4.0 (antes das caixas) |
| D11 | **Fonte de preços reais das skins (em USD)**: qual API ou dado, licença, limites, cobertura, itens sem preço | a medir; nenhuma foi verificada | Medir antes de prometer (PR 3.0). `reference_price` continua dado nosso, atualizável por import (R8) | Etapa 3 |
| D12 | **Anúncio real** para a "mendigagem" (SDK, receita, consentimento LGPD, dependência) | simulado (recompensa sem anúncio) ou rede real | Simulado até a Etapa 6; anúncio real traz receita e privacidade, que são outra decisão | Etapa 6 |
| D8 | **Versão do Django**: LTS (5.2) ou mais nova (6.1) | | **Resolvida:** LTS 5.2 (confirmada pelo dono em 2026-11-19; `requirements.txt` usa 5.2.19) | - |
| D9 | **Nome** | | **Resolvida:** `bahazar` (2026-11-18) | - |
| D10 | **Repo no GitHub**: organização, visibilidade (privado) | `masterlxz` ou `Arven-Labs` | Privado, até decidir D1 | Ruleset e CI |

## Riscos técnicos
| # | Risco | Impacto | Mitigação |
|---|---|---|---|
| R1 | **Sem RLS**: uma regra de visibilidade esquecida vaza carteira ou inventário a quem não é amigo (e, em grupos, um `.filter` esquecido vaza entre salas) | Alto | Selector escopado, permissão padrão negar, **uma** permissão central de visibilidade (dono, amigo, grupo), teste de IDOR parametrizado por endpoint |
| R2 | Condição de corrida em compra, saldo ou convite | Alto | Travas na ordem fixa, `CHECK`s, índices únicos parciais, testes de concorrência **contra Postgres real** (SQLite não serve: ele não reproduz o comportamento de `FOR UPDATE`) |
| R3 | Deadlock por ordem de lock inconsistente | Médio | Ordem fixa (anúncio → instância → carteiras por UUID) + retry limitado |
| R4 | Divergência entre `wallets.balance` e o ledger | Alto | Uma única função grava ambos; auditoria periódica; `balance_after` para achar o ponto |
| R5 | Economia desbalanceada (inflação por **diária, anúncio**, caixas/recompensas, "máquina de dinheiro" com trade-up ou batalha de caixa). **Mais grave agora**: a economia é única e global, sem o amortecedor de salas pequenas | Alto (produto) | Carteira `system` global mede a oferta monetária; sumidouros (taxa); valores provisórios declarados; simular **antes** das caixas (D7, PR 4.0) |
| R6 | RNG enviesado ou manipulável | Alto (confiança dos jogadores) | CSPRNG no servidor, snapshot, teste qui-quadrado |
| R7 | Tempo real via SSE + `LISTEN/NOTIFY` entre múltiplos processos | Médio | Protótipo medido na etapa 6; fallback: polling (já funciona) |
| R8 | Preço de referência desatualizado, ausente ou **sem fonte utilizável**. A premissa "preço real em USD" (ADR 0011) **não foi verificada** | Médio-alto | `reference_price` é dado nosso, ajustável por import; **medir a fonte** (licença, limites, cobertura) antes do catálogo (D11, PR 3.0); não depender de API em tempo real |
| R9 | Operar o próprio backend (deploy, patches, TLS, backup, e-mail) | Médio | PaaS gerenciado, backups com restauração testada, runbook na etapa 6; é o preço de não usar BaaS |
| R10 | Testes pesados só no CI (ADR 0009) tornam o ciclo mais lento | Baixo | PRs pequenos, CI rápido, só o leve local (ruff/tsc) |
| R11 | Rankings por patrimônio ficam caros com muitos itens | Baixo agora | Consulta com índice; medir antes de materializar (`net_worth_snapshots`) |

## Riscos jurídicos e de produto
| # | Risco | Mitigação |
|---|---|---|
| J1 | **Propriedade intelectual da Valve** (imagens, nomes, a marca Counter-Strike) | Nome do projeto neutro; D1 pendente; jogo privado; checar termos antes de qualquer abertura pública. **Não sou jurídico**: recomendo conferir os termos vigentes da Valve/Steam |
| J2 | Moeda virtual com **caixas pagas e batalha de caixa**, em preços reais, pode lembrar jogos de azar. "Moeda real" significa **escala de preços**, não dinheiro real (ADR 0011) | Sem dinheiro real, sem depósito, sem saque e sem conversão. **Se algum dia a moeda tocar dinheiro real**, é decisão separada com análise jurídica. Reavaliar regulação (loot boxes) ao abrir ao público e se houver monetização (inclusive anúncio real, D12). **Não sou jurídico** |
| J3 | Dados pessoais (e-mail, nome de usuário) | Coletar o mínimo; política de privacidade antes de abrir ao público (LGPD); exclusão de conta |
| J4 | Abuso/multi-contas: **renda diária por conta é incentivo a criar contas** (agora dentro do escopo, não só no modo público) | Hoje só o `UNIQUE(user, claim_number)` e a janela de 24h (por conta; sem fuso, nada a manipular). Aceito e registrado: e-mail verificado obrigatório (já planejado para o deploy), limite por IP/dispositivo e moderação ficam para depois |

## O que **não** foi verificado nesta entrega
- Nenhum SQL, migration ou código foi executado; modelos e invariantes são desenho.
- Licença e versão de cada dependência (só versões do PyPI foram medidas) e avisos de segurança.
- Licença do dado de skins (ByMykel/CSGO-API) e termos de uso das imagens.
- Preços/limites de hospedagem.
- Que `LISTEN/NOTIFY` + SSE se comporte bem sob o servidor ASGI escolhido.
