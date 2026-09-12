"use client";

import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { type FormEvent, useEffect, useMemo, useState } from "react";
import { apiGet } from "@/lib/api";
import { useAuth } from "@/components/auth/AuthProvider";
import OrganizationScopePicker from "@/components/OrganizationScopePicker";
import { ROLE_LABELS, type AccountRole } from "@/lib/auth-types";

export const ORG_SLUG = process.env.NEXT_PUBLIC_ORG_SLUG ?? "krankenhaus";

type Icon = React.ReactNode;
type NavItem = { label: string; href: string; icon: keyof typeof ic; roles?: AccountRole[] };

const ic: Record<string, Icon> = {
  dashboard: <path d="M4 12h5l3-7 3 14 2-7h3" />,
  admin: <><rect x="4" y="4" width="16" height="16" rx="3" /><path d="M8 15v-3M12 15V8M16 15v-5" /></>,
  contracts: <><path d="M6 3h8l4 4v14H6z" /><path d="M14 3v5h5" /></>,
  workQueue: <><path d="M5 5h14v14H5z" /><path d="M8 9h8M8 13h5" /></>,
  import: <path d="M12 3v18M3 12h18" />,
  review: <><circle cx="10" cy="10" r="6" /><path d="m15 15 5 5" /></>,
  evidence: <><path d="M4 5h16v14H4z" /><path d="M8 9h8M8 13h5" /></>,
  audit: <><path d="M5 20V4h14v16z" /><path d="M8 8h8M8 12h8M8 16h5" /></>,
  archive: <><path d="M4 8h16v12H4z" /><path d="M7 8V4h10v4" /><path d="M9 12h6" /></>,
  settings: <><circle cx="12" cy="12" r="3" /><path d="M19 12a7 7 0 0 0-.1-1l2-1.5-2-3.4-2.4 1a7 7 0 0 0-1.7-1L14.5 3h-5l-.4 3.1a7 7 0 0 0-1.7 1l-2.4-1-2 3.4L5 11a7 7 0 0 0 0 2l-2 1.5 2 3.4 2.4-1a7 7 0 0 0 1.7 1l.4 3.1h5l.4-3.1a7 7 0 0 0 1.7-1l2.4 1 2-3.4L19 13a7 7 0 0 0 0-1z" /></>,
};

const EDITORS: AccountRole[] = ["admin", "contract_manager"];
const REVIEWERS: AccountRole[] = ["admin", "contract_manager", "reviewer"];
const GROUPS: { label: string; items: NavItem[] }[] = [
  { label: "Arbeitsbereich", items: [
    { label: "Übersicht", href: "/", icon: "dashboard" },
    { label: "Verträge", href: "/contracts", icon: "contracts" },
    { label: "To-dos", href: "/work-queue", icon: "workQueue", roles: REVIEWERS },
    { label: "Import", href: "/import", icon: "import", roles: EDITORS },
  ]},
  { label: "Kontrolle", items: [
    { label: "Prüfungen", href: "/review", icon: "review", roles: REVIEWERS },
    { label: "Nachweise", href: "/nachweise", icon: "evidence" },
    { label: "Audit", href: "/audit", icon: "audit", roles: EDITORS },
    { label: "Archiv", href: "/archiv", icon: "archive", roles: EDITORS },
  ]},
  { label: "System", items: [
    { label: "Admin Dashboard", href: "/admin", icon: "admin", roles: ["admin"] },
    { label: "Organisation", href: "/settings/organization", icon: "settings", roles: ["admin"] },
    { label: "Einstellungen", href: "/settings", icon: "settings", roles: ["admin"] },
  ] },
];

export const NAV_ITEMS: NavItem[] = GROUPS.flatMap((group) => group.items);

function isActive(pathname: string, href: string): boolean {
  if (href === "/") return pathname === "/";
  return pathname === href || pathname.startsWith(`${href}/`);
}

function titleForPath(pathname: string): string {
  if (pathname.startsWith("/contracts/")) return "Vertrag 360";
  if (pathname === "/contracts") return "Verträge";
  if (pathname === "/work-queue") return "To-dos";
  if (pathname === "/import") return "Import";
  if (pathname === "/review") return "Prüfungen";
  if (pathname === "/nachweise") return "Nachweise";
  if (pathname === "/audit") return "Audit";
  if (pathname === "/archiv") return "Archiv";
  if (pathname === "/admin") return "Admin Dashboard";
  if (pathname === "/profile") return "Mein Profil";
  if (pathname === "/system/organizations") return "Organisationen";
  if (pathname.startsWith("/settings/organization")) return "Organisation";
  if (pathname.startsWith("/settings/users")) return "Benutzer";
  if (pathname === "/settings") return "Einstellungen";
  return "Medflux";
}

function Sidebar() {
  const pathname = usePathname();
  const { account, membership, role, logout } = useAuth();
  const [healthy, setHealthy] = useState<boolean | null>(null);

  useEffect(() => {
    let mounted = true;
    apiGet<{ status: string }>("/health")
      .then((h) => mounted && setHealthy(h.status === "ok"))
      .catch(() => mounted && setHealthy(false));
    return () => { mounted = false; };
  }, []);

  const visibleGroups = useMemo(() => GROUPS.map((group) => ({
    ...group,
    items: group.items.filter((item) => !item.roles || (role ? item.roles.includes(role) : false)),
  })).filter((group) => group.items.length > 0), [role]);

  return (
    <aside className="sidebar">
      <Link href="/" className="brand" aria-label="Medflux Startseite">
        <span className="logo" aria-hidden="true" />
        <span><strong>Medflux</strong><small>Intelligentes Vertragsmanagement</small></span>
      </Link>
      <nav className="side-nav-root" aria-label="Hauptnavigation">
        {visibleGroups.map((group) => (
          <div key={group.label}>
            <div className="nav-label">{group.label}</div>
            <div className="side-nav" role="group" aria-label={group.label}>
              {group.items.map((item) => {
                const active = isActive(pathname, item.href);
                return <Link key={item.href} href={item.href} className={`nav-item${active ? " active" : ""}`} aria-current={active ? "page" : undefined}><span className="ico"><svg viewBox="0 0 24 24" aria-hidden="true">{ic[item.icon]}</svg></span>{item.label}</Link>;
              })}
              {group.label === "System" && account?.is_developer ? <Link href="/system/organizations" className={`nav-item${isActive(pathname, "/system/organizations") ? " active" : ""}`}><span className="ico"><svg viewBox="0 0 24 24" aria-hidden="true">{ic.admin}</svg></span>Organisationen</Link> : null}
            </div>
          </div>
        ))}
      </nav>
      <div className="side-bottom">
        <div className="side-ai">
          <div className="side-ai-top"><b>Lokale KI</b><div className="health"><span className="health-dot" aria-hidden="true" />{healthy === null ? "Prüfe…" : healthy ? "Gesund" : "Offline"}</div></div>
          <p>Lokale Verarbeitung<br />Keine externen Modellaufrufe</p>
        </div>
        <div className="org-card">
          <span className="org-avatar" aria-hidden="true">{membership?.organization_name?.slice(0, 1).toUpperCase() ?? "M"}</span>
          <div><b>{membership?.organization_name ?? (account?.is_developer ? "Systemverwaltung" : "Krankenhaus")}</b><small>{membership ? `Arbeitsbereich ${membership.organization_slug}` : account?.is_developer ? "Developer" : `Arbeitsbereich ${ORG_SLUG}`}</small></div>
        </div>
        {account && role ? <div className="account-card account-card-prominent">
          <span className="account-card-label">Angemeldet als</span>
          <strong>{account.display_name}</strong>
          <small>{account.is_developer ? "Developer · Systemzugriff" : ROLE_LABELS[role]}</small>
          <small>{account.email}</small>
          <div className="account-card-actions">
            {account.is_developer ? <Link href="/system/organizations">Organisationen verwalten</Link> : null}
            {role === "admin" && membership ? <Link href="/admin">Admin Dashboard</Link> : null}
            {role === "admin" && membership ? <Link href="/settings/users">Benutzer verwalten</Link> : null}
            <button type="button" onClick={() => void logout()}>Abmelden</button>
          </div>
        </div> : <Link className="sidebar-login-btn" href="/login">Anmelden</Link>}
      </div>
    </aside>
  );
}

function Topbar() {
  const pathname = usePathname();
  const router = useRouter();
  const { account, membership, role, logout } = useAuth();
  const [q, setQ] = useState("");
  const showSectionTitle = pathname !== "/";
  const showImportButton = pathname !== "/" && role != null && EDITORS.includes(role) && Boolean(membership);
  function onSubmit(e: FormEvent) { e.preventDefault(); const term = q.trim(); router.push(term ? `/contracts?q=${encodeURIComponent(term)}` : "/contracts"); }
  return <header className="topbar"><div className="page-title">{showSectionTitle ? <h1>{titleForPath(pathname)}</h1> : null}</div><div className="top-actions">{membership ? <OrganizationScopePicker /> : null}<form className="search" onSubmit={onSubmit} role="search"><svg viewBox="0 0 24 24" aria-hidden="true"><circle cx="10" cy="10" r="6" /><path d="m15 15 5 5" /></svg><input type="search" aria-label="Globale Suche" placeholder="Vertragsnummer, Lieferant, Gerät …" value={q} onChange={(e) => setQ(e.target.value)} /></form>{showImportButton ? <Link className="import-btn" href="/import">Vertrag importieren</Link> : null}{account && role ? <div className="top-user"><Link href="/profile" className="top-user-profile" aria-label="Mein Profil öffnen"><span className="top-user-avatar" aria-hidden="true">{account.display_name.slice(0,1).toUpperCase()}</span><span className="top-user-copy"><strong>{account.display_name}</strong><small>{account.is_developer ? "Developer" : ROLE_LABELS[role]}</small></span></Link><button type="button" className="top-logout-btn" onClick={() => void logout()}>Abmelden</button></div> : <Link className="top-login-btn" href="/login">Anmelden</Link>}</div></header>;
}

export default function ClientNav({ children }: { children: React.ReactNode }) {
  const pathname = usePathname();
  const { account, loading } = useAuth();
  if (pathname === "/login" || pathname === "/select-organization") return <>{children}</>;
  if (loading) return <div className="auth-loading">Medflux wird geladen…</div>;
  if (!account) return <div className="auth-login-required"><p>Sie sind nicht angemeldet.</p><Link href="/login">Anmelden</Link></div>;
  return <div className="app"><Sidebar /><main className="main" id="main-content"><Topbar />{children}</main></div>;
}
