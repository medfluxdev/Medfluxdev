"use client";

import Link from "next/link";
import { useCallback, useEffect, useState } from "react";
import Button from "@/components/ui/Button";
import CoverageValue from "@/components/ui/CoverageValue";
import InlineAlert from "@/components/ui/InlineAlert";
import Skeleton from "@/components/ui/Skeleton";
import { formatCurrency } from "@/lib/format";
import { getDrilldown, type DrilldownBucket, type DrilldownContract, type DrilldownReport } from "@/lib/domain-api/registerGrid";

const LEVEL_LABEL = { hospital: "Krankenhaus", department: "Abteilung" } as const;

// WP5: Organisation -> Krankenhaus -> Abteilung -> Verträge. Nur laufende Verträge, Summen mit Abdeckung.
export default function PortfolioDrilldown({ organizationSlug }: { organizationSlug: string }) {
  const [hospital, setHospital] = useState<string | undefined>();
  const [department, setDepartment] = useState<string | undefined>();
  const [report, setReport] = useState<DrilldownReport | null>(null);
  const [failed, setFailed] = useState(false);

  const load = useCallback(() => {
    setReport(null);
    getDrilldown(organizationSlug, hospital, department)
      .then((data) => { setReport(data); setFailed(false); })
      .catch(() => setFailed(true));
  }, [organizationSlug, hospital, department]);

  useEffect(load, [load]);

  function open(value: string) {
    if (!report) return;
    if (report.level === "hospital") setHospital(value);
    else if (report.level === "department") setDepartment(value);
  }

  const registerHref = report && report.register_filter.length > 0
    ? `/register?filter=${encodeURIComponent(JSON.stringify(report.register_filter))}`
    : "/register";

  return <section className="card card-pad stack-4" aria-labelledby="drilldown-heading">
    <div className="cw-section-head">
      <div><h2 id="drilldown-heading">Kosten nach Bereich</h2><p className="field-hint">Laufende Verträge, Kosten im laufenden Jahr (netto). Unbekannte Kosten werden nicht als 0 gezählt.</p></div>
    </div>
    <nav aria-label="Ebene der Auswertung" className="drill-path">
      <ol>
        <li>{hospital === undefined ? <span aria-current="page">Alle Krankenhäuser</span> : <button type="button" className="rg-link" onClick={() => { setHospital(undefined); setDepartment(undefined); }}>Alle Krankenhäuser</button>}</li>
        {report?.path.map((step, index) => {
          const last = index === report.path.length - 1;
          return <li key={step.level}>{last ? <span aria-current="page">{step.name}</span> : <button type="button" className="rg-link" onClick={() => setDepartment(undefined)}>{step.name}</button>}</li>;
        })}
      </ol>
    </nav>
    {failed ? <InlineAlert tone="warning" action={<Button size="sm" onClick={load}>Erneut laden</Button>}>Die Auswertung konnte nicht geladen werden.</InlineAlert> : null}
    {!report && !failed ? <Skeleton lines={3} label="Auswertung wird geladen…" /> : null}
    {report ? <>
      <p className="drill-total"><strong>{report.count} laufende {report.count === 1 ? "Vertrag" : "Verträge"}</strong> · <CoverageValue value={report.totals.value} currency={report.totals.currency} known={report.totals.known} missing={report.totals.missing} otherCurrencies={report.totals.other_currencies} /></p>
      {report.items.length === 0 ? <p className="cw-muted">Keine laufenden Verträge in dieser Auswahl.</p> : report.level === "contract"
        ? <div className="table-scroll"><table className="rg-table">
            <caption className="visually-hidden">Verträge der Auswahl</caption>
            <thead><tr><th scope="col">Nr.</th><th scope="col">Vertrag</th><th scope="col">Vertragspartner</th><th scope="col">Kosten lfd. Jahr</th><th scope="col">Laufzeitangaben</th></tr></thead>
            <tbody>{(report.items as DrilldownContract[]).map((item) => <tr key={item.contract_id}>
              <td>{item.register_number ?? "–"}</td>
              <th scope="row"><Link href={`/contracts/${item.contract_id}`}>{item.short_description ?? "Vertrag"}</Link></th>
              <td>{item.partner ?? "–"}</td>
              <td>{item.cost_current_year ? formatCurrency(item.cost_current_year, item.currency) : "—"}</td>
              <td>{item.term_status ?? "–"}</td>
            </tr>)}</tbody>
          </table></div>
        : <div className="table-scroll"><table className="rg-table">
            <caption className="visually-hidden">{LEVEL_LABEL[report.level]}</caption>
            <thead><tr><th scope="col">{LEVEL_LABEL[report.level]}</th><th scope="col">Verträge</th><th scope="col">Kosten lfd. Jahr</th></tr></thead>
            <tbody>{(report.items as DrilldownBucket[]).map((item) => <tr key={item.value}>
              <th scope="row"><button type="button" className="rg-link" onClick={() => open(item.value)}>{item.label}</button></th>
              <td>{item.count}</td>
              <td><CoverageValue value={item.cost_current_year} known={item.known} missing={item.missing} /></td>
            </tr>)}</tbody>
          </table></div>}
      {report.truncated ? <p className="field-hint">Es werden die 200 teuersten Verträge gezeigt; alle stehen in der Vertragsliste.</p> : null}
      {report.path.length > 0 ? <Link href={registerHref}>Diese Auswahl in der Vertragsliste öffnen (alle Status)</Link> : null}
    </> : null}
  </section>;
}
