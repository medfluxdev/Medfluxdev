import type { ReactNode } from "react";
import { SignalIcon } from "./Signal";

interface Props {
  title?: string;
  children?: ReactNode;
  action?: ReactNode;
  /** "calm": ruhige graue Zeile fuer "nichts zu tun" in Uebersichtskarten (kein Gruen, Ruhe & Signal).
   *  "compact" ist der fruehere Name und zeigt dasselbe. */
  variant?: "block" | "calm" | "compact";
}

// Leerer Zustand mit einer klaren naechsten Handlung.
export default function EmptyState({ title, children, action, variant = "block" }: Props) {
  if (variant === "calm" || variant === "compact") {
    return (
      <div className="empty-state-calm">
        <span className="empty-state-icon" aria-hidden="true"><SignalIcon tone="neutral" /></span>
        <div>
          {title ? <strong>{title}</strong> : null}
          {children ? <p>{children}</p> : null}
          {action}
        </div>
      </div>
    );
  }
  if (!title && !action) return <p className="state-empty">{children}</p>;
  return (
    <div className="empty-state">
      {title ? <h3>{title}</h3> : null}
      {children ? <p>{children}</p> : null}
      {action}
    </div>
  );
}
