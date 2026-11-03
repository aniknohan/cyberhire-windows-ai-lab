// Google Play Billing, through the native "PlayBilling" plugin that ships inside the Android app
// (play-app/plugin/PlayBillingPlugin.java). Only available in the Play Store build.

export interface PlayProduct {
  available: boolean;
  productId: string;
  title?: string;
  price?: string; // the recurring price, localized by Google (e.g. "$19.99")
  billingPeriod?: string; // ISO 8601, e.g. "P1M"
  trialDays?: number; // >0 when this Google account is eligible for the free trial
}

export interface PlayPurchase {
  purchaseToken: string;
  productId: string;
  acknowledged?: boolean;
}

interface PlayBillingPlugin {
  getProduct(o: { productId: string }): Promise<PlayProduct>;
  subscribe(o: { productId: string; accountId: string }): Promise<PlayPurchase>;
  getPurchases(): Promise<{ purchases: PlayPurchase[] }>;
}

type Cap = { Plugins?: Record<string, unknown>; registerPlugin?: (n: string) => unknown; isNativePlatform?: () => boolean };

export function playBilling(): PlayBillingPlugin | null {
  const cap = (window as unknown as { Capacitor?: Cap }).Capacitor;
  if (!cap) return null;
  const p = (cap.Plugins?.PlayBilling ?? cap.registerPlugin?.("PlayBilling")) as PlayBillingPlugin | undefined;
  return p ?? null;
}

export const PLAY_PACKAGE = (import.meta.env.VITE_PLAY_PACKAGE as string | undefined) ?? "";

export function manageSubscriptionUrl(productId: string): string {
  const q = PLAY_PACKAGE ? `?sku=${encodeURIComponent(productId)}&package=${encodeURIComponent(PLAY_PACKAGE)}` : "";
  return `https://play.google.com/store/account/subscriptions${q}`;
}

/** "P1M" → "month", "P1Y" → "year", "P1W" → "week". */
export function periodWord(iso?: string): string {
  if (!iso) return "month";
  if (iso.endsWith("Y")) return "year";
  if (iso.endsWith("W")) return "week";
  return "month";
}
