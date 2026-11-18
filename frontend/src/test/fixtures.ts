/** Rotas e respostas do backend usadas pelos testes (formato observado na especificação do allauth). */

export const SESSION = "GET /_allauth/browser/v1/auth/session";
export const LOGOUT = "DELETE /_allauth/browser/v1/auth/session";
export const LOGIN = "POST /_allauth/browser/v1/auth/login";
export const SIGNUP = "POST /_allauth/browser/v1/auth/signup";
export const ME = "GET /api/v1/me/";
export const ME_PATCH = "PATCH /api/v1/me/";

export const SENHA = "Tr0ub4dor&3-horse-battery";

export const SESSION_AUTENTICADA = {
  status: 200,
  data: {
    user: {
      id: "u1",
      display: "ana_01",
      username: "ana_01",
      email: "ana@exemplo.com",
      has_usable_password: true,
    },
    methods: [],
  },
  meta: { is_authenticated: true },
};

/** O allauth responde 401 quando não há sessão (e também ao fazer logout). */
export const SESSION_ANONIMA = { status: 401, data: { flows: [] }, meta: { is_authenticated: false } };

export const ME_OK = {
  id: "u1",
  username: "ana_01",
  email: "ana@exemplo.com",
  avatar: "default",
};

export const ERRO_LOGIN = {
  status: 400,
  errors: [
    {
      message: "The username and/or password you specified are not correct.",
      code: "username_password_mismatch",
      param: "password",
    },
  ],
};

export const ERRO_USERNAME_EXISTE = {
  status: 400,
  errors: [
    {
      message: "Já existe um jogador com esse nome de usuário.",
      code: "unique",
      param: "username",
    },
  ],
};
