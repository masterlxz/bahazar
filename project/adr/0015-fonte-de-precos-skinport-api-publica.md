# 0015: Fonte de preços de referência — Skinport API pública

**Data:** 2026-11-25

## Contexto
A Etapa 3.0 (PR #102) definiu que o catálogo de skins (~100-200 itens) teria preços de referência em **centavos de USD** (ADR 0011: moeda virtual na escala de preços reais, não conversão). O comando `import_catalog` baixa o JSON da Skinport (`/v1/items?app_id=730&currency=USD`) e popula `skin_price` (preço sugerido, min/max/mean/median, quantidade, timestamps).

A decisão original (D11 em `PENDING.md`) era "Skinport por snapshot manual", medida em `MEDICAO-3.0-FONTE-DE-PRECOS.md` (cobre 99,94%). Faltava o dono ler os termos da Skinport antes de publicar.

## Decisão
1. **Fonte oficial:** `GET https://api.skinport.com/v1/items?app_id=730&currency=USD` (endpoint público, sem autenticação obrigatória).
2. **Rate limits respeitados:**
   - Global: 1.000 req/h por API key (ou por /24 de IP sem key).
   - `/items` + `/sales/history`: 8 req/5 min, cache 5 min server-side.
   - **Implementação:** 1 requisição a cada 5,5 min por combinação de parâmetros; `Accept-Encoding: br` obrigatório (senão 406); backoff exponencial em 429.
3. **API key própria:** criar em conta Skinport dedicada → configurar como `SKINPORT_CLIENT_ID` / `SKINPORT_CLIENT_SECRET` no ambiente → enviar no header `Authorization: Bearer <client_id>:<client_secret>` (Basic Auth) para ter limite próprio e não compartilhar IP de cloud.
4. **Atribuição visível:** toda exibição de preço vindo do Skinport mostra **"Preço de referência via Skinport"** com link para `https://skinport.com` (boa prática; não exigido explicitamente nos ToS).
5. **Uso restrito a preço de referência:** não há revenda, arbitragem, marketplace real nem conversão para dinheiro real (ADR 0011). O preço é **insumo da economia virtual** (diária, caixas, trade-ups, ranking).
6. **Snapshot histórico guardado:** tabela `skin_price` versiona preços por `updated_at` da API; não há garantia de precisão (ToS §9: responsabilidade limitada a dolo/culpa grave; não respondem pela usabilidade dos conteúdos).
7. **Comunicação com Skinport:** e-mail para `info@skinport.com` confirmando o uso ("preço de referência para economia virtual em jogo de navegador, moeda virtual sem dinheiro real, atribuição dada") → resposta arquivada.

## Alternativas descartadas
- **Steam Community Market API:** não oficial, instável, sem SLA, termos proíbem scraping automatizado.
- **CSFloat / Buff163 / outros:** mesmos problemas; Skinport tem API pública documentada, rate limits claros, empresa alemã registrada (GDPR).
- **Preços fixos/manuais:** não escala, viés humano, desatualização rápida.
- **Não guardar histórico:** perderíamos auditoria e capacidade de reverter/análise; custo de armazenamento é desprezível.

## Consequências
- **Positivas:** fonte única, documentada, rate limits claros, cache server-side reduz carga, atribuição transparente.
- **Riscos:** mudança unilateral de API/ToS (aviso 30 dias, lei alemã prevalece); banimento por abuso de rate limit (mitigado com key própria + backoff); preços `null` quando `quantity=0` (já tratado no import).
- **Pendências:**
  1. Criar conta/chave Skinport dedicada e configurar no deploy (variáveis de ambiente).
  2. Enviar e-mail para `info@skinport.com` e arquivar resposta.
  3. Implementar atribuição visual no frontend (catálogo, detalhe da skin, inventário).
  4. Revisar termos da Valve/Steam para uso de imagens/nomes de itens CS2 (D1, item separado).
- **Custo de reverter:** baixo (trocar endpoint + remover atribuição); tabela `skin_price` e comando `import_catalog` continuam válidos.

---

**Decisão tomada em:** Sessão individual, 2026-11-25, após leitura dos ToS, Privacy Policy, API docs, FAQ e Imprint do Skinport (via jina.ai cache, Cloudflare bloqueia acesso direto).