import type { SessionResponse, SessionUser } from "../types/api";
import { ApiError, request } from "./http";

const BASE = "/_allauth/browser/v1";

/** O usuário da sessão, ou `null` se não há sessão (o allauth responde 401/410: não é erro). */
export async function getSession(): Promise<SessionUser | null> {
  try {
    const corpo = await request<SessionResponse>(`${BASE}/auth/session`);
    const { id, username, email } = corpo.data.user;
    return { id, username, email };
  } catch (erro) {
    if (erro instanceof ApiError && (erro.status === 401 || erro.status === 410)) return null;
    throw erro;
  }
}

/** Aceita nome de usuário ou e-mail: o allauth espera a chave certa para cada um. */
export async function login(identificador: string, password: string): Promise<void> {
  const credenciais = identificador.includes("@")
    ? { email: identificador, password }
    : { username: identificador, password };
  await request(`${BASE}/auth/login`, { method: "POST", body: credenciais });
}

export interface DadosCadastro {
  username: string;
  email: string;
  password: string;
}

export async function signup(dados: DadosCadastro): Promise<void> {
  await request(`${BASE}/auth/signup`, { method: "POST", body: dados });
}

/** O allauth responde 401 ao encerrar a sessão com sucesso (já não há sessão): isso é ok. */
export async function logout(): Promise<void> {
  try {
    await request(`${BASE}/auth/session`, { method: "DELETE" });
  } catch (erro) {
    if (erro instanceof ApiError && erro.status === 401) return;
    throw erro;
  }
}
