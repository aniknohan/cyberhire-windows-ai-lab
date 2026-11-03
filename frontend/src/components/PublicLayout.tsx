import { Link } from "react-router-dom";
import type { ReactNode } from "react";
import { useMe } from "@/lib/auth";
import { useConfig } from "@/lib/config";
import { buttonVariants } from "@/components/ui/button";
import { cn } from "@/lib/utils";

/** Header + footer for the public website pages (landing, legal, password reset). */
export default function PublicLayout({ children }: { children: ReactNode }) {
  const { data: me } = useMe();
  const { data: cfg } = useConfig();
  return (
    <div className="flex min-h-screen flex-col">
      <header className="sticky top-0 z-40 border-b border-white/[0.06] bg-[#090D14]/80 backdrop-blur-xl">
        <div className="mx-auto flex h-14 max-w-6xl items-center gap-4 px-4 sm:px-6">
          <Link to="/" className="flex items-center gap-2" data-testid="public-brand">
            <img src="/logo.png" alt="CyberHire logo" className="size-7 rounded-md" />
            <span className="font-heading text-sm font-semibold tracking-tight text-white">CyberHire</span>
          </Link>
          <nav className="ml-6 hidden items-center gap-5 text-sm text-slate-400 md:flex">
            <a href="/#features" className="hover:text-white">Features</a>
            <a href="/#how" className="hover:text-white">How it works</a>
            <a href="/#pricing" className="hover:text-white">Pricing</a>
            <a href="/#faq" className="hover:text-white">FAQ</a>
          </nav>
          <div className="ml-auto flex items-center gap-2">
            {me ? (
              <Link to="/dashboard" className={buttonVariants({ size: "sm" })} data-testid="public-open-app">Open dashboard</Link>
            ) : (
              <>
                <Link to="/login" className={cn(buttonVariants({ size: "sm", variant: "ghost" }))} data-testid="public-login">Sign in</Link>
                <Link to="/register" className={buttonVariants({ size: "sm" })} data-testid="public-signup">Start free trial</Link>
              </>
            )}
          </div>
        </div>
      </header>
      <div className="flex-1">{children}</div>
      <SiteFooter supportEmail={cfg?.support_email} />
    </div>
  );
}

export function SiteFooter({ supportEmail }: { supportEmail?: string }) {
  return (
    <footer className="border-t border-white/[0.06] py-8 text-xs text-slate-500">
      <div className="mx-auto flex max-w-6xl flex-col gap-4 px-4 sm:flex-row sm:items-center sm:justify-between sm:px-6">
        <div>© {new Date().getFullYear()} CyberHire · AI interview practice for cybersecurity careers</div>
        <nav className="flex flex-wrap gap-x-5 gap-y-2" data-testid="legal-links">
          <Link to="/terms" className="hover:text-slate-300">Terms</Link>
          <Link to="/privacy" className="hover:text-slate-300">Privacy</Link>
          <Link to="/refund-policy" className="hover:text-slate-300">Refunds</Link>
          <Link to="/delete-account" className="hover:text-slate-300">Delete account</Link>
          {supportEmail && <a href={`mailto:${supportEmail}`} className="hover:text-slate-300">Contact</a>}
        </nav>
      </div>
    </footer>
  );
}
