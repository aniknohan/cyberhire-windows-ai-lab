import { useState } from "react";
import { Link, useNavigate, useSearchParams } from "react-router-dom";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { AlertTriangle, CheckCircle2, Loader2 } from "lucide-react";
import { ApiError, apiPost, clearToken } from "@/lib/api";
import { useBilling } from "@/lib/config";
import PublicLayout from "@/components/PublicLayout";
import { Eyebrow, Panel } from "@/components/common";
import { SubscriptionSummary } from "@/pages/Pricing";
import { Button, buttonVariants } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";

function detail(e: unknown, fallback: string): string {
  if (e instanceof ApiError) {
    const d = (e.body as { detail?: unknown })?.detail;
    if (typeof d === "string") return d;
    if (Array.isArray(d)) return "Please check the form: passwords need at least 8 characters.";
  }
  return fallback;
}

function Card({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <PublicLayout>
      <div className="flex justify-center px-4 py-16">
        <div className="w-full max-w-sm space-y-5">
          <h1 className="font-heading text-3xl font-semibold text-white">{title}</h1>
          {children}
        </div>
      </div>
    </PublicLayout>
  );
}

export function ForgotPassword() {
  const [email, setEmail] = useState("");
  const m = useMutation({ mutationFn: () => apiPost("/auth/forgot", { email }) });
  return (
    <Card title="Reset your password">
      {m.isSuccess ? (
        <div className="space-y-4 text-sm text-slate-300" data-testid="forgot-sent">
          <p>If an account exists for <b className="text-white">{email}</b>, we've emailed a link to choose a new password. It works for 1 hour.</p>
          <p className="text-slate-500">Nothing arrived? Check your spam folder, or try again in a few minutes.</p>
          <Link to="/login" className={buttonVariants({ variant: "secondary" })}>Back to sign in</Link>
        </div>
      ) : (
        <form className="space-y-4" onSubmit={(e) => { e.preventDefault(); m.mutate(); }} data-testid="forgot-form">
          <p className="text-sm text-slate-400">Enter your account's email and we'll send you a reset link.</p>
          <div className="space-y-1.5">
            <Label htmlFor="email">Email</Label>
            <Input id="email" type="email" required value={email} onChange={(e) => setEmail(e.target.value)} data-testid="forgot-email-input" />
          </div>
          {m.isError && <div className="text-sm text-red-300">{detail(m.error, "Something went wrong. Please try again.")}</div>}
          <Button type="submit" className="h-10 w-full" disabled={m.isPending} data-testid="forgot-submit">{m.isPending && <Loader2 className="animate-spin" />} Send reset link</Button>
          <p className="text-center text-sm"><Link to="/login" className="text-sky-400 hover:underline">Back to sign in</Link></p>
        </form>
      )}
    </Card>
  );
}

export function ResetPassword() {
  const [params] = useSearchParams();
  const token = params.get("token") || "";
  const [pw, setPw] = useState("");
  const [pw2, setPw2] = useState("");
  const m = useMutation({ mutationFn: () => apiPost("/auth/reset", { token, password: pw }) });
  const mismatch = pw2.length > 0 && pw !== pw2;
  return (
    <Card title="Choose a new password">
      {m.isSuccess ? (
        <div className="space-y-4 text-sm text-slate-300" data-testid="reset-done">
          <p className="flex items-center gap-2"><CheckCircle2 className="size-4 text-emerald-400" /> Your password has been changed.</p>
          <Link to="/login" className={buttonVariants()}>Sign in</Link>
        </div>
      ) : (
        <form className="space-y-4" onSubmit={(e) => { e.preventDefault(); if (!mismatch) m.mutate(); }} data-testid="reset-form">
          <div className="space-y-1.5">
            <Label htmlFor="pw">New password</Label>
            <Input id="pw" type="password" required minLength={8} value={pw} onChange={(e) => setPw(e.target.value)} data-testid="reset-password-input" />
          </div>
          <div className="space-y-1.5">
            <Label htmlFor="pw2">Confirm new password</Label>
            <Input id="pw2" type="password" required minLength={8} value={pw2} onChange={(e) => setPw2(e.target.value)} />
            {mismatch && <p className="text-xs text-red-300">The passwords don't match.</p>}
          </div>
          {!token && <div className="text-sm text-red-300">This link is missing its code. Open the link from the email again.</div>}
          {m.isError && <div className="text-sm text-red-300">{detail(m.error, "Something went wrong. Please try again.")}</div>}
          <Button type="submit" className="h-10 w-full" disabled={m.isPending || !token || mismatch} data-testid="reset-submit">{m.isPending && <Loader2 className="animate-spin" />} Save new password</Button>
        </form>
      )}
    </Card>
  );
}

/** Profile → Subscription panel (website only). */
export function SubscriptionPanel() {
  const { data: b } = useBilling();
  if (!b || b.mode !== "web") return null;
  return (
    <Panel className="max-w-2xl space-y-3" data-testid="subscription-panel">
      <Eyebrow>Subscription</Eyebrow>
      <SubscriptionSummary b={b} />
      {!b.is_pro && <Link to="/pricing" className={buttonVariants({ size: "sm" })}>{b.trial_available ? `Start ${b.trial_days}-day free trial` : "See plans"}</Link>}
    </Panel>
  );
}

/** Profile → Delete account (required by Google Play for apps with accounts). */
export function DeleteAccountPanel({ hasPassword = true }: { hasPassword?: boolean }) {
  const nav = useNavigate();
  const qc = useQueryClient();
  const [open, setOpen] = useState(false);
  const [confirm, setConfirm] = useState("");
  const [password, setPassword] = useState("");
  const m = useMutation({
    mutationFn: () => apiPost("/auth/delete-account", { confirm, password }),
    onSuccess: () => {
      clearToken();
      qc.clear();
      nav("/", { replace: true });
    },
  });
  return (
    <Panel className="max-w-2xl space-y-3 border-red-500/20" data-testid="delete-account-panel">
      <Eyebrow className="text-red-300/80">Delete account</Eyebrow>
      <p className="text-sm text-slate-400">Permanently deletes your profile, resume, interviews, reports and recordings, and cancels any website subscription. This can't be undone.</p>
      {!open ? (
        <Button variant="ghost" className="text-red-300 hover:text-red-200" onClick={() => setOpen(true)} data-testid="delete-account-open">Delete my account…</Button>
      ) : (
        <form className="space-y-3" onSubmit={(e) => { e.preventDefault(); m.mutate(); }}>
          <div className="flex items-start gap-2 rounded-lg border border-red-500/25 bg-red-500/[0.06] p-3 text-xs text-red-200">
            <AlertTriangle className="mt-0.5 size-4 shrink-0" /> Subscribed through Google Play? Cancel it in the Play Store too; deleting your account can't cancel Google Play billing.
          </div>
          <div className="space-y-1.5">
            <Label htmlFor="del-confirm">Type DELETE to confirm</Label>
            <Input id="del-confirm" value={confirm} onChange={(e) => setConfirm(e.target.value)} autoComplete="off" data-testid="delete-confirm-input" />
          </div>
          {hasPassword && (
            <div className="space-y-1.5">
              <Label htmlFor="del-pw">Your password</Label>
              <Input id="del-pw" type="password" value={password} onChange={(e) => setPassword(e.target.value)} data-testid="delete-password-input" />
            </div>
          )}
          {m.isError && <div className="text-sm text-red-300">{detail(m.error, "Couldn't delete the account. Please try again.")}</div>}
          <div className="flex gap-2">
            <Button type="submit" variant="destructive" disabled={m.isPending || confirm.trim().toUpperCase() !== "DELETE"} data-testid="delete-account-submit">
              {m.isPending && <Loader2 className="animate-spin" />} Permanently delete
            </Button>
            <Button type="button" variant="ghost" onClick={() => setOpen(false)}>Keep my account</Button>
          </div>
        </form>
      )}
    </Panel>
  );
}
