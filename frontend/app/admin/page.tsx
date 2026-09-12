"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { useAuth } from "@/components/auth/AuthProvider";
import { apiGet } from "@/lib/api";
import { ORG_SLUG } from "@/components/ClientNav";
import type { ManagedUserDto } from "@/lib/auth-types";

export default function AdminPage() {
  const { account, membership, role } = useAuth();
  const [users, setUsers] = useState<ManagedUserDto[]>([]);
  const [healthy, setHealthy] = useState<boolean | null>(null);

  useEffect(() => {
    if (role !== "admin") return;
    apiGet<{ items: ManagedUserDto[] }>(`/api/users?organization_slug=${encodeURIComponent(ORG_SLUG)}`)
      .then((result) => setUsers(result.items))
      .catch(() => setUsers([]));
    apiGet<{ status: string }>("/health")
      .then((result) => setHealthy(result.status === "ok"))
      .catch(() => setHealthy(false));
  }, [role]);

  if (role !== "admin") {
    return <div className="page admin-dashboard"><section className="admin-denied"><h1>Keine Berechtigung</h1><p>Dieser Bereich ist nur für Administratoren verfügbar.</p><Link href="/">Zur Übersicht</Link></section></div>;
  }

  const activeUsers = users.filter((user) => user.is_active).length;

  return (
    <div className="page admin-dashboard">
      <section className="admin-hero">
        <div><span className="admin-kicker">Administration</span><h1>Admin Dashboard</h1><p>Zentrale Verwaltung der Medflux-Installation.</p></div>
        <div className="admin-identity"><span>{account?.display_name?.slice(0,1).toUpperCase() ?? "A"}</span><div><strong>{account?.display_name}</strong><small>{account?.email}</small></div></div>
      </section>

      <section className="admin-kpis">
        <article><span>Benutzer</span><strong>{users.length}</strong><small>{activeUsers} aktiv</small></article>
        <article><span>Systemstatus</span><strong>{healthy === null ? "Prüfe…" : healthy ? "Online" : "Offline"}</strong><small>Backend / API</small></article>
        <article><span>Arbeitsbereich</span><strong>{membership?.organization_name ?? "Krankenhaus"}</strong><small>{ORG_SLUG}</small></article>
      </section>

      <section className="admin-actions">
        <Link href="/settings/users"><div><strong>Benutzer & Rollen</strong><small>Konten, Rollen und Zugriffe verwalten</small></div><span>→</span></Link>
        <Link href="/audit"><div><strong>Audit</strong><small>Aktivitäten und Änderungen nachvollziehen</small></div><span>→</span></Link>
        <Link href="/settings"><div><strong>Systemeinstellungen</strong><small>KI, Verarbeitung und Diagnose</small></div><span>→</span></Link>
        <Link href="/contracts"><div><strong>Verträge</strong><small>Vertragsbestand öffnen</small></div><span>→</span></Link>
      </section>

      <section className="admin-panel">
        <div className="admin-panel-head"><div><h2>Benutzerübersicht</h2><p>Aktuelle Konten im Arbeitsbereich</p></div><Link href="/settings/users">Verwalten</Link></div>
        <div className="admin-user-list">
          {users.slice(0, 8).map((user) => <div className="admin-user-row" key={user.id}><span className="admin-user-avatar">{user.display_name.slice(0,1).toUpperCase()}</span><div><strong>{user.display_name}</strong><small>{user.email}</small></div><span className="admin-role-chip">{user.role}</span><span className={`admin-user-state${user.is_active ? "" : " off"}`}>{user.is_active ? "Aktiv" : "Inaktiv"}</span></div>)}
        </div>
      </section>
    </div>
  );
}
