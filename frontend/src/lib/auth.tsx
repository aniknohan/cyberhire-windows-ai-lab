import { useQuery } from "@tanstack/react-query";
import { Navigate, useLocation } from "react-router-dom";
import type { ReactNode } from "react";
import { ApiError, apiGet } from "@/lib/api";
import { useBilling, useConfig } from "@/lib/config";
import type { User } from "@/lib/types";

export function useMe() {
  // "Not signed in" is a normal answer (null), not an error: an error state would be refetched every time
  // another component asks, which made public pages flicker between loading and content.
  return useQuery({
    queryKey: ["me"],
    queryFn: async (): Promise<User | null> => {
      try {
        return await apiGet<User>("/auth/me");
      } catch (e) {
        if (e instanceof ApiError && e.status === 401) return null;
        throw e;
      }
    },
    retry: false,
    staleTime: 60_000,
  });
}

function FullScreenLoader() {
  return (
    <div className="flex min-h-screen items-center justify-center" data-testid="auth-loading">
      <div className="size-6 animate-spin rounded-full border-2 border-sky-400 border-t-transparent" />
    </div>
  );
}

export function RequireAuth({ children, admin = false }: { children: ReactNode; admin?: boolean }) {
  const { data, isLoading, isError } = useMe();
  const loc = useLocation();
  if (isLoading) return <FullScreenLoader />;
  if (isError || !data) return <Navigate to="/login" replace state={{ from: loc.pathname }} />;
  if (admin && data.role !== "admin") return <Navigate to="/" replace />;
  return <>{children}</>;
}

/** Website only: pages that use the AI need an active plan (trial or paid); others go to Plans. */
export function RequirePlan({ children }: { children: ReactNode }) {
  const { data: cfg, isLoading: cfgLoading } = useConfig();
  const web = cfg?.mode === "web";
  const { data: b, isLoading } = useBilling(web);
  if (cfgLoading || (web && isLoading)) return <FullScreenLoader />;
  if (web && b && !b.has_access) return <Navigate to="/pricing" replace />;
  return <>{children}</>;
}

export function AuthLoader() {
  return <FullScreenLoader />;
}
