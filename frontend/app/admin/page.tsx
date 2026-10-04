"use client";

import Link from "next/link";
import { useCallback, useEffect, useMemo, useState } from "react";
import { useAuth } from "@/components/auth/AuthProvider";
import type { ManagedUserDto } from "@/lib/auth-types";
import { ROLE_LABELS } from "@/lib/auth-types";
import type { DashboardOverview } from "@/lib/dashboard-types";
import { formatISODateOnly } from "@/lib/format";
import { listUsers } from "@/lib/domain-api/users";
import { getDashboardOverview } from "@/lib/domain-api/dashboard";
import { listActivity, type ActivityDto } from "@/lib/domain-api/activity";
import { downloadContractsCsv } from "@/lib/domain-api/operations";
import { getContractDeletionCapabilities } from "@/lib/domain-api/contracts";
import { listIntelligenceEvents, type IntelligenceEventItem } from "@/lib/domain-api/intelligence";
import JobMonitorPanel from "@/components/deadlines/JobMonitorPanel";
import styles from "./admin.module.css";

const EVENT_LABELS: Record<string, string> = {
  "account.created": "Benutzer angelegt",
  "account.updated": "Benutzer geändert",
  "account.scope_updated": "Benutzerbereich geändert",
  "contract.archived": "Vertrag archiviert",
  "contract.unarchived": "Vertrag aus Archiv wiederhergestellt",
  "contract.deletion_requested": "Vertragslöschung beantragt",
  "contract.deletion_cancelled": "Vertragslöschung abgebrochen",
  "contract.deletion_confirmed": "Vertragslöschung bestätigt",
  "contract.restored": "Gelöschten Vertrag wiederhergestellt",
  "contract.ownership_updated": "Vertragszuordnung geändert",
  "equipment.ownership_updated": "Gerätezuordnung geändert",
  "override.set": "Vertragsangabe geändert",
  "override.void": "Manuelle Änderung entfernt",
  "work_item.acknowledged": "Aufgabe übernommen",
  "work_item.resolved": "Aufgabe erledigt",
  "contracts.exported": "Verträge exportiert",
};

export default function AdminPage() {
  const { account, membership, role } = useAuth();
  const [users, setUsers] = useState<ManagedUserDto[]>([]);
  const [overview, setOverview] = useState<DashboardOverview | null>(null);
  const [activity, setActivity] = useState<ActivityDto[]>([]);
  const [intelligenceEvents, setIntelligenceEvents] = useState<IntelligenceEventItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [exporting, setExporting] = useState(false);
  const [deletionAllowed, setDeletionAllowed] = useState(false);

  useEffect(() => {
    let active = true;
    setDeletionAllowed(false);
    if (role === "admin" && membership?.organization_slug) {
      getContractDeletionCapabilities(membership.organization_slug)
        .then((capability) => { if (active) setDeletionAllowed(capability.can_delete); })
        .catch(() => { if (active) setDeletionAllowed(false); });
    }
    return () => { active = false; };
  }, [role, membership?.organization_slug]);

  const load = useCallback(async () => {
    if (role !== "admin" || !membership) return;
    setLoading(true); setError(null);
    try {
      const [userResult, dashboardResult, activityResult, intelligenceResult] = await Promise.all([
        listUsers(membership.organization_slug),
        getDashboardOverview(membership.organization_slug, formatISODateOnly(new Date())),
        listActivity(membership.organization_slug, { limit: 8 }),
        listIntelligenceEvents(membership.organization_slug, 8),
      ]);
      setUsers(userResult.items);
      setOverview(dashboardResult);
      setActivity(activityResult.items);
      setIntelligenceEvents(intelligenceResult.items);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Admin Dashboard konnte nicht geladen werden.");
    } finally { setLoading(false); }
  }, [membership, role]);

  useEffect(() => { void load(); }, [load]);
  const activeUsers = useMemo(() => users.filter((user) => user.is_active).length, [users]);
  const reviews = overview?.data_quality.reduce((sum, item) => sum + item.count, 0) ?? 0;

  const exportContracts = useCallback(async () => {
    if (!membership || exporting) return;
    setExporting(true);
    setError(null);
    try {
      const { blob, filename } = await downloadContractsCsv(membership.organization_slug, true);
      const url = URL.createObjectURL(blob);
      const anchor = document.createElement("a");
      anchor.href = url;
      anchor.download = filename ?? `medflux-vertraege-${membership.organization_slug}.csv`;
      document.body.appendChild(anchor);
      anchor.click();
      anchor.remove();
      URL.revokeObjectURL(url);
      await load();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Export konnte nicht erstellt werden.");
    } finally {
      setExporting(false);
    }
  }, [exporting, load, membership]);

  if (role !== "admin" || !membership) {
    return <div className={styles.page}><section className={styles.denied}><h1>Keine Berechtigung</h1><p>Bitte wählen Sie zuerst eine Organisation mit Administratorzugriff aus.</p><Link href={account?.is_developer ? "/developer" : "/"}>Zur Übersicht</Link></section></div>;
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
        <article><span>Intelligence Events</span><strong>{intelligenceEvents.length}</strong><small>zuletzt sichtbare Ereignisse</small></article>
      </section>

      <section className={styles.actions} aria-label="Schnellzugriffe">
        <Link href="/contracts"><div><strong>Verträge verwalten</strong><small>Bestand, Zuordnung und Verantwortliche</small></div><span>→</span></Link>
        <Link href="/work-queue"><div><strong>Aufgaben bearbeiten</strong><small>Fristen, Risiken und offene Entscheidungen</small></div><span>→</span></Link>
        <Link href="/settings/users"><div><strong>Benutzer & Rollen</strong><small>Konten und Zugriffsbereiche verwalten</small></div><span>→</span></Link>
        <Link href="/settings/roles"><div><strong>Rollen & Rechte</strong><small>Was jede Rolle darf</small></div><span>→</span></Link>
        <Link href="/settings/catalogs"><div><strong>Kataloge & Nummernkreis</strong><small>Vertragstypen, Auswahllisten, Vertragsnummern</small></div><span>→</span></Link>
        {deletionAllowed && <Link href="/admin/deletion"><div><strong>Vertragslöschung</strong><small>Vorgemerkte Verträge prüfen und wiederherstellen</small></div><span>→</span></Link>}
        <Link href="/audit"><div><strong>Audit öffnen</strong><small>Änderungen nachvollziehen</small></div><span>→</span></Link>
        <button type="button" onClick={() => void exportContracts()} disabled={exporting}><div><strong>Verträge exportieren</strong><small>Scope-gefilterte CSV mit aktuellem Vertragsbestand</small></div><span>{exporting ? "…" : "↓"}</span></button>
      </section>

      <div className={styles.columns}>
        <section className={styles.panel}>
          <div className={styles.panelHead}><div><h2>Letzte Aktivitäten</h2><p>Authentifizierte Änderungen in dieser Organisation</p></div><Link href="/audit">Alle anzeigen</Link></div>
          <div className={styles.activityList}>{activity.length === 0 ? <p className={styles.empty}>Noch keine Aktivitäten vorhanden.</p> : activity.map((item) => <div className={styles.activityRow} key={item.id}><span className={styles.activityDot}/><div><strong>{EVENT_LABELS[item.event_name] ?? item.event_name}</strong><small>{item.display_name ?? "System"} · {item.object_type}</small></div><time>{item.created_at ? new Intl.DateTimeFormat("de-DE", { dateStyle: "short", timeStyle: "short" }).format(new Date(item.created_at)) : "–"}</time></div>)}</div>
        </section>
        <section className={styles.panel}>
          <div className={styles.panelHead}><div><h2>Intelligence Events</h2><p>Backend-Ereignisse im aktuell sichtbaren Vertragsbereich</p></div></div>
          <div className={styles.activityList}>{intelligenceEvents.length === 0 ? <p className={styles.empty}>Keine Intelligence Events vorhanden.</p> : intelligenceEvents.map((item) => <div className={styles.activityRow} key={item.id}><span className={styles.activityDot}/><div><strong>{item.event_type}</strong><small>{item.contract_id ? `Vertrag ${item.contract_id.slice(0, 8)}…` : "Organisationsereignis"}</small></div><time>{item.occurred_at ? new Intl.DateTimeFormat("de-DE", { dateStyle: "short", timeStyle: "short" }).format(new Date(item.occurred_at)) : "–"}</time></div>)}</div>
        </section>
        <section className={styles.panel}>
          <div className={styles.panelHead}><div><h2>Benutzerübersicht</h2><p>Konten im aktuellen Arbeitsbereich</p></div><Link href="/settings/users">Verwalten</Link></div>
          <div className={styles.userList}>{users.length === 0 ? <p className={styles.empty}>Noch keine Benutzer vorhanden.</p> : users.slice(0, 6).map((user) => <div className={styles.userRow} key={user.id}><span className={styles.userAvatar}>{user.display_name.slice(0, 1).toUpperCase()}</span><div><strong>{user.display_name}</strong><small>{user.email}</small></div><span className={styles.roleChip}>{ROLE_LABELS[user.role]}</span><span className={`${styles.userState}${user.is_active ? "" : ` ${styles.off}`}`}>{user.is_active ? "Aktiv" : "Inaktiv"}</span></div>)}</div>
        </section>
      </div>
      {membership?.organization_slug ? <JobMonitorPanel organizationSlug={membership.organization_slug} /> : null}
    </> : null}
  </div>;
}
