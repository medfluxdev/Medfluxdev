"use client";

import { createContext, useCallback, useContext, useEffect, useMemo, useState } from "react";
import { usePathname, useRouter } from "next/navigation";
import { apiGet, apiPost } from "@/lib/api";
import type { AccountRole, CurrentAccountDto, OrganizationMembershipDto } from "@/lib/auth-types";

const STORAGE_KEY = "medflux.organization_slug";

interface AuthContextValue {
  account: CurrentAccountDto | null;
  membership: OrganizationMembershipDto | null;
  memberships: OrganizationMembershipDto[];
  organizationSlug: string | null;
  loading: boolean;
  role: AccountRole | null;
  refresh: () => Promise<CurrentAccountDto | null>;
  selectOrganization: (slug: string) => void;
  logout: () => Promise<void>;
}

const AuthContext = createContext<AuthContextValue | null>(null);

export function AuthProvider({ children, organizationSlug: defaultOrganizationSlug }: { children: React.ReactNode; organizationSlug: string }) {
  const pathname = usePathname();
  const router = useRouter();
  const [account, setAccount] = useState<CurrentAccountDto | null>(null);
  const [selectedSlug, setSelectedSlug] = useState<string | null>(null);
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
    if (typeof window === "undefined") return;
    setSelectedSlug(window.localStorage.getItem(STORAGE_KEY));
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

  const memberships = account?.memberships ?? [];

  useEffect(() => {
    if (!account || memberships.length === 0) return;
    const selectedIsValid = selectedSlug && memberships.some((item) => item.organization_slug === selectedSlug);
    if (selectedIsValid) return;
    if (memberships.length === 1) {
      const slug = memberships[0].organization_slug;
      setSelectedSlug(slug);
      if (typeof window !== "undefined") window.localStorage.setItem(STORAGE_KEY, slug);
      return;
    }
    if (memberships.some((item) => item.organization_slug === defaultOrganizationSlug) && !selectedSlug) {
      // Multiple memberships must be selected explicitly after login.
      return;
    }
  }, [account, memberships, selectedSlug, defaultOrganizationSlug]);

  const membership = useMemo(
    () => memberships.find((item) => item.organization_slug === selectedSlug) ?? null,
    [memberships, selectedSlug]
  );

  useEffect(() => {
    if (loading || !account || pathname === "/login" || pathname === "/select-organization") return;
    if (memberships.length === 0) {
      router.replace("/login?error=organization");
    } else if (memberships.length > 1 && !membership) {
      router.replace("/select-organization");
    }
  }, [account, loading, membership, memberships.length, pathname, router]);

  const selectOrganization = useCallback((slug: string) => {
    if (!memberships.some((item) => item.organization_slug === slug)) return;
    setSelectedSlug(slug);
    if (typeof window !== "undefined") window.localStorage.setItem(STORAGE_KEY, slug);
  }, [memberships]);

  const logout = useCallback(async () => {
    try {
      await apiPost<{ ok: boolean }>("/api/auth/logout", {});
    } finally {
      setAccount(null);
      setSelectedSlug(null);
      if (typeof window !== "undefined") window.localStorage.removeItem(STORAGE_KEY);
      router.replace("/login");
    }
  }, [router]);

  const value = useMemo<AuthContextValue>(() => ({
    account,
    membership,
    memberships,
    organizationSlug: membership?.organization_slug ?? null,
    loading,
    role: membership?.role ?? null,
    refresh,
    selectOrganization,
    logout,
  }), [account, membership, memberships, loading, refresh, selectOrganization, logout]);

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth(): AuthContextValue {
  const value = useContext(AuthContext);
  if (!value) throw new Error("useAuth must be used inside AuthProvider");
  return value;
}
