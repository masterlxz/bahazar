import type { CreatedInvite, Room, RoomInvite, RoomMember } from "../types/api";
import { request } from "./http";

const base = "/api/v1/rooms/";
const daSala = (id: string) => `${base}${encodeURIComponent(id)}/`;

export function getRooms(): Promise<Room[]> {
  return request<Room[]>(base);
}

export function getRoom(id: string): Promise<Room> {
  return request<Room>(daSala(id));
}

export function getMembers(id: string): Promise<RoomMember[]> {
  return request<RoomMember[]>(`${daSala(id)}members/`);
}

export function createRoom(name: string): Promise<Room> {
  return request<Room>(base, { method: "POST", body: { name } });
}

export function renameRoom(id: string, name: string): Promise<Room> {
  return request<Room>(daSala(id), { method: "PATCH", body: { name } });
}

export function leaveRoom(id: string): Promise<void> {
  return request<void>(`${daSala(id)}leave/`, { method: "POST" });
}

export function getInvites(roomId: string): Promise<RoomInvite[]> {
  return request<RoomInvite[]>(`${daSala(roomId)}invites/`);
}

/** A resposta traz o `code`: guarde-o só em estado do componente, nunca em cache. */
export function createInvite(
  roomId: string,
  expiresInDays: number,
  maxUses: number,
): Promise<CreatedInvite> {
  return request<CreatedInvite>(`${daSala(roomId)}invites/`, {
    method: "POST",
    body: { expires_in_days: expiresInDays, max_uses: maxUses },
  });
}

export function revokeInvite(roomId: string, inviteId: string): Promise<void> {
  return request<void>(`${daSala(roomId)}invites/${encodeURIComponent(inviteId)}/`, {
    method: "DELETE",
  });
}

/** O código vai no CORPO, nunca na URL (histórico, logs de acesso e `Referer` guardam URLs). */
export function joinRoom(code: string): Promise<Room> {
  return request<Room>(`${base}join/`, { method: "POST", body: { code } });
}
