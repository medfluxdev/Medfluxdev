"use client";

import { useId, useState, type ReactNode } from "react";

// Hinweis bei Hover und Tastaturfokus; Inhalt ist zusaetzlich per aria-describedby lesbar.
export default function Tooltip({ text, children }: { text: string; children: ReactNode }) {
  const [open, setOpen] = useState(false);
  const id = useId();
  return (
    <span
      className="tooltip"
      onMouseEnter={() => setOpen(true)}
      onMouseLeave={() => setOpen(false)}
      onFocus={() => setOpen(true)}
      onBlur={() => setOpen(false)}
      onKeyDown={(event) => { if (event.key === "Escape") setOpen(false); }}
      aria-describedby={id}
    >
      {children}
      <span id={id} role="tooltip" className="tooltip-bubble" hidden={!open}>{text}</span>
    </span>
  );
}
