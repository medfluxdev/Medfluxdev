import type { DataQualityItem } from "@/lib/dashboard-types";

interface Props {
  items: DataQualityItem[];
}

export default function DataQuality({ items }: Props) {
  if (items.length === 0) {
    return (
      <div className="dash-empty-inline">
        <span className="dash-empty-icon" aria-hidden="true">✓</span>
        <div>
          <strong>Keine manuelle Prüfung erforderlich.</strong>
          <p>Alle aktuell bewerteten Angaben sind ausreichend verlässlich.</p>
        </div>
      </div>
    );
  }
  return (
    <ul className="dq-list dq-list-polished">
      {items.map((q) => (
        <li key={q.label_de} className="dq-row dq-row-polished">
          <span className="dq-label">{q.label_de}</span>
          <span className={`severity-tag severity-${q.severity}`}>{q.count}</span>
          <span className="dash-row-chevron" aria-hidden="true">›</span>
        </li>
      ))}
    </ul>
  );
}
