/**
 * Tipos da API escritos à mão (ADR 0009 e 0012): só o que o frontend usa hoje.
 * Cada tipo é copiado do serializer ou da view lida (com a data da leitura), nunca de memória.
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

/**
 * Resposta de `GET /api/v1/wallet/` (apps/economy/views.py, `WalletView`, lido em 2026-11-23).
 * Todo valor é inteiro em centavos de USD; o cliente só formata (GUIDELINES 1 e 11).
 */
export interface Wallet {
  balance: number;
  daily: {
    can_claim: boolean;
    /** ISO 8601; `null` quando já pode resgatar. */
    available_at: string | null;
    next_streak_day: number;
    next_amount: number;
  };
}

/** Resposta (201) de `POST /api/v1/wallet/daily/` (`DailyClaimView`, lido em 2026-11-23). */
export interface DailyClaimResult {
  amount: number;
  streak_day: number;
  balance: number;
  next_available_at: string | null;
}

/**
 * Outro jogador, como o backend o mostra a quem pode vê-lo: `FriendSerializer`
 * (apps/friends/serializers.py, lido em 2026-11-23). Sem e-mail e sem id.
 */
export interface Friend {
  username: string;
  avatar: AvatarKey;
}

/** Um pedido de amizade: `FriendshipSerializer` (lido em 2026-11-23); os dois lados por username. */
export interface FriendRequest {
  id: string;
  requester: string;
  addressee: string;
  status: "pending" | "accepted" | "blocked";
  created_at: string;
}

export type RoomRole = "owner" | "admin" | "member";

/** Sala vista por um membro: `RoomSerializer` (apps/rooms/serializers.py, lido em 2026-11-23). */
export interface Room {
  id: string;
  name: string;
  visibility: "private" | "public";
  max_members: number;
  /** Papel de quem pergunta. */
  role: RoomRole;
  created_at: string;
}

/** Membro como os outros membros o veem: `MemberSerializer` (lido em 2026-11-23). */
export interface RoomMember {
  username: string;
  avatar: AvatarKey;
  role: RoomRole;
  joined_at: string;
}

/**
 * Convite de uma sala, como o administrador o vê: `InviteSerializer` (lido em 2026-11-23).
 * `status` é calculado pelo SERVIDOR (mesma regra do resgate); a tela só o mostra.
 */
export interface RoomInvite {
  id: string;
  expires_at: string;
  max_uses: number;
  uses: number;
  revoked_at: string | null;
  created_at: string;
  status: "ok" | "revoked" | "expired" | "exhausted";
}

/** Resposta (201) da criação: o único lugar em que o `code` aparece. */
export interface CreatedInvite extends RoomInvite {
  code: string;
}

/** A skin de um item: `SkinSummarySerializer` (apps/inventory/serializers.py, lido em 2026-11-24). */
export interface InventorySkin {
  id: string;
  name: string;
  weapon: string;
  rarity: string;
  /** Pode vir vazia. */
  collection: string;
}

/**
 * Um item do inventário: `InventoryItemSerializer` (lido em 2026-11-24). `float_value` vem como
 * TEXTO (decimal de 9 casas); `wear` é derivado pelo servidor; `reference_price` é inteiro em
 * centavos de USD. O cliente não calcula desgaste nem dinheiro (GUIDELINES 1 e 11).
 */
export interface InventoryItem {
  id: string;
  skin: InventorySkin;
  float_value: string;
  wear: string;
  reference_price: number;
  acquired_at: string;
}

/** Resposta paginada do DRF (`PageNumberPagination`, em apps/inventory/views.py). */
export interface Paginated<T> {
  count: number;
  next: string | null;
  previous: string | null;
  results: T[];
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

/** Skin do catálogo: `CatalogSkinSerializer` (apps/catalog/serializers.py, lido em 2026-11-24). */
export interface CatalogSkin {
  id: string;
  name: string;
  weapon: string;
  rarity: string;
  /** Pode vir vazia. */
  collection: string;
  /** URL da imagem; `null` se não há. */
  image_url: string | null;
  /** Fonte da imagem: "steam", "community", "none". */
  image_source: "steam" | "community" | "none";
}

/** Detalhe de uma skin do catálogo: `CatalogSkinDetailSerializer` (lido em 2026-11-24). */
export interface CatalogSkinDetail extends CatalogSkin {
  /** URLs de imagens em diferentes resoluções (se houver). */
  images: {
    small: string | null;
    medium: string | null;
    large: string | null;
  };
  /** Descrição da skin (Markdown). */
  description: string;
}

/** Facets do catálogo para filtros: `CatalogFacetsView` (lido em 2026-11-24). */
export interface CatalogFacets {
  rarities: string[];
  weapons: string[];
  collections: string[];
  wears: string[];
}

/** Parâmetros de query para o catálogo (apps/catalog/views.py, `CatalogSkinViewSet`). */
export interface CatalogQuery {
  rarity?: string;
  weapon?: string;
  collection?: string;
  wear?: string;
  q?: string;
  ordering?: string;
  page?: number;
}
