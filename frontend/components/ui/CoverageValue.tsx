import Link from "next/link";
import { coverageNote, formatCurrency } from "@/lib/format";

interface Props {
  /** Summe der bekannten Werte; null = kein Wert bekannt (wird nie als 0 gezeigt). */
  value: string | null | undefined;
  currency?: string;
  known?: number;
  missing?: number;
  /** Summen in anderen Währungen (keine Umrechnung). */
  otherCurrencies?: Record<string, string>;
  /** Link zu den Verträgen ohne Wert. */
  missingHref?: string;
  /** Nur den Hinweis (ohne Betrag) zeigen, z. B. unter einer Kennzahl. */
  noteOnly?: boolean;
}

// Betrag mit Abdeckung: „4.200,00 € · bekannt für 3 von 7“ – unbekannt bleibt „—“.
export default function CoverageValue({ value, currency = "EUR", known, missing, otherCurrencies, missingHref, noteOnly = false }: Props) {
  const note = coverageNote(known, missing, value === null || value === undefined);
  const others = Object.entries(otherCurrencies ?? {});
  const partial = Boolean(missing && missing > 0 && known && known > 0);
  return (
    <span className={`coverage${partial ? " coverage--partial" : ""}`}>
      {noteOnly ? null : <span className="coverage-value">{value === null || value === undefined ? "—" : formatCurrency(value, currency)}</span>}
      {others.map(([code, amount]) => <span key={code} className="coverage-other">+ {formatCurrency(amount, code)}</span>)}
      {note ? (
        <span className="coverage-note">
          {note}
          {missingHref && missing ? <> · <Link href={missingHref}>fehlende anzeigen</Link></> : null}
        </span>
      ) : null}
    </span>
  );
}
