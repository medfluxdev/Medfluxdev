"use client";

import { useEffect, useId, useRef, useState, type ReactNode } from "react";

export interface FilterOption {
  value: string;
  label: string;
  /** Zähler als Kapsel rechts (leer = keiner). */
  count?: number;
  /** Zeichen vor dem Namen, z. B. der Statuspunkt. */
  lead?: ReactNode;
}

const CHEVRON = <svg viewBox="0 0 24 24" aria-hidden="true" focusable="false"><path d="m6 9 6 6 6-6" /></svg>;
const CHECK = <svg viewBox="0 0 24 24" aria-hidden="true" focusable="false"><path d="m5 12.5 4.5 4.5L19 7.5" /></svg>;

/**
 * Auswahlfeld „Status: Alle“ als Aufklapper: der Wert steht fett im Feld, die Liste zeigt Zeichen, Namen und Zähler;
 * die gewählte Zeile trägt einen Haken. Bedienung wie eine Auswahlliste (Pfeile, Pos1/Ende, Enter, Esc, Klick außerhalb).
 */
export default function FilterSelect({ label, value, options, onChange, align = "start", bare = false }: {
  label: string;
  /** Ohne „Label:“ im Feld (das Label bleibt als Name der Liste). */
  bare?: boolean;
  value: string;
  options: FilterOption[];
  onChange: (value: string) => void;
  align?: "start" | "end";
}) {
  const [open, setOpen] = useState(false);
  const [active, setActive] = useState(0);
  const root = useRef<HTMLDivElement>(null);
  const trigger = useRef<HTMLButtonElement>(null);
  const list = useRef<HTMLUListElement>(null);
  const id = useId();
  const selected = Math.max(0, options.findIndex((option) => option.value === value));
  const current = options[selected];

  useEffect(() => {
    if (!open) return;
    setActive(selected);
    list.current?.focus();
    function onPointer(event: MouseEvent) {
      if (root.current && !root.current.contains(event.target as Node)) setOpen(false);
    }
    document.addEventListener("mousedown", onPointer);
    return () => document.removeEventListener("mousedown", onPointer);
    // nur beim Öffnen: Markierung auf den gewählten Wert setzen
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [open]);

  function choose(index: number) {
    const option = options[index];
    if (option) onChange(option.value);
    setOpen(false);
    trigger.current?.focus();
  }

  function onKey(event: React.KeyboardEvent) {
    if (event.key === "ArrowDown") { event.preventDefault(); setActive((index) => Math.min(options.length - 1, index + 1)); }
    else if (event.key === "ArrowUp") { event.preventDefault(); setActive((index) => Math.max(0, index - 1)); }
    else if (event.key === "Home") { event.preventDefault(); setActive(0); }
    else if (event.key === "End") { event.preventDefault(); setActive(options.length - 1); }
    else if (event.key === "Enter" || event.key === " ") { event.preventDefault(); choose(active); }
    else if (event.key === "Escape") { event.preventDefault(); setOpen(false); trigger.current?.focus(); }
    else if (event.key === "Tab") setOpen(false);
  }

  return <div className={`fsel${open ? " is-open" : ""}${value && !bare ? " is-active" : ""}${bare ? " fsel--bare" : ""}`} ref={root}>
    <button ref={trigger} type="button" className="fsel-btn" aria-haspopup="listbox" aria-expanded={open} aria-controls={open ? id : undefined}
      onClick={() => setOpen((before) => !before)}
      onKeyDown={(event) => { if (event.key === "ArrowDown" && !open) { event.preventDefault(); setOpen(true); } }}>
      {bare ? null : <span className="fsel-label">{label}:</span>}<span className="fsel-value">{current?.label ?? ""}</span>
      <span className="fsel-chevron" aria-hidden="true">{CHEVRON}</span>
    </button>
    {open ? <ul ref={list} id={id} role="listbox" tabIndex={-1} aria-label={label} aria-activedescendant={`${id}-${active}`} className={`fsel-menu fsel-menu--${align}`} onKeyDown={onKey}>
      {options.map((option, index) => <li key={option.value || "all"} id={`${id}-${index}`} role="option" aria-selected={option.value === value}
        className={`fsel-opt${index === active ? " is-active" : ""}${option.value === value ? " is-selected" : ""}`}
        onMouseEnter={() => setActive(index)} onClick={() => choose(index)}>
        {option.lead ? <span className="fsel-lead" aria-hidden="true">{option.lead}</span> : null}
        <span className="fsel-name">{option.label}</span>
        {option.value === value ? <span className="fsel-check" aria-hidden="true">{CHECK}</span>
          : option.count != null ? <span className="fsel-count" aria-hidden="true">{option.count}</span> : null}
      </li>)}
    </ul> : null}
  </div>;
}
