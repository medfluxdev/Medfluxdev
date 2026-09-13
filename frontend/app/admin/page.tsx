"use client";

import Link from "next/link";
import { useCallback, useEffect, useMemo, useState } from "react";
import { useAuth } from "@/components/auth/AuthProvider";
import { apiGet } from "@/lib/api";
import type { ManagedUserDto } from "@/lib/auth-types";
import { ROLE_LABELS } from "@/lib/auth-types";
import type { DashboardOverview } from "@/lib/dashboard-types";
import { formatISODateOnly } from "@/lib/format";
import styles from "./admin.module.css";

type ActivityItem = { id: string; display_name: string | null; event_name: string; object_type: string; created_at: string | null };

const EVENT_LABELS: Record<string, string> = {
  "account.created": "Benutzer angelegt",
  "account.updated": "Benutzer geändert",
  "contract.archived": "Vertrag archiviert",
  "contract.unarchived": "Vertrag wiederhergestellt",
  "override.set": "Vertragsangabe geändert",
  "override.remove": "Manuelle Änderung entfernt",
};

export default function AdminPage() {
  const { account, membership, role } = useAuth();
  const [users, setUsers] = useState<ManagedUserDto[]>([]);
  const [overview, setOverview] = useState<DashboardOverview | null>(null);
  const [activity, setActivity] = useState<ActivityItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(async () => {
    if (role !== "admin" || !membership) return;
    setLoading(true); setError(null);
    const slug = encodeURIComponent(membership.organization_slug);
    try {
      const [userResult, dashboardResult, activityResult] = await Promise.all([
        apiGet<{ items: ManagedUserDto[] }>(`/api/users?organization_slug=${slug}`),
        apiGet<DashboardOverview>(`/api/dashboard/overview?organization_slug=${slug}&as_of_date=${formatISODateOnly(new Date())}`),
        apiGet<{ items: ActivityItem[] }>(`/api/activity?organization_slug=${slug}&limit=8`),
      ]);
      setUsers(userResult.items); setOverview(dashboardResult); setActivity(activityResult.items);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Admin Dashboard konnte nicht geladen werden.");
    } finally { setLoading(false); }
  }, [membership, role]);

  useEffect(() => { void load(); }, [load]);
  const activeUsers = useMemo(() => users.filter((user) => user.is_active).length, [users]);
  const reviews = overview?.data_quality.reduce((sum, item) => sum + item.count, 0) ?? 0;

  if (account?.is_developer || role !== "admin") {
    return <div className={styles.page}><section className={styles.denied}><h1>Keine Berechtigung</h1><p>Dieses Dashboard ist ausschließlich für Organisationsadministratoren verfügbar.</p><Link href={account?.is_developer ? "/developer" : "/"}>Zur Übersicht</Link></section></div>;
  }

  return <div className={styles.page}>
    <section className={styles.hero}>
      <div><span className={styles.kicker}>Organisation verwalten</span><h1>Admin Dashboard</h1><p>{membership?.organization_name ?? "Medflux"}: Verträge, Aufgaben, Benutzer und Aktivitäten auf einen Blick.</p></div>
      <div className={styles.identity}><span>{account?.display_name?.slice(0, 1).toUpperCase() ?? "A"}</span><div><strong>{account?.display_name}</strong><small>Administrator · {account?.email}</small></div></div>
    </section>

    {error ? <div className={styles.error} role="alert"><span>{error}</span><button type="button" onClick={() => void load()}>Erneut laden</button></div> : null}
    {loading ? <div className={styles.loading}>Admin Dashboard wird geladen…</div> : null}

    {!loading ? <>
      <section className={styles.kpis} aria-label="Administrationskennzahlen">
        <article><span>Offene Aufgaben</span><strong>{overview?.total_action_items ?? 0}</strong><small>priorisierte Handlungspunkte</small></article>
        <article><span>Manuelle Prüfungen</span><strong>{reviews}</strong><small>Angaben mit Prüfbedarf</small></article>
        <article><span>Benutzer</span><strong>{activeUsers}</strong><small>{users.length} Konten insgesamt</small></article>
        <article><span>Arbeitsbereich</span><strong>{membership?.organization_name ?? "–"}</strong><small>{membership?.organization_slug}</small></article>
      </section>

      <section className={styles.actions} aria-label="Schnellzugriffe">
        <Link href="/contracts"><div><strong>Verträge verwalten</strong><small>Bestand, Zuordnung und Verantwortliche</small></div><span>→</span></Link>
        <Link href="/work-queue"><div><strong>Aufgaben bearbeiten</strong><small>Fristen, Risiken und offene Entscheidungen</small></div><span>→</span></Link>
        <Link href="/settings/users"><div><strong>Benutzer & Rollen</strong><small>Konten und Zugriffsbereiche verwalten</small></div><span>→</span></Link>
        <Link href="/audit"><div><strong>Audit öffnen</strong><small>Änderungen nachvollziehen</small></div><span>→</span></Link>
      </section>

      <div className={styles.columns}>
        <section className={styles.panel}>
          <div className={styles.panelHead}><div><h2>Letzte Aktivitäten</h2><p>Aktuelle Änderungen in dieser Organisation</p></div><Link href="/audit">Alle anzeigen</Link></div>
          <div className={styles.activityList}>{activity.length === 0 ? <p className={styles.empty}>Noch keine Aktivitäten vorhanden.</p> : activity.map((item) => <div className={styles.activityRow} key={item.id}><span className={styles.activityDot}/><div><strong>{EVENT_LABELS[item.event_name] ?? item.event_name}</strong><small>{item.display_name ?? "System"} · {item.object_type}</small></div><time>{item.created_at ? new Intl.DateTimeFormat("de-DE", { dateStyle: "short", timeStyle: "short" }).format(new Date(item.created_at)) : "–"}</time></div>)}</div>
        </section>
        <section className={styles.panel}>
          <div className={styles.panelHead}><div><h2>Benutzerübersicht</h2><p>Konten im aktuellen Arbeitsbereich</p></div><Link href="/settings/users">Verwalten</Link></div>
          <div className={styles.userList}>{users.length === 0 ? <p className={styles.empty}>Noch keine Benutzer vorhanden.</p> : users.slice(0, 6).map((user) => <div className={styles.userRow} key={user.id}><span className={styles.userAvatar}>{user.display_name.slice(0, 1).toUpperCase()}</span><div><strong>{user.display_name}</strong><small>{user.email}</small></div><span className={styles.roleChip}>{ROLE_LABELS[user.role]}</span><span className={`${styles.userState}${user.is_active ? "" : ` ${styles.off}`}`}>{user.is_active ? "Aktiv" : "Inaktiv"}</span></div>)}</div>
        </section>
      </div>
    </> : null}
  </div>;
}
