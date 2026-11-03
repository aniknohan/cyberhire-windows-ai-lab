import { Link, NavLink, useNavigate } from "react-router-dom";
import { useQueryClient } from "@tanstack/react-query";
import { useState, type ReactNode } from "react";
import { LayoutDashboard, History, MessageSquareText, Cpu, Mic, Settings2, LogOut, Menu, UserRound, Plus } from "lucide-react";
import { apiPost, clearToken } from "@/lib/api";
import { useMe } from "@/lib/auth";
import { daysLeft, useBilling, useConfig } from "@/lib/config";
import { SiteFooter } from "@/components/PublicLayout";
import { cn } from "@/lib/utils";
import { buttonVariants } from "@/components/ui/button";
import { Sheet, SheetContent, SheetTitle } from "@/components/ui/sheet";

const NAV = [
  { to: "/", label: "Dashboard", icon: LayoutDashboard, end: true },
  { to: "/history", label: "History", icon: History },
  { to: "/skills/communication", label: "Communication", icon: MessageSquareText },
  { to: "/skills/technical", label: "Technical", icon: Cpu },
  { to: "/practice", label: "Practice", icon: Mic },
];

function NavItems({ onNavigate, admin }: { onNavigate?: () => void; admin: boolean }) {
  const items = admin ? [...NAV, { to: "/admin", label: "Admin", icon: Settings2 }] : NAV;
  return (
    <>
      {items.map((n) => (
        <NavLink
          key={n.to}
          to={n.to}
          end={"end" in n ? n.end : false}
          onClick={onNavigate}
          data-testid={`nav-${n.label.toLowerCase()}`}
          className={({ isActive }) =>
            cn(
              "flex items-center gap-2 rounded-lg px-3 py-2 text-sm transition-colors duration-200",
              isActive ? "bg-white/[0.06] text-white" : "text-slate-400 hover:bg-white/[0.04] hover:text-slate-200",
            )
          }
        >
          <n.icon className="size-4" />
          {n.label}
        </NavLink>
      ))}
    </>
  );
}

export default function AppShell({ children }: { children: ReactNode }) {
  const { data: me } = useMe();
  const qc = useQueryClient();
  const nav = useNavigate();
  const [open, setOpen] = useState(false);
  const { data: cfg } = useConfig();
  const web = cfg?.mode === "web";
  const { data: billing } = useBilling(web && !!me);
  const logout = async () => {
    await apiPost("/auth/logout").catch(() => undefined);
    clearToken();
    qc.clear();
    nav(web ? "/" : "/login");
  };
  return (
    <div className="min-h-screen">
      <header className="sticky top-0 z-40 border-b border-white/[0.06] bg-[#090D14]/80 backdrop-blur-xl">
        <div className="mx-auto flex h-14 max-w-7xl items-center gap-4 px-4 sm:px-6">
          <button className="md:hidden" onClick={() => setOpen(true)} data-testid="mobile-nav-button" aria-label="Open navigation">
            <Menu className="size-5 text-slate-300" />
          </button>
          <Link to="/" className="flex items-center gap-2" data-testid="brand-link">
            <img src="/logo.png" alt="CyberHire logo" className="size-7 rounded-md" data-testid="brand-logo" />
            <span className="font-heading text-sm font-semibold tracking-tight text-white">CyberHire</span>
          </Link>
          <nav className="ml-4 hidden items-center gap-1 md:flex">
            <NavItems admin={me?.role === "admin"} />
          </nav>
          <div className="ml-auto flex items-center gap-2">
            {web && billing && me?.role !== "admin" && (billing.on_trial ? (
              <Link to="/profile" className="hidden rounded-md border border-amber-400/30 bg-amber-400/10 px-2 py-0.5 font-mono text-[10px] tracking-wider text-amber-300 sm:inline" data-testid="nav-trial-badge">
                TRIAL · {daysLeft(billing.trial_until).toUpperCase()}
              </Link>
            ) : billing.is_pro ? (
              <Link to="/profile" className="hidden rounded-md border border-sky-500/30 bg-sky-500/10 px-2 py-0.5 font-mono text-[10px] tracking-wider text-sky-300 sm:inline" data-testid="nav-pro-badge">PRO</Link>
            ) : (
              <Link to="/pricing" className={cn(buttonVariants({ size: "sm", variant: "secondary" }))} data-testid="nav-upgrade-button">
                {billing.trial_available ? "Start free trial" : "Subscribe"}
              </Link>
            ))}
            <Link to="/interview/new" className={cn(buttonVariants({ size: "sm" }), "hidden sm:inline-flex")} data-testid="header-start-interview">
              <Plus className="size-3.5" /> New interview
            </Link>
            <Link to="/profile" className="flex items-center gap-2 rounded-lg px-2 py-1 text-sm text-slate-300 hover:bg-white/[0.04]" data-testid="nav-profile">
              <UserRound className="size-4" />
              <span className="hidden lg:inline" data-testid="nav-user-name">{me?.name}</span>
            </Link>
            <button onClick={logout} className="rounded-lg p-2 text-slate-400 transition-colors hover:bg-white/[0.04] hover:text-white" data-testid="logout-button" aria-label="Sign out">
              <LogOut className="size-4" />
            </button>
          </div>
        </div>
      </header>
      <Sheet open={open} onOpenChange={setOpen}>
        <SheetContent side="left" className="w-64 bg-[#0B111E] p-4">
          <SheetTitle className="mb-4 font-heading text-white">Menu</SheetTitle>
          <div className="flex flex-col gap-1">
            <NavItems admin={me?.role === "admin"} onNavigate={() => setOpen(false)} />
          </div>
        </SheetContent>
      </Sheet>
      <main className="mx-auto max-w-7xl px-4 py-8 sm:px-6 lg:py-10">{children}</main>
      {web && <SiteFooter supportEmail={cfg?.support_email} />}
    </div>
  );
}

export function PageHeader({ eyebrow, title, desc, action }: { eyebrow?: string; title: string; desc?: string; action?: ReactNode }) {
  return (
    <div className="mb-8 flex flex-col gap-4 sm:flex-row sm:items-end sm:justify-between">
      <div>
        {eyebrow && <div className="mb-2 font-mono text-[11px] uppercase tracking-[0.18em] text-sky-400/80">{eyebrow}</div>}
        <h1 className="font-heading text-3xl font-semibold tracking-tight text-white sm:text-4xl" data-testid="page-title">
          {title}
        </h1>
        {desc && <p className="mt-2 max-w-2xl text-sm text-slate-400">{desc}</p>}
      </div>
      {action}
    </div>
  );
}
