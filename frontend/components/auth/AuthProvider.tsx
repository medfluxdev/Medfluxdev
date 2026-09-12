"use client";

import { createContext, useCallback, useContext, useEffect, useMemo, useState } from "react";
import { usePathname, useRouter } from "next/navigation";
import { apiGet, apiPost } from "@/lib/api";
import type { AccountRole, CurrentAccountDto, OrganizationMembershipDto } from "@/lib/auth-types";

interface AuthContextValue {
  account: CurrentAccountDto | null;
  membership: OrganizationMembershipDto | null;
  loading: boolean;
  role: AccountRole | null;
  refresh: () => Promise<CurrentAccountDto | null>;
  logout: () => Promise<void>;
}

const AuthContext = createContext<AuthContextValue | null>(null);

export function AuthProvider({ children, organizationSlug }: { children: React.ReactNode; organizationSlug: string }) {
  const pathname = usePathname();
  const router = useRouter();
  const [account, setAccount] = useState<CurrentAccountDto | null>(null);
  const [loading, setLoading] = useState(pathname !== "/login");

  const refresh = useCallback(async () => {
    try {
      const data = await apiGet<CurrentAccountDto>("/api/me");
      setAccount(data);
      return data;
    } catch {
      setAccount(null);
      return null;
    }
  }, []);

  useEffect(() => {
    let active = true;
    if (pathname === "/login") {
      setLoading(false);
      return () => { active = false; };
    }
    setLoading(true);
    refresh().then((data) => {
      if (!active) return;
      setLoading(false);
      if (!data) router.replace("/login");
    });
    return () => { active = false; };
  }, [pathname, refresh, router]);

  const membership = useMemo(
    () => account?.memberships.find((item) => item.organization_slug === organizationSlug) ?? null,
    [account, organizationSlug]
  );

  useEffect(() => {
    if (!loading && pathname !== "/login" && account && !membership) {
      router.replace("/login?error=organization");
    }
  }, [account, loading, membership, pathname, router]);

  const logout = useCallback(async () => {
    try {
      await apiPost<{ ok: boolean }>("/api/auth/logout", {});
    } finally {
      setAccount(null);
      router.replace("/login");
    }
  }, [router]);

  const value = useMemo<AuthContextValue>(() => ({
    account,
    membership,
    loading,
    role: membership?.role ?? null,
    refresh,
    logout,
  }), [account, membership, loading, refresh, logout]);

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth(): AuthContextValue {
  const value = useContext(AuthContext);
  if (!value) throw new Error("useAuth must be used inside AuthProvider");
  return value;
}
