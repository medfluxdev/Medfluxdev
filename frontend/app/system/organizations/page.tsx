"use client";

import { FormEvent, useCallback, useEffect, useState } from "react";
import Link from "next/link";
import PageHeader from "@/components/ui/PageHeader";
import { apiGet, apiPost } from "@/lib/api";
import { useAuth } from "@/components/auth/AuthProvider";

type OrganizationItem = { id: string; name: string; slug: string };

export default function SystemOrganizationsPage() {
  const { account, refresh, selectOrganization } = useAuth();
  const [items, setItems] = useState<OrganizationItem[]>([]);
  const [name, setName] = useState("");
  const [slug, setSlug] = useState("");
  const [busy, setBusy] = useState(false);
  const [message, setMessage] = useState<{ error: boolean; text: string } | null>(null);

  const load = useCallback(async () => {
    if (!account?.is_developer) return;
    try {
      const result = await apiGet<{ items: OrganizationItem[] }>("/api/system/organizations");
      setItems(result.items);
    } catch (error) {
      setMessage({ error: true, text: error instanceof Error ? error.message : "Organisationen konnten nicht geladen werden." });
    }
  }, [account?.is_developer]);

  useEffect(() => { void load(); }, [load]);

  async function createOrganization(event: FormEvent) {
    event.preventDefault();
    setBusy(true);
    setMessage(null);
    try {
      const created = await apiPost<OrganizationItem>("/api/system/organizations", { name, slug });
      setName("");
      setSlug("");
      setMessage({ error: false, text: "Organisation wurde angelegt." });
      await refresh();
      await load();
      selectOrganization(created.slug);
    } catch (error) {
      setMessage({ error: true, text: error instanceof Error ? error.message : "Organisation konnte nicht angelegt werden." });
    } finally {
      setBusy(false);
    }
  }

  if (!account?.is_developer) {
    return <section className="cw-section"><h2>Keine Berechtigung</h2><p className="cw-muted">Dieser Bereich ist nur für den MedFlux Developer verfügbar.</p><Link href="/">Zur Übersicht</Link></section>;
  }

  return (
    <div className="page org-settings-page">
      <PageHeader variant="highlight" eyebrow="Systemverwaltung" title="Organisationen" description="Mandanten anlegen und anschließend deren Krankenhausstruktur verwalten." />

      {message ? <div className={`user-admin-message${message.error ? " error" : ""}`}>{message.text}</div> : null}

      <div className="org-settings-forms">
        <form className="org-settings-card" onSubmit={createOrganization}>
          <h2>Organisation hinzufügen</h2>
          <label>Name<input value={name} onChange={(event) => setName(event.target.value)} placeholder="z. B. Klinikgruppe Heidelberg" required /></label>
          <label>Slug<input value={slug} onChange={(event) => setSlug(event.target.value.toLowerCase().replace(/[^a-z0-9-]/g, "-"))} placeholder="klinikgruppe-heidelberg" required /></label>
          <button type="submit" disabled={busy}>{busy ? "Wird angelegt…" : "Organisation anlegen"}</button>
        </form>

        <section className="org-settings-card">
          <h2>Developer-Zugriff</h2>
          <p className="cw-muted">Der Developer hat systemweiten Zugriff. Normale Administratoren können Krankenhäuser, Abteilungen, Benutzer und Kostenstellen nur innerhalb ihrer Organisation verwalten.</p>
          <strong>{account.display_name}</strong>
          <small>{account.email}</small>
        </section>
      </div>

      <section className="org-settings-list">
        <div className="org-settings-list-head"><h2>Vorhandene Organisationen</h2><span>{items.length}</span></div>
        {items.length === 0 ? <p>Noch keine Organisation angelegt.</p> : items.map((item) => (
          <article className="org-hospital-row" key={item.id}>
            <div className="org-hospital-title"><strong>{item.name}</strong><span>{item.slug}</span></div>
            <button type="button" className="user-action" onClick={() => { selectOrganization(item.slug); window.location.href = "/"; }}>Öffnen</button>
          </article>
        ))}
      </section>
    </div>
  );
}
