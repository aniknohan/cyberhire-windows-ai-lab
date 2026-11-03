import { toast } from "sonner";
import { ApiError } from "@/lib/api";

/** Shows an "Upgrade" toast for 402 (Pro-only / free limit reached). Returns true if handled. */
export function handleUpgradeError(e: unknown, go: (path: string) => void): boolean {
  if (e instanceof ApiError && e.status === 402) {
    const msg = String((e.body as { detail?: string })?.detail ?? "Upgrade to Pro to continue.");
    toast(msg, { action: { label: "See plans", onClick: () => go("/pricing") }, duration: 8000 });
    return true;
  }
  if (e instanceof ApiError && e.status === 429) {
    toast(String((e.body as { detail?: string })?.detail ?? "You've reached a usage limit. Please try again later."), { duration: 8000 });
    return true;
  }
  return false;
}
