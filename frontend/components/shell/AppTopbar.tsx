"use client";

import Link from "next/link";
import { FormEvent, useState } from "react";
import { usePathname, useRouter } from "next/navigation";
import OrganizationScopePicker from "@/components/OrganizationScopePicker";
import { useAuth } from "@/components/auth/AuthProvider";
import { ROLE_LABELS } from "@/lib/auth-types";

function titleForPath(pathname: string) {
  if (pathname.startsWith("/contracts/")) return "Vertrag 360";
  if (pathname === "/contracts") return "Verträge";
  if (pathname === "/work-queue") return "To-dos";
  if (pathname === "/import") return "Import";
  if (pathname === "/review") return "Prüfungen";
  if (pathname === "/nachweise") return "Nachweise";
  if (pathname === "/audit") return "Audit";
  if (pathname === "/archiv") return "Archiv";
  if (pathname === "/admin") return "Admin Dashboard";
  if (pathname === "/developer/components") return "UI-Komponenten";
  if (pathname === "/developer") return "Developer Dashboard";
  if (pathname.startsWith("/system/organizations")) return "Organisationen";
  if (pathname === "/profile") return "Mein Profil";
  if (pathname.startsWith("/settings/users")) return "Benutzer";
  if (pathname.startsWith("/settings/organization")) return "Organisation";
  if (pathname === "/settings") return "Einstellungen";
  return "Medflux";
}

export default function AppTopbar() {
  const pathname = usePathname();
  const router = useRouter();
  const { account, membership, role, logout } = useAuth();
  const [query, setQuery] = useState("");
  const showTitle = pathname !== "/";

  function submit(event: FormEvent) {
    event.preventDefault();
    const value = query.trim();
    router.push(value ? `/contracts?q=${encodeURIComponent(value)}` : "/contracts");
  }

  return (
    <header className="topbar">
      <div className="page-title">{showTitle ? <h1>{titleForPath(pathname)}</h1> : null}</div>
      <div className="top-actions">
        {membership ? <OrganizationScopePicker /> : null}
        <form className="search" onSubmit={submit} role="search" aria-label="Verträge durchsuchen">
          <label className="visually-hidden" htmlFor="global-contract-search">Vertragsnummer suchen</label>
          <input id="global-contract-search" type="search" placeholder="Vertragsnummer …" value={query} onChange={(event) => setQuery(event.target.value)} />
        </form>
        {account && role ? (
          <details className="account-menu">
            <summary className="top-user" aria-label="Kontomenü öffnen">
              <span className="top-user-avatar">{account.display_name.slice(0, 1).toUpperCase()}</span>
              <span className="top-user-copy"><strong>{account.display_name}</strong><small>{account.is_developer ? "Developer" : ROLE_LABELS[role]}</small></span>
            </summary>
            <div className="account-menu-panel">
              <div className="account-menu-identity">
                <strong>{account.display_name}</strong>
                <small>{account.email}</small>
              </div>
              <Link href="/profile">Mein Profil</Link>
              {account.is_developer ? <Link href="/developer">Developer Dashboard</Link> : null}
              {account.is_developer ? <Link href="/developer/components">UI-Komponenten</Link> : null}
              {role === "admin" && membership ? <Link href="/settings/users">Benutzer verwalten</Link> : null}
              <button type="button" onClick={() => void logout()}>Abmelden</button>
            </div>
          </details>
        ) : null}
      </div>
    </header>
  );
}
