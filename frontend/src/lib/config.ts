import { useQuery } from "@tanstack/react-query";
import { apiGet } from "@/lib/api";
import type { BillingStatus, PublicConfig } from "@/lib/types";

/** Whether this is the paid website ("web") or the free desktop app ("desktop"), plus public prices. */
export function useConfig() {
  return useQuery({
    queryKey: ["config"],
    queryFn: () => apiGet<PublicConfig>("/config"),
    staleTime: Infinity,
    retry: 2,
  });
}

export function useBilling(enabled = true) {
  return useQuery({
    queryKey: ["billing"],
    queryFn: () => apiGet<BillingStatus>("/billing/status"),
    enabled,
    staleTime: 30_000,
  });
}

export function daysLeft(iso: string | null | undefined): string {
  if (!iso) return "";
  const hrs = Math.max(0, (new Date(iso).getTime() - Date.now()) / 36e5);
  return hrs >= 24 ? `${Math.ceil(hrs / 24)} days left` : `${Math.max(1, Math.ceil(hrs))} hours left`;
}
