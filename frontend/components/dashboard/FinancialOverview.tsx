import Link from "next/link";
import type { FinancialSummary } from "@/lib/dashboard-types";
import { formatCurrency } from "@/lib/format";

interface Props {
  financial: FinancialSummary;
}

function MoneyList({ title, totals }: { title: string; totals: { currency: string; amount: string; contract_count: number }[] }) {
  if (totals.length === 0) return null;
  return (
    <div className="money-group">
      <p className="money-title">{title}</p>
      <ul className="money-list">
        {totals.map((t) => (
          <li key={t.currency} className="money-row">
            <span className="money-amount">{formatCurrency(t.amount, t.currency)}</span>
            <span className="money-currency">{t.currency}</span>
            <span className="money-count">{t.contract_count} {t.contract_count === 1 ? "Vertrag" : "Verträge"}</span>
          </li>
        ))}
      </ul>
    </div>
  );
}

export default function FinancialOverview({ financial }: Props) {
  const hasCosts = financial.annual_recurring.length > 0;
  const hasTotal = financial.total_contract_value.length > 0;
  const missingAnnual = financial.contracts_without_reliable_annual_cost;
  const missingTotal = financial.contracts_without_reliable_total_value;

  if (!hasCosts && !hasTotal) {
    return (
      <div className="financial-empty-card">
        <div className="financial-empty-icon" aria-hidden="true">▤</div>
        <strong>Keine verlässlichen Kosten verfügbar.</strong>
        <p>Unbekannte oder widersprüchliche Kosten werden nicht als 0 € dargestellt.</p>
        {(missingAnnual > 0 || missingTotal > 0) && <p>{missingAnnual} ohne verlässliche Jahreskosten · {missingTotal} ohne verlässlichen Gesamtwert</p>}
      </div>
    );
  }

  return (
    <div className="financial-overview">
      {financial.multi_currency && <p className="notice">Mehrere Währungen – Beträge werden getrennt ausgewiesen (kein Umtausch).</p>}
      <div className="money-groups">
        <MoneyList title="Jährliche wiederkehrende Kosten" totals={financial.annual_recurring} />
        <MoneyList title="Gesamtvertragswert" totals={financial.total_contract_value} />
      </div>
      {(missingAnnual > 0 || missingTotal > 0) && (
        <div className="financial-coverage" role="note">
          <strong>Datenabdeckung</strong>
          <span>{missingAnnual} {missingAnnual === 1 ? "Vertrag" : "Verträge"} ohne verlässliche Jahreskosten</span>
          <span>{missingTotal} {missingTotal === 1 ? "Vertrag" : "Verträge"} ohne verlässlichen Gesamtwert</span>
          <Link href="/contracts?requires_review=true">Zu den Verträgen mit Prüfbedarf →</Link>
        </div>
      )}
    </div>
  );
}
