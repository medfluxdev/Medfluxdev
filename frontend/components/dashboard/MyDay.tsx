"use client";

import Link from "next/link";
import { useCallback, useEffect, useRef, useState, type KeyboardEvent, type ReactNode } from "react";
import { useAuth } from "@/components/auth/AuthProvider";
import { TERMIN_KIND_ORDER, deadlineKind, type TerminKind } from "@/components/deadlines/TerminKind";
import EmptyState from "@/components/ui/EmptyState";
import PageHeader from "@/components/ui/PageHeader";
import Skeleton from "@/components/ui/Skeleton";
import { getContract } from "@/lib/domain-api/contracts";
import { listDeadlines, type DeadlineDto } from "@/lib/domain-api/deadlines";
import { getGrid, getPortfolioReport, listRenewals, type GridResponse, type NotEvaluableItem, type PortfolioReport, type RenewalListItem } from "@/lib/domain-api/registerGrid";
import { FINANCE_ENTRIES_TARGET, NO_FINANCE_FILTERS, contractHref, notEvaluableLink, registerField, registerHref } from "@/lib/fix-targets";
import { formatCurrency, formatDate } from "@/lib/format";
import { deadlineOrigin } from "@/lib/deadline-origin";
import { buildTodo, compactEuro, readStoredTab, storeTab, type MyDayTab, type TodoIcon, type TodoRow } from "@/lib/my-day";

const FETCH_DAYS = 90;
const HORIZONS = [{ days: 7, label: "Nächste 7 Tage" }, { days: 30, label: "Nächste 30 Tage" }, { days: 90, label: "Nächste 90 Tage" }];
const WEEK_DAYS = 7;

function isoInDays(days: number) {
  const date = new Date();
  date.setDate(date.getDate() + days);
  return date.toISOString().slice(0, 10);
}

/** Heutiges Datum (lokal) als ISO – Schlüssel für den gemerkten Reiter. */
function localToday() {
  return new Intl.DateTimeFormat("sv-SE").format(new Date());
}

function greeting(now: Date) {
  const hour = now.getHours();
  return hour < 11 ? "Guten Morgen" : hour < 18 ? "Guten Tag" : "Guten Abend";
}

// Tafel „Was steht an?“: Zeilen aus buildTodo, nach Art in drei Spalten verteilt.
const BOARD_COLUMNS: { id: "urgent" | "review" | "data"; title: string; keys: string[] }[] = [
  { id: "urgent", title: "Dringend", keys: ["overdue", "decision", "dueSoon"] },
  { id: "review", title: "Zur Prüfung", keys: ["aiReview"] },
  { id: "data", title: "Daten ergänzen", keys: ["missingEnd", "missingCosts"] },
];

function unitLabel(row: TodoRow): string {
  const noun = row.key === "decision" || row.key === "dueSoon" ? ["Frist", "Fristen"] : row.key === "overdue" ? ["Termin", "Termine"] : ["Vertrag", "Verträge"];
  return `${row.count} ${row.count === 1 ? noun[0] : noun[1]}`;
}

const MONTHS = ["Jan", "Feb", "Mär", "Apr", "Mai", "Jun", "Jul", "Aug", "Sep", "Okt", "Nov", "Dez"];

const svg = (body: ReactNode) => <svg viewBox="0 0 24 24" aria-hidden="true" focusable="false">{body}</svg>;
const ICONS: Record<TodoIcon, ReactNode> = {
  cal: svg(<><rect x="4" y="5" width="16" height="15" rx="2" /><path d="M8 3v4M16 3v4M4 10h16" /></>),
  scale: svg(<path d="M12 4v16M6 20h12M5 8h14M5 8l-2 6a3 3 0 0 0 4 0zM19 8l-2 6a3 3 0 0 0 4 0z" />),
  alert: svg(<><path d="M12 4 3 20h18z" /><path d="M12 10v4M12 17v.5" /></>),
  hour: svg(<path d="M7 3h10M7 21h10M8 3c0 5 8 5 8 9s-8 4-8 9M16 3c0 5-8 5-8 9s8 4 8 9" />),
  spark: svg(<path d="M12 3l1.8 5.2L19 10l-5.2 1.8L12 17l-1.8-5.2L5 10l5.2-1.8z" />),
  eur: svg(<path d="M18 6.5A7 7 0 1 0 18 17.5M4 10h10M4 14h10" />),
};
const TAB_ICONS: Record<MyDayTab, ReactNode> = {
  todo: svg(<><rect x="5" y="4" width="14" height="17" rx="2" /><path d="M9 4h6v3H9zM9 12h6M9 16h4" /></>),
  dates: svg(<><rect x="4" y="5" width="16" height="15" rx="2" /><path d="M8 3v4M16 3v4M4 10h16" /></>),
  notice: svg(<><path d="M7 3h7l4 4v14H7z" /><path d="M14 3v4h4M10 12h5M10 16h5" /></>),
  figures: svg(<path d="M6 20V10M12 20V4M18 20v-7" />),
};
const CHEVRON = svg(<path d="m9 6 6 6-6 6" />);
const CHECK = svg(<path d="m5 12.5 4.5 4.5L19 7.5" />);

interface State {
  deadlines: DeadlineDto[] | null;
  renewals: RenewalListItem[] | null;
  notEvaluable: NotEvaluableItem[];
  portfolio: PortfolioReport | null;
  reviewCount: number | null;
  /** Verträge mit Jahreskosten (Kosten je Vertrag) und Verträge ohne Kosten (Daten ergänzen). */
  costs: GridResponse | null;
  withoutCosts: GridResponse | null;
  /** Verträge mit offener KI-Prüfung (die ersten drei) und, sobald geladen, wie viele wesentliche Entscheidungen warten. */
  reviewItems: { id: string; name: string; essentialOpen: number | null }[];
}

// „Mein Tag“ (v5): Begrüßung mit den drei Kennzahlen in einer Zeile, darunter ein Block mit zwei Reitern –
// „Zu erledigen“ (alles, was wirklich zu tun ist, das Dringendste zuerst) und „Termine“ (die nächsten fünf).
// Alle Zahlen aus denselben Quellen wie Vertragsliste, Fristen und Analysen; keine Beispieldaten.
export default function MyDay({ organizationSlug }: { organizationSlug: string }) {
  const { account, role } = useAuth();
  const [state, setState] = useState<State>({ deadlines: null, renewals: null, notEvaluable: [], portfolio: null, reviewCount: null, costs: null, withoutCosts: null, reviewItems: [] });
  const [failed, setFailed] = useState(false);
  const [loaded, setLoaded] = useState(false);
  const [chosen, setChosen] = useState<MyDayTab | null>(null);
  const [horizon, setHorizon] = useState(30);
  const [noticeSort, setNoticeSort] = useState<"date" | "cost">("date");
  const [kindFilter, setKindFilter] = useState<"" | TerminKind>("");
  const tabRefs = useRef<Record<MyDayTab, HTMLButtonElement | null>>({ todo: null, dates: null, notice: null, figures: null });
  const reviewer = Boolean(account?.is_developer || role === "admin" || role === "contract_manager" || role === "reviewer");

  const load = useCallback(() => {
    setFailed(false);
    Promise.allSettled([
      listDeadlines(organizationSlug, { status: "open", mine: true, dueBefore: isoInDays(FETCH_DAYS) }),
      listRenewals(organizationSlug, 90),
      getPortfolioReport(organizationSlug),
      reviewer ? getGrid(organizationSlug, { columns: ["register_number"], filters: [{ column: "review_pending", op: "is", value: true }] }, { offset: 0, limit: 3 }) : Promise.resolve(null),
      getGrid(organizationSlug, { columns: ["register_number", "short_description", "annual_cost"], filters: [] }, { offset: 0, limit: 200 }),
      getGrid(organizationSlug, { columns: ["register_number", "short_description"], filters: NO_FINANCE_FILTERS }, { offset: 0, limit: 5 }),
    ]).then(([deadlines, renewals, portfolio, review, costs, withoutCosts]) => {
      const items = review.status === "fulfilled" && review.value
        ? review.value.items.map((item) => ({ id: item.contract_id, name: [item.values.register_number, item.values.short_description].filter(Boolean).join(" · ") || "Vertrag", essentialOpen: null as number | null }))
        : [];
      // Wie viele wesentliche Entscheidungen warten, steht in der Prüfung des Vertrags – für die ersten drei nachladen.
      items.forEach((item) => {
        getContract(item.id, organizationSlug)
          .then((detail) => setState((current) => ({ ...current, reviewItems: current.reviewItems.map((entry) => (entry.id === item.id ? { ...entry, essentialOpen: detail.field_review?.essential_open ?? null } : entry)) })))
          .catch(() => undefined);
      });
      setState({
        deadlines: deadlines.status === "fulfilled" ? deadlines.value.items : null,
        renewals: renewals.status === "fulfilled" ? renewals.value.items : null,
        notEvaluable: renewals.status === "fulfilled" ? renewals.value.not_evaluable ?? [] : [],
        portfolio: portfolio.status === "fulfilled" ? portfolio.value : null,
        reviewCount: review.status === "fulfilled" && review.value ? review.value.total : null,
        costs: costs.status === "fulfilled" ? costs.value : null,
        withoutCosts: withoutCosts.status === "fulfilled" ? withoutCosts.value : null,
        reviewItems: items,
      });
      setLoaded(true);
      if ([deadlines, renewals, portfolio].every((result) => result.status === "rejected")) setFailed(true);
    });
  }, [organizationSlug, reviewer]);

  useEffect(load, [load]);
  useEffect(() => { setChosen(readStoredTab(localToday())); }, []);

  const now = new Date();
  const firstName = account?.display_name?.split(" ")[0] ?? "";
  const insights = state.portfolio?.insights ?? [];
  const insight = (key: string) => insights.find((item) => item.key === key);
  const noEnd = insight("no_end");
  const noFinance = insight("no_finance");

  const todo = buildTodo({
    overdue: (state.deadlines ?? []).filter((item) => item.overdue),
    openDecisions: (state.renewals ?? []).filter((item) => !item.decision),
    missingEnd: { count: noEnd?.count ?? 0, href: registerHref(noEnd?.filters ?? (noEnd ? [noEnd.filter] : [])) },
    missingCosts: { count: noFinance?.count ?? 0, href: registerHref(noFinance?.filters ?? (noFinance ? [noFinance.filter] : NO_FINANCE_FILTERS)) },
    reviewCount: reviewer ? state.reviewCount ?? 0 : 0,
    hrefs: { overdue: "/fristen?ansicht=termine&nur=meine", decisions: "/fristen?ansicht=entscheidungen", review: "/register?ansicht=review" },
  });
  const notices = [...(state.renewals ?? [])].sort((a, b) => noticeSort === "cost"
    ? Number(b.annual_cost ?? -1) - Number(a.annual_cost ?? -1) || a.cancel_by.localeCompare(b.cancel_by)
    : a.cancel_by.localeCompare(b.cancel_by));
  const noticeColumns = [
    { id: "urgent", title: "Dringend", items: notices.filter((item) => item.days_left <= 30) },
    { id: "soon", title: "Demnächst", items: notices.filter((item) => item.days_left > 30) },
    { id: "unknown", title: "Nicht berechenbar", items: [] as RenewalListItem[], extra: state.notEvaluable.length },
  ];
  // Termine der Person: im gewählten Zeitraum und nach Art; Überfälliges zählt immer mit.
  const dated = (state.deadlines ?? [])
    .filter((item) => item.overdue || item.days_until_due <= horizon)
    .filter((item) => !kindFilter || deadlineKind(item) === kindFilter)
    .sort((a, b) => a.due_date.localeCompare(b.due_date));
  const dateColumns = [
    { id: "late", title: "Überfällig", items: dated.filter((item) => item.overdue) },
    { id: "week", title: "Diese Woche", items: dated.filter((item) => !item.overdue && item.days_until_due <= WEEK_DAYS) },
    { id: "later", title: "Später", items: dated.filter((item) => !item.overdue && item.days_until_due > WEEK_DAYS) },
  ];
  const upcoming = dated;
  const hasCritical = todo.some((row) => row.tone === "critical");
  const tab: MyDayTab = chosen ?? (todo.length > 0 ? "todo" : "dates");

  function select(next: MyDayTab, focus = false) {
    setChosen(next);
    storeTab(localToday(), next);
    if (focus) tabRefs.current[next]?.focus();
  }

  function onKeyDown(event: KeyboardEvent<HTMLDivElement>) {
    const order: MyDayTab[] = ["todo", "dates", "notice", "figures"];
    const index = order.indexOf(tab);
    const target = event.key === "ArrowRight" ? order[(index + 1) % order.length]
      : event.key === "ArrowLeft" ? order[(index + order.length - 1) % order.length]
        : event.key === "Home" ? order[0] : event.key === "End" ? order[order.length - 1] : null;
    if (!target) return;
    event.preventDefault();
    select(target, true);
  }

  const totals = state.portfolio?.totals;
  const coverage = totals?.amounts?.annual_cost;
  const costKnown = coverage?.known ?? 0;
  const costMissing = coverage?.missing ?? 0;
  const costRows = (state.costs?.items ?? [])
    .map((item) => ({ id: item.contract_id, value: Number(item.values.annual_cost), name: [item.values.register_number, item.values.short_description].filter(Boolean).join(" · ") || "Vertrag" }))
    .filter((row) => Number.isFinite(row.value) && row.value > 0)
    .sort((a, b) => b.value - a.value);
  const costSum = costRows.reduce((sum, row) => sum + row.value, 0);
  const byType = (state.portfolio?.cost_by?.contract_type ?? [])
    .map((item) => ({ label: item.label, value: Number(item.annual_cost) }))
    .filter((item) => Number.isFinite(item.value) && item.value > 0)
    .sort((a, b) => b.value - a.value)
    .slice(0, 6);
  const byTypeMax = Math.max(1, ...byType.map((item) => item.value));
  const byTypeSum = Math.max(1, byType.reduce((sum, item) => sum + item.value, 0));
  const annual = totals?.annual_cost ?? null;
  const canCreate = role === "admin" || role === "contract_manager" || account?.is_developer;
  const dateText = new Intl.DateTimeFormat("de-DE", { weekday: "long", day: "numeric", month: "long", year: "numeric" }).format(now);
  return (
    <div className="page my-day">
      <PageHeader
        className="my-day-head"
        documentTitle="Mein Tag"
        title={`${greeting(now)}${firstName ? `, ${firstName}` : ""}`}
        description={dateText}
        actions={canCreate ? <Link href="/contracts/new" className="btn btn-primary my-day-create"><svg viewBox="0 0 24 24" aria-hidden="true" focusable="false"><path d="M12 5v14M5 12h14" /></svg>Vertrag anlegen</Link> : undefined}
      />

      {failed ? <p className="alert alert--critical" role="alert">Die Übersicht konnte nicht geladen werden. <button type="button" className="btn btn-sm" onClick={load}>Erneut laden</button></p> : null}

      <section className="my-day-block" aria-label="Heute">
        <div className="my-day-tabs" role="tablist" aria-label="Heute" onKeyDown={onKeyDown}>
          <button type="button" role="tab" id="my-tab-todo" aria-selected={tab === "todo"} aria-controls="my-panel-todo" tabIndex={tab === "todo" ? 0 : -1}
            ref={(element) => { tabRefs.current.todo = element; }} onClick={() => select("todo")}>
            <span className="my-tab-icon" aria-hidden="true">{TAB_ICONS.todo}</span>Zu erledigen<span className={`my-day-badge${hasCritical ? " is-critical" : ""}`}>{todo.length}</span>
          </button>
          <button type="button" role="tab" id="my-tab-dates" aria-selected={tab === "dates"} aria-controls="my-panel-dates" tabIndex={tab === "dates" ? 0 : -1}
            ref={(element) => { tabRefs.current.dates = element; }} onClick={() => select("dates")}>
            <span className="my-tab-icon" aria-hidden="true">{TAB_ICONS.dates}</span>Termine<span className="my-day-badge">{dated.length}</span>
          </button>
          <button type="button" role="tab" id="my-tab-notice" aria-selected={tab === "notice"} aria-controls="my-panel-notice" tabIndex={tab === "notice" ? 0 : -1}
            ref={(element) => { tabRefs.current.notice = element; }} onClick={() => select("notice")}>
            <span className="my-tab-icon" aria-hidden="true">{TAB_ICONS.notice}</span>Kündigung<span className={`my-day-badge${notices.some((item) => item.days_left <= 30 && !item.decision) ? " is-critical" : ""}`}>{notices.length}</span>
          </button>
          <button type="button" role="tab" id="my-tab-figures" aria-selected={tab === "figures"} aria-controls="my-panel-figures" tabIndex={tab === "figures" ? 0 : -1}
            ref={(element) => { tabRefs.current.figures = element; }} onClick={() => select("figures")}>
            <span className="my-tab-icon" aria-hidden="true">{TAB_ICONS.figures}</span>Zahlen
          </button>
        </div>

        <div role="tabpanel" id="my-panel-todo" aria-labelledby="my-tab-todo" hidden={tab !== "todo"}>
          {!loaded ? <div className="my-day-pad"><Skeleton lines={4} label="Aufgaben werden geladen…" /></div>
            : state.portfolio === null && state.deadlines === null && state.renewals === null ? <p className="field-hint my-day-pad">Die Aufgaben konnten nicht geladen werden.</p>
              : todo.length === 0 ? <EmptyState variant="calm" title="Alles erledigt">Keine offenen Aufgaben – schönen Tag.</EmptyState>
                : <div className="my-board">
                  <h2 className="my-board-title">Was steht an?<span>{todo.length} {todo.length === 1 ? "Hinweis" : "Hinweise"}</span></h2>
                  <div className="my-board-cols">
                    {BOARD_COLUMNS.map((column) => {
                      const rows = todo.filter((row) => column.keys.includes(row.key));
                      return <section key={column.id} className={`my-col my-col--${column.id}`} aria-labelledby={`my-col-${column.id}`}>
                        <h3 id={`my-col-${column.id}`} className="my-col-head"><span className="my-col-dot" aria-hidden="true" />{column.title}<span className="my-col-count">{rows.length}</span></h3>
                        {column.id === "review" && state.reviewItems.length > 0 ? <>
                          {state.reviewItems.map((item) => <article key={item.id} className="my-card my-card--ai">
                            <header className="my-card-head">
                              <span className="my-card-icon" aria-hidden="true">{ICONS.spark}</span>
                              <div className="my-card-text"><span className="my-card-word">KI-Prüfung</span><h4>{item.name}</h4></div>
                              {item.essentialOpen ? <span className="my-card-unit">{item.essentialOpen} wesentlich</span> : null}
                            </header>
                            <p className="my-card-context">{item.essentialOpen ? `${item.essentialOpen} wesentliche ${item.essentialOpen === 1 ? "Entscheidung wartet" : "Entscheidungen warten"}` : "Vorschläge der KI bestätigen oder korrigieren"}</p>
                            <Link className="btn my-card-action" href={`/contracts/${item.id}?tab=documents&subtab=review`}>Wesentliche Angaben prüfen<span className="visually-hidden">: {item.name}</span>{CHEVRON}</Link>
                          </article>)}
                          {(state.reviewCount ?? 0) > state.reviewItems.length ? <p className="my-col-more"><Link href="/register?ansicht=review">und {(state.reviewCount ?? 0) - state.reviewItems.length} weitere {(state.reviewCount ?? 0) - state.reviewItems.length === 1 ? "Vertrag" : "Verträge"} →</Link></p> : null}
                        </> : rows.length === 0 ? <p className="my-col-empty">Nichts offen</p> : rows.map((row, index) => (
                          <article key={row.key} className={`my-card my-card--${row.tone}${column.id === "urgent" && index === 0 ? " is-first" : ""}`}>
                            <header className="my-card-head">
                              <span className="my-card-icon" aria-hidden="true">{ICONS[row.icon]}</span>
                              <div className="my-card-text">
                                <span className="my-card-word">{row.word}</span>
                                <h4>{row.title}</h4>
                              </div>
                              {row.key !== "overdue" ? <span className="my-card-unit">{unitLabel(row)}</span> : null}
                            </header>
                            <p className="my-card-context">{row.context}</p>
                            <Link className={`btn my-card-action${column.id === "urgent" && index === 0 ? " btn-primary" : ""}`} href={row.href}>{row.action}<span className="visually-hidden">: {row.title}</span>{CHEVRON}</Link>
                          </article>
                        ))}
                      </section>;
                    })}
                  </div>
                  <p className="my-board-note">Hinweise können denselben Vertrag betreffen.</p>
                </div>}
        </div>

        <div role="tabpanel" id="my-panel-dates" aria-labelledby="my-tab-dates" hidden={tab !== "dates"} className="card my-day-card">
          {!loaded ? <div className="my-day-pad"><Skeleton lines={4} label="Termine werden geladen…" /></div>
            : state.deadlines === null ? <p className="field-hint my-day-pad">Die Termine konnten nicht geladen werden.</p>
              : <div className="my-board my-board--dates">
                <div className="my-board-bar">
                  <h2 className="my-board-title">Anstehende Termine<span>{dated.length} {dated.length === 1 ? "Termin" : "Termine"}</span></h2>
                  <label className="my-filter">Zeitraum<select value={horizon} onChange={(event) => setHorizon(Number(event.target.value))}>
                    {HORIZONS.map((item) => <option key={item.days} value={item.days}>{item.label}</option>)}
                  </select></label>
                  <label className="my-filter">Terminart<select value={kindFilter} onChange={(event) => setKindFilter(event.target.value as "" | TerminKind)}>
                    <option value="">Alle Terminarten</option>
                    {TERMIN_KIND_ORDER.map((kind) => <option key={kind} value={kind}>{kind}</option>)}
                  </select></label>
                </div>
                {dated.length === 0 ? <p className="my-day-empty">Keine Termine in den nächsten {horizon} Tagen.</p> : <div className="my-board-cols">
                  {dateColumns.map((column) => <section key={column.id} className={`my-col my-col--${column.id}`} aria-labelledby={`my-dcol-${column.id}`}>
                    <h3 id={`my-dcol-${column.id}`} className="my-col-head"><span className="my-col-dot" aria-hidden="true" />{column.title}<span className="my-col-count">{column.items.length}</span></h3>
                    {column.items.length === 0 ? <p className="my-col-empty">Nichts offen</p> : column.items.map((item, index) => {
                      const origin = deadlineOrigin(item);
                      const lead = Math.round((new Date(`${item.due_date}T00:00:00`).getTime() - new Date(`${item.remind_on}T00:00:00`).getTime()) / 86400000);
                      return <article key={item.id} className={`my-card my-card--date${column.id === "late" ? " my-card--late" : ""}`}>
                        <header className="my-card-head">
                          <span className="my-card-icon" aria-hidden="true">{ICONS.cal}</span>
                          <div className="my-card-text">
                            <h4><Link className="my-card-link" href={origin.href} title={`Zur Quelle: ${origin.label}`}>{item.title}</Link></h4>
                            <span className="my-card-when">{formatDate(item.due_date)}{item.overdue ? " · Überfällig" : item.days_until_due === 0 ? " · Heute" : ""}</span>
                            <span className="my-card-context">{[deadlineKind(item), item.contract_label].filter(Boolean).join(" · ")}</span>
                          </div>
                        </header>
                        <footer className="my-card-foot">
                          <span className="my-card-reminder"><svg viewBox="0 0 24 24" aria-hidden="true" focusable="false"><path d="M6 8a6 6 0 0 1 12 0c0 7 3 9 3 9H3s3-2 3-9M10.3 21a1.9 1.9 0 0 0 3.4 0" /></svg>{lead > 0 ? `Erinnerung: ${lead} ${lead === 1 ? "Tag" : "Tage"} vorher` : "Erinnerung am Fälligkeitstag"}</span>
                          <Link className={`btn btn-sm${column.id === "week" && index === 0 ? " btn-primary" : ""}`} href={origin.href}>Termin öffnen<span className="visually-hidden">: {item.title}</span>{CHEVRON}</Link>
                        </footer>
                      </article>;
                    })}
                  </section>)}
                </div>}
              </div>}
          <p className="my-day-foot"><Link href="/fristen?ansicht=termine&nur=meine">Alle Termine →</Link></p>
        </div>

        <div role="tabpanel" id="my-panel-notice" aria-labelledby="my-tab-notice" hidden={tab !== "notice"} className="card my-day-card">
          {!loaded ? <div className="my-day-pad"><Skeleton lines={3} label="Kündigungsfristen werden geladen…" /></div>
            : state.renewals === null ? <p className="field-hint my-day-pad">Die Kündigungsfristen konnten nicht geladen werden.</p>
              : <div className="my-board my-board--dates">
                <div className="my-board-bar">
                  <h2 className="my-board-title">Kündigungsfristen im Blick<span>{notices.length + state.notEvaluable.length} {notices.length + state.notEvaluable.length === 1 ? "Vertrag" : "Verträge"}</span></h2>
                  <label className="my-filter">Sortierung<select value={noticeSort} onChange={(event) => setNoticeSort(event.target.value as "date" | "cost")}>
                    <option value="date">Nach Frist sortiert</option>
                    <option value="cost">Nach Kosten sortiert</option>
                  </select></label>
                </div>
                <div className="my-board-cols">
                  {noticeColumns.map((column) => <section key={column.id} className={`my-col my-col--${column.id}`} aria-labelledby={`my-ncol-${column.id}`}>
                    <h3 id={`my-ncol-${column.id}`} className="my-col-head"><span className="my-col-dot" aria-hidden="true" />{column.title}<span className="my-col-count">{column.id === "unknown" ? state.notEvaluable.length : column.items.length}</span></h3>
                    {column.items.length === 0 && !(column.id === "unknown" && state.notEvaluable.length > 0) ? <p className="my-col-empty">Nichts offen</p> : column.items.map((item, index) => {
                      const name = [item.register_number, item.short_description].filter(Boolean).join(" · ") || "Vertrag";
                      return <article key={item.contract_id} className="my-card my-card--notice">
                        <header className="my-card-head">
                          <div className="my-card-text">
                            <h4>{name}</h4>
                            <span className="my-card-context">{item.partner ?? "Vertragspartner offen"}</span>
                          </div>
                          <span className={`my-card-unit my-card-unit--${column.id}`}>{item.days_left < 0 ? "Frist verstrichen" : `Noch ${item.days_left} ${item.days_left === 1 ? "Tag" : "Tage"}`}</span>
                        </header>
                        <dl className="my-card-facts">
                          <div><dt>Kündigung spätestens</dt><dd>{formatDate(item.cancel_by)}</dd></div>
                          <div><dt>Vertragsende</dt><dd>{item.possible_end ? formatDate(item.possible_end) : "–"}</dd></div>
                          <div><dt>Jährliche Kosten</dt><dd>{item.annual_cost ? formatCurrency(item.annual_cost, "EUR") : "–"}</dd></div>
                          {item.decision ? <div><dt>Entscheidung</dt><dd>{item.decision.label}</dd></div> : null}
                        </dl>
                        <Link className="my-card-source" href={contractHref(item.contract_id, registerField("notice_period"))}>Fristgrundlage ansehen</Link>
                        <Link className={`btn my-card-action${column.id === "urgent" && index === 0 ? " btn-primary" : ""}`} href={column.id === "urgent" ? `/contracts/${item.contract_id}?tab=deadlines` : `/contracts/${item.contract_id}`}>
                          {column.id === "urgent" ? "Kündigung vorbereiten" : "Vertrag prüfen"}<span className="visually-hidden">: {name}</span>{CHEVRON}
                        </Link>
                      </article>;
                    })}
                    {column.id === "unknown" ? state.notEvaluable.map((item) => {
                      const name = [item.register_number, item.short_description].filter(Boolean).join(" · ") || "Vertrag";
                      return <article key={item.contract_id} className="my-card my-card--notice">
                        <header className="my-card-head"><div className="my-card-text"><h4>{name}</h4></div></header>
                        <p className="my-card-missing"><span aria-hidden="true">{ICONS.alert}</span>{item.reason}</p>
                        <Link className="btn my-card-action" href={contractHref(item.contract_id, { tab: "register", section: "term" })}>Laufzeit ergänzen<span className="visually-hidden">: {name}</span>{CHEVRON}</Link>
                      </article>;
                    }) : null}
                  </section>)}
                </div>
                <p className="my-board-note">Vorbereitung versendet keine Kündigung.</p>
              </div>}
          <p className="my-day-foot"><Link href="/fristen?ansicht=entscheidungen">Alle Kündigungsfristen →</Link></p>
        </div>

        <div role="tabpanel" id="my-panel-figures" aria-labelledby="my-tab-figures" hidden={tab !== "figures"} className="card my-day-card">
          {!loaded ? <div className="my-day-pad"><Skeleton lines={3} label="Zahlen werden geladen…" /></div>
            : !totals && state.renewals === null ? <p className="field-hint my-day-pad">Die Zahlen konnten nicht geladen werden.</p>
              : <div className="my-board my-board--dates my-costs">
                <div className="my-board-bar">
                  <h2 className="my-board-title">Vertragskosten im Überblick<span>netto · EUR</span></h2>
                </div>
                <div className="my-kpis">
                  <Link href="/register" className="my-kpi"><span className="my-kpi-icon my-kpi-icon--blue" aria-hidden="true">{ICONS.eur}</span>
                    <span className="my-kpi-body"><span className="my-kpi-label">Erfasste Jahreskosten</span><span className="my-kpi-value">{annual ? formatCurrency(annual, "EUR") : "—"}</span><span className="my-kpi-sub">Auf ein Jahr normiert</span></span></Link>
                  <Link href="/register" className="my-kpi"><span className="my-kpi-icon my-kpi-icon--teal" aria-hidden="true">{TAB_ICONS.figures}</span>
                    <span className="my-kpi-body"><span className="my-kpi-label">Kosten laufendes Jahr</span><span className="my-kpi-value">{totals?.cost_current_year ? formatCurrency(totals.cost_current_year, "EUR") : "—"}</span><span className="my-kpi-sub">Zeitanteilig bis heute</span></span></Link>
                  <Link href={registerHref(NO_FINANCE_FILTERS)} className="my-kpi"><span className="my-kpi-icon my-kpi-icon--amber" aria-hidden="true">{TAB_ICONS.notice}</span>
                    <span className="my-kpi-body"><span className="my-kpi-label">Kostendaten vorhanden</span>
                      <span className="my-kpi-value">{costKnown} von {costKnown + costMissing} {costKnown + costMissing === 1 ? "Vertrag" : "Verträgen"}</span>
                      {costMissing > 0 ? <span className="my-kpi-chip">{costMissing} unvollständig</span> : <span className="my-kpi-sub">alle erfasst</span>}</span></Link>
                </div>
                {costMissing > 0 ? <p className="my-partial" role="note"><span aria-hidden="true">{ICONS.alert}</span><span><strong>Teilübersicht:</strong> Fehlende Kosten sind nicht als 0 € enthalten.</span></p> : null}
                <div className="my-costs-grid">
                  <section className="my-subcard" aria-labelledby="my-cost-by">
                    <h3 id="my-cost-by">Jahreskosten nach Vertragstyp</h3>
                    <p className="my-subcard-sub">Nur Verträge mit erfassten Kosten</p>
                    {byType.length === 0 ? <p className="my-col-empty">Keine Kosten erfasst.</p> : <ul className="my-bars">
                      {byType.map((item) => <li key={item.label}>
                        <span className="my-bar-label">{item.label}</span>
                        <span className="my-bar-track" aria-hidden="true"><span style={{ width: `${Math.max(2, (item.value / byTypeMax) * 100)}%` }} /></span>
                        <span className="my-bar-value">{formatCurrency(String(item.value), "EUR")} <span>({Math.round((item.value / byTypeSum) * 100)} %)</span></span>
                      </li>)}
                    </ul>}
                  </section>
                  <section className="my-subcard" aria-labelledby="my-cost-missing">
                    <h3 id="my-cost-missing">Daten ergänzen</h3>
                    {(state.withoutCosts?.items.length ?? 0) === 0 ? <p className="my-col-empty">Für alle Verträge sind Kosten erfasst.</p> : <ul className="my-missing">
                      {state.withoutCosts!.items.map((item) => {
                        const name = [item.values.register_number, item.values.short_description].filter(Boolean).join(" · ") || "Vertrag";
                        return <li key={item.contract_id}>
                          <span className="my-missing-icon" aria-hidden="true">{TAB_ICONS.notice}</span>
                          <span className="my-missing-text"><strong>{name}</strong><small>Jährlicher Betrag fehlt</small></span>
                          <Link href={contractHref(item.contract_id, FINANCE_ENTRIES_TARGET)}>Ergänzen<span className="visually-hidden">: {name}</span>{CHEVRON}</Link>
                        </li>;
                      })}
                    </ul>}
                  </section>
                </div>
                <section className="my-subcard" aria-labelledby="my-cost-table">
                  <div className="my-subcard-head"><h3 id="my-cost-table">Kosten je Vertrag</h3><Link href="/register">Alle Verträge anzeigen →</Link></div>
                  {costRows.length === 0 ? <p className="my-col-empty">Keine Kosten erfasst.</p> : <table className="my-cost-table">
                    <thead><tr><th scope="col">Vertrag</th><th scope="col" className="num">Jahreskosten</th></tr></thead>
                    <tbody>
                      {costRows.slice(0, 3).map((row) => <tr key={row.id}><th scope="row"><Link href={`/contracts/${row.id}`}>{row.name}</Link></th><td className="num">{formatCurrency(String(row.value), "EUR")}</td></tr>)}
                      {costRows.length > 3 ? <tr><th scope="row">Weitere {costRows.length - 3} {costRows.length - 3 === 1 ? "Vertrag" : "Verträge"}</th><td className="num">{formatCurrency(String(costRows.slice(3).reduce((sum, row) => sum + row.value, 0)), "EUR")}</td></tr> : null}
                    </tbody>
                    <tfoot><tr><th scope="row">Summe ({costRows.length} {costRows.length === 1 ? "Vertrag" : "Verträge"})</th><td className="num">{formatCurrency(String(costSum), "EUR")}</td></tr></tfoot>
                  </table>}
                </section>
              </div>}
        </div>
      </section>
    </div>
  );
}
