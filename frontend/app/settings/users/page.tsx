"use client";

import { FormEvent, useCallback, useEffect, useMemo, useState } from "react";
import Link from "next/link";
import { useAuth } from "@/components/auth/AuthProvider";
import { ROLE_LABELS, type AccountRole, type ManagedUserDto } from "@/lib/auth-types";
import {
  createUser,
  listUsers,
  listUserScopes,
  updateUser,
  updateUserScope,
  type UserScopeDto,
} from "@/lib/domain-api/users";
import {
  getOrganizationStructure,
  type DepartmentDto,
  type HospitalDto,
  type OrganizationStructureDto,
} from "@/lib/domain-api/organizations";

const ROLES: AccountRole[] = ["admin", "contract_manager", "reviewer", "viewer"];

export default function UsersPage() {
  const { role, account, organizationSlug } = useAuth();
  const [items, setItems] = useState<ManagedUserDto[]>([]);
  const [scopes, setScopes] = useState<Record<string, UserScopeDto>>({});
  const [structure, setStructure] = useState<OrganizationStructureDto>({ hospitals: [], departments: [] });
  const [loading, setLoading] = useState(true);
  const [busy, setBusy] = useState(false);
  const [editing, setEditing] = useState<string | null>(null);
  const [message, setMessage] = useState<{ error: boolean; text: string } | null>(null);
  const [form, setForm] = useState({ email: "", display_name: "", password: "", role: "viewer" as AccountRole });
  const [edit, setEdit] = useState({ display_name: "", role: "viewer" as AccountRole, password: "", hospital_id: "", department_id: "" });

  const load = useCallback(async () => {
    if (!organizationSlug) return;
    setLoading(true);
    try {
      const [usersResponse, scopesResponse, structureResponse] = await Promise.all([
        listUsers(organizationSlug),
        listUserScopes(organizationSlug),
        getOrganizationStructure(organizationSlug),
      ]);
      setItems(usersResponse.items);
      setScopes(Object.fromEntries(scopesResponse.items.map((item) => [item.account_id, item])));
      setStructure(structureResponse);
    } catch (err) {
      setMessage({ error: true, text: err instanceof Error ? err.message : "Benutzer konnten nicht geladen werden." });
    } finally {
      setLoading(false);
    }
  }, [organizationSlug]);

  useEffect(() => {
    if (role === "admin" && organizationSlug) void load();
    else setLoading(false);
  }, [role, organizationSlug, load]);

  async function createManagedUser(event: FormEvent) {
    event.preventDefault();
    if (!organizationSlug) return;
    setBusy(true);
    setMessage(null);
    try {
      await createUser(organizationSlug, form);
      setForm({ email: "", display_name: "", password: "", role: "viewer" });
      setMessage({ error: false, text: "Benutzer wurde angelegt. Bitte anschließend Krankenhaus und Abteilung zuweisen." });
      await load();
    } catch (err) {
      setMessage({ error: true, text: err instanceof Error ? err.message : "Benutzer konnte nicht angelegt werden." });
    } finally {
      setBusy(false);
    }
  }

  function beginEdit(user: ManagedUserDto) {
    const scope = scopes[user.id];
    setEditing(user.id);
    setEdit({ display_name: user.display_name, role: user.role, password: "", hospital_id: scope?.hospital_id ?? "", department_id: scope?.department_id ?? "" });
  }

  const editDepartments = useMemo(
    () => structure.departments.filter((item) => item.is_active && (!edit.hospital_id || item.hospital_id === edit.hospital_id)),
    [structure.departments, edit.hospital_id],
  );

  async function saveUser(user: ManagedUserDto) {
    if (!organizationSlug) return;
    setBusy(true);
    setMessage(null);
    try {
      await updateUser(organizationSlug, user.id, {
        display_name: edit.display_name,
        role: edit.role,
        password: edit.password || undefined,
      });
      await updateUserScope(organizationSlug, user.id, {
        hospital_id: edit.hospital_id || null,
        department_id: edit.department_id || null,
        is_default: true,
      });
      setEditing(null);
      setMessage({ error: false, text: "Benutzer und Arbeitsbereich wurden aktualisiert." });
      await load();
    } catch (err) {
      setMessage({ error: true, text: err instanceof Error ? err.message : "Änderung konnte nicht gespeichert werden." });
    } finally {
      setBusy(false);
    }
  }

  async function toggleUser(user: ManagedUserDto) {
    if (!organizationSlug) return;
    setBusy(true);
    setMessage(null);
    try {
      await updateUser(organizationSlug, user.id, { is_active: !user.is_active });
      await load();
    } catch (err) {
      setMessage({ error: true, text: err instanceof Error ? err.message : "Status konnte nicht geändert werden." });
    } finally {
      setBusy(false);
    }
  }

  if (role !== "admin") {
    return <section className="cw-section"><h2>Keine Berechtigung</h2><p className="cw-muted">Die Benutzerverwaltung ist Administratoren vorbehalten.</p><Link href="/">Zur Übersicht</Link></section>;
  }

  return <div className="user-admin">
    <div className="user-admin-head"><div><h1>Benutzerverwaltung</h1><p className="cw-muted">Benutzer, Rollen sowie Krankenhaus- und Abteilungszugriffe verwalten.</p></div><Link href="/settings">Zurück zu Einstellungen</Link></div>
    {message ? <div className={`user-admin-message${message.error ? " error" : ""}`} role="status">{message.text}</div> : null}
    <form className="user-admin-form" onSubmit={createManagedUser}>
      <label>Name<input value={form.display_name} onChange={(e) => setForm((v) => ({ ...v, display_name: e.target.value }))} required /></label>
      <label>E-Mail<input type="email" value={form.email} onChange={(e) => setForm((v) => ({ ...v, email: e.target.value }))} required /></label>
      <label>Initiales Passwort<input type="password" minLength={10} value={form.password} onChange={(e) => setForm((v) => ({ ...v, password: e.target.value }))} required /></label>
      <label>Rolle<select value={form.role} onChange={(e) => setForm((v) => ({ ...v, role: e.target.value as AccountRole }))}>{ROLES.map((item) => <option value={item} key={item}>{ROLE_LABELS[item]}</option>)}</select></label>
      <button type="submit" disabled={busy}>+ Benutzer hinzufügen</button>
    </form>
    <section className="user-list" aria-label="Benutzer">
      {loading ? <p className="cw-muted">Benutzer werden geladen…</p> : null}
      {!loading && items.length === 0 ? <p className="cw-muted">Keine Benutzer vorhanden.</p> : null}
      {items.map((user) => {
        const scope = scopes[user.id];
        const hospitalName = structure.hospitals.find((item: HospitalDto) => item.id === scope?.hospital_id)?.name;
        const departmentName = structure.departments.find((item: DepartmentDto) => item.id === scope?.department_id)?.name;
        return <article className="user-row" key={user.id}>
          <div><strong>{user.display_name}</strong><small>{user.id === account?.id ? "Aktueller Benutzer" : "Benutzer"}</small></div>
          <div>{user.email}<small>{hospitalName ? ` · ${hospitalName}${departmentName ? ` / ${departmentName}` : ""}` : user.role === "admin" ? " · Organisationsweit" : " · Noch nicht zugewiesen"}</small></div>
          <div className="user-role">{ROLE_LABELS[user.role]}</div>
          <span className={`user-status${user.is_active ? "" : " off"}`}>{user.is_active ? "Aktiv" : "Inaktiv"}</span>
          <div>{user.last_login_at ? new Intl.DateTimeFormat("de-DE", { dateStyle: "short", timeStyle: "short" }).format(new Date(user.last_login_at)) : "Noch nie"}</div>
          <button className="user-action" type="button" onClick={() => beginEdit(user)}>Bearbeiten</button>
          {editing === user.id ? <div className="user-edit-row">
            <input aria-label="Name" value={edit.display_name} onChange={(e) => setEdit((v) => ({ ...v, display_name: e.target.value }))} />
            <select aria-label="Rolle" value={edit.role} onChange={(e) => setEdit((v) => ({ ...v, role: e.target.value as AccountRole }))}>{ROLES.map((item) => <option value={item} key={item}>{ROLE_LABELS[item]}</option>)}</select>
            <select aria-label="Krankenhaus" value={edit.hospital_id} onChange={(e) => setEdit((v) => ({ ...v, hospital_id: e.target.value, department_id: "" }))}><option value="">{edit.role === "admin" ? "Organisationsweit" : "Krankenhaus wählen"}</option>{structure.hospitals.filter((item) => item.is_active).map((item) => <option key={item.id} value={item.id}>{item.name}</option>)}</select>
            <select aria-label="Abteilung" value={edit.department_id} disabled={!edit.hospital_id} onChange={(e) => setEdit((v) => ({ ...v, department_id: e.target.value }))}><option value="">Alle Abteilungen</option>{editDepartments.map((item) => <option key={item.id} value={item.id}>{item.name}</option>)}</select>
            <input type="password" minLength={10} placeholder="Neues Passwort (optional)" value={edit.password} onChange={(e) => setEdit((v) => ({ ...v, password: e.target.value }))} />
            <button type="button" disabled={busy} onClick={() => void saveUser(user)}>Speichern</button>
            <button type="button" className="user-action" disabled={busy || user.id === account?.id} onClick={() => void toggleUser(user)}>{user.is_active ? "Deaktivieren" : "Aktivieren"}</button>
          </div> : null}
        </article>;
      })}
    </section>
  </div>;
}
