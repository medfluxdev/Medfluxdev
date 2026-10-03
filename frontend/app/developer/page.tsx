"use client";

import Link from "next/link";
import { FormEvent, useCallback, useEffect, useState } from "react";
import { apiGet, apiPost } from "@/lib/api";
import { useAuth } from "@/components/auth/AuthProvider";
import DeleteOrganizationButton from "@/components/developer/DeleteOrganizationButton";
import styles from "./developer.module.css";

type OrganizationItem = { id: string; name: string; slug: string };
type SystemStatus = { app_name: string; app_version: string; api: "online"; database: "online"; database_engine: string; authentication: boolean; organization_count: number };
type AIStatus = { available: boolean; model: string | null; model_available: boolean; message: string };

export default function DeveloperDashboard() {
  const { account, refresh, selectOrganization } = useAuth();
  const [organizations, setOrganizations] = useState<OrganizationItem[]>([]);
  const [system, setSystem] = useState<SystemStatus | null>(null);
  const [ai, setAi] = useState<AIStatus | null>(null);
  const [name, setName] = useState(""); const [slug, setSlug] = useState("");
  const [busy, setBusy] = useState(false); const [loading, setLoading] = useState(true);
  const [message, setMessage] = useState<{ error: boolean; text: string } | null>(null);

  const load = useCallback(async () => {
    if (!account?.is_developer) return;
    setLoading(true);
    try {
      const [orgResult, statusResult, aiResult] = await Promise.all([
        apiGet<{ items: OrganizationItem[] }>("/api/system/organizations"),
        apiGet<SystemStatus>("/api/system/organizations/status"),
        apiGet<AIStatus>("/api/ai/status"),
      ]);
      setOrganizations(orgResult.items); setSystem(statusResult); setAi(aiResult);
    } catch (error) {
      setMessage({ error: true, text: error instanceof Error ? error.message : "Systemstatus konnte nicht geladen werden." });
    } finally { setLoading(false); }
  }, [account?.is_developer]);

  useEffect(() => { void load(); }, [load]);

  async function createOrganization(event: FormEvent) {
    event.preventDefault(); setBusy(true); setMessage(null);
    try {
      const created = await apiPost<OrganizationItem>("/api/system/organizations", { name, slug });
      setName(""); setSlug(""); setMessage({ error: false, text: "Organisation wurde angelegt." });
      await refresh(); await load(); selectOrganization(created.slug);
    } catch (error) { setMessage({ error: true, text: error instanceof Error ? error.message : "Organisation konnte nicht angelegt werden." }); }
    finally { setBusy(false); }
  }

  function openOrganization(item: OrganizationItem, target: string) { selectOrganization(item.slug); window.location.href = target; }

  if (!account?.is_developer) return <section className="cw-section"><h2>Keine Berechtigung</h2><p className="cw-muted">Dieser Bereich ist ausschließlich für den Medflux Developer verfügbar.</p><Link href="/">Zur Übersicht</Link></section>;

  return <div className={styles.page}>
    <section className={styles.hero}><div><span>Systemverwaltung</span><h1>Developer Dashboard</h1><p>Technischer Zustand, lokale KI und alle Medflux-Organisationen.</p></div><button type="button" onClick={() => void load()} disabled={loading}>{loading ? "Prüfe…" : "Status aktualisieren"}</button></section>
    {message?.text ? <div className={`${styles.message}${message.error ? ` ${styles.messageError}` : ""}`} role="status">{message.text}</div> : null}

    <section className={styles.statusGrid} aria-label="Systemstatus">
      <article><span className={`${styles.dot} ${system ? styles.ok : styles.wait}`}/><div><small>API</small><strong>{system ? "Online" : loading ? "Prüfe…" : "Nicht verfügbar"}</strong><p>{system ? `${system.app_name} ${system.app_version}` : "Keine Statusdaten"}</p></div></article>
      <article><span className={`${styles.dot} ${system ? styles.ok : styles.wait}`}/><div><small>Datenbank</small><strong>{system?.database === "online" ? "Online" : loading ? "Prüfe…" : "Nicht verfügbar"}</strong><p>{system?.database_engine ?? "–"}</p></div></article>
      <article><span className={`${styles.dot} ${ai?.available && ai.model_available ? styles.ok : styles.warn}`}/><div><small>Lokale KI</small><strong>{ai?.available && ai.model_available ? "Bereit" : "Nicht bereit"}</strong><p>{ai?.model ?? ai?.message ?? "–"}</p></div></article>
      <article><span className={`${styles.dot} ${system?.authentication ? styles.ok : styles.warn}`}/><div><small>Sicherheit</small><strong>{system?.authentication ? "Login aktiv" : "Login deaktiviert"}</strong><p>{system?.organization_count ?? organizations.length} Organisationen</p></div></article>
    </section>

    <div className={styles.mainGrid}>
      <section className={styles.panel}>
        <div className={styles.panelHead}><div><h2>Organisationen</h2><p>Arbeitsbereiche öffnen und administrieren</p></div><span>{organizations.length}</span></div>
        <div className={styles.orgList}>{organizations.length === 0 ? <p className={styles.empty}>Noch keine Organisation angelegt.</p> : organizations.map((item) => <article className={styles.orgRow} key={item.id}><div><span>{item.name.slice(0, 1).toUpperCase()}</span><p><strong>{item.name}</strong><small>{item.slug}</small></p></div><div className={styles.orgActions}><button type="button" onClick={() => openOrganization(item, "/")}>Arbeitsbereich</button><button type="button" onClick={() => openOrganization(item, "/settings/organization")}>Struktur</button><button type="button" onClick={() => openOrganization(item, "/settings/users")}>Benutzer</button><DeleteOrganizationButton organizationId={item.id} organizationName={item.name} onDeleted={async () => { await refresh(); await load(); }} onMessage={setMessage}/></div></article>)}</div>
      </section>

      <aside className={styles.sideColumn}>
        <form className={styles.panel} onSubmit={createOrganization}><div className={styles.panelHead}><div><h2>Organisation hinzufügen</h2><p>Neuen isolierten Arbeitsbereich anlegen</p></div></div><div className={styles.form}><label>Name<input value={name} onChange={(e) => setName(e.target.value)} placeholder="Klinikgruppe Heidelberg" required/></label><label>Slug<input value={slug} onChange={(e) => setSlug(e.target.value.toLowerCase().replace(/[^a-z0-9-]/g, "-"))} placeholder="klinikgruppe-heidelberg" required/></label><button type="submit" disabled={busy}>{busy ? "Wird angelegt…" : "Organisation anlegen"}</button></div></form>
        <section className={styles.panel}><div className={styles.panelHead}><div><h2>Systemwerkzeuge</h2><p>Technische Konfiguration</p></div></div><nav className={styles.tools}><Link href="/settings">Lokale KI & Verarbeitung <span>→</span></Link><Link href="/developer/processing">Processing Runs & Fehlerdiagnose <span>→</span></Link><Link href="/system/organizations">Organisationen verwalten <span>→</span></Link><Link href="/profile">Developer-Profil <span>→</span></Link></nav></section>
      </aside>
    </div>
  </div>;
}
