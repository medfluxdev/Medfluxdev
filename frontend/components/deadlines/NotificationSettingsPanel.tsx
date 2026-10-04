"use client";

import { useEffect, useState } from "react";
import { useAuth } from "@/components/auth/AuthProvider";
import { formatDate } from "@/lib/format";
import { listOwnershipAssignees, type AssigneeDto } from "@/lib/domain-api/ownership";
import {
  createDeputy,
  deactivateDeputy,
  getNotificationSettings,
  listDeputies,
  updateNotificationSettings,
  type DeputyDto,
  type NotificationSettingsDto,
} from "@/lib/domain-api/deadlines";

export default function NotificationSettingsPanel() {
  const { organizationSlug, role, account } = useAuth();
  const canManageDeputies = Boolean(account?.is_developer || role === "admin" || role === "contract_manager");
  const [settings, setSettings] = useState<NotificationSettingsDto | null>(null);
  const [deputies, setDeputies] = useState<DeputyDto[]>([]);
  const [people, setPeople] = useState<AssigneeDto[]>([]);
  const [form, setForm] = useState({ deputy_account_id: "", valid_from: "", valid_to: "" });
  const [message, setMessage] = useState<{ tone: "ok" | "error"; text: string } | null>(null);
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    if (!organizationSlug) return;
    let cancelled = false;
    Promise.allSettled([
      getNotificationSettings(organizationSlug),
      listDeputies(organizationSlug),
      canManageDeputies ? listOwnershipAssignees(organizationSlug) : Promise.resolve({ items: [] as AssigneeDto[] }),
    ]).then(([settingsResult, deputyResult, peopleResult]) => {
      if (cancelled) return;
      if (settingsResult.status === "fulfilled") setSettings(settingsResult.value);
      if (deputyResult.status === "fulfilled") setDeputies(deputyResult.value.items);
      if (peopleResult.status === "fulfilled") setPeople(peopleResult.value.items.filter((item) => item.id !== account?.id));
    });
    return () => { cancelled = true; };
  }, [account?.id, canManageDeputies, organizationSlug]);

  async function run<T>(action: () => Promise<T>, apply: (value: T) => void, success: string) {
    setBusy(true);
    setMessage(null);
    try {
      apply(await action());
      setMessage({ tone: "ok", text: success });
    } catch (caught) {
      setMessage({ tone: "error", text: caught instanceof Error ? caught.message : "Speichern fehlgeschlagen." });
    } finally {
      setBusy(false);
    }
  }

  if (!organizationSlug || !settings) return null;

  return <section className="card card-pad" aria-labelledby="notification-settings-heading">
    <h2 className="card-title" id="notification-settings-heading">Benachrichtigungen & Vertretung</h2>
    <p className="muted">E-Mails gehen an {settings.email}. Im Postfach erscheinen Erinnerungen immer.</p>
    {message ? <p role={message.tone === "error" ? "alert" : "status"} className={message.tone === "error" ? "rg-error" : "rg-ok"}>{message.text}</p> : null}
    <div className="rg-period my-3">
      <label className="rg-check"><input type="checkbox" checked={settings.receives_reminders} disabled={busy} onChange={(event) => void run(() => updateNotificationSettings(organizationSlug, { receives_reminders: event.target.checked }), setSettings, "Gespeichert.")} />Erinnerungen per E-Mail</label>
      <label className="rg-check"><input type="checkbox" checked={settings.receives_notifications} disabled={busy} onChange={(event) => void run(() => updateNotificationSettings(organizationSlug, { receives_notifications: event.target.checked }), setSettings, "Gespeichert.")} />Überfälligkeiten und Eskalationen per E-Mail</label>
    </div>
    {canManageDeputies ? <>
      <label className="rg-form-grid form-grid-single">Standardvertretung
        <select value={settings.default_deputy_account_id ?? ""} disabled={busy} onChange={(event) => void run(() => updateNotificationSettings(organizationSlug, { default_deputy_account_id: event.target.value || null }), setSettings, "Gespeichert.")}>
          <option value="">Keine</option>{people.map((item) => <option key={item.id} value={item.id}>{item.display_name}</option>)}
        </select>
      </label>
      <h3>Abwesenheit eintragen</h3>
      <form className="rg-form-grid" onSubmit={(event) => { event.preventDefault(); void run(() => createDeputy(organizationSlug, { deputy_account_id: form.deputy_account_id || settings.default_deputy_account_id || "", valid_from: form.valid_from, valid_to: form.valid_to }), (value) => { setDeputies(value.items); setForm({ deputy_account_id: "", valid_from: "", valid_to: "" }); }, "Vertretung eingetragen."); }}>
        <label>Vertretung<select value={form.deputy_account_id || settings.default_deputy_account_id || ""} onChange={(event) => setForm((current) => ({ ...current, deputy_account_id: event.target.value }))} required><option value="">Bitte auswählen</option>{people.map((item) => <option key={item.id} value={item.id}>{item.display_name}</option>)}</select></label>
        <label>Von<input type="date" required value={form.valid_from} onChange={(event) => setForm((current) => ({ ...current, valid_from: event.target.value }))} /></label>
        <label>Bis<input type="date" required min={form.valid_from || undefined} value={form.valid_to} onChange={(event) => setForm((current) => ({ ...current, valid_to: event.target.value }))} /></label>
        <button type="submit" className="btn btn-primary" disabled={busy}>Eintragen</button>
      </form>
    </> : null}
    {deputies.length > 0 ? <table className="rg-table mt-3">
      <thead><tr><th scope="col">Abwesend</th><th scope="col">Vertretung</th><th scope="col">Zeitraum</th><th scope="col"><span className="sr-only">Aktion</span></th></tr></thead>
      <tbody>{deputies.map((item) => <tr key={item.id} className={item.is_active ? undefined : "rg-inactive"}>
        <td>{item.account_name}</td><td>{item.deputy_name}{item.current ? " (aktiv)" : ""}</td>
        <td>{formatDate(item.valid_from)} – {formatDate(item.valid_to)}</td>
        <td>{item.is_active && canManageDeputies && item.account_id === account?.id ? <button type="button" className="rg-link" disabled={busy} onClick={() => void run(() => deactivateDeputy(organizationSlug, item.id), (value) => setDeputies(value.items), "Vertretung beendet.")}>Beenden</button> : null}</td>
      </tr>)}</tbody>
    </table> : null}
  </section>;
}
