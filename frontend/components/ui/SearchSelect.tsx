"use client";

import { useId, useMemo, useRef, useState, type KeyboardEvent } from "react";

export interface SearchOption {
  value: string;
  label: string;
  /** Kleiner Zusatz rechts (z. B. Typ). */
  note?: string;
}

/**
 * Auswahl mit Suchfeld (ARIA-Combobox mit Liste): tippen filtert, Pfeiltasten wählen, Enter übernimmt.
 * `emptyLabel` bietet eine leere Wahl an (z. B. „Keine – direkt im Krankenhaus“).
 */
export default function SearchSelect({ id, value, options, onChange, emptyLabel, placeholder = "Suchen …", disabled, describedBy, invalid }: {
  id: string;
  value: string;
  options: SearchOption[];
  onChange: (value: string) => void;
  emptyLabel?: string;
  placeholder?: string;
  disabled?: boolean;
  describedBy?: string;
  invalid?: boolean;
}) {
  const listId = useId();
  const [open, setOpen] = useState(false);
  const [query, setQuery] = useState("");
  const [active, setActive] = useState(0);
  const input = useRef<HTMLInputElement>(null);
  const selected = options.find((option) => option.value === value);
  const all: SearchOption[] = useMemo(() => [...(emptyLabel !== undefined ? [{ value: "", label: emptyLabel }] : []), ...options], [emptyLabel, options]);
  const term = query.trim().toLocaleLowerCase("de");
  const visible = term ? all.filter((option) => option.label.toLocaleLowerCase("de").includes(term)) : all;

  function choose(option: SearchOption) {
    onChange(option.value);
    setQuery("");
    setOpen(false);
  }

  function onKeyDown(event: KeyboardEvent<HTMLInputElement>) {
    if (event.key === "ArrowDown") {
      event.preventDefault();
      setOpen(true);
      setActive((current) => Math.min(current + 1, visible.length - 1));
    } else if (event.key === "ArrowUp") {
      event.preventDefault();
      setActive((current) => Math.max(current - 1, 0));
    } else if (event.key === "Enter" && open) {
      event.preventDefault();
      if (visible[active]) choose(visible[active]);
    } else if (event.key === "Escape") {
      setOpen(false);
      setQuery("");
    }
  }

  const shown = open ? query : selected?.label ?? (value ? "" : emptyLabel ?? "");
  return <div className="search-select">
    <input
      ref={input}
      id={id}
      type="text"
      role="combobox"
      aria-expanded={open}
      aria-controls={listId}
      aria-autocomplete="list"
      aria-activedescendant={open && visible[active] ? `${listId}-${active}` : undefined}
      aria-describedby={describedBy}
      aria-invalid={invalid || undefined}
      autoComplete="off"
      disabled={disabled}
      placeholder={open ? placeholder : undefined}
      value={shown}
      onFocus={() => { setOpen(true); setActive(0); }}
      onClick={() => setOpen(true)}
      onBlur={() => window.setTimeout(() => { setOpen(false); setQuery(""); }, 120)}
      onChange={(event) => { setQuery(event.target.value); setOpen(true); setActive(0); }}
      onKeyDown={onKeyDown}
    />
    {open ? <ul id={listId} role="listbox" className="search-select-list">
      {visible.length === 0 ? <li className="search-select-empty" role="presentation">Nichts gefunden.</li> : visible.map((option, index) => <li
        key={option.value || "__empty"}
        id={`${listId}-${index}`}
        role="option"
        aria-selected={option.value === value}
        className={index === active ? "is-active" : undefined}
        onMouseDown={(event) => { event.preventDefault(); choose(option); }}
      >
        <span>{option.label}</span>{option.note ? <small>{option.note}</small> : null}
      </li>)}
    </ul> : null}
  </div>;
}
