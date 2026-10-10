import type { ReactNode } from "react";
import { SignalIcon, type SignalTone } from "./Signal";

export type BadgeTone = "neutral" | "success" | "warning" | "danger" | "info" | "ai";

const SIGNAL: Record<BadgeTone, SignalTone | null> = {
  danger: "critical", warning: "warning", info: "info", success: "done", ai: "ai", neutral: null,
};

// Kurzes Kennzeichen; der Text traegt die Bedeutung, Form und Farbe unterstuetzen (Ruhe & Signal).
export default function Badge({ tone = "neutral", children, title }: { tone?: BadgeTone; children: ReactNode; title?: string }) {
  const signal = SIGNAL[tone];
  return (
    <span className={`badge${tone === "neutral" ? "" : ` badge--${tone}`}`} title={title}>
      {signal ? <SignalIcon tone={signal} /> : null}
      {children}
    </span>
  );
}
