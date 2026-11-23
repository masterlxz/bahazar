/** Rotas e respostas do backend usadas pelos testes (formato observado na especificação do allauth). */

export const SESSION = "GET /_allauth/browser/v1/auth/session";
export const LOGOUT = "DELETE /_allauth/browser/v1/auth/session";
export const LOGIN = "POST /_allauth/browser/v1/auth/login";
export const SIGNUP = "POST /_allauth/browser/v1/auth/signup";
export const ME = "GET /api/v1/me/";
export const ME_PATCH = "PATCH /api/v1/me/";

export const WALLET = "GET /api/v1/wallet/";
export const DAILY = "POST /api/v1/wallet/daily/";

export const FRIENDS = "GET /api/v1/friends/";
export const REQUESTS = "GET /api/v1/friends/requests/";
export const SENT = "GET /api/v1/friends/requests/sent/";
export const BLOCKS = "GET /api/v1/blocks/";
export const SEND_REQUEST = "POST /api/v1/friends/requests/";
export const acceptRoute = (id: string) => `POST /api/v1/friends/requests/${id}/accept/`;
export const declineRoute = (id: string) => `POST /api/v1/friends/requests/${id}/decline/`;
export const removeRoute = (username: string) => `DELETE /api/v1/friends/${username}/`;
export const blockRoute = (username: string) => `POST /api/v1/friends/${username}/block/`;
export const unblockRoute = (username: string) => `DELETE /api/v1/friends/${username}/block/`;

/**
 * Formatos de apps/friends/serializers.py (lidos em 2026-11-23; fixados pelo backend em
 * tests/friends/test_friends_api.py e test_blocks_api.py): `FriendSerializer` = {username, avatar};
 * `FriendshipSerializer` = {id, requester, addressee, status, created_at} (usernames).
 */
export const CARLA = { username: "carla_03", avatar: "ember" };
export const EVA = { username: "eva_05", avatar: "default" };
export const PEDIDO_DO_BRUNO = {
  id: "r1",
  requester: "bruno_02",
  addressee: "ana_01",
  status: "pending",
  created_at: "2026-11-23T12:00:00Z",
};
export const PEDIDO_PARA_DIEGO = {
  id: "r2",
  requester: "ana_01",
  addressee: "diego_04",
  status: "pending",
  created_at: "2026-11-23T12:05:00Z",
};

/** Erros 409 do nosso DRF ao enviar pedido (apps/friends/services.py). */
export const ERRO_PEDIDO_INDISPONIVEL = {
  code: "friendship_unavailable",
  message: "Não foi possível enviar o pedido a este jogador.",
};
export const ERRO_JA_PENDENTE = {
  code: "already_pending",
  message: "Já existe um pedido pendente entre vocês.",
};
export const ERRO_JA_AMIGOS = { code: "already_friends", message: "Vocês já são amigos." };

export const SENHA = "Tr0ub4dor&3-horse-battery";

/**
 * Formato de `GET /api/v1/wallet/` (apps/economy/views.py, WalletView, lido em 2026-11-23;
 * fixado pelo backend em tests/economy/test_wallet_api.py). Valores em centavos de USD.
 */
export const WALLET_PODE_RESGATAR = {
  balance: 10_000,
  daily: { can_claim: true, available_at: null, next_streak_day: 1, next_amount: 1_000 },
};

export const WALLET_AGUARDANDO = {
  balance: 11_000,
  daily: {
    can_claim: false,
    available_at: "2026-11-24T12:00:00+00:00",
    next_streak_day: 2,
    next_amount: 2_000,
  },
};

/** Formato de `POST /api/v1/wallet/daily/` (DailyClaimView): 201 com o resgate feito. */
export const DAILY_RESGATADA = {
  amount: 1_000,
  streak_day: 1,
  balance: 11_000,
  next_available_at: "2026-11-24T12:00:00+00:00",
};

/** 409 de `DailyClaimView`: corpo no formato do nosso DRF (não o do allauth). */
export const ERRO_DIARIA_NAO_LIBERADA = {
  code: "daily_not_ready",
  message: "A diária ainda não está disponível.",
  available_at: "2026-11-24T12:00:00+00:00",
};

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

/**
 * Limite de falhas de login por conta, medido no backend real (2026-11-19): `400` com este
 * `code` e sem `param`. O texto de `message` não foi capturado; só o `code` é contrato.
 */
export const ERRO_LOGIN_MUITAS_TENTATIVAS = {
  status: 400,
  errors: [{ message: "Too many failed login attempts.", code: "too_many_login_attempts" }],
};

/** Limite geral por IP, medido no backend real (2026-11-19): `429` com corpo só `{ status: 429 }`. */
export const ERRO_LIMITE_GERAL = { status: 429 };

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
