import Link from "next/link";
import type { ReactNode } from "react";

interface Props {
  label: string;
  value: ReactNode;
  hint?: ReactNode;
  href?: string;
  linkLabel?: string;
}

// Kennzahl-Kachel: Beschriftung, Wert (Tabellenziffern), optionaler Hinweis und Sprung.
export default function KpiTile({ label, value, hint, href, linkLabel }: Props) {
  return (
    <article className="kpi">
      <span className="kpi-label">{label}</span>
      <strong className="kpi-value">{value}</strong>
      {hint ? <span className="kpi-hint">{hint}</span> : null}
      {href ? <Link href={href} className="btn-link">{linkLabel ?? "Anzeigen"}</Link> : null}
    </article>
  );
}
