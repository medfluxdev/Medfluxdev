"use client";

import Link from "next/link";
import { useMemo, useState, type ReactNode } from "react";
import { contractHref } from "@/lib/fix-targets";
import type { PortfolioReport as RiskReport } from "@/lib/domain-api/reports";
import type { PortfolioItem, PortfolioReport, RenewalListItem, NotEvaluableItem } from "@/lib/domain-api/registerGrid";
import { formatCurrency } from "@/lib/format";
import { registerLink } from "@/lib/master-data";

const num = (value: string | null | undefined) => (value == null || value === "" ? null : Number(value));
const de = new Intl.NumberFormat("de-DE", { maximumFractionDigits: 1 });

/** Kurzform: „2,4 Mio. €“, „452 Tsd. €“, sonst ganze Euro. */
export function shortEuro(value: number | null): string {
  if (value == null || !Number.isFinite(value)) return "–";
  const abs = Math.abs(value);
  if (abs >= 1_000_000) return `${de.format(value / 1_000_000)} Mio. €`;
  if (abs >= 10_000) return `${Math.round(value / 1000).toLocaleString("de-DE")} Tsd. €`;
  return `${Math.round(value).toLocaleString("de-DE")} €`;
}

const euro = (value: number | null) => (value == null ? "–" : formatCurrency(String(value), "EUR"));
const filterLink = (column: string, op: string, value?: unknown) => `/register?filter=${encodeURIComponent(JSON.stringify([value === undefined ? { column, op } : { column, op, value }]))}`;

function Question({ dot, children }: { dot: "cost" | "device" | "info" | "critical"; children: ReactNode }) {
  return <p className="an-question"><span className={`an-dot an-dot--${dot}`} aria-hidden="true" />{children}</p>;
}

const svg = (body: ReactNode) => <svg viewBox="0 0 24 24" aria-hidden="true" focusable="false">{body}</svg>;
const ICON = {
  euro: svg(<path d="M18 6.5A7 7 0 1 0 18 17.5M4 10h10M4 14h10" />),
  trend: svg(<path d="M4 17l6-6 4 4 6-7M15 8h5v5" />),
  calendar: svg(<><rect x="4" y="5" width="16" height="15" rx="2" /><path d="M8 3v4M16 3v4M4 10h16" /></>),
  scale: svg(<path d="M12 4v16M6 20h12M5 8h14M5 8l-2 6a3 3 0 0 0 4 0zM19 8l-2 6a3 3 0 0 0 4 0z" />),
  warn: svg(<><path d="M12 4 3 20h18z" /><path d="M12 10v4M12 17v.5" /></>),
  spark: svg(<path d="M12 3l1.8 5.2L19 10l-5.2 1.8L12 17l-1.8-5.2L5 10l5.2-1.8z" />),
};

interface Props {
  report: PortfolioReport;
  renewals: RenewalListItem[];
  notEvaluable: NotEvaluableItem[];
  risk: RiskReport | null;
}

const DIMENSIONS: { key: string; label: string; tone: "hospital" | "device" | "partner" | "type" }[] = [
  { key: "hospital", label: "Krankenhaus", tone: "hospital" },
  { key: "device_type", label: "Gerätetyp", tone: "device" },
  { key: "partner", label: "Lieferant", tone: "partner" },
  { key: "contract_type", label: "Vertragsart", tone: "type" },
];

/** Die vier Fragen der Analysen in Reihenfolge: Wie viel? Wohin? Was kommt / wo sparen? Wo liegt Risiko? */
export default function AnalysenOverview({ report, renewals, notEvaluable, risk }: Props) {
  const asOf = new Date(report.as_of);
  const year = asOf.getFullYear();
  const [dimension, setDimension] = useState("hospital");
  const [flowTable, setFlowTable] = useState(false);
  const [yearTable, setYearTable] = useState(false);
  const [month, setMonth] = useState<string | null>(null);

  // ---- Wie viel? -------------------------------------------------------------------------------------------
  const annual = num(report.totals.amounts?.annual_cost?.value ?? report.totals.annual_cost);
  const byYear = report.cost_by_year.map((item) => ({ year: item.year, expense: num(item.expense), income: num(item.income), forecast: item.is_projection }));
  const current = byYear.find((item) => item.year === year)?.expense ?? null;
  const previous = byYear.find((item) => item.year === year - 1)?.expense ?? null;
  const change = current != null && previous != null && previous > 0 ? ((current - previous) / previous) * 100 : null;
  const cancellable = renewals.filter((item) => item.days_left >= 0 && item.days_left <= 90);
  const cancellableCost = cancellable.reduce((sum, item) => sum + (num(item.annual_cost) ?? 0), 0);
  const insight = (key: string) => report.insights.find((item) => item.key === key);
  const noCosts = insight("no_finance")?.count ?? 0;
  const noEnd = insight("no_end")?.count ?? 0;

  const status = report.by_status;
  const statusTotal = status.reduce((sum, item) => sum + item.count, 0);
  const STATUS_TONE: Record<string, string> = { gueltig: "done", in_arbeit: "info", gekuendigt: "warning", beendet: "muted" };

  // ---- Kosten je Jahr --------------------------------------------------------------------------------------
  const yearMax = Math.max(1, ...byYear.map((item) => item.expense ?? 0));
  const income = byYear.find((item) => item.year === year)?.income ?? 0;

  // ---- Wohin fließt das Geld ---------------------------------------------------------------------------------
  const dim = DIMENSIONS.find((item) => item.key === dimension) ?? DIMENSIONS[0];
  const flow = useMemo(() => {
    const raw: PortfolioItem[] = report.cost_by[dimension] ?? [];
    const rows = raw.map((item) => ({ label: item.label.startsWith("Übrige") ? "" : item.label, value: num(item.annual_cost) ?? 0, item, other: item.label.startsWith("Übrige") }))
      .filter((row) => row.value > 0);
    const named = rows.filter((row) => !row.other).sort((a, b) => b.value - a.value);
    const head = named.slice(0, 6);
    const tail = [...named.slice(6), ...rows.filter((row) => row.other)];
    const total = rows.reduce((sum, row) => sum + row.value, 0);
    const tailValue = tail.reduce((sum, row) => sum + row.value, 0);
    return { head, tail, tailValue, total, max: Math.max(1, head[0]?.value ?? 0, tailValue) };
  }, [report.cost_by, dimension]);

  // ---- Was kommt? --------------------------------------------------------------------------------------------
  const upcoming = renewals.filter((item) => item.days_left >= 0 && item.days_left <= 183);
  const months = Array.from({ length: 6 }, (_, offset) => {
    const date = new Date(asOf.getFullYear(), asOf.getMonth() + offset, 1);
    const key = `${date.getFullYear()}-${String(date.getMonth() + 1).padStart(2, "0")}`;
    const items = upcoming.filter((item) => item.cancel_by.startsWith(key));
    return { key, label: new Intl.DateTimeFormat("de-DE", { month: "short" }).format(date), long: new Intl.DateTimeFormat("de-DE", { month: "long" }).format(date), items, cost: items.reduce((sum, item) => sum + (num(item.annual_cost) ?? 0), 0) };
  });
  const monthMax = Math.max(1, ...months.map((item) => item.cost));
  const listed = (month ? upcoming.filter((item) => item.cancel_by.startsWith(month)) : upcoming)
    .slice().sort((a, b) => (num(b.annual_cost) ?? -1) - (num(a.annual_cost) ?? -1) || a.cancel_by.localeCompare(b.cancel_by));
  const listedCost = listed.reduce((sum, item) => sum + (num(item.annual_cost) ?? 0), 0);
  const selectedMonth = months.find((item) => item.key === month) ?? null;

  // ---- Risiko --------------------------------------------------------------------------------------------------
  const high = risk?.contracts.by_risk.high ?? 0;
  const medium = risk?.contracts.by_risk.medium ?? 0;
  const concentration = report.supplier_concentration;
  const share = concentration ? Number(concentration.share_percent) : null;
  const dependency = share == null ? null : share >= 50 ? "sehr hohe Konzentration" : share >= 25 ? "größter Lieferant – bei Verhandlungen bündeln" : "breit verteilt";

  return <div className="an-sections">
    {/* 1) Wie viel? */}
    <section className="an-block" aria-labelledby="an-q1">
      <Question dot="cost"><span id="an-q1">Wie viel?</span></Question>
      <div className="an-kpis card">
        <div className="an-kpi">
          <span className="an-kpi-icon an-kpi-icon--cost" aria-hidden="true">{ICON.euro}</span>
          <span className="an-kpi-label">Jährliche Kosten (netto)</span>
          <strong className="an-kpi-value">{euro(annual)}</strong>
        </div>
        <div className="an-kpi">
          <span className={`an-kpi-icon an-kpi-icon--${change == null ? "muted" : change > 0 ? "warning" : "done"}`} aria-hidden="true">{ICON.trend}</span>
          <span className="an-kpi-label">Veränderung zum Vorjahr</span>
          <strong className="an-kpi-value">{change == null ? "–" : `${change > 0 ? "↑ +" : change < 0 ? "↓ " : ""}${de.format(change)} %`}</strong>
          {change == null ? <span className="an-kpi-sub">kein Vorjahr mit Kosten</span> : <span className="an-kpi-sub">{year} gegenüber {year - 1}</span>}
        </div>
        <Link className="an-kpi" href="/fristen?ansicht=entscheidungen">
          <span className="an-kpi-icon an-kpi-icon--info" aria-hidden="true">{ICON.calendar}</span>
          <span className="an-kpi-label">Kündbar in 90 Tagen</span>
          <strong className="an-kpi-value">{cancellable.length}</strong>
          <span className="an-kpi-sub">{cancellable.length === 1 ? "Vertrag" : "Verträge"}</span>
        </Link>
        <div className="an-kpi an-kpi--cost">
          <span className="an-kpi-icon an-kpi-icon--cost" aria-hidden="true">{ICON.scale}</span>
          <span className="an-kpi-label">Kosten der kündbaren Verträge</span>
          <strong className="an-kpi-value">{cancellable.length ? euro(cancellableCost) : "–"}</strong>
          <span className="an-kpi-sub">pro Jahr</span>
        </div>
      </div>
      {noCosts > 0 || noEnd > 0 ? <p className="an-missing" role="note"><span aria-hidden="true">{ICON.warn}</span>
        <span>{noCosts > 0 ? `${noCosts} ${noCosts === 1 ? "Vertrag" : "Verträge"} ohne Kosten` : ""}{noCosts > 0 && noEnd > 0 ? ", " : ""}{noEnd > 0 ? `${noEnd} ohne Vertragsende` : ""} – nicht enthalten · </span>
        <Link href={noCosts > 0 ? filterLink("cost_current_year", "empty") : filterLink("term_status", "in", ["Unvollständig"])}>Ergänzen →</Link></p> : null}
      {statusTotal > 0 ? <div className="an-stock" aria-label="Bestand">
        <span className="an-stock-label">Bestand</span>
        <span className="an-stock-bar" aria-hidden="true">{status.filter((item) => item.count > 0).map((item) => <span key={item.status} className={`an-seg an-seg--${STATUS_TONE[item.status] ?? "muted"}`} style={{ flexGrow: item.count }} />)}</span>
        <span className="an-stock-text">{status.map((item, index) => <span key={item.status}>{index ? " · " : ""}<Link href={registerLink("business_status", item.label)}>{item.count} {item.label.toLowerCase()}</Link></span>)}</span>
      </div> : null}
    </section>

    <div className="an-cols">
      {/* Kosten je Jahr */}
      <section className="an-block" aria-labelledby="an-years">
        <Question dot="cost"><span>Wie viel? Im Verlauf</span></Question>
        <div className="card an-card">
          <div className="an-card-head"><h2 id="an-years">Kosten je Jahr</h2>
            <button type="button" className="btn btn-sm" aria-label={`Kosten je Jahr ${yearTable ? "als Diagramm" : "als Tabelle"}`} aria-pressed={yearTable} onClick={() => setYearTable(!yearTable)}>{yearTable ? "Als Diagramm" : "Als Tabelle"}</button></div>
          {byYear.every((item) => item.expense == null) ? <p className="an-empty">Keine Kosten in den gepflegten Finanzdaten.</p> : yearTable
            ? <table className="an-table"><thead><tr><th scope="col">Jahr</th><th scope="col" className="num">Kosten (netto)</th><th scope="col">Art</th></tr></thead>
              <tbody>{byYear.map((item) => <tr key={item.year}><th scope="row">{item.year}</th><td className="num">{euro(item.expense)}</td><td>{item.forecast ? "Prognose" : "Ist"}</td></tr>)}</tbody></table>
            : <>
              <div className="an-bars" role="img" aria-label={`Kosten je Jahr: ${byYear.map((item) => `${item.year} ${euro(item.expense)}${item.forecast ? " (Prognose)" : ""}`).join(", ")}`}>
                {byYear.map((item, index) => {
                  const labelled = index === 0 || item.year === year || index === byYear.length - 1;
                  return <div key={item.year} className="an-bar-col" title={`${item.year}: ${euro(item.expense)}${item.forecast ? " (Prognose)" : ""}`}>
                    <span className="an-bar-value">{labelled ? shortEuro(item.expense) : ""}</span>
                    <span className="an-bar-track"><span className={`an-bar${item.forecast ? " an-bar--forecast" : ""}`} style={{ height: `${((item.expense ?? 0) / yearMax) * 100}%` }} /></span>
                    <span className={`an-bar-year${item.year === year ? " is-current" : ""}`}>{item.year}</span>
                  </div>;
                })}
              </div>
              <p className="an-legend"><span><i className="an-key an-key--solid" />Ist</span><span><i className="an-key an-key--forecast" />Prognose</span></p>
            </>}
          {income > 0 ? <p className="an-note">Zusätzlich Einnahmen {year}: {euro(income)} – in den Kosten nicht verrechnet.</p> : null}
        </div>
      </section>

      {/* Wohin fließt das Geld */}
      <section className="an-block" aria-labelledby="an-flow">
        <Question dot="device"><span>Wohin?</span></Question>
        <div className="card an-card">
          <div className="an-card-head"><h2 id="an-flow">Wohin fließt das Geld</h2>
            <button type="button" className="btn btn-sm" aria-label={`Wohin fließt das Geld ${flowTable ? "als Balken" : "als Tabelle"}`} aria-pressed={flowTable} onClick={() => setFlowTable(!flowTable)}>{flowTable ? "Als Balken" : "Als Tabelle"}</button></div>
          <div className="an-seg-buttons" role="group" aria-label="Aufteilen nach">
            <span className="an-seg-label">Aufteilen nach</span>
            {DIMENSIONS.map((item) => <button key={item.key} type="button" className={`an-segbtn an-segbtn--${item.tone}`} aria-pressed={dimension === item.key} onClick={() => setDimension(item.key)}>{item.label}</button>)}
          </div>
          {flow.total === 0 ? <p className="an-empty">Für die laufenden Verträge sind keine Kosten gepflegt.</p> : <>
            {dimension === "device_type" ? <p className="an-flow-head"><span /><span>pro Jahr</span><span>je Gerät</span><span>Anteil</span></p> : <p className="an-flow-head an-flow-head--plain"><span /><span>pro Jahr</span><span>Anteil</span></p>}
            <ul className={`an-flow an-flow--${dim.tone}${dimension === "device_type" ? " has-device" : ""}`}>
              {flow.head.map((row) => <li key={row.item.label}>
                <span className="an-flow-name">{row.item.label || "(ohne)"}{row.item.shared_count ? <span className="an-shared" title="Ein Vertrag mit mehreren Gerätearten ist gleichmäßig aufgeteilt">◐ geteilt</span> : null}</span>
                {flowTable ? null : <span className="an-flow-track" aria-hidden="true"><span style={{ width: `${(row.value / flow.max) * 100}%` }} /></span>}
                <span className="an-flow-value">{shortEuro(row.value)}</span>
                {dimension === "device_type" ? <span className="an-flow-per">{row.item.cost_per_device ? euro(num(row.item.cost_per_device)) : "–"}</span> : null}
                <span className="an-flow-share">{Math.round((row.value / flow.total) * 100)} %</span>
              </li>)}
              {flow.tail.length ? <li className="an-flow-other">
                <span className="an-flow-name">Sonstige ({flow.tail.reduce((sum, row) => sum + (row.other ? Math.max(row.item.count, 1) : 1), 0)})</span>
                {flowTable ? null : <span className="an-flow-track" aria-hidden="true"><span style={{ width: `${(flow.tailValue / flow.max) * 100}%` }} /></span>}
                <span className="an-flow-value">{shortEuro(flow.tailValue)}</span>
                {dimension === "device_type" ? <span className="an-flow-per">–</span> : null}
                <span className="an-flow-share">{Math.round((flow.tailValue / flow.total) * 100)} %</span>
              </li> : null}
            </ul>
            <p className="an-sum">Summe <strong>{euro(flow.total)}</strong> = Jährliche Kosten</p>
          </>}
        </div>
      </section>
    </div>

    {/* Was kommt? Wo sparen? */}
    <section className="an-block" aria-labelledby="an-decisions">
      <Question dot="info"><span>Was kommt? Wo sparen?</span></Question>
      <div className="card an-card">
        <div className="an-card-head"><h2 id="an-decisions">Entscheidungen in den nächsten 6 Monaten</h2></div>
        <ul className="an-months" aria-label="Kündigungsfristen je Monat">
          {months.map((item) => <li key={item.key}>
            <button type="button" aria-pressed={month === item.key} disabled={item.items.length === 0} onClick={() => setMonth(month === item.key ? null : item.key)}>
              <span className="an-month-name">{item.label}</span>
              <strong className="an-month-count">{item.items.length}</strong>
              <span className="an-month-bar" aria-hidden="true"><span style={{ width: `${(item.cost / monthMax) * 100}%` }} /></span>
              <span className="an-month-cost">{item.cost > 0 ? shortEuro(item.cost) : "–"}</span>
            </button>
          </li>)}
        </ul>
        {listed.length === 0 ? <p className="an-empty">{month ? `Im ${selectedMonth?.long ?? "Monat"} endet keine Kündigungsfrist.` : "In den nächsten 6 Monaten endet keine berechenbare Kündigungsfrist."}
          {notEvaluable.length > 0 ? ` Für ${notEvaluable.length} ${notEvaluable.length === 1 ? "Vertrag" : "Verträge"} ist das Vertragsende nicht bekannt.` : ""}</p>
          : <ul className="an-decisions">
            {listed.slice(0, 8).map((item) => {
              const date = new Date(`${item.cancel_by}T00:00:00`);
              const name = item.short_description ?? "Vertrag";
              return <li key={item.contract_id}>
                <span className={`an-date${item.days_left <= 30 ? " is-soon" : ""}`} aria-hidden="true"><b>{String(date.getDate()).padStart(2, "0")}</b>{new Intl.DateTimeFormat("de-DE", { month: "short" }).format(date)}</span>
                <span className="an-dec-text">
                  <Link href={contractHref(item.contract_id)} className="an-dec-title">{name}</Link>
                  <small>{[`in ${item.days_left} ${item.days_left === 1 ? "Tag" : "Tagen"}`, item.register_number, item.partner, item.device_types?.length ? item.device_types.join(", ") : null, item.renewal_text].filter(Boolean).join(" · ")}</small>
                </span>
                <span className="an-dec-cost">{item.annual_cost ? <>{euro(num(item.annual_cost))}<small>/ Jahr</small></> : <small>Kosten fehlen</small>}</span>
                <Link className="btn btn-sm" href={contractHref(item.contract_id, { tab: "deadlines" })}>Entscheiden<span className="visually-hidden">: {name}</span></Link>
              </li>;
            })}
          </ul>}
        <p className="an-foot">{listed.length} {listed.length === 1 ? "Entscheidung" : "Entscheidungen"} · zusammen {shortEuro(listedCost)} pro Jahr
          {selectedMonth ? <> · im {selectedMonth.long} · <button type="button" className="rg-link" onClick={() => setMonth(null)}>alle Monate</button></> : null}
          {" · "}<Link href="/fristen?ansicht=entscheidungen">Alle Kündigungsfristen →</Link></p>
      </div>
    </section>

    {/* Wo liegt Risiko? */}
    <section className="an-block" aria-labelledby="an-risk">
      <Question dot="critical"><span>Wo liegt Risiko?</span></Question>
      <div className="card an-card an-risk">
        <div className="an-risk-row">
          <h2 id="an-risk">Risiken laut KI-Analyse</h2>
          {high + medium === 0 ? <span className="an-muted">Noch keine Einschätzung.</span> : <>
            {high > 0 ? <Link className="an-pill an-pill--high" href={registerLink("risk", "Hoch")}>{high} Hoch</Link> : null}
            {medium > 0 ? <Link className="an-pill an-pill--medium" href={registerLink("risk", "Mittel")}>{medium} Mittel</Link> : null}
          </>}
          <span className="an-hint">Hinweis der lokalen KI – kein geprüfter Wert</span>
        </div>
        {concentration && share != null ? <div className="an-risk-row an-risk-row--dep">
          <h3>Abhängigkeit</h3>
          <span><strong>{de.format(share)} %</strong> der Kosten bei {concentration.partner}</span>
          <span className="an-muted">{dependency}</span>
        </div> : null}
      </div>
    </section>
  </div>;
}
