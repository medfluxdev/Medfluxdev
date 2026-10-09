import type { ReactNode } from "react";

interface Props {
  title?: string;
  children?: ReactNode;
  action?: ReactNode;
  /** "compact": kurze Zeile mit Haken fuer "nichts zu tun" in Uebersichtskarten. */
  variant?: "block" | "compact";
}

// Leerer Zustand mit einer klaren naechsten Handlung.
export default function EmptyState({ title, children, action, variant = "block" }: Props) {
  if (variant === "compact") {
    return (
      <div className="empty-state-compact">
        <span className="empty-state-icon" aria-hidden="true">
          <svg viewBox="0 0 24 24" focusable="false"><path d="M20 6 9 17l-5-5" /></svg>
        </span>
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
