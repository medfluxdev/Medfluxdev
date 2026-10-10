import type { ReactNode } from "react";
import { SignalIcon, type SignalTone } from "./Signal";

type Tone = "neutral" | "info" | "success" | "warning" | "critical";

const SIGNAL: Record<Tone, SignalTone> = { critical: "critical", warning: "warning", info: "info", success: "done", neutral: "neutral" };

interface Props {
  tone?: Tone;
  children: ReactNode;
  role?: "alert" | "status";
  action?: ReactNode;
}

// Konsistente Hinweis-/Fehlermeldung. Form und Farbe der Signalstufe unterstuetzen;
// der Inhalt traegt die Information (Text + semantische Rolle).
export default function InlineAlert({
  tone = "neutral",
  children,
  role,
  action,
}: Props) {
  return (
    <div className={`alert alert--${tone}`} role={role}>
      <span className="alert-body"><SignalIcon tone={SIGNAL[tone]} className="alert-icon" /><span>{children}</span></span>
      {action}
    </div>
  );
}
