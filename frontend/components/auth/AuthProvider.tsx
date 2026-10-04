"use client";

import { createContext, useCallback, useContext, useEffect, useMemo, useState } from "react";
import { usePathname, useRouter } from "next/navigation";
import { apiGet, apiPost } from "@/lib/api";
import type { AccountRole, CurrentAccountDto, OrganizationMembershipDto } from "@/lib/auth-types";

const STORAGE_KEY = "medflux.organization_slug";
const PREVIEW_KEY = "medflux.role_preview";
type ScopedMembership = OrganizationMembershipDto;

interface AuthContextValue {
  account: CurrentAccountDto | null;
  membership: ScopedMembership | null;
  memberships: ScopedMembership[];
  organizationSlug: string | null;
  loading: boolean;
  role: AccountRole | null;
  /** Echte Rolle, wenn eine Rollenvorschau aktiv ist; sonst null. */
  previewOf: AccountRole | null;
  /** Nur Darstellung: die Rechte prueft weiterhin das Backend mit der echten Rolle. */
  setPreviewRole: (role: AccountRole | null) => void;
  refresh: () => Promise<CurrentAccountDto | null>;
  selectOrganization: (slug: string) => void;
  logout: () => Promise<void>;
}

const AuthContext = createContext<AuthContextValue | null>(null);

function clearLocalScope() {
  if (typeof window === "undefined") return;
  window.localStorage.removeItem(STORAGE_KEY);
  window.localStorage.removeItem("medflux.hospitalId");
  window.localStorage.removeItem("medflux.departmentId");
}

function persistAssignedScope(membership: ScopedMembership) {
  if (typeof window === "undefined") return;
  window.localStorage.setItem(STORAGE_KEY, membership.organization_slug);
  if (membership.hospital_id) window.localStorage.setItem("medflux.hospitalId", membership.hospital_id);
  else window.localStorage.removeItem("medflux.hospitalId");
  if (membership.department_id) window.localStorage.setItem("medflux.departmentId", membership.department_id);
  else window.localStorage.removeItem("medflux.departmentId");
}

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
    if (typeof window === "undefined") return;
    const onSessionExpired = () => {
      setAccount(null);
      setSelectedSlug(null);
      clearLocalScope();
      if (pathname !== "/login") router.replace("/login?error=session");
    };
    window.addEventListener("medflux:session-expired", onSessionExpired);
    return () => window.removeEventListener("medflux:session-expired", onSessionExpired);
  }, [pathname, router]);

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

  const memberships = useMemo(() => account?.memberships ?? [], [account?.memberships]);
  const isDeveloper = Boolean(account?.is_developer);
  const isAdminAccount = isDeveloper || memberships.some((item) => item.role === "admin");

  useEffect(() => {
    if (!account || memberships.length === 0) return;
    const selectedIsValid = selectedSlug && memberships.some((item) => item.organization_slug === selectedSlug);

    if (!isAdminAccount) {
      const assigned = memberships.find((item) => item.is_default) ?? memberships.find((item) => item.organization_slug === defaultOrganizationSlug) ?? memberships[0];
      if (selectedSlug !== assigned.organization_slug) setSelectedSlug(assigned.organization_slug);
      persistAssignedScope(assigned);
      return;
    }

    if (selectedIsValid) return;
    if (memberships.length === 1) {
      const only = memberships[0];
      setSelectedSlug(only.organization_slug);
      persistAssignedScope(only);
    }
  }, [account, memberships, selectedSlug, defaultOrganizationSlug, isAdminAccount]);

  const membership = useMemo(
    () => memberships.find((item) => item.organization_slug === selectedSlug) ?? null,
    [memberships, selectedSlug]
  );

  useEffect(() => {
    if (loading || !account || pathname === "/login") return;

    if (isDeveloper && memberships.length === 0) {
      if (pathname !== "/system/organizations") router.replace("/system/organizations");
      return;
    }

    if (!isDeveloper && memberships.length === 0) {
      router.replace("/login?error=organization");
      return;
    }

    if (pathname === "/select-organization") {
      if (!isAdminAccount || memberships.length <= 1) router.replace("/");
      return;
    }

    if (isAdminAccount && memberships.length > 1 && !membership && pathname !== "/system/organizations") {
      router.replace("/select-organization");
    }
  }, [account, loading, membership, memberships.length, pathname, router, isAdminAccount, isDeveloper]);

  const selectOrganization = useCallback((slug: string) => {
    if (!isAdminAccount) return;
    const selected = memberships.find((item) => item.organization_slug === slug);
    if (!selected) return;
    setSelectedSlug(slug);
    persistAssignedScope(selected);
  }, [memberships, isAdminAccount]);

  const logout = useCallback(async () => {
    try {
      await apiPost<{ ok: boolean }>("/api/auth/logout", {});
    } finally {
      setAccount(null);
      setSelectedSlug(null);
      clearLocalScope();
      router.replace("/login");
    }
  }, [router]);

  const realRole: AccountRole | null = membership?.role ?? (isDeveloper ? "admin" : null);
  const [previewRole, setPreviewState] = useState<AccountRole | null>(null);
  useEffect(() => {
    try {
      const stored = window.sessionStorage.getItem(PREVIEW_KEY);
      if (stored === "contract_manager" || stored === "reviewer" || stored === "viewer") setPreviewState(stored);
    } catch { /* ohne Speicher keine Vorschau */ }
  }, []);
  const setPreviewRole = useCallback((next: AccountRole | null) => {
    setPreviewState(next);
    try {
      if (next) window.sessionStorage.setItem(PREVIEW_KEY, next);
      else window.sessionStorage.removeItem(PREVIEW_KEY);
    } catch { /* nur fuer diese Sitzung */ }
  }, []);
  const previewActive = Boolean(previewRole && realRole === "admin");

  const value = useMemo<AuthContextValue>(() => ({
    account: previewActive && account ? { ...account, is_developer: false } : account,
    membership: previewActive && membership ? { ...membership, role: previewRole as AccountRole } : membership,
    memberships,
    organizationSlug: membership?.organization_slug ?? null,
    loading,
    role: previewActive ? previewRole : realRole,
    previewOf: previewActive ? realRole : null,
    setPreviewRole,
    refresh,
    selectOrganization,
    logout,
  }), [account, membership, memberships, loading, refresh, selectOrganization, logout, realRole, previewActive, previewRole, setPreviewRole]);

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth(): AuthContextValue {
  const value = useContext(AuthContext);
  if (!value) throw new Error("useAuth must be used inside AuthProvider");
  return value;
}
