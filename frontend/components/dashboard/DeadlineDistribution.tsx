import type { DeadlineBucket } from "@/lib/dashboard-types";

interface Props {
  buckets: DeadlineBucket[];
}

function maxCount(buckets: DeadlineBucket[]): number {
  return buckets.reduce((m, b) => Math.max(m, b.contract_count), 0);
}

// Kompakte, barrierefreie Fristen-Verteilung als semantische Liste.
// Balkenbreite ist unterstützend; die Zahlen sind der verlässliche Wert.
export default function DeadlineDistribution({ buckets }: Props) {
  const max = Math.max(1, maxCount(buckets));
  const hasAny = buckets.some((b) => b.contract_count > 0);

  return (
    <div className="deadline-dist">
      <ul className="deadline-list">
        {buckets.map((b) => (
          <li key={b.label_de} className="deadline-row">
            <span className="deadline-label">{b.label_de}</span>
            <span
              className="deadline-bar"
              style={{ width: `${Math.round((b.contract_count / max) * 100)}%` }}
            />
            <span className="deadline-count">{b.contract_count}</span>
            <span className="deadline-detail">
              {(b.cancellation > 0 || b.contract_end > 0) &&
                `Kündigung ${b.cancellation} · Ende ${b.contract_end}`}
            </span>
          </li>
        ))}
      </ul>
      {!hasAny && (
        <p className="empty-state">
          Keine Fristen innerhalb der Warn-Schwellen.
        </p>
      )}
    </div>
  );
}
