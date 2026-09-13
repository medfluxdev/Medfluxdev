"use client";

export type ValueOriginKind = "extracted" | "reviewed" | "corrected" | "calculated" | "missing" | "system";

const LABELS: Record<ValueOriginKind, string> = {
  extracted: "Extrahiert",
  reviewed: "Geprüft",
  corrected: "Korrigiert",
  calculated: "Berechnet",
  missing: "Fehlt",
  system: "Systemwert",
};

export default function ValueOriginBadge({ kind, detail }: { kind: ValueOriginKind; detail?: string | null }) {
  const label = LABELS[kind];
  return (
    <span className={`cw-origin-badge cw-origin-${kind}`} title={detail ?? undefined}>
      {label}
    </span>
  );
}
