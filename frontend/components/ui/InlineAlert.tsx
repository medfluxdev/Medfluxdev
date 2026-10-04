import type { ReactNode } from "react";

type Tone = "neutral" | "info" | "success" | "warning" | "critical";

interface Props {
  tone?: Tone;
  children: ReactNode;
  role?: "alert" | "status";
  action?: ReactNode;
}

// Konsistente Hinweis-/Fehlermeldung. Farbe ist unterstützend; der Inhalt
// trägt die Information (Text + semantische Rolle).
export default function InlineAlert({
  tone = "neutral",
  children,
  role,
  action,
}: Props) {
  return (
    <div className={`alert alert--${tone}`} role={role}>
      <span>{children}</span>
      {action}
    </div>
  );
}