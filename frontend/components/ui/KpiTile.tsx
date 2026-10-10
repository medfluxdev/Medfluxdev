import Link from "next/link";
import type { ReactNode } from "react";
import Signal, { type SignalTone } from "./Signal";

export type KpiTone = "neutral" | "info" | "success" | "warning" | "danger";

interface Props {
  label: string;
  /** null/undefined/"" = noch keine echten Zahlen: Anzeige „—“ mit „Noch keine Daten“. */
  value: ReactNode | null | undefined;
  hint?: ReactNode;
  href?: string;
  linkLabel?: string;
  loading?: boolean;
  /** Veraltet (Ruhe & Signal): Kacheln sind immer neutral; Aufmerksamkeit traegt `signal`. */
  tone?: KpiTone;
  /** Signal statt Hinweis, z. B. { tone: "warning", label: "Kosten fehlen bei 3 Verträgen" }. */
  signal?: { tone: SignalTone; label: string };
  /** Kleines Liniensymbol (18px) oben rechts. */
  icon?: ReactNode;
}

// Kennzahl-Kachel: Beschriftung, Wert (Tabellenziffern), optionaler Hinweis und Sprung.
// Mit href ist die ganze Kachel ein Link.
export default function KpiTile({ label, value, hint, href, linkLabel, loading = false, icon, signal }: Props) {
  const empty = !loading && (value === null || value === undefined || value === "");
  const className = `kpi${empty ? " kpi--empty" : ""}`;
  const body = (
    <>
      <span className="kpi-top">
        {icon ? <span className="kpi-icon" aria-hidden="true">{icon}</span> : null}
        <span className="kpi-label">{label}</span>
      </span>
      <strong className="kpi-value">{loading ? "…" : empty ? "—" : value}</strong>
      {loading ? null : signal ? <span className="kpi-hint"><Signal tone={signal.tone}>{signal.label}</Signal></span> : empty ? <span className="kpi-hint">Noch keine Daten</span> : hint ? <span className="kpi-hint">{hint}</span> : null}
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
