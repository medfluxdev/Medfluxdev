"use client";

import Link from "next/link";
import { useCallback, useEffect, useState } from "react";
import { formatDate } from "@/lib/format";
import {
  NOTIFICATION_KIND_LABEL,
  getInbox,
  markAllNotificationsRead,
  markNotificationRead,
  type InboxDto,
} from "@/lib/domain-api/deadlines";

const timestamp = new Intl.DateTimeFormat("de-DE", { dateStyle: "short", timeStyle: "short" });

export default function InboxView({ organizationSlug }: { organizationSlug: string }) {
  const [data, setData] = useState<InboxDto | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [onlyUnread, setOnlyUnread] = useState(false);

  const load = useCallback(async () => {
    try {
      setData(await getInbox(organizationSlug));
      setError(null);
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "Postfach konnte nicht geladen werden.");
    }
  }, [organizationSlug]);

  useEffect(() => { void load(); }, [load]);

  async function read(id: string | null) {
    try {
      if (id) await markNotificationRead(organizationSlug, id);
      else await markAllNotificationsRead(organizationSlug);
      await load();
      window.dispatchEvent(new Event("medflux:inbox-changed"));
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "Aktion fehlgeschlagen.");
    }
  }

  if (error && !data) return <p role="alert" className="rg-error">{error}</p>;
  if (!data) return <p role="status">Postfach wird geladen…</p>;

  const notes = onlyUnread ? data.notifications.filter((item) => !item.read_at) : data.notifications;

  return <div className="rg-panel">
    {error ? <p role="alert" className="rg-error">{error}</p> : null}
    {data.representing.length > 0 ? <p className="rg-hint">Sie vertreten derzeit: {data.representing.map((item) => item.display_name).join(", ")}. Deren Termine erscheinen hier mit.</p> : null}

    <section className="cw-section" aria-labelledby="inbox-deadlines-heading">
      <div className="cw-section-head"><div><h2 id="inbox-deadlines-heading">Meine Wiedervorlage</h2><p>Offene Termine, für die Sie zuständig sind ({data.deadlines.length}).</p></div><Link href="/fristen?nur=meine" className="rg-link">In Fristen & Aufgaben öffnen</Link></div>
      {data.deadlines.length === 0 ? <p className="cw-muted">Keine offenen Termine.</p> : <ul className="rg-deadlines">{data.deadlines.map((item) => <li key={item.id} className={`rg-deadline${item.overdue ? " rg-deadline-overdue" : ""}`}>
        <div className="rg-deadline-main">
          <Link href={`/contracts/${item.contract_id}?tab=deadlines`}><strong>{item.title}</strong></Link>
          <span>{item.contract_label}</span>
          <span>Fällig {formatDate(item.due_date)}{item.overdue ? " · überfällig" : ""}{item.todo_text ? ` · ${item.todo_text}` : ""}</span>
          {item.basis_unconfirmed ? <span className="rg-origin rg-origin-ai_corrected">Basiert auf ungeprüften KI-Werten</span> : null}
        </div>
      </li>)}</ul>}
    </section>

    <section className="cw-section" aria-labelledby="inbox-notes-heading">
      <div className="cw-section-head">
        <div><h2 id="inbox-notes-heading">Benachrichtigungen</h2><p>{data.unread_count} ungelesen</p></div>
        <div className="rg-actions">
          <label className="rg-check"><input type="checkbox" checked={onlyUnread} onChange={(event) => setOnlyUnread(event.target.checked)} />Nur ungelesene</label>
          <button type="button" className="btn" disabled={data.unread_count === 0} onClick={() => void read(null)}>Alle als gelesen markieren</button>
        </div>
      </div>
      {notes.length === 0 ? <p className="cw-muted">Keine Benachrichtigungen.</p> : <ol className="rg-remarks">{notes.map((item) => <li key={item.id} className={item.read_at ? "rg-inactive" : undefined}>
        <div className="rg-remark-meta">
          <strong>{NOTIFICATION_KIND_LABEL[item.kind]}{item.on_behalf_of_name ? ` · Vertretung für ${item.on_behalf_of_name}` : ""}</strong>
          <time dateTime={item.created_at ?? undefined}>{item.created_at ? timestamp.format(new Date(item.created_at)) : ""}</time>
        </div>
        <p>{item.contract_id ? <Link href={`/contracts/${item.contract_id}?tab=deadlines`}>{item.title}</Link> : item.title}</p>
        {item.body ? <p className="cw-muted">{item.body}</p> : null}
        {!item.read_at ? <button type="button" className="rg-link" onClick={() => void read(item.id)}>Als gelesen markieren</button> : null}
      </li>)}</ol>}
    </section>
  </div>;
}
