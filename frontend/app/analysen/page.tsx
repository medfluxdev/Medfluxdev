"use client";

import { useEffect, useState } from "react";
import { useAuth } from "@/components/auth/AuthProvider";
import AnalysenOverview from "@/components/analytics/AnalysenOverview";
import PortfolioQueryPanel from "@/components/analytics/PortfolioQueryPanel";
import InlineAlert from "@/components/ui/InlineAlert";
import PageHeader from "@/components/ui/PageHeader";
import Skeleton from "@/components/ui/Skeleton";
import { downloadPortfolioXlsx, getPortfolioReport, listRenewals, saveBlob, type NotEvaluableItem, type PortfolioReport, type RenewalListItem } from "@/lib/domain-api/registerGrid";
import { getPortfolioReport as getRiskReport, type PortfolioReport as RiskReport } from "@/lib/domain-api/reports";
import { formatDate } from "@/lib/format";

// Analysen: vier Fragen in Reihenfolge – Wie viel? Wohin? Was kommt / wo sparen? Wo liegt Risiko?
// Alle Zahlen kommen aus den bestehenden Berichten (Stammdaten und gepflegte Finanzdaten, ohne ungeprüfte KI-Vorschläge).
export default function AnalyticsPage() {
  const { organizationSlug, role, account } = useAuth();
  const canExport = Boolean(account?.is_developer || role === "admin" || role === "contract_manager");
  const [report, setReport] = useState<PortfolioReport | null>(null);
  const [renewals, setRenewals] = useState<RenewalListItem[]>([]);
  const [notEvaluable, setNotEvaluable] = useState<NotEvaluableItem[]>([]);
  const [risk, setRisk] = useState<RiskReport | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!organizationSlug) return;
    let cancelled = false;
    Promise.allSettled([getPortfolioReport(organizationSlug), listRenewals(organizationSlug, 183), getRiskReport(organizationSlug)]).then(([portfolio, renewal, riskResult]) => {
      if (cancelled) return;
      if (portfolio.status === "fulfilled") setReport(portfolio.value);
      else setError(portfolio.reason instanceof Error && portfolio.reason.message ? portfolio.reason.message : "Die Analysen konnten nicht geladen werden.");
      if (renewal.status === "fulfilled") { setRenewals(renewal.value.items); setNotEvaluable(renewal.value.not_evaluable ?? []); }
      if (riskResult.status === "fulfilled") setRisk(riskResult.value);
    });
    return () => { cancelled = true; };
  }, [organizationSlug]);

  async function exportXlsx() {
    if (!organizationSlug) return;
    try {
      const { blob, filename } = await downloadPortfolioXlsx(organizationSlug);
      saveBlob(blob, filename ?? "portfoliobericht.xlsx");
    } catch (err) {
      setError(err instanceof Error && err.message ? err.message : "Export fehlgeschlagen.");
    }
  }

  return (
    <div className="page analytics-page an">
      <PageHeader
        title="Analysen"
        description={`Netto, EUR · aus Stammdaten und gepflegten Finanzdaten, ohne ungeprüfte KI-Vorschläge${report ? ` · Stand ${formatDate(report.as_of)}` : ""}`}
        actions={canExport ? <button type="button" className="btn" onClick={() => void exportXlsx()}>Bericht als Excel</button> : undefined}
      />
      {organizationSlug ? <PortfolioQueryPanel organizationSlug={organizationSlug} /> : null}
      {error ? <InlineAlert tone="critical" role="alert">{error}</InlineAlert> : null}
      {!report && !error ? <Skeleton lines={5} label="Analysen werden geladen…" /> : null}
      {report ? <AnalysenOverview report={report} renewals={renewals} notEvaluable={notEvaluable} risk={risk} /> : null}
    </div>
  );
}
