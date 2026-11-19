import type { AllauthErrorBody } from "../types/api";

const CONFIG_URL = "/_allauth/browser/v1/config";

export class ApiError extends Error {
  readonly status: number;
  /** Mensagens do servidor por campo (`param` do allauth). */
  readonly fieldErrors: Record<string, string[]>;
  /** Mensagens do servidor que não se referem a um campo. */
  readonly nonFieldErrors: string[];
  /** `code` de cada erro do servidor (estável, ao contrário do texto de `message`). */
  readonly codes: string[];

  constructor(status: number, body: unknown) {
    super(`Erro ${status} da API`);
    this.name = "ApiError";
    this.status = status;
    this.fieldErrors = {};
    this.nonFieldErrors = [];
    this.codes = [];

    for (const erro of (body as AllauthErrorBody | null)?.errors ?? []) {
      this.codes.push(erro.code);
      if (erro.param) {
        (this.fieldErrors[erro.param] ??= []).push(erro.message);
      } else {
        this.nonFieldErrors.push(erro.message);
      }
    }
  }
}

export interface RequestOptions {
  method?: "GET" | "POST" | "PATCH" | "DELETE";
  body?: unknown;
}

function lerTokenCsrf(): string | null {
  const achado = document.cookie.match(/(?:^|;\s*)csrftoken=([^;]*)/);
  return achado?.[1] ? decodeURIComponent(achado[1]) : null;
}

/**
 * O cookie `csrftoken` só existe depois que o servidor o define. Se ainda não existe, uma ida ao
 * endpoint de configuração do allauth faz o servidor emitir o cookie.
 */
async function obterTokenCsrf(): Promise<string> {
  const existente = lerTokenCsrf();
  if (existente) return existente;

  await fetch(CONFIG_URL, { credentials: "same-origin", headers: { Accept: "application/json" } });

  const novo = lerTokenCsrf();
  if (!novo) throw new Error("Não foi possível obter o token CSRF do servidor.");
  return novo;
}

async function lerJson(resposta: Response): Promise<unknown> {
  const texto = await resposta.text();
  if (!texto) return null;
  try {
    return JSON.parse(texto);
  } catch {
    return null; // corpo que não é JSON (ex.: página de erro 500)
  }
}

/**
 * Chamada à API do próprio site (mesma origem; em dev, o proxy do Vite).
 * Requisições que mudam estado levam `X-CSRFToken`; erros HTTP viram `ApiError`.
 */
export async function request<T = unknown>(
  caminho: string,
  { method = "GET", body }: RequestOptions = {},
): Promise<T> {
  const headers: Record<string, string> = { Accept: "application/json" };
  if (body !== undefined) headers["Content-Type"] = "application/json";
  if (method !== "GET") headers["X-CSRFToken"] = await obterTokenCsrf();

  const resposta = await fetch(caminho, {
    method,
    headers,
    credentials: "same-origin",
    body: body === undefined ? undefined : JSON.stringify(body),
  });

  const dados = await lerJson(resposta);
  if (!resposta.ok) throw new ApiError(resposta.status, dados);
  return dados as T;
}
