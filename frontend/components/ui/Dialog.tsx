"use client";

import { useId, useRef, type ReactNode } from "react";
import { useFocusTrap } from "./useFocusTrap";

interface Props {
  open: boolean;
  title: string;
  description?: ReactNode;
  onClose: () => void;
  children?: ReactNode;
  actions?: ReactNode;
}

// Modaler Dialog: Fokusfalle, Escape, Klick auf Hintergrund schliesst.
export default function Dialog({ open, title, description, onClose, children, actions }: Props) {
  const ref = useRef<HTMLDivElement>(null);
  const titleId = useId();
  const descriptionId = useId();
  useFocusTrap(ref, open, onClose);
  if (!open) return null;
  return (
    <div className="dialog-backdrop" onMouseDown={(event) => { if (event.target === event.currentTarget) onClose(); }}>
      <div ref={ref} className="dialog" role="dialog" aria-modal="true" aria-labelledby={titleId} aria-describedby={description ? descriptionId : undefined} tabIndex={-1}>
        <h2 id={titleId}>{title}</h2>
        {description ? <p id={descriptionId} className="field-hint">{description}</p> : null}
        {children}
        {actions ? <div className="form-actions">{actions}</div> : null}
      </div>
    </div>
  );
}
