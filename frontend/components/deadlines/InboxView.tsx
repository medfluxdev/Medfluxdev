"use client";

import Link from "next/link";
import { useCallback, useEffect, useState } from "react";
import EmptyState from "@/components/ui/EmptyState";
import {
  NOTIFICATION_KIND_LABEL,
  getInbox,
  markAllNotificationsRead,
  markNotificationRead,
  type InboxNotification,
} from "@/lib/domain-api/deadlines";

const timestamp = new Intl.DateTimeFormat("de-DE", { dateStyle: "short", timeStyle: "short" });
const PAGE = 50;

// Vollständiges Benachrichtigungsprotokoll (Glocke → „Alle Benachrichtigungen“).
// Die persönliche Wiedervorlage steht unter Fristen & Aufgaben → Termine → „Nur meine“.
export default function InboxView({ organizationSlug }: { organizationSlug: string }) {
  const [items, setItems] = useState<InboxNotification[] | null>(null);
  const [total, setTotal] = useState(0);
  const [unread, setUnread] = useState(0);
  const [representing, setRepresenting] = useState<string[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [onlyUnread, setOnlyUnread] = useState(false);
  const [loadingMore, setLoadingMore] = useState(false);

  const load = useCallback(async () => {
    try {
      const data = await getInbox(organizationSlug, { limit: PAGE, unreadOnly: onlyUnread });
      setItems(data.notifications);
      setTotal(data.total ?? data.notifications.length);
      setUnread(data.unread_count);
      setRepresenting(data.representing.map((item) => item.display_name));
      setError(null);
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "Benachrichtigungen konnten nicht geladen werden.");
    }
  }, [onlyUnread, organizationSlug]);

  useEffect(() => { void load(); }, [load]);

  async function more() {
    if (!items) return;
    setLoadingMore(true);
    try {
      const data = await getInbox(organizationSlug, { limit: PAGE, offset: items.length, unreadOnly: onlyUnread });
      setItems([...items, ...data.notifications]);
      setTotal(data.total ?? total);
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "Weitere Benachrichtigungen konnten nicht geladen werden.");
    } finally {
      setLoadingMore(false);
    }
  }

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

  if (error && !items) return <p role="alert" className="rg-error">{error} <button type="button" className="btn btn-sm" onClick={() => void load()}>Erneut versuchen</button></p>;
  if (!items) return <p role="status">Benachrichtigungen werden geladen…</p>;

  return <div className="rg-panel">
    {error ? <p role="alert" className="rg-error">{error}</p> : null}
    {representing.length > 0 ? <p className="rg-hint">Sie vertreten derzeit: {representing.join(", ")}. Deren Erinnerungen erscheinen hier mit.</p> : null}
    <p className="field-hint">Ihre offenen Termine finden Sie unter <Link href="/fristen?ansicht=termine&nur=meine">Fristen & Aufgaben → Termine → Nur meine</Link>.</p>

    <section className="cw-section" aria-labelledby="inbox-notes-heading">
      <div className="cw-section-head">
        <div><h2 id="inbox-notes-heading">Benachrichtigungen</h2><p>{unread} ungelesen · {total} {onlyUnread ? "ungelesene" : "insgesamt"}</p></div>
        <div className="rg-actions">
          <label className="rg-check"><input type="checkbox" checked={onlyUnread} onChange={(event) => setOnlyUnread(event.target.checked)} />Nur ungelesene</label>
          <button type="button" className="btn" disabled={unread === 0} onClick={() => void read(null)}>Alle als gelesen markieren</button>
        </div>
      </div>
      {items.length === 0
        ? (onlyUnread
          ? <EmptyState variant="calm" title="Keine ungelesenen Benachrichtigungen"><>Alles gelesen. <button type="button" className="rg-link" onClick={() => setOnlyUnread(false)}>Alle anzeigen</button></></EmptyState>
          : <EmptyState variant="calm" title="Keine Benachrichtigungen">Erinnerungen und Eskalationen zu Ihren Terminen erscheinen hier.</EmptyState>)
        : <ol className="rg-remarks">{items.map((item) => <li key={item.id} className={item.read_at ? "rg-inactive" : undefined}>
          <div className="rg-remark-meta">
            <strong>{NOTIFICATION_KIND_LABEL[item.kind]}{item.on_behalf_of_name ? ` · Vertretung für ${item.on_behalf_of_name}` : ""}{item.read_at ? "" : " · ungelesen"}</strong>
            <time dateTime={item.created_at ?? undefined}>{item.created_at ? timestamp.format(new Date(item.created_at)) : ""}</time>
          </div>
          <p>{item.contract_id ? <Link href={item.href ?? `/contracts/${item.contract_id}?tab=deadlines`} onClick={() => { if (!item.read_at) void read(item.id); }}>{item.title}</Link> : item.title}</p>
          {item.body ? <p className="cw-muted">{item.body}</p> : null}
          {!item.read_at ? <button type="button" className="rg-link" onClick={() => void read(item.id)}>Als gelesen markieren</button> : null}
        </li>)}</ol>}
      {items.length < total ? <button type="button" className="btn" disabled={loadingMore} onClick={() => void more()}>{loadingMore ? "Wird geladen…" : `Weitere laden (${total - items.length})`}</button> : null}
    </section>
  </div>;
}
