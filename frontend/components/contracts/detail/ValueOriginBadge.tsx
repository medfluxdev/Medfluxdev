"use client";

import Signal from "@/components/ui/Signal";

export type ValueOriginKind = "extracted" | "reviewed" | "corrected" | "calculated" | "missing" | "system";

// Ruhe & Signal: Herkunft ist eine kleine graue Marke; Farbe nur, wenn etwas zu tun ist
// (KI-Vorschlag noch nicht bestätigt, Wert fehlt).
const QUIET: Partial<Record<ValueOriginKind, { label: string; icon: "db" | "calc" | "check" | "pen" }>> = {
  system: { label: "gepflegt", icon: "db" },
  calculated: { label: "berechnet", icon: "calc" },
  reviewed: { label: "geprüft", icon: "check" },
  corrected: { label: "korrigiert", icon: "pen" },
};

const ICONS = {
  db: <><ellipse cx="12" cy="6" rx="7" ry="3" /><path d="M5 6v12c0 1.7 3.1 3 7 3s7-1.3 7-3V6M5 12c0 1.7 3.1 3 7 3s7-1.3 7-3" /></>,
  calc: <><rect x="5" y="3" width="14" height="18" rx="2" /><path d="M8 7h8M8 12h2M12 12h2M8 16h2M12 16h2M16 12v4" /></>,
  check: <path d="m5 12.5 4.5 4.5L19 7.5" />,
  pen: <path d="M4 20h4L19 9l-4-4L4 16v4z" />,
};

export default function ValueOriginBadge({ kind, detail }: { kind: ValueOriginKind; detail?: string | null }) {
  if (kind === "extracted") return <Signal tone="ai" size="sm" title={detail ?? "Aus dem Dokument gelesen, noch nicht bestätigt"}>KI-Vorschlag</Signal>;
  if (kind === "missing") return <Signal tone="critical" size="sm" title={detail ?? undefined}>Fehlt</Signal>;
  const quiet = QUIET[kind]!;
  return (
    <span className="value-origin" title={detail ?? undefined}>
      <svg viewBox="0 0 24 24" aria-hidden="true" focusable="false">{ICONS[quiet.icon]}</svg>
      {quiet.label}
    </span>
  );
}
