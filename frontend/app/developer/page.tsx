"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { apiGet } from "@/lib/api";
import { useAuth } from "@/components/auth/AuthProvider";

type OrganizationItem = { id: string; name: string; slug: string };

export default function DeveloperDashboard() {
  const { account, selectOrganization } = useAuth();
  const [organizations, setOrganizations] = useState<OrganizationItem[]>([]);

  useEffect(() => {
    if (!account?.is_developer) return;
    apiGet<{ items: OrganizationItem[] }>("/api/system/organizations")
      .then((result) => setOrganizations(result.items))
      .catch(() => setOrganizations([]));
  }, [account?.is_developer]);

  if (!account?.is_developer) {
    return <section className="cw-section"><h2>Keine Berechtigung</h2><p className="cw-muted">Dieser Bereich ist ausschließlich für den Medflux Developer verfügbar.</p><Link href="/">Zur Übersicht</Link></section>;
  }

  return <div className="page org-settings-page">
    <div className="org-settings-head"><div><span>Systemverwaltung</span><h1>Developer Dashboard</h1><p>Zentrale Verwaltung aller Organisationen und systemweiten Funktionen.</p></div></div>
    <div className="org-settings-forms">
      <Link className="org-settings-card" href="/system/organizations"><h2>Organisationen</h2><p className="cw-muted">Organisationen anlegen, öffnen und verwalten.</p><strong>{organizations.length} Organisationen</strong></Link>
      <section className="org-settings-card"><h2>Developer</h2><p className="cw-muted">Systemweiter Vollzugriff auf alle Medflux-Organisationen.</p><strong>{account.display_name}</strong><small>{account.email}</small></section>
    </div>
    <section className="org-settings-list">
      <div className="org-settings-list-head"><h2>Organisationen</h2><Link href="/system/organizations">Verwalten</Link></div>
      {organizations.length === 0 ? <p>Noch keine Organisation angelegt.</p> : organizations.map((item) => <article className="org-hospital-row" key={item.id}><div className="org-hospital-title"><strong>{item.name}</strong><span>{item.slug}</span></div><button type="button" className="user-action" onClick={() => { selectOrganization(item.slug); window.location.href = "/"; }}>Öffnen</button></article>)}
    </section>
  </div>;
}
