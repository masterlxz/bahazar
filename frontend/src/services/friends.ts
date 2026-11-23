import type { Friend, FriendRequest } from "../types/api";
import { request } from "./http";

const base = "/api/v1/friends/";
const doJogador = (username: string) => `${base}${encodeURIComponent(username)}/`;

export function getFriends(): Promise<Friend[]> {
  return request<Friend[]>(base);
}

export function getReceivedRequests(): Promise<FriendRequest[]> {
  return request<FriendRequest[]>(`${base}requests/`);
}

export function getSentRequests(): Promise<FriendRequest[]> {
  return request<FriendRequest[]>(`${base}requests/sent/`);
}

/** Quem eu bloqueei (rota própria, fora de /friends/: ver apps/friends/urls.py). */
export function getBlocked(): Promise<Friend[]> {
  return request<Friend[]>("/api/v1/blocks/");
}

export function sendRequest(username: string): Promise<FriendRequest> {
  return request<FriendRequest>(`${base}requests/`, { method: "POST", body: { username } });
}

export function acceptRequest(id: string): Promise<FriendRequest> {
  return request<FriendRequest>(`${base}requests/${encodeURIComponent(id)}/accept/`, {
    method: "POST",
  });
}

export function declineRequest(id: string): Promise<void> {
  return request<void>(`${base}requests/${encodeURIComponent(id)}/decline/`, { method: "POST" });
}

export function removeFriend(username: string): Promise<void> {
  return request<void>(doJogador(username), { method: "DELETE" });
}

export function blockUser(username: string): Promise<void> {
  return request<void>(`${doJogador(username)}block/`, { method: "POST" });
}

export function unblockUser(username: string): Promise<void> {
  return request<void>(`${doJogador(username)}block/`, { method: "DELETE" });
}
