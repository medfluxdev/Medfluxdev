import type { KpiCard as KpiCardType } from "@/lib/dashboard-types";

interface Props {
  card: KpiCardType;
}

export default function KpiCard({ card }: Props) {
  return (
    <article className="kpi-card">
      <p className="kpi-label">{card.label_de}</p>
      <p className="kpi-value" aria-label={`${card.label_de}: ${card.value}`}>
        {card.value}
      </p>
      {card.secondary_de && (
        <p className="kpi-secondary" aria-hidden="true">
          {card.secondary_de}
        </p>
      )}
      {card.status_de && (
        <p className="visually-hidden" role="status">
          {card.status_de}
        </p>
      )}
    </article>
  );
}
