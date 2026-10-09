import Link from "next/link";
import type { ReactNode } from "react";

export type KpiTone = "neutral" | "info" | "success" | "warning" | "danger";

interface Props {
  label: string;
  /** null/undefined/"" = noch keine echten Zahlen: Anzeige „—“ mit „Noch keine Daten“. */
  value: ReactNode | null | undefined;
  hint?: ReactNode;
  href?: string;
  linkLabel?: string;
  loading?: boolean;
  /** Farbe traegt Bedeutung: warning/danger faerben den Wert, info/success nur das Symbol. */
  tone?: KpiTone;
  /** Kleines Liniensymbol (18px) oben rechts. */
  icon?: ReactNode;
}

// Kennzahl-Kachel: Beschriftung, Wert (Tabellenziffern), optionaler Hinweis und Sprung.
// Mit href ist die ganze Kachel ein Link.
export default function KpiTile({ label, value, hint, href, linkLabel, loading = false, tone = "neutral", icon }: Props) {
  const empty = !loading && (value === null || value === undefined || value === "");
  const className = `kpi kpi--${tone}${empty ? " kpi--empty" : ""}`;
  const body = (
    <>
      <span className="kpi-top">
        <span className="kpi-label">{label}</span>
        {icon ? <span className="kpi-icon" aria-hidden="true">{icon}</span> : null}
      </span>
      <strong className="kpi-value">{loading ? "…" : empty ? "—" : value}</strong>
      {loading ? null : empty ? <span className="kpi-hint">Noch keine Daten</span> : hint ? <span className="kpi-hint">{hint}</span> : null}
    </>
  );
  if (href) {
    return (
      <Link href={href} className={className} aria-busy={loading || undefined}>
        {body}
        <span className="kpi-more">{linkLabel ?? "Anzeigen"}</span>
      </Link>
    );
  }
  return <article className={className} aria-busy={loading || undefined}>{body}</article>;
}
