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
  return <span className={`severity-tag severity-${severity}`}>{severityLabel[severity] ?? severity}</span>;
}

export default function ActionList({ items, total }: Props) {
  if (total === 0) {
    return (
      <div className="dash-empty-inline">
        <span className="dash-empty-icon" aria-hidden="true">✓</span>
        <div><strong>Kein akuter Handlungsbedarf.</strong><p>Aktuell sind keine priorisierten Aufgaben offen.</p></div>
      </div>
    );
  }

  return (
    <div className="action-list-wrap">
      <p className="sr-text">{total} {total === 1 ? "Handlungsbedarf" : "Handlungspunkte"} insgesamt</p>
      <ul className="action-list action-list-polished">
        {items.map((item, i) => (
          <li key={`${item.warning_type}-${item.target_date ?? "none"}-${i}`} className="action-item action-item-polished">
            <div className="action-main">
              <SeverityTag severity={item.severity} />
              <div className="action-copy">
                <span className="action-title">{item.title_de}</span>
                <div className="action-meta">
                  {item.contract_title && <span>{item.contract_title}</span>}
                  {item.supplier && <span>{item.supplier}</span>}
                </div>
                <div className="action-flags" aria-label="Erforderliche Bearbeitung">
                  {item.requires_action && <span>Aktion erforderlich</span>}
                  {item.requires_review && <span>Prüfung erforderlich</span>}
                </div>
              </div>
            </div>
            <div className="action-right">
              {item.target_date && <span className="action-target">{formatDate(item.target_date)} · {formatDaysRemaining(item.days_remaining)}</span>}
              {item.annual_cost ? (
                <span className="action-cost">Jährliche Kosten: {formatCurrency(item.annual_cost.amount, item.annual_cost.currency)}</span>
              ) : item.cost_unreliable ? (
                <span className="action-cost unreliable">Kosten nicht verlässlich ermittelt</span>
              ) : null}
            </div>
          </li>
        ))}
      </ul>
    </div>
  );
}
