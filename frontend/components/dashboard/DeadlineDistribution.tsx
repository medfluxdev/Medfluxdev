import Link from "next/link";
import type { DeadlineBucket } from "@/lib/dashboard-types";

interface Props {
  buckets: DeadlineBucket[];
}

function maxCount(buckets: DeadlineBucket[]): number {
  return buckets.reduce((m, b) => Math.max(m, b.contract_count), 0);
}

export default function DeadlineDistribution({ buckets }: Props) {
  const max = Math.max(1, maxCount(buckets));
  const hasAny = buckets.some((b) => b.contract_count > 0);
  const cancellationCount = buckets.reduce((sum, bucket) => sum + bucket.cancellation, 0);
  const endCount = buckets.reduce((sum, bucket) => sum + bucket.contract_end, 0);

  return (
    <div className="deadline-dist deadline-dist-polished">
      {hasAny && (
        <div className="deadline-summary" aria-label="Fristarten">
          <Link href="/contracts?critical_cancellation=true" className="deadline-summary-item deadline-summary-critical">
            <strong>{cancellationCount}</strong>
            <span>Kündigungsfristen</span>
          </Link>
          <div className="deadline-summary-item">
            <strong>{endCount}</strong>
            <span>Vertragsenden</span>
          </div>
        </div>
      )}
      <ul className="deadline-list">
        {buckets.map((b) => {
          const width = Math.round((b.contract_count / max) * 100);
          return (
            <li key={b.label_de} className="deadline-row deadline-row-polished">
              <span className="deadline-label">{b.label_de}</span>
              <span className="deadline-track" aria-hidden="true">
                <span className="deadline-bar" style={{ width: `${width}%` }} />
              </span>
              <span className="deadline-count">{b.contract_count}</span>
              <span className="deadline-detail">
                {(b.cancellation > 0 || b.contract_end > 0) && `Kündigung ${b.cancellation} · Ende ${b.contract_end}`}
              </span>
            </li>
          );
        })}
      </ul>
      {!hasAny && (
        <div className="deadline-note">
          <span aria-hidden="true">i</span>
          <em>Keine Fristen innerhalb der Warn-Schwellen.</em>
        </div>
      )}
    </div>
  );
}
