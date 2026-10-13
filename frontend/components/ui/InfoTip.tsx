"use client";

import { useId, useState } from "react";

/**
 * ⓘ neben einer Beschriftung: Erklärung bei Hover, Tastaturfokus und Klick; der Text ist zugleich
 * die Beschreibung des Knopfs (aria-describedby), auch wenn die Blase geschlossen ist.
 */
export default function InfoTip({ text, label }: { text: string; /** Zugänglicher Name, z. B. „Erläuterung zu Löschen ab“. */ label: string }) {
  const [open, setOpen] = useState(false);
  const id = useId();
  return <span className="tooltip info-tip" onMouseEnter={() => setOpen(true)} onMouseLeave={() => setOpen(false)}>
    <button
      type="button"
      className="info-tip-button"
      aria-label={label}
      aria-describedby={id}
      aria-expanded={open}
      onFocus={() => setOpen(true)}
      onBlur={() => setOpen(false)}
      onClick={() => setOpen((value) => !value)}
      onKeyDown={(event) => { if (event.key === "Escape") setOpen(false); }}
    >
      <svg viewBox="0 0 24 24" aria-hidden="true" focusable="false"><circle cx="12" cy="12" r="9" /><path d="M12 11v5M12 7.5v.5" /></svg>
    </button>
    <span id={id} role="tooltip" className="tooltip-bubble" hidden={!open}>{text}</span>
  </span>;
}
