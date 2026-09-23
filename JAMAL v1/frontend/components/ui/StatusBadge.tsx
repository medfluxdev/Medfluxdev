// Semantischer Status-Pill. Traegt IMMER ein Text-Label; der Punkt/Icon ist
// unterstuetzend (Status nie als Farbe allein).
export type StatusTone =
  | "neutral"
  | "information"
  | "success"
  | "warning"
  | "critical"
  | "review"
  | "stale";

interface Props {
  label: string;
  tone?: StatusTone;
  showDot?: boolean;
}

export default function StatusBadge({
  label,
  tone = "neutral",
  showDot = true,
}: Props) {
  return (
    <span className={`status-badge status-badge--${tone}`}>
      {showDot && <span className="sb-dot" aria-hidden="true" />}
      {label}
    </span>
  );
}