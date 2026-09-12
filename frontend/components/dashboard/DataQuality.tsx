import type { DataQualityItem } from "@/lib/dashboard-types";

interface Props {
  items: DataQualityItem[];
}

export default function DataQuality({ items }: Props) {
  if (items.length === 0) {
    return <p className="empty-state">Keine manuelle Prüfung erforderlich.</p>;
  }
  return (
    <ul className="dq-list">
      {items.map((q) => (
        <li key={q.label_de} className="dq-row">
          <span className="dq-label">{q.label_de}</span>
          <span className={`severity-tag severity-${q.severity}`}>{q.count}</span>
        </li>
      ))}
    </ul>
  );
}
