"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { useEffect, useMemo, useState } from "react";
import { apiGet } from "@/lib/api";
import { useAuth } from "@/components/auth/AuthProvider";
import MedFluxLogo from "@/components/brand/MedFluxLogo";
import { type AccountRole } from "@/lib/auth-types";
import type { AIStatus } from "@/lib/ai-types";

type Icon = React.ReactNode;
type NavItem = { label: string; href: string; icon: keyof typeof icons; roles?: AccountRole[] };

const icons: Record<string, Icon> = {
  dashboard: <path d="M4 12h5l3-7 3 14 2-7h3" />,
  admin: <><rect x="4" y="4" width="16" height="16" rx="3"/><path d="M8 15v-3M12 15V8M16 15v-5"/></>,
  contracts: <><path d="M6 3h8l4 4v14H6z"/><path d="M14 3v5h5"/></>,
  equipment: <><rect x="5" y="4" width="14" height="16" rx="2"/><path d="M9 8h6M9 12h6M9 16h3"/></>,
  workQueue: <><path d="M5 5h14v14H5z"/><path d="M8 9h8M8 13h5"/></>,
  import: <path d="M12 3v18M3 12h18" />,
  review: <><circle cx="10" cy="10" r="6"/><path d="m15 15 5 5"/></>,
  evidence: <><path d="M4 5h16v14H4z"/><path d="M8 9h8M8 13h5"/></>,
  audit: <><path d="M5 20V4h14v16z"/><path d="M8 8h8M8 12h8M8 16h5"/></>,
  archive: <><path d="M4 8h16v12H4z"/><path d="M7 8V4h10v4"/><path d="M9 12h6"/></>,
  settings: <><circle cx="12" cy="12" r="3"/><path d="M19 12a7 7 0 0 0-.1-1l2-1.5-2-3.4-2.4 1a7 7 0 0 0-1.7-1L14.5 3h-5l-.4 3.1a7 7 0 0 0-1.7 1l-2.4-1-2 3.4L5 11a7 7 0 0 0 0 2l-2 1.5 2 3.4 2.4-1a7 7 0 0 0 1.7 1l.4 3.1h5l.4-3.1a7 7 0 0 0 1.7 1l2.4 1 2-3.4L19 13a7 7 0 0 0 0-1z"/></>,
};

const EDITORS: AccountRole[] = ["admin", "contract_manager"];
const REVIEWERS: AccountRole[] = ["admin", "contract_manager", "reviewer"];
const STATUS_REFRESH_MS = 60_000;
const STATUS_STALE_MS = 120_000;

const GROUPS: { label: string; items: NavItem[] }[] = [
  { label: "Arbeitsbereich", items: [
    { label: "Übersicht", href: "/", icon: "dashboard" },
    { label: "Verträge", href: "/contracts", icon: "contracts" },
    { label: "Geräte", href: "/equipment", icon: "equipment" },
    { label: "To-dos", href: "/work-queue", icon: "workQueue", roles: REVIEWERS },
  ]},
  { label: "Dokumente & Prüfung", items: [
    { label: "Import", href: "/import", icon: "import", roles: EDITORS },
    { label: "Prüfungen", href: "/review", icon: "review", roles: REVIEWERS },
    { label: "Nachweise", href: "/nachweise", icon: "evidence" },
    { label: "Archiv", href: "/archiv", icon: "archive", roles: EDITORS },
  ]},
  { label: "Administration", items: [
    { label: "Audit", href: "/audit", icon: "audit", roles: EDITORS },
    { label: "Admin Dashboard", href: "/admin", icon: "admin", roles: ["admin"] },
    { label: "Einstellungen", href: "/settings", icon: "settings", roles: ["admin"] },
  ]},
];

function isActive(pathname: string, href: string) {
  return href === "/" ? pathname === "/" : pathname === href || pathname.startsWith(`${href}/`);
}

export default function AppSidebar() {
  const pathname = usePathname();
  const { account, membership, role } = useAuth();
  const [apiHealthy, setApiHealthy] = useState<boolean | null>(null);
  const [aiStatus, setAiStatus] = useState<AIStatus | null>(null);
  const [statusCheckedAt, setStatusCheckedAt] = useState<number | null>(null);
  const [now, setNow] = useState(() => Date.now());

  useEffect(() => {
    let mounted = true;
    let controller: AbortController | null = null;

    async function refreshStatus() {
      controller?.abort();
      controller = new AbortController();
      const signal = controller.signal;
      const [apiResult, aiResult] = await Promise.allSettled([
        apiGet<{ status: string }>("/health", signal),
        apiGet<AIStatus>("/api/ai/status", signal),
      ]);
      if (!mounted || signal.aborted) return;
      setApiHealthy(apiResult.status === "fulfilled" ? apiResult.value.status === "ok" : false);
      setAiStatus(aiResult.status === "fulfilled" ? aiResult.value : null);
      const checkedAt = Date.now();
      setStatusCheckedAt(checkedAt);
      setNow(checkedAt);
    }

    void refreshStatus();
    const interval = window.setInterval(() => {
      setNow(Date.now());
      void refreshStatus();
    }, STATUS_REFRESH_MS);
    const onVisible = () => {
      if (document.visibilityState === "visible") void refreshStatus();
    };
    document.addEventListener("visibilitychange", onVisible);
    return () => {
      mounted = false;
      controller?.abort();
      window.clearInterval(interval);
      document.removeEventListener("visibilitychange", onVisible);
    };
  }, []);

  const groups = useMemo(
    () => GROUPS.map((group) => ({ ...group, items: group.items.filter((item) => !item.roles || (role ? item.roles.includes(role) : false)) })).filter((group) => group.items.length),
    [role]
  );

  const statusStale = statusCheckedAt !== null && now - statusCheckedAt > STATUS_STALE_MS;
  const aiReady = Boolean(aiStatus?.available && aiStatus?.model_available);
  const apiLabel = statusStale ? "API Status veraltet" : apiHealthy === null ? "API unbekannt" : apiHealthy ? "API verfügbar" : "API offline";
  const aiLabel = statusStale ? "Status veraltet" : aiStatus === null ? "Status unbekannt" : aiReady ? `${aiStatus.model} bereit` : aiStatus.message || "Nicht bereit";
  const statusTitle = `API: ${statusStale ? "veraltet" : apiHealthy === null ? "unbekannt" : apiHealthy ? "verfügbar" : "offline"} · KI: ${statusStale ? "veraltet" : aiStatus === null ? "unbekannt" : aiReady ? "bereit" : "nicht bereit"}`;

  return (
    <aside className="sidebar">
      <div className="sidebar-head">
        <Link href="/" className="brand" aria-label="MedFlux Startseite">
          <MedFluxLogo priority />
        </Link>
      </div>

      <nav className="side-nav-root" aria-label="Hauptnavigation">
        {groups.map((group) => (
          <div key={group.label} className="side-nav-group">
            <div className="nav-label sidebar-label-copy">{group.label}</div>
            <div className="side-nav">
              {group.items.map((item) => (
                <Link key={item.href} href={item.href} className={`nav-item${isActive(pathname, item.href) ? " active" : ""}`} aria-current={isActive(pathname, item.href) ? "page" : undefined}>
                  <span className="ico"><svg viewBox="0 0 24 24" aria-hidden="true">{icons[item.icon]}</svg></span>
                  <span className="sidebar-label-copy">{item.label}</span>
                </Link>
              ))}
              {group.label === "Administration" && account?.is_developer ? (
                <Link href="/developer" className={`nav-item${isActive(pathname, "/developer") || isActive(pathname, "/system/organizations") ? " active" : ""}`} aria-current={isActive(pathname, "/developer") ? "page" : undefined}>
                  <span className="ico"><svg viewBox="0 0 24 24" aria-hidden="true">{icons.admin}</svg></span>
                  <span className="sidebar-label-copy">Developer Dashboard</span>
                </Link>
              ) : null}
            </div>
          </div>
        ))}
      </nav>

      <div className="side-bottom">
        <div className="side-ai" title={statusTitle} aria-live="polite">
          <div className="side-ai-top"><b className="sidebar-label-copy">Systemstatus</b><div className="health"><span className="health-dot"/>{apiLabel}</div></div>
          <p className="sidebar-label-copy">KI: {aiLabel}</p>
        </div>
        <div className="org-card">
          <span className="org-avatar">{membership?.organization_name?.slice(0, 1).toUpperCase() ?? "M"}</span>
          <div className="sidebar-label-copy"><b>{membership?.organization_name ?? (account?.is_developer ? "Systemverwaltung" : "Krankenhaus")}</b><small>{membership ? `Arbeitsbereich ${membership.organization_slug}` : account?.is_developer ? "Developer" : "Arbeitsbereich"}</small></div>
        </div>
      </div>
    </aside>
  );
}
