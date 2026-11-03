import { useEffect, useRef, useState } from "react";
import { Link, useSearchParams } from "react-router-dom";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { Check, CheckCircle2, Clock, CreditCard, ExternalLink, Loader2, RotateCcw, ShieldCheck, XCircle } from "lucide-react";
import { toast } from "sonner";
import { ApiError, IS_NATIVE, WEB_ORIGIN, apiGet, apiPost } from "@/lib/api";
import { daysLeft, useBilling, useConfig } from "@/lib/config";
import { useMe } from "@/lib/auth";
import { manageSubscriptionUrl, periodWord, playBilling, type PlayProduct } from "@/lib/playBilling";
import type { BillingStatus, CheckoutOut, PaymentStatusOut, PortalOut } from "@/lib/types";
import AppShell, { PageHeader } from "@/components/AppShell";
import { Eyebrow, Panel } from "@/components/common";
import { Button, buttonVariants } from "@/components/ui/button";
import { cn } from "@/lib/utils";

export const PRO_FEATURES = [
  "Live voice interviews: recruiter, technical, SOC investigation and hiring manager rounds",
  "Hiring decision, scores and a full report after every interview",
  "Coach mode, weakness drills and 6 practice modules",
  "Resume upload: interviewers ask about your real experience",
  "638-question SOC bank: Splunk, Wireshark, Nmap, Active Directory, Python",
];
type Interval = "month" | "year";

export const PLANS: { interval: Interval; title: string; price: string; unit: string; note: string; badge?: string }[] = [
  { interval: "month", title: "Pro Monthly", price: "$19.99", unit: "/ month", note: "Billed monthly. Cancel anytime." },
  { interval: "year", title: "Pro Yearly", price: "$159", unit: "/ year", note: "Just $13.25 a month, billed yearly. Cancel anytime.", badge: "Save 34%" },
];

function detail(e: unknown, fallback: string): string {
  return e instanceof ApiError ? String((e.body as { detail?: string })?.detail ?? fallback) : fallback;
}

export function useManageBilling() {
  return useMutation({
    mutationFn: () => apiPost<PortalOut>("/billing/portal"),
    onSuccess: (r) => {
      window.location.href = r.url;
    },
    onError: (e) => toast.error(detail(e, "Couldn't open the billing page.")),
  });
}

export function SubscriptionSummary({ b }: { b: BillingStatus }) {
  const manage = useManageBilling();
  if (b.mode !== "web") return null;
  const date = (iso: string | null) => (iso ? new Date(iso).toLocaleDateString([], { dateStyle: "medium" }) : "");
  return (
    <div className="space-y-3 text-sm" data-testid="subscription-summary">
      {b.on_trial ? (
        <div className="flex items-start gap-2 text-amber-100">
          <Clock className="mt-0.5 size-4 shrink-0 text-amber-300" />
          <span>
            Free trial: <b>{daysLeft(b.trial_until)}</b>.{" "}
            {b.cancel_at_period_end
              ? `It ends on ${date(b.trial_until)} and you won't be charged.`
              : `Your ${b.interval === "year" ? "yearly" : "monthly"} plan starts on ${date(b.trial_until)}.`}
          </span>
        </div>
      ) : b.is_pro ? (
        <div className="flex items-start gap-2 text-emerald-200">
          <CheckCircle2 className="mt-0.5 size-4 shrink-0 text-emerald-400" />
          <span>
            CyberHire Pro ({b.interval === "year" ? "yearly" : "monthly"}) · {b.cancel_at_period_end ? "ends" : "renews"} on {date(b.pro_until)}
            {b.provider === "google_play" ? " · billed by Google Play" : ""}
          </span>
        </div>
      ) : (
        <div className="text-slate-400">No active plan.</div>
      )}
      {b.interviews_limit != null && b.is_pro && (
        <div className="text-xs text-slate-500" data-testid="usage-line">
          {b.interviews_used} of {b.interviews_limit} interviews used {b.on_trial ? "in your trial" : "in the last 30 days"}
        </div>
      )}
      {b.provider === "stripe" && !IS_NATIVE && (
        <Button variant="secondary" size="sm" onClick={() => manage.mutate()} disabled={manage.isPending} data-testid="manage-billing-button">
          {manage.isPending ? <Loader2 className="animate-spin" /> : <ExternalLink />} Manage billing, card or cancel
        </Button>
      )}
      {b.provider === "stripe" && IS_NATIVE && <p className="text-xs text-slate-400">This plan was bought on the CyberHire website. Manage it there.</p>}
      {b.provider === "google_play" && (
        <div className="space-y-2">
          {IS_NATIVE && (
            <a href={manageSubscriptionUrl(b.play_product_id || "cyberhire_pro")} className={buttonVariants({ variant: "secondary", size: "sm" })} data-testid="manage-play-button">
              <ExternalLink /> Manage or cancel in Google Play
            </a>
          )}
          <p className="text-xs text-slate-400">Billed by Google Play. You can also manage it in the Play Store app → Payments &amp; subscriptions → Subscriptions.</p>
        </div>
      )}
    </div>
  );
}

export function PlanCards({ b, onChoose, busyInterval, ctaFor }: {
  b?: BillingStatus;
  onChoose: (i: Interval) => void;
  busyInterval?: Interval | null;
  ctaFor?: (i: Interval) => string;
}) {
  const trial = b ? b.trial_available : true;
  return (
    <div className="grid max-w-4xl gap-6 md:grid-cols-2">
      {PLANS.map((p) => (
        <Panel
          key={p.interval}
          className={cn("relative space-y-4", p.interval === "year" && "border-sky-500/30 bg-gradient-to-b from-[#0F1A30] to-[#0E1524]")}
          data-testid={`plan-${p.interval}`}
        >
          <div className="flex items-center justify-between">
            <Eyebrow className={p.interval === "year" ? "text-sky-400/80" : undefined}>{p.title}</Eyebrow>
            {p.badge && <span className="rounded-full bg-emerald-400/10 px-2 py-0.5 font-mono text-[10px] tracking-wider text-emerald-300">{p.badge}</span>}
          </div>
          <div className="font-heading text-4xl font-semibold text-white" data-testid={`plan-${p.interval}-price`}>
            {p.price}<span className="text-base font-normal text-slate-400"> {p.unit}</span>
          </div>
          {trial && <div className="text-sm text-sky-300">First {b?.trial_days ?? 3} days free</div>}
          <ul className="space-y-2 text-sm text-slate-200">
            {PRO_FEATURES.map((f) => <li key={f} className="flex gap-2"><Check className="mt-0.5 size-4 shrink-0 text-sky-400" />{f}</li>)}
          </ul>
          <div className="space-y-2">
            <Button size="lg" className="h-11 w-full" onClick={() => onChoose(p.interval)} disabled={!!busyInterval} data-testid={`checkout-stripe-${p.interval}-button`}>
              {busyInterval === p.interval ? <Loader2 className="animate-spin" /> : <CreditCard />}
              {ctaFor ? ctaFor(p.interval) : trial ? `Start ${b?.trial_days ?? 3}-day free trial` : "Subscribe"}
            </Button>
            <p className="text-[11px] leading-relaxed text-slate-500">
              {trial
                ? `No charge today. Then ${p.price} ${p.unit.replace("/ ", "per ")} unless you cancel before the trial ends. ${p.note.split(".").slice(1).join(".").trim()}`
                : p.note}
            </p>
          </div>
        </Panel>
      ))}
    </div>
  );
}

function playErr(e: unknown): string {
  const m = (e as { message?: string; code?: string })?.message || "";
  if (/cancel/i.test(m) || (e as { code?: string })?.code === "USER_CANCELED") return "";
  if (e instanceof ApiError) return detail(e, "Couldn't confirm the purchase.");
  return m || "Google Play couldn't complete the purchase. Please try again.";
}

/** Android (Play Store) app: subscribe with Google Play. No web checkout links here, as Play policy requires. */
function NativePricing() {
  const qc = useQueryClient();
  const [params] = useSearchParams();
  const { data: me } = useMe();
  const { data: b } = useBilling();
  const plugin = playBilling();
  const productId = b?.play_product_id || "cyberhire_pro";
  const [product, setProduct] = useState<PlayProduct | null>(null);
  const [busy, setBusy] = useState<"" | "buy" | "restore">("");
  const restored = useRef(false);

  const verify = async (token: string) => {
    await apiPost("/billing/google-play/verify", { purchase_token: token, product_id: productId });
    const fresh = await apiGet<BillingStatus>("/billing/status");
    qc.setQueryData(["billing"], fresh);
    return fresh;
  };
  const restore = async (quiet: boolean) => {
    if (!plugin) return;
    if (!quiet) setBusy("restore");
    try {
      const { purchases } = await plugin.getPurchases();
      let ok = false;
      for (const p of purchases) {
        try {
          if ((await verify(p.purchaseToken)).has_access) ok = true;
        } catch (e) {
          if (!quiet) toast.error(playErr(e) || "Couldn't restore this purchase.");
        }
      }
      if (!quiet) (ok ? toast.success("Subscription restored.") : !purchases.length && toast("No Google Play subscription found on this Google account."));
    } catch (e) {
      if (!quiet) toast.error(playErr(e) || "Couldn't reach Google Play.");
    } finally {
      setBusy("");
    }
  };

  useEffect(() => {
    if (!plugin) return;
    plugin.getProduct({ productId }).then(setProduct).catch(() => setProduct({ available: false, productId }));
    if (!restored.current && b && !b.has_access) {
      restored.current = true;
      void restore(true); // reinstall / new phone: pick up an existing subscription silently
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [plugin, productId, b?.has_access]);

  const buy = async () => {
    if (!plugin || !me) return;
    setBusy("buy");
    try {
      const p = await plugin.subscribe({ productId, accountId: me.id });
      const fresh = await verify(p.purchaseToken);
      if (fresh.has_access) toast.success(fresh.on_trial ? "Your free trial has started." : "Welcome to CyberHire Pro!");
    } catch (e) {
      const m = playErr(e);
      if (m) toast.error(m);
    } finally {
      setBusy("");
    }
  };

  const trialDays = product?.trialDays ?? 0;
  const price = product?.price ?? "$19.99";
  const unit = periodWord(product?.billingPeriod);
  const welcome = params.get("welcome") === "1";
  return (
    <AppShell>
      <PageHeader
        eyebrow={welcome ? "Welcome to CyberHire" : "CyberHire Pro"}
        title={b?.is_pro ? "Your plan" : trialDays ? `Try CyberHire Pro free for ${trialDays} days` : "Subscribe to CyberHire Pro"}
        desc={b?.is_pro ? "Thanks for practising with CyberHire." : trialDays ? `Then ${price} per ${unit}. Cancel anytime in Google Play before the trial ends and you won't be charged.` : `${price} per ${unit}, billed by Google Play. Cancel anytime.`}
      />
      {b?.is_pro ? (
        <Panel className="max-w-2xl" data-testid="pro-active"><SubscriptionSummary b={b} /></Panel>
      ) : (
        <Panel className="max-w-xl space-y-4 border-sky-500/30" data-testid="play-plan">
          <div className="flex items-center justify-between">
            <Eyebrow className="text-sky-400/80">Pro Monthly</Eyebrow>
            {trialDays > 0 && <span className="rounded-full bg-emerald-400/10 px-2 py-0.5 font-mono text-[10px] tracking-wider text-emerald-300">{trialDays} DAYS FREE</span>}
          </div>
          <div className="font-heading text-4xl font-semibold text-white">{price}<span className="text-base font-normal text-slate-400"> / {unit}</span></div>
          <ul className="space-y-2 text-sm text-slate-200">
            {PRO_FEATURES.map((f) => <li key={f} className="flex gap-2"><Check className="mt-0.5 size-4 shrink-0 text-sky-400" />{f}</li>)}
          </ul>
          {!plugin || product?.available === false ? (
            <p className="text-sm text-amber-200" data-testid="play-unavailable">Subscriptions aren't available right now. Make sure the app was installed from Google Play and you're signed in to the Play Store, then try again.</p>
          ) : (
            <Button size="lg" className="h-12 w-full text-base" onClick={buy} disabled={!!busy || !product} data-testid="play-subscribe-button">
              {busy === "buy" || !product ? <Loader2 className="animate-spin" /> : null}
              {trialDays ? `Start ${trialDays}-day free trial` : "Subscribe"}
            </Button>
          )}
          <p className="text-[11px] leading-relaxed text-slate-500">
            {trialDays ? `No charge today. After ${trialDays} days, ${price} per ${unit} is charged to your Google Play payment method and renews automatically until you cancel. ` : `${price} per ${unit}, renewing automatically until you cancel. `}
            Cancel anytime in Google Play → Payments &amp; subscriptions. See the <Link to="/terms" className="text-sky-400">Terms</Link> and <Link to="/privacy" className="text-sky-400">Privacy policy</Link>.
          </p>
          <Button variant="ghost" size="sm" onClick={() => restore(false)} disabled={!!busy || !plugin} data-testid="play-restore-button">
            {busy === "restore" ? <Loader2 className="animate-spin" /> : <RotateCcw />} Restore purchase
          </Button>
        </Panel>
      )}
    </AppShell>
  );
}

export default function Pricing() {
  return IS_NATIVE ? <NativePricing /> : <WebPricing />;
}

function WebPricing() {
  const qc = useQueryClient();
  const [params] = useSearchParams();
  const { data: b } = useBilling();
  const { data: cfg } = useConfig();
  const checkout = useMutation({
    mutationFn: (interval: Interval) =>
      apiPost<CheckoutOut>("/billing/stripe/checkout", { origin_url: IS_NATIVE ? WEB_ORIGIN : window.location.origin, interval }),
    onSuccess: (r) => {
      window.location.href = r.checkout_url;
    },
    onError: (e) => {
      toast.error(detail(e, "Checkout failed. Please try again."));
      qc.invalidateQueries({ queryKey: ["billing"] });
    },
  });
  useEffect(() => {
    if (params.get("checkout") === "cancelled") toast("Checkout cancelled. No charge was made.");
  }, [params]);

  const welcome = params.get("welcome") === "1";
  if (cfg && !cfg.web_checkout && b && !b.is_pro) {
    // Website without card payments set up: subscriptions are sold in the Android app (Google Play).
    return (
      <AppShell>
        <PageHeader eyebrow={welcome ? "Welcome to CyberHire" : "Plans"} title="Get CyberHire Pro on Android" desc="Subscribe in the CyberHire app on Google Play: 3 days free, then $19.99 a month. Then sign in here with the same account to practise on your computer too." />
        <Panel className="max-w-xl space-y-4" data-testid="get-on-play">
          <ul className="space-y-2 text-sm text-slate-200">{PRO_FEATURES.map((f) => <li key={f} className="flex gap-2"><Check className="mt-0.5 size-4 shrink-0 text-sky-400" />{f}</li>)}</ul>
          {cfg.play_store_url ? (
            <a href={cfg.play_store_url} className={cn(buttonVariants({ size: "lg" }), "h-11 w-full")} data-testid="play-store-link">Get it on Google Play</a>
          ) : (
            <p className="text-sm text-slate-400">The Android app is coming to Google Play soon.</p>
          )}
        </Panel>
      </AppShell>
    );
  }
  return (
    <AppShell>
      <PageHeader
        eyebrow={welcome ? "Welcome to CyberHire" : "Plans"}
        title={b?.is_pro ? "Your plan" : b?.trial_available !== false ? `Try CyberHire Pro free for ${b?.trial_days ?? 3} days` : "Subscribe to CyberHire Pro"}
        desc={
          b?.is_pro
            ? "Thanks for practising with CyberHire."
            : b?.trial_available !== false
              ? "Pick a plan to start your free trial. You won't be charged today, and you can cancel anytime before the trial ends."
              : "Your free trial has been used. Subscribe to keep practising; your past reports stay available."
        }
      />
      {b?.is_pro ? (
        <Panel className="max-w-2xl" data-testid="pro-active">
          <SubscriptionSummary b={b} />
        </Panel>
      ) : (
        <>
          <PlanCards b={b} onChoose={(i) => checkout.mutate(i)} busyInterval={checkout.isPending ? checkout.variables : null} />
          <div className="mt-6 flex max-w-4xl items-start gap-2 text-xs text-slate-500">
            <ShieldCheck className="mt-0.5 size-4 shrink-0 text-slate-400" />
            <span>
              Payments are processed securely by Stripe; CyberHire never sees your card number. One free trial per person.
              See the <Link to="/terms" className="text-sky-400 hover:underline">Terms</Link> and{" "}
              <Link to="/refund-policy" className="text-sky-400 hover:underline">Refund policy</Link>.
            </span>
          </div>
        </>
      )}
    </AppShell>
  );
}

export function PaymentSuccess() {
  const [params] = useSearchParams();
  const qc = useQueryClient();
  const sessionId = params.get("session_id");
  const [state, setState] = useState<"checking" | "paid" | "failed" | "timeout">("checking");
  const [trial, setTrial] = useState(false);
  const tries = useRef(0);
  useEffect(() => {
    let stop = false;
    const poll = async () => {
      if (stop) return;
      try {
        const r = await apiGet<PaymentStatusOut>(`/payments/status/${sessionId}`);
        if (r.payment_status === "paid") {
          const b = await apiGet<BillingStatus>("/billing/status");
          if (b.has_access) {
            setTrial(b.on_trial);
            setState("paid");
            qc.setQueryData(["billing"], b);
            return;
          }
        }
        if (r.payment_status === "expired" || r.status === "failed") return setState("failed");
      } catch {
        /* keep polling */
      }
      if (++tries.current >= 20) return setState("timeout");
      setTimeout(poll, 2000);
    };
    if (sessionId) poll();
    else setState("failed");
    return () => {
      stop = true;
    };
  }, [sessionId, qc]);
  return (
    <AppShell>
      <Panel className="mx-auto max-w-md space-y-4 text-center" data-testid="payment-success-page">
        {state === "checking" && <><Loader2 className="mx-auto size-8 animate-spin text-sky-400" /><div className="text-white">Confirming your subscription…</div></>}
        {state === "paid" && (
          <>
            <CheckCircle2 className="mx-auto size-10 text-emerald-400" />
            <div className="font-heading text-2xl text-white" data-testid="payment-confirmed">{trial ? "Your free trial has started" : "Welcome to CyberHire Pro"}</div>
            <p className="text-sm text-slate-400">
              {trial ? "Everything is unlocked. To avoid being charged, cancel from your Profile before the trial ends." : "Everything is unlocked."}
            </p>
            <Link to="/interview/new" className={buttonVariants()} data-testid="payment-start-interview">Start your first interview</Link>
          </>
        )}
        {(state === "failed" || state === "timeout") && (
          <>
            <XCircle className="mx-auto size-10 text-amber-400" />
            <div className="text-white">{state === "timeout" ? "Still processing. Refresh this page in a minute." : "We couldn't confirm this checkout."}</div>
            <Link to="/pricing" className={buttonVariants({ variant: "secondary" })} data-testid="payment-back-pricing">Back to plans</Link>
          </>
        )}
      </Panel>
    </AppShell>
  );
}

export function PaymentCancel() {
  return (
    <AppShell>
      <Panel className="mx-auto max-w-md space-y-4 text-center" data-testid="payment-cancel-page">
        <div className="font-heading text-2xl text-white">Checkout cancelled</div>
        <p className="text-sm text-slate-400">No charge was made. You can start your trial whenever you're ready.</p>
        <Link to="/pricing" className={buttonVariants()} data-testid="payment-cancel-back">Back to plans</Link>
      </Panel>
    </AppShell>
  );
}
