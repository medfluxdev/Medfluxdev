"use client";

import { useCallback, useEffect, useId, useRef, useState, type ReactNode } from "react";

interface Props {
  /** Sichtbarer Text des Knopfs. */
  label: ReactNode;
  /** Name der aufgeklappten Fläche für Screenreader. */
  panelLabel: string;
  children: ReactNode | ((close: () => void) => ReactNode);
  /** Knopf hervorheben, wenn eine Auswahl aktiv ist. */
  active?: boolean;
  align?: "start" | "end";
  wide?: boolean;
  className?: string;
  /** Eigene Klasse des Knopfs statt `btn` (z. B. gestrichelter Hinzufügen-Knopf). */
  triggerClassName?: string;
  /** Zugänglicher Name des Knopfs, wenn der sichtbare Text allein nicht reicht. */
  triggerLabel?: string;
  /** Pfeil ▾ hinter dem Text (Standard: ja). */
  caret?: boolean;
  /** Beim ersten Anzeigen geöffnet (z. B. Sprung über ?feld=). */
  defaultOpen?: boolean;
}

// Aufklappfläche unter einem Knopf (Filterauswahl, Darstellung): nicht modal, Escape schließt und
// gibt den Fokus an den Knopf zurück, ein Klick daneben schließt.
export default function Popover({ label, panelLabel, children, active = false, align = "start", wide = false, className, triggerClassName, triggerLabel, caret = true, defaultOpen = false }: Props) {
  const [open, setOpen] = useState(defaultOpen);
  const panelId = useId();
  const root = useRef<HTMLDivElement>(null);
  const button = useRef<HTMLButtonElement>(null);
  const close = useCallback(() => {
    setOpen(false);
    button.current?.focus();
  }, []);

  useEffect(() => {
    if (!open) return;
    function onPointer(event: MouseEvent) {
      if (root.current && !root.current.contains(event.target as Node)) setOpen(false);
    }
    function onKey(event: KeyboardEvent) {
      if (event.key === "Escape") close();
    }
    document.addEventListener("mousedown", onPointer);
    document.addEventListener("keydown", onKey);
    return () => { document.removeEventListener("mousedown", onPointer); document.removeEventListener("keydown", onKey); };
  }, [close, open]);

  return <div className={["popover", className].filter(Boolean).join(" ")} ref={root}>
    <button
      ref={button}
      type="button"
      className={`${triggerClassName ?? "btn"} popover-trigger${active ? " popover-trigger--active" : ""}`}
      aria-label={triggerLabel}
      aria-expanded={open}
      aria-controls={open ? panelId : undefined}
      onClick={() => setOpen((value) => !value)}
    >
      {label}{caret ? <> <span aria-hidden="true">▾</span></> : null}
    </button>
    {open ? <div id={panelId} role="group" aria-label={panelLabel} className={`popover-panel popover-panel--${align}${wide ? " popover-panel--wide" : ""}`}>
      {typeof children === "function" ? children(close) : children}
    </div> : null}
  </div>;
}
