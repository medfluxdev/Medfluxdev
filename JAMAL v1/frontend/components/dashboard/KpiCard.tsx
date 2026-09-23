import Link from "next/link";
import type { KpiCard as KpiCardType } from "@/lib/dashboard-types";

interface Props {
  card: KpiCardType;
  href?: string;
}

function iconForLabel(label: string): string {
  const lower = label.toLowerCase();
  if (lower.includes("kündigung")) return "!";
  if (lower.includes("aktiv")) return "✓";
  if (lower.includes("ablauf") || lower.includes("bald")) return "△";
  if (lower.includes("wert") || lower.includes("kosten")) return "€";
  return "▤";
}

function toneForLabel(label: string): string {
  const lower = label.toLowerCase();
  if (lower.includes("kündigung")) return "danger";
  if (lower.includes("aktiv")) return "success";
  if (lower.includes("ablauf") || lower.includes("bald")) return "warning";
  if (lower.includes("wert") || lower.includes("kosten")) return "money";
  return "info";
}

export default function KpiCard({ card, href }: Props) {
  const tone = toneForLabel(card.label_de);
  const content = (
    <>
      <div className="kpi-card-top">
        <p className="kpi-label">{card.label_de}</p>
        <span className={`kpi-icon kpi-icon-${tone}`} aria-hidden="true">
          {iconForLabel(card.label_de)}
        </span>
      </div>
      <p className="kpi-value" aria-label={`${card.label_de}: ${card.value}`}>
        {card.value}
      </p>
      {card.secondary_de && <p className="kpi-secondary">{card.secondary_de}</p>}
      {card.status_de && <p className="visually-hidden" role="status">{card.status_de}</p>}
      {href && <span className="kpi-link-hint">Verträge anzeigen <span aria-hidden="true">→</span></span>}
    </>
  );

  if (href) {
    return <Link href={href} className={`kpi-card kpi-card-polished kpi-${tone} kpi-card-link`}>{content}</Link>;
  }

  return <article className={`kpi-card kpi-card-polished kpi-${tone}`}>{content}</article>;
}
