"use client";

import { Fragment, useCallback, useEffect, useId, useRef, useState, type KeyboardEvent, type ReactNode } from "react";

export type ActionMenuItem =
  | { label: string; onSelect: () => void; icon?: ReactNode; danger?: boolean; disabled?: boolean }
  | "separator";

interface Props {
  items: ActionMenuItem[];
  /** Zugänglicher Name des Knopfs (Standard „Weitere Aktionen“). */
  label?: string;
  disabled?: boolean;
}

const MORE_ICON = <svg className="action-menu-icon" viewBox="0 0 24 24" aria-hidden="true" focusable="false"><circle cx="5" cy="12" r="1.7" /><circle cx="12" cy="12" r="1.7" /><circle cx="19" cy="12" r="1.7" /></svg>;

/**
 * „⋯“-Menü für Zeilenaktionen (role="menu"): Pfeiltasten wechseln, Pos1/Ende springen,
 * Enter/Leertaste führt aus, Escape schließt und gibt den Fokus an den Knopf zurück; ein Klick daneben schließt.
 */
export default function ActionMenu({ items, label = "Weitere Aktionen", disabled = false }: Props) {
  const [open, setOpen] = useState(false);
  const menuId = useId();
  const root = useRef<HTMLDivElement>(null);
  const trigger = useRef<HTMLButtonElement>(null);
  const menu = useRef<HTMLDivElement>(null);

  const entries = () => Array.from(menu.current?.querySelectorAll<HTMLButtonElement>('[role="menuitem"]:not([disabled])') ?? []);
  const close = useCallback((focusTrigger = true) => {
    setOpen(false);
    if (focusTrigger) trigger.current?.focus();
  }, []);

  useEffect(() => {
    if (!open) return;
    entries()[0]?.focus();
    function onPointer(event: MouseEvent) {
      if (root.current && !root.current.contains(event.target as Node)) setOpen(false);
    }
    document.addEventListener("mousedown", onPointer);
    return () => document.removeEventListener("mousedown", onPointer);
  }, [open]);

  function onMenuKey(event: KeyboardEvent<HTMLDivElement>) {
    const list = entries();
    const index = list.indexOf(document.activeElement as HTMLButtonElement);
    if (event.key === "ArrowDown" || event.key === "ArrowUp") {
      event.preventDefault();
      const step = event.key === "ArrowDown" ? 1 : -1;
      list[(index + step + list.length) % list.length]?.focus();
    } else if (event.key === "Home" || event.key === "End") {
      event.preventDefault();
      list[event.key === "Home" ? 0 : list.length - 1]?.focus();
    } else if (event.key === "Escape") {
      event.preventDefault();
      close();
    } else if (event.key === "Tab") {
      close(false);
    }
  }

  function onTriggerKey(event: KeyboardEvent<HTMLButtonElement>) {
    if (event.key === "ArrowDown" && !open) {
      event.preventDefault();
      setOpen(true);
    }
  }

  return <div className="action-menu" ref={root}>
    <button
      ref={trigger}
      type="button"
      className="btn btn-sm btn-ghost btn-icon action-menu-trigger"
      aria-label={label}
      aria-haspopup="menu"
      aria-expanded={open}
      aria-controls={open ? menuId : undefined}
      disabled={disabled}
      onClick={() => setOpen((value) => !value)}
      onKeyDown={onTriggerKey}
    >{MORE_ICON}</button>
    {open ? <div id={menuId} ref={menu} role="menu" aria-label={label} className="action-menu-panel" onKeyDown={onMenuKey}>
      {items.map((item, index) => item === "separator"
        ? <div key={`sep-${index}`} role="separator" className="action-menu-separator" />
        : <Fragment key={item.label}>
          <button
            type="button"
            role="menuitem"
            tabIndex={-1}
            className={`action-menu-item${item.danger ? " action-menu-item--danger" : ""}`}
            disabled={item.disabled}
            onClick={() => { close(); item.onSelect(); }}
          >{item.icon}<span>{item.label}</span></button>
        </Fragment>)}
    </div> : null}
  </div>;
}
