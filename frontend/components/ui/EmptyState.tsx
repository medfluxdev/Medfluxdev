import type { ReactNode } from "react";

interface Props {
  title?: string;
  children?: ReactNode;
  action?: ReactNode;
}

// Leerer Zustand mit einer klaren naechsten Handlung.
export default function EmptyState({ title, children, action }: Props) {
  if (!title && !action) return <p className="state-empty">{children}</p>;
  return (
    <div className="empty-state">
      {title ? <h3>{title}</h3> : null}
      {children ? <p>{children}</p> : null}
      {action}
    </div>
  );
}
