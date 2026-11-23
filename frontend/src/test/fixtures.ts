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

export const ROOMS = "GET /api/v1/rooms/";
export const CREATE_ROOM = "POST /api/v1/rooms/";
export const JOIN_ROOM = "POST /api/v1/rooms/join/";
export const roomRoute = (id: string) => `GET /api/v1/rooms/${id}/`;
export const renameRoute = (id: string) => `PATCH /api/v1/rooms/${id}/`;
export const leaveRoute = (id: string) => `POST /api/v1/rooms/${id}/leave/`;
export const membersRoute = (id: string) => `GET /api/v1/rooms/${id}/members/`;

/**
 * Formatos de apps/rooms/serializers.py (lidos em 2026-11-23; fixados pelo backend em
 * tests/rooms/test_rooms_api.py e test_members_api.py): `RoomSerializer` (com `role` de quem
 * pergunta) e `MemberSerializer` = {username, avatar, role, joined_at}.
 */
const sala = (id: string, name: string, role: string) => ({
  id,
  name,
  visibility: "private",
  max_members: 20,
  role,
  created_at: "2026-11-23T12:00:00Z",
});
export const SALA_DONO = sala("s1", "Amigos", "owner");
export const SALA_MEMBRO = sala("s2", "Time B", "member");
export const SALA_ADMIN = sala("s3", "Clube", "admin");
export const MEMBROS_DA_S1 = [
  { username: "ana_01", avatar: "default", role: "owner", joined_at: "2026-11-23T12:00:00Z" },
  { username: "bruno_02", avatar: "ember", role: "member", joined_at: "2026-11-23T12:30:00Z" },
];

/** Erros do nosso DRF em salas (apps/rooms/services.py). */
export const ERRO_LIMITE_DE_SALAS = {
  code: "room_limit_reached",
  message: "Você já é dono de 5 salas.",
};
export const ERRO_CONVITE: Record<string, { code: string; message: string }> = {
  invite_expired: { code: "invite_expired", message: "Este convite expirou." },
  invite_revoked: { code: "invite_revoked", message: "Este convite foi revogado." },
  invite_exhausted: {
    code: "invite_exhausted",
    message: "Este convite já foi usado o máximo de vezes.",
  },
  room_full: { code: "room_full", message: "A sala está cheia." },
  room_archived: { code: "room_archived", message: "A sala foi arquivada." },
};

export const invitesRoute = (id: string) => `GET /api/v1/rooms/${id}/invites/`;
export const createInviteRoute = (id: string) => `POST /api/v1/rooms/${id}/invites/`;
export const revokeInviteRoute = (id: string, inviteId: string) =>
  `DELETE /api/v1/rooms/${id}/invites/${inviteId}/`;

/**
 * Formatos de apps/rooms/serializers.py (`InviteSerializer`, lido em 2026-11-23; fixado pelo
 * backend em tests/rooms/test_invites_api.py e test_invites_status_api.py). O `code` só existe
 * na resposta de criação; `status` é calculado pelo servidor (ok, revoked, expired, exhausted).
 */
const convite = (id: string, status: string, uses: number, revoked: boolean) => ({
  id,
  expires_at: "2026-11-30T12:00:00Z",
  max_uses: 10,
  uses,
  revoked_at: revoked ? "2026-11-24T12:00:00Z" : null,
  created_at: "2026-11-23T12:00:00Z",
  status,
});
export const CONVITE_ATIVO = convite("i1", "ok", 3, false);
export const CONVITE_EXPIRADO = convite("i2", "expired", 1, false);
export const CONVITE_ESGOTADO = convite("i3", "exhausted", 10, false);
export const CONVITE_REVOGADO = convite("i4", "revoked", 0, true);
export const CODIGO_DO_CONVITE = "k3Jx9TqLw2ZrVbN5mQ7yAg";
export const CONVITE_NOVO = { ...convite("i9", "ok", 0, false), code: CODIGO_DO_CONVITE };

export const ERRO_LIMITE_DE_CONVITES = {
  code: "invite_limit_reached",
  message: "A sala já tem 10 convites ativos.",
};
export const ERRO_POLITICA_DO_CONVITE = {
  code: "invalid_invite_policy",
  message: "Use de 1 a 30 dias e de 1 a 50 usos.",
};

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
