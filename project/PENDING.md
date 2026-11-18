# Pendências

Critério: só entra o que está **em aberto** e depende de decisão ou ação. Decisões de produto e infraestrutura: ver `RISCOS.md` (D1-D10).

## Aguardando o dono
- [ ] Aprovar (ou pedir mudanças em) a arquitetura desta entrega.
- [ ] Responder D2, D3, D7, D8 (bloqueiam a etapa 1 e 4).
- [ ] Confirmar o nome `bazaar` (D9) e onde criar o repo no GitHub (D10).

## ADRs gravados em `project/adr/` (2026-11-18, status: propostos até a aprovação da arquitetura)
0001 Django + DRF no lugar de Supabase · 0002 Regras econômicas em services · 0003 Ledger de partida dobrada · 0004 Autorização no código (sem RLS) · 0005 Polling primeiro, SSE depois · 0006 Monólito modular · 0007 Dinheiro em centavos.

## Verificações pendentes (antes da etapa 1)
- Licença do repo-fonte do catálogo de skins e termos das imagens.
- Licenças, datas de release e avisos de segurança das dependências (pré-triagem em DEPENDENCIAS).
- Criar modelo de CI para Python em `padrao/workflows/` do workspace (hoje só há Rust).
