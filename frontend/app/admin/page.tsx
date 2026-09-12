"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { useAuth } from "@/components/auth/AuthProvider";
import { apiGet } from "@/lib/api";
import { ORG_SLUG } from "@/components/ClientNav";
import { ROLE_LABELS, type ManagedUserDto } from "@/lib/auth-types";
import styles from "./admin.module.css";

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
    return <div className={styles.page}><section className={styles.denied}><h1>Keine Berechtigung</h1><p>Dieser Bereich ist nur für Administratoren verfügbar.</p><Link href="/">Zur Übersicht</Link></section></div>;
  }

  const activeUsers = users.filter((user) => user.is_active).length;

  return (
    <div className={styles.page}>
      <section className={styles.hero}>
        <div><span className={styles.kicker}>Administration</span><h1>Admin Dashboard</h1><p>Zentrale Verwaltung der Medflux-Installation.</p></div>
        <div className={styles.identity}><span>{account?.display_name?.slice(0,1).toUpperCase() ?? "A"}</span><div><strong>{account?.display_name}</strong><small>{account?.email}</small></div></div>
      </section>

      <section className={styles.kpis}>
        <article><span>Benutzer</span><strong>{users.length}</strong><small>{activeUsers} aktiv</small></article>
        <article><span>Systemstatus</span><strong>{healthy === null ? "Prüfe…" : healthy ? "Online" : "Offline"}</strong><small>Backend / API</small></article>
        <article><span>Arbeitsbereich</span><strong>{membership?.organization_name ?? "Krankenhaus"}</strong><small>{ORG_SLUG}</small></article>
      </section>

      <section className={styles.actions}>
        <Link href="/settings/users"><div><strong>Benutzer & Rollen</strong><small>Konten, Rollen und Zugriffe verwalten</small></div><span>→</span></Link>
        <Link href="/audit"><div><strong>Audit</strong><small>Aktivitäten und Änderungen nachvollziehen</small></div><span>→</span></Link>
        <Link href="/settings"><div><strong>Systemeinstellungen</strong><small>KI, Verarbeitung und Diagnose</small></div><span>→</span></Link>
        <Link href="/contracts"><div><strong>Verträge</strong><small>Vertragsbestand öffnen</small></div><span>→</span></Link>
      </section>

      <section className={styles.panel}>
        <div className={styles.panelHead}><div><h2>Benutzerübersicht</h2><p>Aktuelle Konten im Arbeitsbereich</p></div><Link href="/settings/users">Verwalten</Link></div>
        <div className={styles.userList}>
          {users.slice(0, 8).map((user) => <div className={styles.userRow} key={user.id}><span className={styles.userAvatar}>{user.display_name.slice(0,1).toUpperCase()}</span><div><strong>{user.display_name}</strong><small>{user.email}</small></div><span className={styles.roleChip}>{ROLE_LABELS[user.role]}</span><span className={`${styles.userState}${user.is_active ? "" : ` ${styles.off}`}`}>{user.is_active ? "Aktiv" : "Inaktiv"}</span></div>)}
        </div>
      </section>
    </div>
  );
}
