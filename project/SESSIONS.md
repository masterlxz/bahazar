# Registro de sessões

Mais recente no topo.

### 2026-11-18 — Sessão 1 (arquitetura inicial)

- **Pedido**: abrir o projeto e entregar só a documentação de arquitetura do jogo (sem implementar).
- **Decisão do dono**: sem BaaS (Supabase fora); backend em Python + Django + DRF; docs no repo novo em `project/`; imagens de skins ficam como decisão pendente; nome `bazaar`.
- **Feito** (commit inicial direto na `main`, necessário para o guard existir antes do ruleset; ver `padrao/README.md`): docs (INDEX, OVERVIEW, ARQUITETURA, MODELO-DE-DADOS, SEGURANCA, PLANO, DEPENDENCIAS, RISCOS, PENDING, GUIDELINES), 7 ADRs, template de PR e guard do workspace.
- **CI**: ver resultado real do `guard` na `main` abaixo, na seção "Fica".
- **Não verificado**: nenhum SQL ou código executado; licenças/avisos de dependências; licença do dado de skins; preços de hospedagem.
- **Fica**: revisão do dono; decisões D1-D10 em `RISCOS.md`; ADRs propostos em `PENDING.md`; criar repo no GitHub e aplicar o ruleset na ordem de `padrao/README.md`.
