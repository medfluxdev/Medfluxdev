"use client";

import { useId, useRef, type ReactNode } from "react";
import { useFocusTrap } from "./useFocusTrap";

interface Props {
  open: boolean;
  title: string;
  onClose: () => void;
  children: ReactNode;
  actions?: ReactNode;
}

// Seitenleiste fuer Vorschau, KI-Assistent und Entwicklerdetails.
export default function Drawer({ open, title, onClose, children, actions }: Props) {
  const ref = useRef<HTMLDivElement>(null);
  const titleId = useId();
  useFocusTrap(ref, open, onClose);
  if (!open) return null;
  return (
    <>
      <div className="drawer-backdrop" onClick={onClose} aria-hidden="true" />
      <div ref={ref} className="drawer" role="dialog" aria-modal="true" aria-labelledby={titleId} tabIndex={-1}>
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
