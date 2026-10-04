"use client";

import Link from "next/link";
import { useCallback, useEffect, useState } from "react";
import { useAuth } from "@/components/auth/AuthProvider";
import KpiTile from "@/components/ui/KpiTile";
import Skeleton from "@/components/ui/Skeleton";
import EmptyState from "@/components/ui/EmptyState";
import Badge from "@/components/ui/Badge";
import { getInbox, listDeadlines, type DeadlineDto } from "@/lib/domain-api/deadlines";
import { getGrid, getPortfolioReport, listRenewals, type PortfolioReport, type RenewalListItem } from "@/lib/domain-api/registerGrid";
import { formatCurrency, formatDate } from "@/lib/format";

function isoInDays(days: number) {
  const date = new Date();
  date.setDate(date.getDate() + days);
  return date.toISOString().slice(0, 10);
}

function greeting(now: Date) {
  const hour = now.getHours();
  return hour < 11 ? "Guten Morgen" : hour < 18 ? "Guten Tag" : "Guten Abend";
}

interface State {
  deadlines: DeadlineDto[] | null;
  renewals: RenewalListItem[] | null;
  portfolio: PortfolioReport | null;
  unread: number | null;
  reviewCount: number | null;
}

// "Mein Tag": eigene Aufgaben zuerst, Kennzahlen aus denselben Registerdaten
// wie die Vertragsliste (UX-Plan U4).
export default function MyDay({ organizationSlug }: { organizationSlug: string }) {
  const { account, role } = useAuth();
  const [state, setState] = useState<State>({ deadlines: null, renewals: null, portfolio: null, unread: null, reviewCount: null });
  const [failed, setFailed] = useState(false);
  const reviewer = Boolean(account?.is_developer || role === "admin" || role === "contract_manager" || role === "reviewer");

  const load = useCallback(() => {
    setFailed(false);
    Promise.allSettled([
      listDeadlines(organizationSlug, { status: "open", mine: true, dueBefore: isoInDays(7) }),
      listRenewals(organizationSlug, 90),
      getPortfolioReport(organizationSlug),
      getInbox(organizationSlug),
      reviewer ? getGrid(organizationSlug, { columns: ["register_number"], filters: [{ column: "review_pending", op: "is", value: true }] }, { offset: 0, limit: 1 }) : Promise.resolve(null),
    ]).then(([deadlines, renewals, portfolio, inbox, review]) => {
      setState({
        deadlines: deadlines.status === "fulfilled" ? deadlines.value.items : [],
        renewals: renewals.status === "fulfilled" ? renewals.value.items : [],
        portfolio: portfolio.status === "fulfilled" ? portfolio.value : null,
        unread: inbox.status === "fulfilled" ? inbox.value.unread_count : null,
        reviewCount: review.status === "fulfilled" && review.value ? review.value.total : null,
      });
      if ([deadlines, renewals, portfolio].every((result) => result.status === "rejected")) setFailed(true);
    });
  }, [organizationSlug, reviewer]);

  useEffect(load, [load]);

  const now = new Date();
  const firstName = account?.display_name?.split(" ")[0] ?? "";
  const openDecisions = (state.renewals ?? []).filter((item) => !item.decision);
  const overdue = (state.deadlines ?? []).filter((item) => item.overdue);

  return (
    <div className="page my-day">
      <header className="my-day-head">
        <div>
          <h1>{greeting(now)}{firstName ? `, ${firstName}` : ""}</h1>
          <p className="field-hint">{new Intl.DateTimeFormat("de-DE", { weekday: "long", day: "numeric", month: "long", year: "numeric" }).format(now)}</p>
        </div>
        {role === "admin" || role === "contract_manager" || account?.is_developer ? <Link href="/contracts/new" className="btn btn-primary">Vertrag anlegen</Link> : null}
      </header>

      {failed ? <p className="alert alert--critical" role="alert">Die Übersicht konnte nicht geladen werden. <button type="button" className="btn btn-sm" onClick={load}>Erneut laden</button></p> : null}

      <section className="my-day-kpis" aria-label="Kennzahlen">
        <KpiTile label="Laufende Verträge" value={state.portfolio ? state.portfolio.totals.running : "…"} hint={state.portfolio ? `von ${state.portfolio.totals.contracts}` : undefined} href="/register" linkLabel="Zur Vertragsliste" />
        <KpiTile label="Jährliche Kosten (netto)" value={state.portfolio ? formatCurrency(state.portfolio.totals.annual_cost, "EUR") : "…"} hint="aus den gepflegten Finanzdaten" href="/analysen" linkLabel="Zu den Analysen" />
        <KpiTile label="Kündigungsfristen in 90 Tagen" value={state.renewals ? state.renewals.length : "…"} hint={state.renewals ? `${openDecisions.length} ohne Entscheidung` : undefined} href="/verlaengerungen" linkLabel="Zu den Verlängerungen" />
        <KpiTile label="Ungelesene Erinnerungen" value={state.unread ?? "…"} href="/postfach" linkLabel="Zum Postfach" />
      </section>

      <div className="my-day-grid">
        <section className="card card-pad" aria-labelledby="my-deadlines">
          <div className="section-head"><div><h2 id="my-deadlines">Meine Termine bis {formatDate(isoInDays(7))}</h2><p>{overdue.length > 0 ? `${overdue.length} überfällig` : "Fällig in den nächsten sieben Tagen"}</p></div><Link href="/termine" className="btn btn-sm">Alle Termine</Link></div>
          {state.deadlines === null ? <Skeleton lines={4} label="Termine werden geladen…" /> : state.deadlines.length === 0 ? <EmptyState title="Keine Termine diese Woche">Neue Fristen erscheinen hier automatisch.</EmptyState> : (
            <ul className="my-day-list">
              {state.deadlines.slice(0, 8).map((item) => (
                <li key={item.id}>
                  <span className={`my-day-date${item.overdue ? " is-overdue" : ""}`}>{formatDate(item.due_date)}</span>
                  <div><Link href={`/contracts/${item.contract_id}?tab=deadlines`}>{item.title}</Link><small>{item.contract_label ?? ""}</small></div>
                  {item.overdue ? <Badge tone="danger">Überfällig</Badge> : item.days_until_due === 0 ? <Badge tone="warning">Heute</Badge> : null}
                </li>
              ))}
            </ul>
          )}
        </section>

        <section className="card card-pad" aria-labelledby="my-decisions">
          <div className="section-head"><div><h2 id="my-decisions">Entscheidungen vor Kündigungsfrist</h2><p>Verträge mit Frist in 90 Tagen ohne erfasste Entscheidung</p></div><Link href="/verlaengerungen" className="btn btn-sm">Alle anzeigen</Link></div>
          {state.renewals === null ? <Skeleton lines={4} label="Fristen werden geladen…" /> : openDecisions.length === 0 ? <EmptyState title="Alles entschieden">Für die nächsten 90 Tage sind keine Entscheidungen offen.</EmptyState> : (
            <ul className="my-day-list">
              {openDecisions.slice(0, 6).map((item) => (
                <li key={item.contract_id}>
                  <span className={`my-day-date${item.days_left <= 30 ? " is-overdue" : ""}`}>{formatDate(item.cancel_by)}</span>
                  <div><Link href={`/contracts/${item.contract_id}?tab=deadlines`}>{item.register_number ?? "–"} · {item.short_description ?? ""}</Link><small>{item.partner ?? ""}{item.annual_cost ? ` · ${formatCurrency(item.annual_cost, "EUR")} jährlich` : ""}</small></div>
                  <Badge tone={item.days_left < 0 ? "danger" : item.days_left <= 30 ? "warning" : "neutral"}>{item.days_left < 0 ? "verstrichen" : `${item.days_left} Tage`}</Badge>
                </li>
              ))}
            </ul>
          )}
        </section>

        <section className="card card-pad" aria-labelledby="my-attention">
          <div className="section-head"><div><h2 id="my-attention">Handlungsbedarf im Portfolio</h2><p>Lücken, die Fristen und Kosten unsicher machen</p></div></div>
          {state.portfolio === null ? <Skeleton lines={4} /> : (
            <ul className="my-day-list">
              {reviewer && state.reviewCount ? <li><span className="my-day-count">{state.reviewCount}</span><div><Link href="/review">Verträge mit offener KI-Prüfung</Link></div></li> : null}
              {state.portfolio.insights.filter((item) => item.count > 0).map((item) => (
                <li key={item.key}><span className="my-day-count">{item.count}</span><div><Link href={`/register?filter=${encodeURIComponent(JSON.stringify([item.filter]))}`}>{item.label}</Link></div></li>
              ))}
              {state.portfolio.insights.every((item) => item.count === 0) && !state.reviewCount ? <li><div>Kein Handlungsbedarf erkannt.</div></li> : null}
            </ul>
          )}
        </section>
      </div>
    </div>
  );
}
