import type { DailyClaimResult, Wallet } from "../types/api";
import { request } from "./http";

export function getWallet(): Promise<Wallet> {
  return request<Wallet>("/api/v1/wallet/");
}

/** Sem corpo: o valor e a sequência são sempre do servidor. */
export function claimDaily(): Promise<DailyClaimResult> {
  return request<DailyClaimResult>("/api/v1/wallet/daily/", { method: "POST" });
}
