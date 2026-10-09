"use client";

import { useId, useRef, type ReactNode } from "react";
import { useFocusTrap } from "./useFocusTrap";

interface Props {
  open: boolean;
  title: string;
  onClose: () => void;
  children: ReactNode;
  actions?: ReactNode;
  /** Breitere Leiste, z. B. fuer Tabellen-Vorschauen. */
  wide?: boolean;
}

// Seitenleiste fuer Vorschau, Bearbeitung ohne Seitenwechsel, KI-Assistent und Entwicklerdetails.
export default function Drawer({ open, title, onClose, children, actions, wide }: Props) {
  const ref = useRef<HTMLDivElement>(null);
  const titleId = useId();
  useFocusTrap(ref, open, onClose);
  if (!open) return null;
  return (
    <>
      <div className="drawer-backdrop" onClick={onClose} aria-hidden="true" />
      <div ref={ref} className={wide ? "drawer drawer-wide" : "drawer"} role="dialog" aria-modal="true" aria-labelledby={titleId} tabIndex={-1}>
        <div className="drawer-head">
          <h2 id={titleId}>{title}</h2>
          <div className="btn-group">
            {actions}
            <button type="button" className="btn btn-ghost btn-icon" onClick={onClose} aria-label="Schließen">×</button>
          </div>
        </div>
        <div className="drawer-body">{children}</div>
      </div>
    </>
  );
}
