"use client";

import { useEffect, useState, type ReactNode } from "react";

const STORAGE_KEY = "medflux.collapsed-sections";

function readCollapsed(): Set<string> {
  try {
    const raw = window.localStorage.getItem(STORAGE_KEY);
    return new Set(raw ? (JSON.parse(raw) as string[]) : []);
  } catch {
    return new Set();
  }
}

function writeCollapsed(ids: Set<string>) {
  try {
    window.localStorage.setItem(STORAGE_KEY, JSON.stringify([...ids]));
  } catch {
    // Nur Komfort: ohne Speicher bleibt der Kasten offen.
  }
}

interface Props {
  /** Stabile Kennung (Überschrift-ID `<id>-heading`, gemerkter Zustand). */
  id: string;
  title: string;
  description?: ReactNode;
  /** Aktionen oben rechts neben dem Einklappen (z. B. Bearbeiten / Speichern). */
  actions?: ReactNode;
  /** Von außen aufklappen (z. B. Sprung zu einem Feld in diesem Kasten). */
  forceOpen?: boolean;
  className?: string;
  children: ReactNode;
}

/**
 * Kasten mit Überschrift, Aktionen und Einklappen in der rechten oberen Ecke.
 * Eingeklappte Kästen merkt sich der Browser (je Kennung).
 */
export default function CollapsibleSection({ id, title, description, actions, forceOpen = false, className, children }: Props) {
  const [collapsed, setCollapsed] = useState(false);
  useEffect(() => { setCollapsed(readCollapsed().has(id)); }, [id]);
  useEffect(() => {
    if (!forceOpen || !collapsed) return;
    setCollapsed(false);
    const ids = readCollapsed();
    ids.delete(id);
    writeCollapsed(ids);
  }, [collapsed, forceOpen, id]);

  function toggle() {
    const next = !collapsed;
    setCollapsed(next);
    const ids = readCollapsed();
    if (next) ids.add(id); else ids.delete(id);
    writeCollapsed(ids);
  }

  const bodyId = `${id}-body`;
  return <section className={["cw-section collapsible", collapsed ? "is-collapsed" : "", className ?? ""].filter(Boolean).join(" ")} aria-labelledby={`${id}-heading`}>
    <div className="cw-section-head">
      <div><h2 id={`${id}-heading`}>{title}</h2>{description && !collapsed ? <p>{description}</p> : null}</div>
      <div className="collapsible-corner">
        {!collapsed ? actions : null}
        <button type="button" className="btn btn-ghost btn-icon btn-sm collapsible-toggle" aria-expanded={!collapsed} aria-controls={bodyId} onClick={toggle} aria-label={`${title} ${collapsed ? "aufklappen" : "einklappen"}`} title={collapsed ? "Aufklappen" : "Einklappen"}>
          <svg viewBox="0 0 24 24" aria-hidden="true" width="16" height="16"><path d={collapsed ? "m6 9 6 6 6-6" : "m6 15 6-6 6 6"} fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" /></svg>
        </button>
      </div>
    </div>
    <div id={bodyId} hidden={collapsed}>{children}</div>
  </section>;
}
