"use client";

import Link from "next/link";
import StatusBadge, { type StatusTone } from "@/components/ui/StatusBadge";
import type { SupplierPerformanceItem } from "@/lib/domain-api/intelligenceAnalytics";
import type { PortfolioReport } from "@/lib/domain-api/reports";
import { registerLink } from "@/lib/master-data";

const RISK: Record<string, { label: string; tone: StatusTone; order: number }> = {
  high: { label: "Hoch", tone: "critical", order: 0 },
  medium: { label: "Mittel", tone: "warning", order: 1 },
  low: { label: "Niedrig", tone: "success", order: 2 },
  unknown: { label: "Nicht bewertet", tone: "neutral", order: 3 },
};

// Was die KI-Analyse über das Portfolio sagt – in Worten und mit Sprung in die passende Liste.
export default function AiPortfolioNotes({ report, suppliers }: { report: PortfolioReport; suppliers: SupplierPerformanceItem[] }) {
  const risks = Object.entries(report.contracts.by_risk)
    .map(([key, count]) => ({ key, count, ...(RISK[key] ?? { label: key, tone: "neutral" as StatusTone, order: 9 }) }))
    .filter((item) => item.count > 0)
    .sort((a, b) => a.order - b.order);
  const openTasks = Object.entries(report.work_queue.by_status)
    .filter(([status]) => status !== "resolved")
    .reduce((sum, [, count]) => sum + count, 0);
  const withObligations = suppliers.filter((item) => item.total_obligations > 0);

  return <section className="card card-pad ai-notes" aria-labelledby="ai-notes-heading">
    <div className="section-head">
      <div>
        <h2 id="ai-notes-heading">Aus der KI-Analyse</h2>
        <p>Einschätzungen der lokalen KI – als Hinweis, nicht als geprüfter Wert.</p>
      </div>
    </div>
    <div className="ai-notes-grid">
      <div>
        <h3>Risiko je Vertrag</h3>
        {risks.length === 0 ? <p className="field-hint">Noch keine Einschätzung.</p> : <ul className="ai-notes-list">
          {risks.map((item) => <li key={item.key}>
            <StatusBadge label={item.label} tone={item.tone} />
            {item.key in RISK && item.key !== "unknown"
              ? <Link href={registerLink("risk", item.label)}>{item.count} {item.count === 1 ? "Vertrag" : "Verträge"}</Link>
              : <span>{item.count} {item.count === 1 ? "Vertrag" : "Verträge"}</span>}
          </li>)}
        </ul>}
      </div>
      <div>
        <h3>Offen</h3>
        <ul className="ai-notes-list">
          <li><span className="ai-notes-count">{openTasks}</span><Link href="/fristen?ansicht=aufgaben">{openTasks === 1 ? "offene Aufgabe" : "offene Aufgaben"} aus der Analyse</Link></li>
          <li><span className="ai-notes-count">{report.contracts.archived}</span><Link href="/archiv">{report.contracts.archived === 1 ? "archivierter Vertrag" : "archivierte Verträge"}</Link></li>
        </ul>
      </div>
    </div>
    {withObligations.length > 0 ? <div className="table-scroll">
      <table className="data-table">
        <caption>Pflichten der Vertragspartner (aus der Analyse)</caption>
        <thead><tr><th scope="col">Vertragspartner</th><th scope="col" className="num">Verträge</th><th scope="col" className="num">Pflichten verletzt</th></tr></thead>
        <tbody>{withObligations.map((item) => <tr key={item.supplier}>
          <th scope="row">{item.supplier}</th>
          <td className="num">{item.contract_count}</td>
          <td className="num">{item.breached_obligations} von {item.total_obligations}</td>
        </tr>)}</tbody>
      </table>
    </div> : null}
  </section>;
}
