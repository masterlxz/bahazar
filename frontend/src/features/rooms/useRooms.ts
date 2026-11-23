import { useQuery } from "@tanstack/react-query";

import { getInvites, getMembers, getRoom, getRooms } from "../../services/rooms";
import type { RoomRole } from "../../types/api";

// Chaves hierárquicas: um único `removeQueries(ROOMS_ROOT_KEY)` no logout apaga todas.
export const ROOMS_ROOT_KEY = ["rooms"] as const;
export const ROOMS_LIST_KEY = ["rooms", "list"] as const;
export const roomKey = (id: string) => ["rooms", "detail", id] as const;
export const membersKey = (id: string) => ["rooms", "members", id] as const;
export const invitesKey = (id: string) => ["rooms", "invites", id] as const;

export const PAPEL: Record<RoomRole, string> = {
  owner: "Dono",
  admin: "Administrador",
  member: "Membro",
};

/** Só dono e administrador renomeiam (a regra de verdade está no backend; isto só esconde o botão). */
export const podeGerenciar = (papel: RoomRole) => papel === "owner" || papel === "admin";

export function useRooms() {
  return useQuery({ queryKey: ROOMS_LIST_KEY, queryFn: getRooms });
}

export function useRoom(id: string) {
  return useQuery({ queryKey: roomKey(id), queryFn: () => getRoom(id) });
}

/** Convites da sala (sem o código). Só dono e administrador: quem chama decide se monta isto. */
export function useInvites(id: string) {
  return useQuery({ queryKey: invitesKey(id), queryFn: () => getInvites(id) });
}

export function useMembers(id: string) {
  return useQuery({ queryKey: membersKey(id), queryFn: () => getMembers(id) });
}
