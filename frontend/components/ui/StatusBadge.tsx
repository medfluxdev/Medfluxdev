import { SignalIcon, type SignalTone } from "./Signal";

// Semantischer Status-Pill. Traegt IMMER ein Text-Label; die Form der Signalstufe
// unterstuetzt (Status nie als Farbe allein).
export type StatusTone =
  | "neutral"
  | "information"
  | "success"
  | "warning"
  | "critical"
  | "review"
  | "stale";

const SIGNAL: Record<StatusTone, SignalTone> = {
  critical: "critical", warning: "warning", review: "warning", information: "info", success: "done", neutral: "neutral", stale: "neutral",
};

interface Props {
  label: string;
  tone?: StatusTone;
  /** Form der Signalstufe zeigen (Standard). */
  showDot?: boolean;
}

export default function StatusBadge({
  label,
  tone = "neutral",
  showDot = true,
}: Props) {
  return (
    <span className={`status-badge status-badge--${tone}`}>
      {showDot && <SignalIcon tone={SIGNAL[tone]} />}
      {label}
    </span>
  );
}
