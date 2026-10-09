"use client";

import Link from "next/link";
import { useCallback, useEffect, useState, type ReactNode } from "react";
import { useAuth } from "@/components/auth/AuthProvider";
import KpiTile from "@/components/ui/KpiTile";
import PageHeader from "@/components/ui/PageHeader";
import Skeleton from "@/components/ui/Skeleton";
import EmptyState from "@/components/ui/EmptyState";
import Badge from "@/components/ui/Badge";
import { ICONS } from "@/components/shell/navigation";
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

// Liniensymbole im Stil der Navigation (components/shell/navigation.tsx), 18px in der Kachel.
function TileIcon({ children }: { children: ReactNode }) {
  return <svg viewBox="0 0 24 24" aria-hidden="true" focusable="false">{children}</svg>;
}
const EURO_ICON = <path d="M18 6.5A7 7 0 1 0 18 17.5M4 10h10M4 14h10" />;
const CLOCK_ICON = <><circle cx="12" cy="12" r="9" /><path d="M12 7v5l3 2" /></>;
const BELL_ICON = <><path d="M6 8a6 6 0 0 1 12 0c0 7 3 9 3 9H3s3-2 3-9" /><path d="M10.3 21a1.9 1.9 0 0 0 3.4 0" /></>;

// Handlungsbedarf: KI-Pruefung violett; was die Fristberechnung unmoeglich macht (kein berechenbares
// Vertragsende) rot; alle anderen Luecken gelb. Schluessel aus backend/app/reports/exports.py.
const DANGER_INSIGHTS = new Set(["no_end"]);

interface AttentionItem {
  key: string;
  label: string;
  count: number;
  href: string;
  tone: "ai" | "danger" | "warning";
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
  const [loaded, setLoaded] = useState(false);
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
        renewals: renewals.status === "fulfilled" ? renewals.value.items : null,
        portfolio: portfolio.status === "fulfilled" ? portfolio.value : null,
        unread: inbox.status === "fulfilled" ? inbox.value.unread_count : null,
        reviewCount: review.status === "fulfilled" && review.value ? review.value.total : null,
      });
      setLoaded(true);
      if ([deadlines, renewals, portfolio].every((result) => result.status === "rejected")) setFailed(true);
    });
  }, [organizationSlug, reviewer]);

  useEffect(load, [load]);

  const now = new Date();
  const firstName = account?.display_name?.split(" ")[0] ?? "";
  const openDecisions = (state.renewals ?? []).filter((item) => !item.decision);
  const overdue = (state.deadlines ?? []).filter((item) => item.overdue);
  const attention: AttentionItem[] = [
    ...(reviewer && state.reviewCount ? [{ key: "review", label: "Verträge mit offener KI-Prüfung", count: state.reviewCount, href: "/review", tone: "ai" as const }] : []),
    ...(state.portfolio?.insights ?? []).filter((item) => item.count > 0).map((item) => ({
      key: item.key,
      label: item.label,
      count: item.count,
      href: `/register?filter=${encodeURIComponent(JSON.stringify([item.filter]))}`,
      tone: DANGER_INSIGHTS.has(item.key) ? ("danger" as const) : ("warning" as const),
    })),
  ];
  const noticeTone = state.renewals === null ? "neutral" : openDecisions.length === 0 ? "success" : openDecisions.some((item) => item.days_left <= 30) ? "danger" : "warning";

  return (
    <div className="page my-day">
      <PageHeader
        variant="highlight"
        className="my-day-head"
        eyebrow="Mein Tag"
        documentTitle="Mein Tag"
        title={`${greeting(now)}${firstName ? `, ${firstName}` : ""}`}
        description={new Intl.DateTimeFormat("de-DE", { weekday: "long", day: "numeric", month: "long", year: "numeric" }).format(now)}
        actions={role === "admin" || role === "contract_manager" || account?.is_developer ? <Link href="/contracts/new" className="btn btn-primary">Vertrag anlegen</Link> : undefined}
      />

      {failed ? <p className="alert alert--critical" role="alert">Die Übersicht konnte nicht geladen werden. <button type="button" className="btn btn-sm" onClick={load}>Erneut laden</button></p> : null}

      <section className="my-day-kpis" aria-label="Kennzahlen">
        <KpiTile label="Laufende Verträge" tone="info" icon={<TileIcon>{ICONS.contracts}</TileIcon>} loading={!loaded} value={state.portfolio?.totals.running} hint={state.portfolio ? `von ${state.portfolio.totals.contracts} Verträgen` : undefined} href="/register" linkLabel="Zur Vertragsliste" />
        <KpiTile label="Jährliche Kosten (netto)" icon={<TileIcon>{EURO_ICON}</TileIcon>} loading={!loaded} value={state.portfolio && Number(state.portfolio.totals.annual_cost) !== 0 ? formatCurrency(state.portfolio.totals.annual_cost, "EUR") : null} hint="aus den gepflegten Finanzdaten" href="/analysen" linkLabel="Zu den Analysen" />
        <KpiTile label="Kündigungsfristen in 90 Tagen" tone={noticeTone} icon={<TileIcon>{CLOCK_ICON}</TileIcon>} loading={!loaded} value={state.renewals?.length} hint={state.renewals === null ? undefined : openDecisions.length === 0 ? <><span className="kpi-ok" aria-hidden="true">✓</span> Keine Entscheidung offen</> : `${openDecisions.length} ohne Entscheidung`} href="/fristen?ansicht=entscheidungen" linkLabel="Zu den Kündigungsentscheidungen" />
        <KpiTile label="Ungelesene Erinnerungen" tone={state.unread ? "warning" : "neutral"} icon={<TileIcon>{BELL_ICON}</TileIcon>} loading={!loaded} value={state.unread} hint="Erinnerungen und Eskalationen" href="/postfach" linkLabel="Zum Postfach" />
      </section>

      <div className="my-day-grid">
        <section className="card card-pad" aria-labelledby="my-attention">
          <div className="section-head"><div><h2 id="my-attention">Handlungsbedarf im Portfolio{attention.length > 0 ? <span className="my-day-attention-count">{attention.length}<span className="sr-only"> offene Punkte</span></span> : null}</h2><p>Lücken, die Fristen und Kosten unsicher machen</p></div></div>
          {state.portfolio === null ? <Skeleton lines={4} /> : attention.length === 0 ? <EmptyState variant="compact" title="Kein Handlungsbedarf erkannt">Die gepflegten Vertragsdaten sind vollständig.</EmptyState> : (
            <ul className="my-day-list">
              {attention.map((item) => (
                <li key={item.key} className="my-day-todo">
                  <Link href={item.href}>
                    <span className={`my-day-pill${item.tone === "warning" ? "" : ` my-day-pill--${item.tone}`}`}>{item.count}</span>
                    <span className="my-day-todo-label">{item.label}</span>
                    <svg viewBox="0 0 24 24" aria-hidden="true" focusable="false"><path d="m9 6 6 6-6 6" /></svg>
                  </Link>
                </li>
              ))}
            </ul>
          )}
        </section>

        <section className="card card-pad" aria-labelledby="my-deadlines">
          <div className="section-head"><div><h2 id="my-deadlines">Meine Termine bis {formatDate(isoInDays(7))}</h2><p>{overdue.length > 0 ? `${overdue.length} überfällig` : "Fällig in den nächsten sieben Tagen"}</p></div><Link href="/fristen?nur=meine" className="btn btn-sm">Alle Termine</Link></div>
          {state.deadlines === null ? <Skeleton lines={4} label="Termine werden geladen…" /> : state.deadlines.length === 0 ? <EmptyState variant="compact" title="Keine Termine diese Woche">Neue Fristen erscheinen hier automatisch.</EmptyState> : (
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
          <div className="section-head"><div><h2 id="my-decisions">Entscheidungen vor Kündigungsfrist</h2><p>Verträge mit Frist in 90 Tagen ohne erfasste Entscheidung</p></div><Link href="/fristen?ansicht=entscheidungen" className="btn btn-sm">Alle anzeigen</Link></div>
          {!loaded ? <Skeleton lines={4} label="Fristen werden geladen…" /> : state.renewals === null ? <p className="field-hint">Die Kündigungsfristen konnten nicht geladen werden.</p> : openDecisions.length === 0 ? <EmptyState variant="compact" title="Alles entschieden">Für die nächsten 90 Tage sind keine Entscheidungen offen.</EmptyState> : (
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
      </div>
    </div>
  );
}
