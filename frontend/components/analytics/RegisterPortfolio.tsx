"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { useAuth } from "@/components/auth/AuthProvider";
import {
  downloadPortfolioXlsx,
  getPortfolioReport,
  saveBlob,
  type GridFilter,
  type PortfolioReport,
} from "@/lib/domain-api/registerGrid";
import CoverageValue from "@/components/ui/CoverageValue";
import { formatCurrency, formatDate } from "@/lib/format";
import { ColumnChart, HorizontalBarChart } from "./RegisterCharts";

const DIMENSION_COLUMN: Record<string, string> = {
  hospital: "hospital",
  department: "department",
  cost_center: "cost_center",
  contract_type: "contract_type",
  partner: "partner",
};

const compact = new Intl.NumberFormat("de-DE", { notation: "compact", maximumFractionDigits: 1 });

export function registerLink(filters: GridFilter[]) {
  return `/register?filter=${encodeURIComponent(JSON.stringify(filters))}`;
}

function euro(value: string | number | null | undefined) {
  return value === null || value === undefined ? "—" : formatCurrency(String(value), "EUR");
}

const NO_FINANCE = registerLink([{ column: "cost_current_year", op: "empty" }]);

function monthLabel(key: string) {
  const [year, month] = key.split("-").map(Number);
  return new Intl.DateTimeFormat("de-DE", { month: "short" }).format(new Date(year, month - 1, 1));
}

function AmountTile({ label, sub, report, amountKey }: { label: string; sub: string; report: PortfolioReport; amountKey: "annual_cost" | "cost_current_year" | "income_current_year" }) {
  const amount = report.totals.amounts?.[amountKey];
  return <article title={amountKey === "annual_cost" ? report.definitions?.annual_cost : undefined}>
    <span>{label}</span>
    <strong>{euro(amount ? amount.value : report.totals[amountKey])}</strong>
    <small>{sub}</small>
    {amount ? <CoverageValue noteOnly value={amount.value} known={amount.known} missing={amount.missing} otherCurrencies={amount.other_currencies} missingHref={amountKey === "income_current_year" ? undefined : NO_FINANCE} /> : null}
  </article>;
}

export default function RegisterPortfolio({ organizationSlug }: { organizationSlug: string }) {
  const { role, account } = useAuth();
  const canExport = Boolean(account?.is_developer || role === "admin" || role === "contract_manager");
  const [report, setReport] = useState<PortfolioReport | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [dimension, setDimension] = useState("hospital");

  useEffect(() => {
    let cancelled = false;
    getPortfolioReport(organizationSlug)
      .then((result) => { if (!cancelled) setReport(result); })
      .catch((err) => { if (!cancelled) setError(err instanceof Error && err.message ? err.message : "Der Portfoliobericht konnte nicht geladen werden."); });
    return () => { cancelled = true; };
  }, [organizationSlug]);

  async function exportXlsx() {
    try {
      const { blob, filename } = await downloadPortfolioXlsx(organizationSlug);
      saveBlob(blob, filename ?? "portfoliobericht.xlsx");
    } catch (err) {
      setError(err instanceof Error && err.message ? err.message : "Export fehlgeschlagen.");
    }
  }

  if (error) return <p role="alert" className="rg-error">{error}</p>;
  if (!report) return <p role="status">Portfoliobericht wird geladen…</p>;

  const dimensionLabel = report.dimensions.find((item) => item.key === dimension)?.label ?? dimension;
  const costItems = report.cost_by[dimension] ?? [];

  return <section className="rg-panel" aria-labelledby="portfolio-heading">
    <div className="cw-section-head"><div>
      <h2 id="portfolio-heading">Vertragsportfolio</h2>
      <p>Deterministisch aus Stammdaten und gepflegten Finanzdaten berechnet (netto, EUR; KI-Vorschläge nicht enthalten) · Stand {formatDate(report.as_of)}</p>
    </div>{canExport ? <button type="button" className="btn" onClick={() => void exportXlsx()}>Bericht als Excel</button> : null}</div>

    <div className="viz-tiles">
      <article title={report.definitions?.running}><span>Laufende Verträge</span><strong>{report.totals.running}</strong><small>von {report.totals.contracts} (ohne gelöschte){report.totals.in_progress ? ` · ${report.totals.in_progress} in Arbeit` : ""}</small></article>
      <AmountTile label="Jährliche Kosten" sub="aktueller Satz" report={report} amountKey="annual_cost" />
      <AmountTile label={`Kosten ${new Date(report.as_of).getFullYear()}`} sub="laufendes Jahr" report={report} amountKey="cost_current_year" />
      <AmountTile label={`Einnahmen ${new Date(report.as_of).getFullYear()}`} sub="laufendes Jahr" report={report} amountKey="income_current_year" />
    </div>

    <section className="cw-section" aria-labelledby="insights-heading">
      <h3 id="insights-heading">Handlungsbedarf im Portfolio</h3>
      <ul className="viz-insights">
        {report.insights.map((item) => <li key={item.key}>
          <strong>{item.count}</strong>
          {item.count > 0 ? <Link href={registerLink([item.filter])}>{item.label}</Link> : <span>{item.label}</span>}
        </li>)}
        {report.supplier_concentration ? <li><strong>{report.supplier_concentration.share_percent.replace(".", ",")} %</strong><span>der Kosten {new Date(report.as_of).getFullYear()} entfallen auf den größten Partner ({report.supplier_concentration.partner})</span></li> : null}
      </ul>
    </section>

    <div className="viz-layout">
      <section className="cw-section" aria-labelledby="cost-dim-heading">
        <div className="viz-head">
          <h3 id="cost-dim-heading">Kosten {new Date(report.as_of).getFullYear()} je {dimensionLabel}</h3>
          <label>Aufteilen nach<select value={dimension} onChange={(event) => setDimension(event.target.value)}>
            {report.dimensions.map((item) => <option key={item.key} value={item.key}>{item.label}</option>)}
          </select></label>
        </div>
        {costItems.length === 0 ? <p className="cw-muted">Keine laufenden Verträge.</p> : costItems.every((item) => item.cost_current_year === null) ? <p className="cw-muted">Für die laufenden Verträge sind keine Kosten gepflegt. <Link href={NO_FINANCE}>Verträge ohne Kosten anzeigen</Link></p> : <HorizontalBarChart
          title={dimensionLabel}
          valueLabel={`Kosten ${new Date(report.as_of).getFullYear()} (netto)`}
          data={costItems.map((item) => ({
            label: item.label,
            value: Number(item.cost_current_year ?? 0),
            display: euro(item.cost_current_year),
            note: item.missing ? `${item.count} Verträge, ${item.missing} ohne Kosten` : `${item.count} Verträge`,
            href: item.value === null ? undefined : registerLink([{ column: DIMENSION_COLUMN[dimension], op: "in", value: [item.value] }]),
          }))}
        />}
      </section>

      <section className="cw-section" aria-labelledby="years-heading">
        <h3 id="years-heading">Ausgaben und Einnahmen je Jahr</h3>
        {report.cost_by_year.every((item) => item.expense === null && item.income === null) ? <p className="cw-muted">Keine gepflegten Finanzposten – ohne Daten wird keine Jahreskurve gezeichnet.</p> : <ColumnChart
          title="Jahr"
          series={[{ key: "expense", label: "Ausgaben", className: "viz-series-1" }, { key: "income", label: "Einnahmen", className: "viz-series-2" }]}
          data={report.cost_by_year.map((item) => ({
            label: String(item.year),
            sublabel: item.is_projection ? "Prognose" : undefined,
            values: { expense: Number(item.expense ?? 0), income: Number(item.income ?? 0) },
            display: { expense: euro(item.expense), income: euro(item.income) },
          }))}
          format={(value) => `${compact.format(value)} €`}
        />}
        {report.cost_by_year_coverage && report.cost_by_year_coverage.known < report.cost_by_year_coverage.total ? <p className="cw-muted">Teilsumme: Finanzposten für {report.cost_by_year_coverage.known} von {report.cost_by_year_coverage.total} Verträgen gepflegt.</p> : null}
        <p className="cw-muted">Künftige Jahre: Hochrechnung aus den gepflegten Finanzposten inkl. vereinbarter prozentualer Preisanpassung.</p>
      </section>

      <section className="cw-section" aria-labelledby="deadline-heading">
        <h3 id="deadline-heading">Fristen der nächsten 6 Monate</h3>
        <ColumnChart
          title="Monat"
          stacked
          series={[{ key: "notice", label: "Kündigungsfristen", className: "viz-series-1" }, { key: "other", label: "Weitere Termine", className: "viz-series-2" }]}
          data={report.deadlines_by_month.map((item) => ({
            label: monthLabel(item.month),
            values: { notice: item.notice, other: item.other },
            display: { notice: String(item.notice), other: String(item.other) },
          }))}
          format={(value) => String(Math.round(value))}
        />
        {report.upcoming.length > 0 ? <details className="viz-table"><summary>Nächste Fristen ({report.upcoming.length})</summary>
          <ul className="hist-details">{report.upcoming.slice(0, 20).map((item) => <li key={`${item.contract_id}-${item.due_date}-${item.title}`}>
            <span>{formatDate(item.due_date)}</span> <Link href={`/contracts/${item.contract_id}?tab=deadlines`}>{item.register_number ?? "–"} · {item.short_description ?? ""}</Link> – {item.title}
          </li>)}</ul>
        </details> : null}
      </section>

      <section className="cw-section" aria-labelledby="status-heading">
        <h3 id="status-heading">Verträge nach Status</h3>
        <HorizontalBarChart
          title="Status"
          valueLabel="Anzahl"
          data={report.by_status.map((item) => ({
            label: item.label, value: item.count, display: String(item.count),
            href: registerLink([{ column: "business_status", op: "in", value: [item.status] }]),
          }))}
        />
      </section>
    </div>
  </section>;
}
