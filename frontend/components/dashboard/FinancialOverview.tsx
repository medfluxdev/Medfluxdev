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
            <span className="money-amount">
              {formatCurrency(t.amount, t.currency)}
            </span>
            <span className="money-currency">{t.currency}</span>
            <span className="money-count">
              {t.contract_count} {t.contract_count === 1 ? "Vertrag" : "Verträge"}
            </span>
          </li>
        ))}
      </ul>
    </div>
  );
}

export default function FinancialOverview({ financial }: Props) {
  const hasCosts = financial.annual_recurring.length > 0;
  const hasTotal = financial.total_contract_value.length > 0;
  const excluded =
    financial.contracts_without_reliable_annual_cost +
    financial.contracts_without_reliable_total_value;

  if (!hasCosts && !hasTotal) {
    return (
      <p className="empty-state">
        Keine verlässlichen Kosten verfügbar.
      </p>
    );
  }

  return (
    <div className="financial-overview">
      {financial.multi_currency && (
        <p className="notice">
          Mehrere Währungen – Beträge werden getrennt ausgewiesen (kein Umtausch).
        </p>
      )}
      <div className="money-groups">
        <MoneyList title="Jährliche wiederkehrende Kosten" totals={financial.annual_recurring} />
        <MoneyList title="Gesamtvertragswert" totals={financial.total_contract_value} />
      </div>
      {excluded > 0 && (
        <p className="notice">
          {excluded} {excluded === 1 ? "Vertrag" : "Verträge"} ohne verlässliche
          Kosten-/Wertangabe (nicht als 0 gezählt).
        </p>
      )}
    </div>
  );
}
