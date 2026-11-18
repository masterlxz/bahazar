/**
 * Tipos da API escritos à mão (ADR 0009): só o que o frontend usa hoje.
 * Quando entrarem salas e carteiras (Etapa 2), isto passa a ser gerado do OpenAPI.
 */

export const AVATAR_KEYS = [
  "default",
  "ember",
  "glacier",
  "verdant",
  "violet",
  "amber",
  "slate",
  "crimson",
] as const;

export type AvatarKey = (typeof AVATAR_KEYS)[number];

/** Resposta de `GET /api/v1/me/`. */
export interface Me {
  id: string;
  username: string;
  email: string;
  avatar: AvatarKey;
}

/** O que o frontend guarda do usuário da sessão (o allauth devolve mais campos). */
export interface SessionUser {
  id: string;
  username: string;
  email: string;
}

/** Resposta de `GET /_allauth/browser/v1/auth/session` quando há sessão. */
export interface SessionResponse {
  data: { user: SessionUser };
}

/** Formato de erro do allauth headless: `param` indica o campo (ausente = erro geral). */
export interface AllauthError {
  message: string;
  code: string;
  param?: string;
}

export interface AllauthErrorBody {
  status: number;
  errors?: AllauthError[];
}
