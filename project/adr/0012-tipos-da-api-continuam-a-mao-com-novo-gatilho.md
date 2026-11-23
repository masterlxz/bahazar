# 0012: Tipos da API continuam escritos à mão, com novo gatilho

**Data:** 2026-11-23

## Contexto
O ADR 0009 adiou a geração de tipos a partir do OpenAPI para a Etapa 2 e deu o gatilho: "entrada do app `rooms`, ou o terceiro recurso próprio da API". O gatilho disparou: o backend tem hoje 14 rotas próprias (`me`, `health`, `wallet`, `friends`, `rooms` e convites), fora o login, o cadastro e a sessão, que são do django-allauth. A PR 2.5 começa as telas de carteira, amigos e grupos, então é a hora de decidir com dados atuais.

Medido no registro em 2026-11-23 (`npm view`, API JSON do PyPI), não de memória:

| Opção | Versão | Peer / suporte | Mantenedores | Última release | Dependências diretas | Licença |
|---|---|---|---|---|---|---|
| `openapi-typescript` | 7.13.0 | `typescript ^5.x` (o projeto usa 6.0.3) | 2 | 2026-06-15 | 6 | MIT |
| `@hey-api/openapi-ts` | 0.99.0 (pré-1.0) | `typescript >=5.5.3 \|\| >=6.0.0` | 1 | 2026-09-30 | 10 | MIT |
| `openapi-fetch` (cliente) | 0.17.0 | sem peer de TS | 3 | 2026-06-15 | 1 | MIT |
| `drf-spectacular` (lado Python) | 0.30.0 | classificadores listam Django 5.2 e 6.0 | n/m | 2026-07-06 | 6 (Django, DRF, `uritemplate`, `PyYAML`, `jsonschema`, `inflection`) | n/m |

"n/m" = não medi. `drf-spectacular` teve 2 releases em 2025-2026 (0.29.0 em 2025-11-02 e 0.30.0 em 2026-07-06); só a última cai nos 12 meses anteriores à medição. Não medi o suporte do allauth 65 a uma especificação consumível por esses geradores; o ADR 0009 já registrou que o allauth publica uma especificação separada, o que continua exigindo duas fontes.

## Decisão
Os tipos continuam em `frontend/src/types/api.ts`, escritos à mão, e o cliente continua sendo `frontend/src/services/http.ts`. Nenhuma dependência nova.

Para reduzir o risco de divergência que o ADR 0009 apontou, valem estas regras:
1. Todo tipo novo em `types/api.ts` é copiado do **serializer ou da view lida** no momento (e a data da leitura vai no comentário), nunca de memória.
2. As fixtures do frontend (`src/test/fixtures.ts`) usam exatamente os campos que os testes de API do backend fixam (`tests/*/test_*_api.py`).
3. `ApiError` passa a entender também o corpo de erro do nosso DRF (`{code, message}`), além do formato do allauth.

**Novo gatilho para reabrir** (o que ocorrer primeiro): (a) o backend passar de ~25 rotas próprias; (b) aparecer a **primeira divergência real** entre um tipo escrito à mão e a resposta do servidor (bug visto em tela ou em teste); (c) `openapi-typescript` publicar versão com peer compatível com o TypeScript do projeto, ou `@hey-api/openapi-ts` chegar à 1.0.

## Alternativas descartadas
- **`@hey-api/openapi-ts` + `drf-spectacular` agora:** são o gerador (10 dependências diretas) mais o `drf-spectacular` (6) para tipar ~14 rotas, e o gerador pré-1.0 com 1 mantenedor viraria dependência do build. O allauth ficaria de fora do mesmo jeito, então a divergência só mudaria de lugar.
- **`openapi-typescript` com `legacy-peer-deps`:** continua desligando a checagem de compatibilidade do projeto inteiro (mesma razão do ADR 0009); o peer `^5.x` não mudou entre as medições.
- **`openapi-fetch` como cliente:** só faria sentido junto de um gerador; o cliente próprio tem cerca de 100 linhas e cuida de CSRF, JSON e erros.

## Consequências
- Cada tela nova escreve seus tipos à mão; o custo cresce com as rotas, e o gatilho acima limita até onde.
- O risco de divergência continua, mitigado pelas regras 1 a 3 e pelos testes do backend que fixam os formatos.
- **Dado não medido:** compatibilidade real do `drf-spectacular` com o código atual (rodar o gerador exige instalar, o que esta decisão evitou) e o suporte do allauth. Se o gatilho disparar, medir de novo antes de adotar.
- **Custo de reverter:** baixo (trocar `types/api.ts` por arquivo gerado).
