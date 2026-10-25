"use client";

import type { ReactNode } from "react";

export type SuggestionKind = "confirmed" | "ai" | "conflict";

const CHECK = <svg viewBox="0 0 24 24" aria-hidden="true" focusable="false"><path d="m5 12.5 4.5 4.5L19 7.5" /></svg>;
const SPARK = <svg viewBox="0 0 24 24" aria-hidden="true" focusable="false"><path d="M12 3v4M12 17v4M3 12h4M17 12h4M6 6l2.5 2.5M15.5 15.5 18 18M18 6l-2.5 2.5M8.5 15.5 6 18" /></svg>;
const WARN = <svg viewBox="0 0 24 24" aria-hidden="true" focusable="false"><path d="M12 4 3 20h18zM12 10v4M12 17v.5" /></svg>;

/**
 * Vorschlag aus der Prüfung am Ort des Felds (Vertragsdaten): bestätigter Wert, KI-Vorschlag oder Widerspruch.
 * Übernommen wird nur auf Klick; der Wert der Vertragsdaten ändert sich vorher nie.
 */
export default function FieldSuggestion({ kind, value, page, busy, onApply, onKeep, onOther }: {
  kind: SuggestionKind;
  value: string;
  page?: number | null;
  busy?: boolean;
  onApply: () => void;
  /** Nur bei Widerspruch: aktuellen Wert beibehalten. */
  onKeep?: () => void;
  /** Nur bei KI-Vorschlag: anders erfassen. */
  onOther?: () => void;
}): ReactNode {
  const where = page ? ` · Seite ${page}` : "";
  return <div className={`fs fs--${kind}`} role="group" aria-label={kind === "conflict" ? "Widerspruch zur Prüfung" : "Vorschlag aus der Prüfung"}>
    <span className="fs-icon">{kind === "confirmed" ? CHECK : kind === "ai" ? SPARK : WARN}</span>
    <span className="fs-text">
      {kind === "conflict"
        ? <span>Die Prüfung sagt <strong>{value}</strong><span className="fs-source">{where}</span></span>
        : <><strong className="fs-value">{value}</strong><span className="fs-source">{kind === "confirmed" ? "In der Prüfung bestätigt" : "KI-Vorschlag, noch nicht geprüft"}{where}</span></>}
    </span>
    <span className="fs-actions">
      <button type="button" className="btn btn-sm btn-primary" disabled={busy} onClick={onApply}>Übernehmen</button>
      {kind === "conflict" && onKeep ? <button type="button" className="btn btn-sm" disabled={busy} onClick={onKeep}>Beibehalten</button> : null}
      {kind === "ai" && onOther ? <button type="button" className="btn btn-sm" disabled={busy} onClick={onOther}>Anders</button> : null}
    </span>
  </div>;
}
