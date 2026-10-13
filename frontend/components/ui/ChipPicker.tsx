"use client";

import { useEffect, useRef, useState } from "react";
import Popover from "./Popover";

export interface ChipPickerGroup {
  label: string;
  options: { value: string; label: string }[];
}

const SEARCH_FROM = 8;

/**
 * Mehrfachauswahl als Chips (32px, Entfernen 24px) plus gesondertem Knopf „+ …“.
 * Der Knopf öffnet eine Liste (Gruppen in der übergebenen Reihenfolge, Vorschläge zuerst);
 * ab acht Einträgen mit Suchfeld. Escape schließt und gibt den Fokus an den Knopf zurück.
 */
export default function ChipPicker({ labelId, items, onRemove, groups, onAdd, addLabel, addAriaLabel, disabledHint }: {
  /** ID der sichtbaren Feldbeschriftung (benennt die Chip-Liste). */
  labelId: string;
  items: { id: string; label: string }[];
  onRemove: (id: string) => void;
  groups: ChipPickerGroup[];
  onAdd: (value: string) => void;
  /** Sichtbarer Text des Knopfs, z. B. „Abteilung“. */
  addLabel: string;
  /** Zugänglicher Name, z. B. „Nutzende Abteilung hinzufügen“. */
  addAriaLabel: string;
  /** Statt des Knopfs: warum gerade nichts hinzugefügt werden kann. */
  disabledHint?: string | null;
}) {
  const total = groups.reduce((sum, group) => sum + group.options.length, 0);
  return <div className="chip-picker">
    {items.length ? <ul className="chip-list" aria-labelledby={labelId}>
      {items.map((item) => <li key={item.id} className="chip">
        <span>{item.label}</span>
        <button type="button" className="chip-remove" onClick={() => onRemove(item.id)} aria-label={`${item.label} entfernen`}>
          <svg viewBox="0 0 24 24" aria-hidden="true" focusable="false"><path d="M6 6l12 12M18 6 6 18" /></svg>
        </button>
      </li>)}
    </ul> : null}
    {disabledHint ? <span className="chip-picker-hint">{disabledHint}</span> : total > 0 ? <Popover
      className="chip-add"
      triggerClassName="chip-add-trigger"
      triggerLabel={addAriaLabel}
      caret={false}
      panelLabel={addAriaLabel}
      label={<><svg viewBox="0 0 24 24" aria-hidden="true" focusable="false"><path d="M12 5v14M5 12h14" /></svg>{addLabel}</>}
    >
      {(close) => <ChipOptions groups={groups} search={total >= SEARCH_FROM} onPick={(value) => { onAdd(value); close(); }} />}
    </Popover> : null}
  </div>;
}

function ChipOptions({ groups, search, onPick }: { groups: ChipPickerGroup[]; search: boolean; onPick: (value: string) => void }) {
  const [query, setQuery] = useState("");
  const root = useRef<HTMLDivElement>(null);
  useEffect(() => {
    root.current?.querySelector<HTMLElement>("input, button")?.focus();
  }, []);
  const term = query.trim().toLocaleLowerCase("de");
  const visible = groups
    .map((group) => ({ ...group, options: term ? group.options.filter((option) => option.label.toLocaleLowerCase("de").includes(term)) : group.options }))
    .filter((group) => group.options.length);
  return <div className="chip-options" ref={root}>
    {search ? <input type="search" className="chip-options-search" aria-label="Liste durchsuchen" placeholder="Suchen …" value={query} onChange={(event) => setQuery(event.target.value)} /> : null}
    {visible.length ? visible.map((group) => <div key={group.label} role="group" aria-label={group.label} className="chip-options-group">
      <p className="chip-options-label" aria-hidden="true">{group.label}</p>
      <ul>{group.options.map((option) => <li key={option.value}>
        <button type="button" onClick={() => onPick(option.value)}>{option.label}</button>
      </li>)}</ul>
    </div>) : <p className="chip-options-empty" role="status">Keine Treffer.</p>}
  </div>;
}
