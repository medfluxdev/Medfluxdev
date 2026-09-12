"use client";

import { FormEvent, useCallback, useEffect, useState } from "react";
import Link from "next/link";
import { apiGet, apiPatch, apiPost } from "@/lib/api";
import { ORG_SLUG } from "@/components/ClientNav";
import { useAuth } from "@/components/auth/AuthProvider";
import { ROLE_LABELS, type AccountRole, type ManagedUserDto } from "@/lib/auth-types";

const ROLES: AccountRole[] = ["admin", "contract_manager", "reviewer", "viewer"];

export default function UsersPage() {
  const { role, account } = useAuth();
  const [items, setItems] = useState<ManagedUserDto[]>([]);
  const [loading, setLoading] = useState(true);
  const [busy, setBusy] = useState(false);
  const [editing, setEditing] = useState<string | null>(null);
  const [message, setMessage] = useState<{ error: boolean; text: string } | null>(null);
  const [form, setForm] = useState({ email: "", display_name: "", password: "", role: "viewer" as AccountRole });
  const [edit, setEdit] = useState({ display_name: "", role: "viewer" as AccountRole, password: "" });

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const response = await apiGet<{ items: ManagedUserDto[] }>(`/api/users?organization_slug=${encodeURIComponent(ORG_SLUG)}`);
      setItems(response.items);
    } catch (err) {
      setMessage({ error: true, text: err instanceof Error ? err.message : "Benutzer konnten nicht geladen werden." });
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    if (role === "admin") void load();
    else setLoading(false);
  }, [role, load]);

  async function createUser(event: FormEvent) {
    event.preventDefault();
    setBusy(true);
    setMessage(null);
    try {
      await apiPost<ManagedUserDto>(`/api/users?organization_slug=${encodeURIComponent(ORG_SLUG)}`, form);
      setForm({ email: "", display_name: "", password: "", role: "viewer" });
      setMessage({ error: false, text: "Benutzer wurde angelegt." });
      await load();
    } catch (err) {
      setMessage({ error: true, text: err instanceof Error ? err.message : "Benutzer konnte nicht angelegt werden." });
    } finally {
      setBusy(false);
    }
  }

  function beginEdit(user: ManagedUserDto) {
    setEditing(user.id);
    setEdit({ display_name: user.display_name, role: user.role, password: "" });
  }

  async function saveUser(user: ManagedUserDto) {
    setBusy(true);
    setMessage(null);
    try {
      await apiPatch<ManagedUserDto>(
        `/api/users/${encodeURIComponent(user.id)}?organization_slug=${encodeURIComponent(ORG_SLUG)}`,
        {
          display_name: edit.display_name,
          role: edit.role,
          password: edit.password || undefined,
        }
      );
      setEditing(null);
      setMessage({ error: false, text: "Benutzer wurde aktualisiert." });
      await load();
    } catch (err) {
      setMessage({ error: true, text: err instanceof Error ? err.message : "Änderung konnte nicht gespeichert werden." });
    } finally {
      setBusy(false);
    }
  }

  async function toggleUser(user: ManagedUserDto) {
    setBusy(true);
    setMessage(null);
    try {
      await apiPatch<ManagedUserDto>(
        `/api/users/${encodeURIComponent(user.id)}?organization_slug=${encodeURIComponent(ORG_SLUG)}`,
        { is_active: !user.is_active }
      );
      await load();
    } catch (err) {
      setMessage({ error: true, text: err instanceof Error ? err.message : "Status konnte nicht geändert werden." });
    } finally {
      setBusy(false);
    }
  }

  if (role !== "admin") {
    return (
      <section className="cw-section">
        <h2>Keine Berechtigung</h2>
        <p className="cw-muted">Die Benutzerverwaltung ist Administratoren vorbehalten.</p>
        <Link href="/">Zur Übersicht</Link>
      </section>
    );
  }

  return (
    <div className="user-admin">
      <div className="user-admin-head">
        <div>
          <h1>Benutzerverwaltung</h1>
          <p className="cw-muted">Benutzer, Rollen und Zugriffe für diesen Arbeitsbereich verwalten.</p>
        </div>
        <Link href="/settings">Zurück zu Einstellungen</Link>
      </div>

      {message ? <div className={`user-admin-message${message.error ? " error" : ""}`} role="status">{message.text}</div> : null}

      <form className="user-admin-form" onSubmit={createUser}>
        <label>Name<input value={form.display_name} onChange={(e) => setForm((v) => ({ ...v, display_name: e.target.value }))} required /></label>
        <label>E-Mail<input type="email" value={form.email} onChange={(e) => setForm((v) => ({ ...v, email: e.target.value }))} required /></label>
        <label>Initiales Passwort<input type="password" minLength={10} value={form.password} onChange={(e) => setForm((v) => ({ ...v, password: e.target.value }))} required /></label>
        <label>Rolle<select value={form.role} onChange={(e) => setForm((v) => ({ ...v, role: e.target.value as AccountRole }))}>{ROLES.map((item) => <option value={item} key={item}>{ROLE_LABELS[item]}</option>)}</select></label>
        <button type="submit" disabled={busy}>+ Benutzer hinzufügen</button>
      </form>

      <section className="user-list" aria-label="Benutzer">
        {loading ? <p className="cw-muted">Benutzer werden geladen…</p> : null}
        {!loading && items.length === 0 ? <p className="cw-muted">Keine Benutzer vorhanden.</p> : null}
        {items.map((user) => (
          <article className="user-row" key={user.id}>
            <div><strong>{user.display_name}</strong><small>{user.id === account?.id ? "Aktueller Benutzer" : "Benutzer"}</small></div>
            <div>{user.email}</div>
            <div className="user-role">{ROLE_LABELS[user.role]}</div>
            <span className={`user-status${user.is_active ? "" : " off"}`}>{user.is_active ? "Aktiv" : "Inaktiv"}</span>
            <div>{user.last_login_at ? new Intl.DateTimeFormat("de-DE", { dateStyle: "short", timeStyle: "short" }).format(new Date(user.last_login_at)) : "Noch nie"}</div>
            <button className="user-action" type="button" onClick={() => beginEdit(user)}>Bearbeiten</button>
            {editing === user.id ? (
              <div className="user-edit-row">
                <input aria-label="Name" value={edit.display_name} onChange={(e) => setEdit((v) => ({ ...v, display_name: e.target.value }))} />
                <select aria-label="Rolle" value={edit.role} onChange={(e) => setEdit((v) => ({ ...v, role: e.target.value as AccountRole }))}>{ROLES.map((item) => <option value={item} key={item}>{ROLE_LABELS[item]}</option>)}</select>
                <input type="password" minLength={10} placeholder="Neues Passwort (optional)" value={edit.password} onChange={(e) => setEdit((v) => ({ ...v, password: e.target.value }))} />
                <button type="button" disabled={busy} onClick={() => void saveUser(user)}>Speichern</button>
                <button type="button" className="user-action" disabled={busy || user.id === account?.id} onClick={() => void toggleUser(user)}>{user.is_active ? "Deaktivieren" : "Aktivieren"}</button>
              </div>
            ) : null}
          </article>
        ))}
      </section>
    </div>
  );
}
