"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { useAuth } from "@/components/auth/AuthProvider";
import { listNotifications, type NotificationItem } from "@/lib/domain-api/notifications";

export default function NotificationCenter() {
  const { organizationSlug } = useAuth();
  const [items, setItems] = useState<NotificationItem[]>([]);
  const [error, setError] = useState(false);

  useEffect(() => {
    let active = true;
    if (!organizationSlug) {
      setItems([]);
      return;
    }
    listNotifications(organizationSlug, 40)
      .then((response) => {
        if (!active) return;
        setItems(response?.items ?? []);
        setError(false);
      })
      .catch(() => {
        if (!active) return;
        setItems([]);
        setError(true);
      });
    return () => { active = false; };
  }, [organizationSlug]);

  if (!organizationSlug) return null;

  return (
    <details className="account-menu notification-center">
      <summary className="notification-trigger" aria-label={`${items.length} offene Hinweise`}>
        <span aria-hidden="true">🔔</span>
        {items.length > 0 ? <span className="notification-count">{items.length > 99 ? "99+" : items.length}</span> : null}
      </summary>
      <div className="account-menu-panel notification-panel">
        <div className="account-menu-identity"><strong>Hinweise</strong><small>Aufgaben und Freigaben aus dem aktuellen Bereich</small></div>
        {error ? <p className="muted">Hinweise konnten nicht geladen werden.</p> : null}
        {!error && items.length === 0 ? <p className="muted">Keine offenen Hinweise.</p> : null}
        {items.slice(0, 12).map((item) => (
          <Link key={item.id} href={item.href} className="notification-item">
            <strong>{item.title}</strong>
            {item.message ? <small>{item.message}</small> : null}
            <span>{item.severity}</span>
          </Link>
        ))}
        {items.some((item) => item.kind === "work_item") ? <Link href="/work-queue">Alle To-dos öffnen</Link> : null}
      </div>
    </details>
  );
}
