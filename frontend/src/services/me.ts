import type { AvatarKey, Me } from "../types/api";
import { request } from "./http";

export function getMe(): Promise<Me> {
  return request<Me>("/api/v1/me/");
}

export function updateAvatar(avatar: AvatarKey): Promise<Me> {
  return request<Me>("/api/v1/me/", { method: "PATCH", body: { avatar } });
}
