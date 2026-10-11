import type { ReactNode } from "react";

export type SignalTone = "critical" | "warning" | "info" | "done" | "ai" | "neutral";

// Jede Stufe hat eine eigene Form (Farbsehschwäche): Achteck, Dreieck, Kreis mit i,
// Kreis mit Haken, Funke, Kreis mit Strich. Pfade aus dem Entwurf Mein Tag v3.
const SHAPES: Record<SignalTone, ReactNode> = {
  critical: <><path d="M8.2 3h7.6L21 8.2v7.6L15.8 21H8.2L3 15.8V8.2z" /><path d="M12 8v5M12 16.5v.5" /></>,
  warning: <><path d="M12 3.5 22 20H2z" /><path d="M12 10v4M12 17v.5" /></>,
  info: <><circle cx="12" cy="12" r="9" /><path d="M12 11v5M12 7.5v.5" /></>,
  done: <><circle cx="12" cy="12" r="9" /><path d="m8 12.5 2.5 2.5L16 9.5" /></>,
  ai: <path d="M12 3l1.8 5.2L19 10l-5.2 1.8L12 17l-1.8-5.2L5 10l5.2-1.8z" />,
  neutral: <><circle cx="12" cy="12" r="9" /><path d="M8 12h8" /></>,
};

/** Liniensymbol einer Signalstufe (16px, dekorativ). */
export function SignalIcon({ tone, className }: { tone: SignalTone; className?: string }) {
  return (
    <svg className={`signal-icon${className ? ` ${className}` : ""}`} viewBox="0 0 24 24" aria-hidden="true" focusable="false">
      {SHAPES[tone]}
    </svg>
  );
}

interface Props {
  tone: SignalTone;
  /** Das Wort trägt die Bedeutung (Pflicht). */
  children: ReactNode;
  /** Abweichendes Symbol; Standard ist die Form der Stufe. */
  icon?: ReactNode;
  title?: string;
  /** Kleine Form (z. B. neben einem Wert oder in Listen). */
  size?: "sm";
}

// Ruhe & Signal: Farbe + Form + Wort, nie Farbe allein. Grün (done) nur für Bestätigtes.
export default function Signal({ tone, children, icon, title, size }: Props) {
  return (
    <span className={`signal signal--${tone}${size === "sm" ? " signal--sm" : ""}`} title={title}>
      {icon ?? <SignalIcon tone={tone} />}
      <span className="signal-label">{children}</span>
    </span>
  );
}
