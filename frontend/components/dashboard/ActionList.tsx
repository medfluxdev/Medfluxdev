import type { ActionItem } from "@/lib/dashboard-types";
import { formatCurrency, formatDate, formatDaysRemaining } from "@/lib/format";

interface Props {
  items: ActionItem[];
  total: number;
}

const severityLabel: Record<string, string> = {
  critical: "Kritisch",
  high: "Hoch",
  medium: "Mittel",
  low: "Niedrig",
  info: "Info",
};

function SeverityTag({ severity }: { severity: string }) {
  // Farbe ist unterstützend, nie das einzige Signal: immer ein Text-Label.
  return (
    <span className={`severity-tag severity-${severity}`}>
      {severityLabel[severity] ?? severity}
    </span>
  );
}

export default function ActionList({ items, total }: Props) {
  if (total === 0) {
    return (
      <p className="empty-state">Derzeit kein akuter Handlungsbedarf.</p>
    );
  }
  return (
    <div>
      <p className="sr-text">
        {total} {total === 1 ? "Handlungsbedarf" : "Handlungspunkte"} insgesamt
      </p>
      <ul className="action-list">
        {items.map((item, i) => (
          <li key={i} className="action-item">
            <div className="action-main">
              <SeverityTag severity={item.severity} />
              <span className="action-title">{item.title_de}</span>
            </div>
            <div className="action-meta">
              {item.contract_title && <span>{item.contract_title}</span>}
              {item.supplier && <span>{item.supplier}</span>}
            </div>
            <div className="action-right">
              {item.target_date && (
                <span className="action-target">
                  {formatDate(item.target_date)} ·{" "}
                  {formatDaysRemaining(item.days_remaining)}
                </span>
              )}
              {item.annual_cost ? (
                <span className="action-cost">
                  Jährliche Kosten:{" "}
                  {formatCurrency(
                    item.annual_cost.amount,
                    item.annual_cost.currency
                  )}
                </span>
              ) : item.cost_unreliable ? (
                <span className="action-cost unreliable">
                  Kosten nicht verlässlich ermittelt
                </span>
              ) : null}
            </div>
          </li>
        ))}
      </ul>
    </div>
  );
}
