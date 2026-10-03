"use client";

import { useEffect, useState } from "react";
import { useAuth } from "@/components/auth/AuthProvider";
import PortfolioQueryPanel from "@/components/analytics/PortfolioQueryPanel";
import { getPortfolioReport, type PortfolioReport } from "@/lib/domain-api/reports";
import { getSupplierPerformance, type SupplierPerformanceItem } from "@/lib/domain-api/intelligenceAnalytics";

export default function AnalyticsPage() {
  const { organizationSlug } = useAuth();
  const [report, setReport] = useState<PortfolioReport | null>(null);
  const [suppliers, setSuppliers] = useState<SupplierPerformanceItem[]>([]);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!organizationSlug) return;
    Promise.all([getPortfolioReport(organizationSlug), getSupplierPerformance(organizationSlug)])
      .then(([portfolio, supplierResult]) => {
        setReport(portfolio);
        setSuppliers(supplierResult.items ?? []);
      })
      .catch((err) => setError(err instanceof Error ? err.message : "Analysen konnten nicht geladen werden."));
  }, [organizationSlug]);

  return (
    <div className="page">
      <header className="entity-header"><h1>Analysen</h1><p className="page-sub">Kennzahlen direkt aus dem Backend.</p></header>
      {organizationSlug ? <PortfolioQueryPanel organizationSlug={organizationSlug} /> : null}
      {error ? <div className="alert alert--critical">{error}</div> : null}
      {!report && !error ? <p className="state-loading">Analysen werden geladen…</p> : null}
      {report ? <>
        <section className="intel-strip">
          <article className="intel"><span>Verträge</span><strong>{report.contracts.total}</strong></article>
          <article className="intel"><span>Aktiv</span><strong>{report.contracts.active}</strong></article>
          <article className="intel"><span>Archiviert</span><strong>{report.contracts.archived}</strong></article>
          <article className="intel"><span>Lieferanten</span><strong>{suppliers.length}</strong></article>
        </section>
        <div className="cw-two-col">
          <section className="card card-pad"><h2>Risiken</h2><ul>{Object.entries(report.contracts.by_risk).map(([key, value]) => <li key={key}>{key.replace(/_/g, " ")}: <strong>{value}</strong></li>)}</ul></section>
          <section className="card card-pad"><h2>To-dos</h2><ul>{Object.entries(report.work_queue.by_status).map(([key, value]) => <li key={key}>{key.replace(/_/g, " ")}: <strong>{value}</strong></li>)}</ul></section>
        </div>
        <section className="card card-pad"><h2>Lieferanten</h2>{suppliers.length === 0 ? <p>Keine Daten vorhanden.</p> : <ul>{suppliers.map((item) => <li key={item.supplier}><strong>{item.supplier}</strong> · {item.contract_count} Verträge · {item.breached_obligations}/{item.total_obligations} Pflichten verletzt</li>)}</ul>}</section>
      </> : null}
    </div>
  );
}
