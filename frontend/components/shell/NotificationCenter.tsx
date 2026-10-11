"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useEffect, useRef, useState } from "react";
import { useAuth } from "@/components/auth/AuthProvider";
import { SignalIcon } from "@/components/ui/Signal";
import { listNotifications, type NotificationItem } from "@/lib/domain-api/notifications";
import { getInbox, getInboxSummary, markNotificationRead, NOTIFICATION_KIND_LABEL, type InboxNotification } from "@/lib/domain-api/deadlines";

const SEVERITY_LABEL: Record<string, string> = { critical: "Kritisch", high: "Hoch", medium: "Mittel", low: "Niedrig", info: "Hinweis", warning: "Warnung" };

interface State {
  mine: InboxNotification[];
  unread: number | null;
  work: NotificationItem[];
  workTotal: number | null;
}

const EMPTY: State = { mine: [], unread: null, work: [], workTotal: null };

function noteHref(item: InboxNotification) {
  if (item.href) return item.href;
  return item.contract_id ? `/contracts/${item.contract_id}?tab=deadlines` : "/postfach";
}

// Glocke: „Für mich“ (ungelesene Benachrichtigungen – nur sie zählen im Abzeichen) und
// „Arbeitsvorrat“ (offene Aufgaben und Freigaben im Bereich, eigener Zähler ohne Abzeichen).
// Zähler und Listen kommen aus denselben Abfragen; ein Ladefehler wird nie als 0 gezeigt.
export default function NotificationCenter() {
  const { organizationSlug } = useAuth();
  const router = useRouter();
  const menu = useRef<HTMLDetailsElement>(null);
  const [state, setState] = useState<State>(EMPTY);
  const [failed, setFailed] = useState(false);
  const [refreshTick, setRefreshTick] = useState(0);

  useEffect(() => {
    const onChange = () => setRefreshTick((value) => value + 1);
    window.addEventListener("medflux:inbox-changed", onChange);
    return () => window.removeEventListener("medflux:inbox-changed", onChange);
  }, []);

  useEffect(() => {
    let active = true;
    if (!organizationSlug) {
      setState(EMPTY);
      return;
    }
    Promise.allSettled([
      getInboxSummary(organizationSlug),
      getInbox(organizationSlug, { limit: 6, unreadOnly: true }),
      listNotifications(organizationSlug, 8),
    ]).then(([summary, personal, feed]) => {
      if (!active) return;
      const counts = summary.status === "fulfilled" && typeof summary.value?.unread_for_me === "number" ? summary.value : null;
      setState({
        unread: counts ? counts.unread_for_me : null,
        workTotal: counts ? counts.work_queue_open : feed.status === "fulfilled" && typeof feed.value?.total === "number" ? feed.value.total : null,
        mine: personal.status === "fulfilled" ? personal.value?.notifications ?? [] : [],
        work: feed.status === "fulfilled" ? feed.value?.items ?? [] : [],
      });
      setFailed(counts === null);
    });
    return () => { active = false; };
  }, [organizationSlug, refreshTick]);

  if (!organizationSlug) return null;
  const unread = state.unread ?? 0;
  const label = failed ? "Benachrichtigungen (Zähler nicht verfügbar)" : unread > 0 ? `${unread} ungelesene Benachrichtigungen` : "Benachrichtigungen";

  async function open(item: InboxNotification) {
    // Öffnen markiert diese eine Benachrichtigung als gelesen; Aufgaben bleiben unverändert.
    menu.current?.removeAttribute("open");
    try {
      if (!item.read_at && organizationSlug) await markNotificationRead(organizationSlug, item.id);
    } catch {
      // Lesen ist Komfort; das Ziel wird trotzdem geöffnet.
    }
    window.dispatchEvent(new Event("medflux:inbox-changed"));
    router.push(noteHref(item));
  }

  return (
    <details className="shell-menu" ref={menu}>
      <summary className="btn btn-ghost btn-icon shell-bell" aria-label={label} title={failed ? "Zähler konnte nicht geladen werden" : undefined}>
        <svg viewBox="0 0 24 24" aria-hidden="true" className="shell-icon"><path d="M18 8a6 6 0 1 0-12 0c0 7-3 9-3 9h18s-3-2-3-9" /><path d="M13.7 21a2 2 0 0 1-3.4 0" /></svg>
        {!failed && unread > 0 ? <span className="shell-count" aria-hidden="true">{unread > 99 ? "99+" : unread}</span> : null}
      </summary>
      <div className="shell-menu-panel shell-menu-panel--wide notification-panel">
        <section aria-labelledby="bell-mine">
          <div className="shell-menu-head">
            <strong id="bell-mine">Für mich</strong>
            <small>{failed ? "Zähler nicht verfügbar" : unread === 0 ? "Keine ungelesenen Benachrichtigungen" : `${unread} ungelesen`}</small>
          </div>
          {state.mine.map((item) => (
            <button key={item.id} type="button" className="notification-item" onClick={() => void open(item)}>
              <strong>{item.title}</strong>
              {item.on_behalf_of_name ? <small>Vertretung für {item.on_behalf_of_name}</small> : null}
              <span>{NOTIFICATION_KIND_LABEL[item.kind]}</span>
            </button>
          ))}
          <Link href="/postfach" className="btn-link">Alle Benachrichtigungen</Link>
        </section>
        <section aria-labelledby="bell-work" className="notification-work">
          <div className="shell-menu-head">
            <strong id="bell-work">Arbeitsvorrat</strong>
            <small>{state.workTotal === null ? "Nicht verfügbar" : state.workTotal === 0 ? "Keine offenen Aufgaben oder Freigaben" : `${state.workTotal} offene Aufgaben und Freigaben im Bereich`}</small>
          </div>
          {state.work.slice(0, 5).map((item) => (
            <Link key={item.id} href={item.href} className="notification-item">
              <strong>{item.title}</strong>
              {item.message ? <small>{item.message}</small> : null}
              <span className="notification-severity">{item.severity === "critical" || item.severity === "high" ? <SignalIcon tone={item.severity === "critical" ? "critical" : "warning"} /> : null}{SEVERITY_LABEL[item.severity] ?? item.severity}</span>
            </Link>
          ))}
          {state.workTotal ? <Link href="/fristen?ansicht=aufgaben" className="btn-link">Alle Aufgaben öffnen</Link> : null}
        </section>
      </div>
    </details>
  );
}
