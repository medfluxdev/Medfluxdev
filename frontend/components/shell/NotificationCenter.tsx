"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { useAuth } from "@/components/auth/AuthProvider";
import { listNotifications, type NotificationItem } from "@/lib/domain-api/notifications";
import { getInbox, NOTIFICATION_KIND_LABEL, type InboxNotification } from "@/lib/domain-api/deadlines";

const SEVERITY_LABEL: Record<string, string> = { critical: "Kritisch", high: "Hoch", medium: "Mittel", low: "Niedrig", info: "Hinweis", warning: "Warnung" };

export default function NotificationCenter() {
  const { organizationSlug } = useAuth();
  const [items, setItems] = useState<NotificationItem[]>([]);
  const [inbox, setInbox] = useState<InboxNotification[]>([]);
  const [unread, setUnread] = useState(0);
  const [error, setError] = useState(false);
  const [refreshTick, setRefreshTick] = useState(0);

  useEffect(() => {
    const onChange = () => setRefreshTick((value) => value + 1);
    window.addEventListener("medflux:inbox-changed", onChange);
    return () => window.removeEventListener("medflux:inbox-changed", onChange);
  }, []);

  useEffect(() => {
    let active = true;
    if (!organizationSlug) {
      setItems([]);
      setInbox([]);
      setUnread(0);
      return;
    }
    Promise.allSettled([listNotifications(organizationSlug, 40), getInbox(organizationSlug)]).then(([feed, personal]) => {
      if (!active) return;
      setItems(feed.status === "fulfilled" ? feed.value?.items ?? [] : []);
      if (personal.status === "fulfilled" && personal.value) {
        setInbox((personal.value.notifications ?? []).filter((item) => !item.read_at));
        setUnread(personal.value.unread_count ?? 0);
      } else {
        setInbox([]);
        setUnread(0);
      }
      setError(feed.status === "rejected" && personal.status === "rejected");
    });
    return () => { active = false; };
  }, [organizationSlug, refreshTick]);

  if (!organizationSlug) return null;
  const total = items.length + unread;

  return (
    <details className="shell-menu">
      <summary className="btn btn-ghost btn-icon shell-bell" aria-label={total > 0 ? `${total} offene Hinweise` : "Hinweise"}>
        <svg viewBox="0 0 24 24" aria-hidden="true" className="shell-icon"><path d="M18 8a6 6 0 1 0-12 0c0 7-3 9-3 9h18s-3-2-3-9" /><path d="M13.7 21a2 2 0 0 1-3.4 0" /></svg>
        {total > 0 ? <span className="shell-count" aria-hidden="true">{total > 99 ? "99+" : total}</span> : null}
      </summary>
      <div className="shell-menu-panel shell-menu-panel--wide">
        <div className="shell-menu-head"><strong>Hinweise</strong><small>Erinnerungen, Aufgaben und Freigaben aus dem aktuellen Bereich</small></div>
        {error ? <p className="muted">Hinweise konnten nicht geladen werden.</p> : null}
        {!error && total === 0 ? <p className="muted">Keine offenen Hinweise.</p> : null}
        {inbox.slice(0, 6).map((item) => (
          <Link key={item.id} href={item.contract_id ? `/contracts/${item.contract_id}?tab=deadlines` : "/postfach"} className="notification-item">
            <strong>{item.title}</strong>
            {item.on_behalf_of_name ? <small>Vertretung für {item.on_behalf_of_name}</small> : null}
            <span>{NOTIFICATION_KIND_LABEL[item.kind]}</span>
          </Link>
        ))}
        {items.slice(0, 12 - Math.min(inbox.length, 6)).map((item) => (
          <Link key={item.id} href={item.href} className="notification-item">
            <strong>{item.title}</strong>
            {item.message ? <small>{item.message}</small> : null}
            <span>{SEVERITY_LABEL[item.severity] ?? item.severity}</span>
          </Link>
        ))}
        <Link href="/postfach" className="btn-link">Postfach öffnen{unread > 0 ? ` (${unread} ungelesen)` : ""}</Link>
        {items.some((item) => item.kind === "work_item") ? <Link href="/fristen?ansicht=aufgaben" className="btn-link">Alle Aufgaben öffnen</Link> : null}
      </div>
    </details>
  );
}
