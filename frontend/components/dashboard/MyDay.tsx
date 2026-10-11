"use client";

import Link from "next/link";
import { NO_FINANCE_FILTERS, notEvaluableLink, registerHref } from "@/lib/fix-targets";
import { useCallback, useEffect, useState, type ReactNode } from "react";
import { useAuth } from "@/components/auth/AuthProvider";
import EmptyState from "@/components/ui/EmptyState";
import KpiTile from "@/components/ui/KpiTile";
import PageHeader from "@/components/ui/PageHeader";
import Signal, { SignalIcon, type SignalTone } from "@/components/ui/Signal";
import Skeleton from "@/components/ui/Skeleton";
import { ICONS } from "@/components/shell/navigation";
import { listDeadlines, type DeadlineDto } from "@/lib/domain-api/deadlines";
import { getGrid, getPortfolioReport, listRenewals, type NotEvaluableItem, type PortfolioReport, type RenewalListItem } from "@/lib/domain-api/registerGrid";
import { coverageNote, formatCurrency, formatDate } from "@/lib/format";

function isoInDays(days: number) {
  const date = new Date();
  date.setDate(date.getDate() + days);
  return date.toISOString().slice(0, 10);
}

function greeting(now: Date) {
  const hour = now.getHours();
  return hour < 11 ? "Guten Morgen" : hour < 18 ? "Guten Tag" : "Guten Abend";
}

function plural(count: number, one: string, many: string) {
  return `${count} ${count === 1 ? one : many}`;
}

// Liniensymbole im Stil der Navigation (components/shell/navigation.tsx).
function TileIcon({ children }: { children: ReactNode }) {
  return <svg viewBox="0 0 24 24" aria-hidden="true" focusable="false">{children}</svg>;
}
const EURO_ICON = <path d="M18 6.5A7 7 0 1 0 18 17.5M4 10h10M4 14h10" />;
const CLOCK_ICON = <><circle cx="12" cy="12" r="9" /><path d="M12 7v5l3 2" /></>;

const LEVEL_WORD: Record<"critical" | "ai" | "warning", string> = { critical: "Kritisch", ai: "KI-Prüfung", warning: "Prüfen" };
const LEVEL_ORDER = { critical: 0, ai: 1, warning: 2 } as const;
// Was eine Frist oder ein Vertragsende unberechenbar macht, ist kritisch; übrige Lücken „Prüfen“
// (Schweregrad kommt aus backend/app/reports/exports.py, Feld `severity`).
const SUBTEXT: Record<string, string> = {
  no_end: "Ende und Kündigungsfrist können nicht überwacht werden",
  review: "Vorschläge der KI bestätigen oder korrigieren",
  no_finance: "Kostenkennzahlen bleiben unvollständig",
};

interface WorkItem {
  key: string;
  level: "critical" | "ai" | "warning";
  label: string;
  count: number;
  href: string;
}

interface State {
  deadlines: DeadlineDto[] | null;
  renewals: RenewalListItem[] | null;
  notEvaluable: NotEvaluableItem[];
  portfolio: PortfolioReport | null;
  reviewCount: number | null;
}

// „Mein Tag“ (Ruhe & Signal v3): ein Lagebild in einem Satz, drei ruhige Kennzahlen, links was im Portfolio
// zu erledigen ist (nach Dringlichkeit), rechts die persönlichen Termine und Entscheidungen.
// Alle Zahlen aus denselben Quellen wie Vertragsliste, Fristen und Analysen; keine Beispieldaten.
export default function MyDay({ organizationSlug }: { organizationSlug: string }) {
  const { account, role } = useAuth();
  const [state, setState] = useState<State>({ deadlines: null, renewals: null, notEvaluable: [], portfolio: null, reviewCount: null });
  const [failed, setFailed] = useState(false);
  const [loaded, setLoaded] = useState(false);
  const reviewer = Boolean(account?.is_developer || role === "admin" || role === "contract_manager" || role === "reviewer");

  const load = useCallback(() => {
    setFailed(false);
    Promise.allSettled([
      listDeadlines(organizationSlug, { status: "open", mine: true, dueBefore: isoInDays(7) }),
      listRenewals(organizationSlug, 90),
      getPortfolioReport(organizationSlug),
      reviewer ? getGrid(organizationSlug, { columns: ["register_number"], filters: [{ column: "review_pending", op: "is", value: true }] }, { offset: 0, limit: 1 }) : Promise.resolve(null),
    ]).then(([deadlines, renewals, portfolio, review]) => {
      setState({
        deadlines: deadlines.status === "fulfilled" ? deadlines.value.items : null,
        renewals: renewals.status === "fulfilled" ? renewals.value.items : null,
        notEvaluable: renewals.status === "fulfilled" ? renewals.value.not_evaluable ?? [] : [],
        portfolio: portfolio.status === "fulfilled" ? portfolio.value : null,
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
  const urgentDecisions = openDecisions.filter((item) => item.days_left <= 30);
  const overdue = (state.deadlines ?? []).filter((item) => item.overdue);
  const insights = state.portfolio?.insights ?? [];
  const noFinance = insights.find((item) => item.key === "no_finance")?.count ?? 0;

  const work: WorkItem[] = [
    ...(reviewer && state.reviewCount ? [{ key: "review", level: "ai" as const, label: "Verträge mit offener KI-Prüfung", count: state.reviewCount, href: "/register?ansicht=review" }] : []),
    ...insights.filter((item) => item.count > 0).map((item) => ({
      key: item.key,
      level: (item.severity === "critical" ? "critical" : "warning") as WorkItem["level"],
      label: item.label,
      count: item.count,
      href: registerHref(item.filters ?? [item.filter]),
    })),
  ].sort((a, b) => LEVEL_ORDER[a.level] - LEVEL_ORDER[b.level]);

  // Lagebild: Themen (nicht Verträge), die heute Aufmerksamkeit brauchen.
  const criticalInsights = work.filter((item) => item.level === "critical");
  // Jedes Thema führt direkt zu der Liste, in der es erledigt wird.
  const topics: { tone: SignalTone; text: string; href: string }[] = [
    ...criticalInsights.map((item) => ({ tone: "critical" as const, text: item.key === "no_end" ? plural(item.count, "Vertrag ohne berechenbare Frist", "Verträge ohne berechenbare Frist") : `${item.count} ${item.label}`, href: item.href })),
    ...(overdue.length ? [{ tone: "critical" as const, text: plural(overdue.length, "Termin überfällig", "Termine überfällig"), href: "/fristen?ansicht=termine&nur=meine" }] : []),
    ...(reviewer && state.reviewCount ? [{ tone: "ai" as const, text: plural(state.reviewCount, "KI-Prüfung", "KI-Prüfungen"), href: "/register?ansicht=review" }] : []),
    ...(urgentDecisions.length ? [{ tone: "warning" as const, text: plural(urgentDecisions.length, "Entscheidung in ≤ 30 Tagen", "Entscheidungen in ≤ 30 Tagen"), href: "/fristen?ansicht=entscheidungen" }] : []),
  ];
  const calm: string[] = [
    ...(state.deadlines !== null && state.deadlines.length === 0 ? ["Keine Termine diese Woche"] : []),
    ...(state.renewals !== null && openDecisions.length === 0 && state.notEvaluable.length === 0 ? ["Keine Entscheidung offen"] : []),
  ];

  const annual = state.portfolio?.totals.amounts?.annual_cost;
  // Ohne laufende Verträge gibt es keine Jahreskosten – das ist etwas anderes als fehlende Daten.
  const annualSignal = state.portfolio && !state.portfolio.totals.annual_cost
    ? noFinance > 0
      ? { tone: "warning" as const, label: `Kosten fehlen bei ${plural(noFinance, "Vertrag", "Verträgen")}` }
      : state.portfolio.totals.running === 0
        ? { tone: "neutral" as const, label: "Keine laufenden Verträge" }
        : undefined
    : undefined;
  const annualHint = annual ? coverageNote(annual.known, annual.missing) || "aus den gepflegten Finanzdaten" : "aus den gepflegten Finanzdaten";
  const runningHint = state.portfolio
    ? `von ${state.portfolio.totals.contracts} Verträgen${state.portfolio.totals.in_progress ? ` · ${state.portfolio.totals.in_progress} in Arbeit` : ""}`
    : undefined;
  const notEvaluableHref = notEvaluableLink(state.notEvaluable);
  const canCreate = role === "admin" || role === "contract_manager" || account?.is_developer;

  return (
    <div className="page my-day">
      <PageHeader
        className="my-day-head"
        documentTitle="Mein Tag"
        title={`${greeting(now)}${firstName ? `, ${firstName}` : ""}`}
        description={new Intl.DateTimeFormat("de-DE", { weekday: "long", day: "numeric", month: "long", year: "numeric" }).format(now)}
        actions={canCreate ? <Link href="/contracts/new" className="btn btn-primary">Vertrag anlegen</Link> : undefined}
      />

      {failed ? <p className="alert alert--critical" role="alert">Die Übersicht konnte nicht geladen werden. <button type="button" className="btn btn-sm" onClick={load}>Erneut laden</button></p> : null}

      <section className="card my-day-brief" aria-label="Lagebild">
        {!loaded ? <Skeleton lines={1} label="Lagebild wird erstellt…" /> : <>
          <p className="my-day-brief-main">
            <SignalIcon tone={topics.length ? "warning" : "neutral"} className={topics.length ? "my-day-brief-icon is-attention" : "my-day-brief-icon"} />
            {topics.length ? `Heute ${topics.length === 1 ? "braucht 1 Thema" : `brauchen ${topics.length} Themen`} Ihre Aufmerksamkeit` : "Heute ist nichts dringend"}
          </p>
          <div className="my-day-brief-items">
            {topics.slice(0, 3).map((item) => <Link key={item.text} className="signal-link" href={item.href}><Signal tone={item.tone}>{item.text}</Signal></Link>)}
            {topics.length < 3 ? calm.slice(0, 3 - topics.length).map((text) => <Signal key={text} tone="neutral">{text}</Signal>) : null}
          </div>
        </>}
      </section>

      <section className="my-day-kpis" aria-label="Kennzahlen">
        <KpiTile label="Laufende Verträge" icon={<TileIcon>{ICONS.contracts}</TileIcon>} loading={!loaded} value={state.portfolio?.totals.running} hint={runningHint} href="/register" linkLabel="Zur Vertragsliste" />
        <KpiTile label="Jährliche Kosten (netto)" icon={<TileIcon>{EURO_ICON}</TileIcon>} loading={!loaded} value={state.portfolio?.totals.annual_cost ? formatCurrency(state.portfolio.totals.annual_cost, "EUR") : null} hint={annualHint} signal={annualSignal} href={noFinance > 0 ? registerHref(NO_FINANCE_FILTERS) : "/analysen"} linkLabel={noFinance > 0 ? "Verträge ohne Kosten anzeigen" : "Zu den Analysen"} />
        <KpiTile label="Kündigungsfristen in 90 Tagen" icon={<TileIcon>{CLOCK_ICON}</TileIcon>} loading={!loaded} value={state.renewals?.length} hint={state.renewals === null ? undefined : openDecisions.length === 0 ? (state.notEvaluable.length > 0 ? `${state.notEvaluable.length} nicht bewertbar` : "Keine Entscheidung offen") : `${openDecisions.length} ohne Entscheidung`} href={openDecisions.length === 0 && state.notEvaluable.length > 0 ? notEvaluableHref : "/fristen?ansicht=entscheidungen"} linkLabel={openDecisions.length === 0 && state.notEvaluable.length > 0 ? "Laufzeitangaben ergänzen" : "Zu den Kündigungsentscheidungen"} />
      </section>

      <div className="my-day-grid">
        <section className="card card-pad" aria-labelledby="my-attention">
          <div className="section-head"><div><h2 id="my-attention">Zu erledigen – nach Dringlichkeit</h2><p>Portfolio: Lücken, die Fristen und Kosten unsicher machen{work.length ? ` · ${plural(work.length, "Problemart", "Problemarten")}` : ""}</p></div></div>
          {state.portfolio === null && !loaded ? <Skeleton lines={4} /> : state.portfolio === null ? <p className="field-hint">Der Portfoliostand konnte nicht geladen werden.</p> : work.length === 0 ? <EmptyState variant="calm" title="Nichts zu erledigen">Die gepflegten Vertragsdaten sind vollständig.</EmptyState> : (
            <ul className="my-day-work">
              {work.map((item) => (
                <li key={item.key}>
                  <Link href={item.href}>
                    <Signal tone={item.level}>{LEVEL_WORD[item.level]}</Signal>
                    <span className="my-day-work-count">{item.count}</span>
                    <span className="my-day-work-label">{item.label}{SUBTEXT[item.key] ? <small>{SUBTEXT[item.key]}</small> : null}</span>
                    <svg className="my-day-chevron" viewBox="0 0 24 24" aria-hidden="true" focusable="false"><path d="m9 6 6 6-6 6" /></svg>
                  </Link>
                </li>
              ))}
            </ul>
          )}
        </section>

        <div className="my-day-stack">
          <section className="card card-pad" aria-labelledby="my-deadlines">
            <div className="section-head"><div><h2 id="my-deadlines">Meine Termine bis {formatDate(isoInDays(7))}</h2><p>Persönlich: {overdue.length > 0 ? `${overdue.length} überfällig, ` : ""}nächste sieben Tage</p></div><Link href="/fristen?ansicht=termine&nur=meine&zeitraum=7" className="btn btn-sm">Alle Termine</Link></div>
            {!loaded ? <Skeleton lines={4} label="Termine werden geladen…" /> : state.deadlines === null ? <p className="field-hint">Die Termine konnten nicht geladen werden.</p> : state.deadlines.length === 0 ? <EmptyState variant="calm" title="Keine Termine diese Woche"><>Neue Fristen erscheinen hier automatisch. <Link href="/fristen?ansicht=termine&nur=meine&zeitraum=alle">Alle meine offenen Termine</Link></></EmptyState> : (
              <ul className="my-day-list">
                {[...overdue, ...state.deadlines.filter((item) => !item.overdue)].slice(0, 8).map((item) => (
                  <li key={item.id}>
                    <span className="my-day-date">{formatDate(item.due_date)}</span>
                    <div><Link href={`/contracts/${item.contract_id}?tab=deadlines`}>{item.title}</Link><small>{item.contract_label ?? ""}</small></div>
                    {item.overdue ? <Signal tone="critical">Überfällig</Signal> : item.days_until_due === 0 ? <Signal tone="warning">Heute</Signal> : null}
                  </li>
                ))}
              </ul>
            )}
          </section>

          <section className="card card-pad" aria-labelledby="my-decisions">
            <div className="section-head"><div><h2 id="my-decisions">Entscheidungen vor Kündigungsfrist</h2><p>Frist in 90 Tagen, ohne erfasste Entscheidung</p></div><Link href="/fristen?ansicht=entscheidungen" className="btn btn-sm">Alle anzeigen</Link></div>
            {!loaded ? <Skeleton lines={4} label="Fristen werden geladen…" /> : state.renewals === null ? <p className="field-hint">Die Kündigungsfristen konnten nicht geladen werden.</p> : openDecisions.length === 0 ? (state.notEvaluable.length > 0
              ? <EmptyState variant="calm" title="Keine offenen Entscheidungen bekannt"><>Für {plural(state.notEvaluable.length, "Vertrag", "Verträge")} ist die Kündigungsfrist nicht berechenbar. <Link href={notEvaluableHref}>Laufzeitangaben ergänzen</Link></></EmptyState>
              : <EmptyState variant="calm" title="Alles entschieden">Für die nächsten 90 Tage sind keine Entscheidungen offen.</EmptyState>) : (
              <ul className="my-day-list">
                {openDecisions.slice(0, 6).map((item) => (
                  <li key={item.contract_id}>
                    <span className="my-day-date">{formatDate(item.cancel_by)}</span>
                    <div><Link href={`/contracts/${item.contract_id}?tab=deadlines`}>{item.register_number ?? "–"} · {item.short_description ?? ""}</Link><small>{item.partner ?? ""}{item.annual_cost ? ` · ${formatCurrency(item.annual_cost, "EUR")} jährlich` : ""}</small></div>
                    <Signal tone={item.days_left < 0 ? "critical" : item.days_left <= 30 ? "warning" : "neutral"}>{item.days_left < 0 ? "verstrichen" : `in ${item.days_left} Tagen`}</Signal>
                  </li>
                ))}
              </ul>
            )}
          </section>
        </div>
      </div>
    </div>
  );
}
