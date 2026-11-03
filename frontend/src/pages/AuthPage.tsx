import { useState } from "react";
import { Link, useLocation, useNavigate } from "react-router-dom";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { Loader2, Video, MessagesSquare, Gavel } from "lucide-react";
import { ApiError, apiPost } from "@/lib/api";
import { useConfig } from "@/lib/config";
import type { User } from "@/lib/types";
import { EXPERIENCE, POSITIONS } from "@/lib/constants";
import { PositionOptions } from "@/components/common";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";

function errMsg(e: unknown): string {
  if (e instanceof ApiError) {
    const d = (e.body as { detail?: unknown })?.detail;
    if (typeof d === "string") return d;
    if (Array.isArray(d)) return "Please check your email and use a password of at least 8 characters.";
  }
  return "Something went wrong. Please try again.";
}

export default function AuthPage({ mode }: { mode: "login" | "register" }) {
  const nav = useNavigate();
  const loc = useLocation();
  const qc = useQueryClient();
  const { data: cfg } = useConfig();
  const web = cfg?.mode === "web";
  const [form, setForm] = useState({ email: "", password: "", name: "", target_role: "SOC Analyst L1", experience_level: "Entry Level" });
  const m = useMutation({
    mutationFn: () => apiPost<User>(mode === "login" ? "/auth/login" : "/auth/register", mode === "login" ? { email: form.email, password: form.password } : form),
    onSuccess: (u) => {
      qc.clear();
      qc.setQueryData(["me"], u);
      const from = (loc.state as { from?: string })?.from;
      nav(mode === "register" && web ? "/pricing?welcome=1" : from || "/", { replace: true });
    },
  });
  const set = (k: keyof typeof form) => (e: React.ChangeEvent<HTMLInputElement>) => setForm((f) => ({ ...f, [k]: e.target.value }));

  return (
    <div className="grid min-h-screen lg:grid-cols-[1.1fr_1fr]">
      <div className="relative hidden overflow-hidden border-r border-white/[0.06] lg:block">
        <img
          src="https://images.unsplash.com/photo-1758873268631-fa944fc5cad2?crop=entropy&cs=srgb&fm=jpg&q=85&w=1600"
          alt=""
          className="absolute inset-0 h-full w-full object-cover opacity-35"
        />
        <div className="absolute inset-0 bg-gradient-to-br from-[#090D14] via-[#090D14]/80 to-transparent" />
        <div className="relative flex h-full flex-col justify-between p-12">
          <Link to="/" className="flex items-center gap-2">
            <img src="/logo.png" alt="CyberHire logo" className="size-8 rounded-md" data-testid="brand-logo" />
            <span className="font-heading font-semibold text-white">CyberHire</span>
          </Link>
          <div className="max-w-lg">
            <h1 className="font-heading text-5xl leading-[1.05] font-semibold tracking-tight text-white">Walk into your next cybersecurity interview like you've already done it.</h1>
            <p className="mt-5 text-slate-300">Face-to-face video interviews with a recruiter, a senior analyst, an incident response lead and a SOC manager — then a real hiring decision.</p>
            <div className="mt-8 grid gap-3 text-sm text-slate-300">
              <div className="flex items-center gap-3"><Video className="size-4 text-sky-400" /> Voice-first video interviews with four distinct interviewers</div>
              <div className="flex items-center gap-3"><MessagesSquare className="size-4 text-sky-400" /> Separate scores for job readiness and professional English</div>
              <div className="flex items-center gap-3"><Gavel className="size-4 text-sky-400" /> Strong Hire to No Hire, with the reasons explained</div>
            </div>
          </div>
          <div className="font-mono text-[11px] text-slate-500">Hundreds of cybersecurity interview questions · SOC, tools &amp; Python · live investigations</div>
        </div>
      </div>
      <div className="flex items-center justify-center px-6 py-12">
        <form
          className="w-full max-w-sm space-y-5"
          onSubmit={(e) => {
            e.preventDefault();
            m.mutate();
          }}
          data-testid={`${mode}-form`}
        >
          <div>
            <h2 className="font-heading text-3xl font-semibold text-white">{mode === "login" ? "Welcome back" : "Create your account"}</h2>
            <p className="mt-1 text-sm text-slate-400">{mode === "login" ? "Sign in to continue your interview prep." : "Your interview history stays private to you."}</p>
          </div>
          {mode === "register" && (
            <div className="space-y-1.5">
              <Label htmlFor="name">Full name</Label>
              <Input id="name" value={form.name} onChange={set("name")} required data-testid="register-name-input" />
            </div>
          )}
          <div className="space-y-1.5">
            <Label htmlFor="email">Email</Label>
            <Input id="email" type="email" value={form.email} onChange={set("email")} required data-testid={`${mode}-email-input`} />
          </div>
          <div className="space-y-1.5">
            <Label htmlFor="password">Password</Label>
            <Input id="password" type="password" value={form.password} onChange={set("password")} required minLength={mode === "register" ? 8 : 1} autoComplete={mode === "login" ? "current-password" : "new-password"} data-testid={`${mode}-password-input`} />
            {mode === "login" && web && <div className="text-right"><Link to="/forgot-password" className="text-xs text-sky-400 hover:underline" data-testid="forgot-link">Forgot password?</Link></div>}
            {mode === "register" && <p className="text-[11px] text-slate-500">At least 8 characters.</p>}
          </div>
          {mode === "register" && (
            <div className="grid grid-cols-2 gap-3">
              <div className="space-y-1.5">
                <Label>Target role</Label>
                <Select value={form.target_role} onValueChange={(v: string) => setForm((f) => ({ ...f, target_role: v }))}>
                  <SelectTrigger className="w-full" data-testid="register-role-select"><SelectValue /></SelectTrigger>
                  <SelectContent><PositionOptions /></SelectContent>
                </Select>
              </div>
              <div className="space-y-1.5">
                <Label>Experience</Label>
                <Select value={form.experience_level} onValueChange={(v: string) => setForm((f) => ({ ...f, experience_level: v }))}>
                  <SelectTrigger className="w-full" data-testid="register-experience-select"><SelectValue /></SelectTrigger>
                  <SelectContent>{EXPERIENCE.map((p) => <SelectItem key={p} value={p}>{p}</SelectItem>)}</SelectContent>
                </Select>
              </div>
            </div>
          )}
          {cfg?.google_login && (
            <>
          <Button
            type="button"
            variant="secondary"
            size="lg"
            className="h-10 w-full"
            onClick={() => {
              // REMINDER: DO NOT HARDCODE THE URL, OR ADD ANY FALLBACKS OR REDIRECT URLS, THIS BREAKS THE AUTH
              const redirectUrl = window.location.origin + "/";
              window.location.href = `https://auth.emergentagent.com/?redirect=${encodeURIComponent(redirectUrl)}`;
            }}
            data-testid={`${mode}-google-button`}
          >
            <svg viewBox="0 0 24 24" className="size-4" aria-hidden="true"><path fill="#EA4335" d="M12 10.2v3.9h5.5c-.2 1.3-1.6 3.9-5.5 3.9-3.3 0-6-2.7-6-6.1s2.7-6.1 6-6.1c1.9 0 3.1.8 3.8 1.5l2.6-2.5C16.8 3.3 14.6 2.3 12 2.3 6.6 2.3 2.3 6.6 2.3 12s4.3 9.7 9.7 9.7c5.6 0 9.3-3.9 9.3-9.5 0-.6-.1-1.1-.2-1.6H12z"/></svg>
            Continue with Google
          </Button>
          <div className="flex items-center gap-3 text-[11px] uppercase tracking-wider text-slate-600"><span className="h-px flex-1 bg-white/10" />or with email<span className="h-px flex-1 bg-white/10" /></div>
            </>
          )}
          {m.isError && <div className="rounded-md border border-red-500/30 bg-red-500/10 px-3 py-2 text-sm text-red-300" data-testid={`${mode}-error`}>{errMsg(m.error)}</div>}
          <Button type="submit" size="lg" className="h-10 w-full" disabled={m.isPending} data-testid={`${mode}-submit-button`}>
            {m.isPending && <Loader2 className="animate-spin" />} {mode === "login" ? "Sign in" : "Create account"}
          </Button>
          <p className="text-center text-sm text-slate-400">
            {mode === "login" ? "New here? " : "Already have an account? "}
            <Link to={mode === "login" ? "/register" : "/login"} className="text-sky-400 hover:underline" data-testid={`${mode}-switch-link`}>
              {mode === "login" ? "Create an account" : "Sign in"}
            </Link>
          </p>
          {mode === "register" && web && (
            <p className="text-center text-[11px] leading-relaxed text-slate-500">
              By creating an account you agree to the <Link to="/terms" className="text-sky-400 hover:underline">Terms</Link> and{" "}
              <Link to="/privacy" className="text-sky-400 hover:underline">Privacy policy</Link>. Next you'll choose a plan and start your free trial.
            </p>
          )}
        </form>
      </div>
    </div>
  );
}
