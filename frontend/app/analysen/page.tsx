"use client";

import { useEffect, useState } from "react";
import { useAuth } from "@/components/auth/AuthProvider";
import AiPortfolioNotes from "@/components/analytics/AiPortfolioNotes";
import PortfolioDrilldown from "@/components/analytics/PortfolioDrilldown";
import PortfolioQueryPanel from "@/components/analytics/PortfolioQueryPanel";
import RegisterPortfolio from "@/components/analytics/RegisterPortfolio";
import InlineAlert from "@/components/ui/InlineAlert";
import PageHeader from "@/components/ui/PageHeader";
import Skeleton from "@/components/ui/Skeleton";
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
    <div className="page analytics-page">
      <PageHeader title="Analysen" description="Kosten, Fristen und Handlungsbedarf im Vertragsportfolio." />
      {organizationSlug ? <RegisterPortfolio organizationSlug={organizationSlug} /> : null}
      {organizationSlug ? <PortfolioDrilldown organizationSlug={organizationSlug} /> : null}
      {error ? <InlineAlert tone="critical" role="alert">{error}</InlineAlert> : null}
      {!report && !error ? <Skeleton lines={3} label="KI-Hinweise werden geladen…" /> : null}
      {report ? <AiPortfolioNotes report={report} suppliers={suppliers} /> : null}
      {organizationSlug ? <PortfolioQueryPanel organizationSlug={organizationSlug} /> : null}
    </div>
  );
}
