"use client";

import { useEffect, useState, type ReactNode } from "react";
import { clearSelection, isHeadDoubleClick } from "@/lib/box-collapse";
import { cardIcon, tileClass } from "@/lib/card-icons";

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
  /** Kurzfassung (2–3 Werte, Fehlendes als Signal); ersetzt im eingeklappten Zustand die Beschreibung. */
  summary?: ReactNode;
  /** Kachel 40 × 40 zwischen Einklappen und Überschrift (Kennfarbe des Inhalts, dekorativ). */
  icon?: ReactNode;
  /** Kennfarbe der Kachel, z. B. `section-tile--type`. */
  iconClassName?: string;
  /** Aktionen oben rechts neben dem Einklappen (z. B. Bearbeiten / Speichern). */
  actions?: ReactNode;
  /** Von außen aufklappen (z. B. Sprung zu einem Feld in diesem Kasten). */
  forceOpen?: boolean;
  className?: string;
  children: ReactNode;
}

/**
 * Kasten mit Einklappen-Knopf links (40 × 40), Überschrift, Beschreibung bzw. eingeklappt der
 * Kurzfassung und Aktionen rechts. Nur der Knopf klappt (plus Doppelklick auf freie Kopffläche),
 * damit Aktionen im Kopf bedienbar bleiben. Eingeklappte Kästen merkt sich der Browser (je Kennung).
 */
export default function CollapsibleSection({ id, title, description, summary, icon, iconClassName, actions, forceOpen = false, className, children }: Props) {
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
  // Jede Karte hat eine Kachel: eigenes Symbol oder eines aus der Überschrift (lib/card-icons.ts).
  const auto = cardIcon(title);
  return <section className={["cw-section collapsible", collapsed ? "is-collapsed" : "", className ?? ""].filter(Boolean).join(" ")} aria-labelledby={`${id}-heading`}>
    <div className="cw-section-head collapsible-head has-icon" onDoubleClick={(event) => { if (!isHeadDoubleClick(event, event.currentTarget)) return; clearSelection(); toggle(); }}>
      <button type="button" className="collapsible-toggle" aria-expanded={!collapsed} aria-controls={bodyId} onClick={toggle} aria-label={`${title} ${collapsed ? "aufklappen" : "einklappen"}`} title={collapsed ? "Aufklappen" : "Einklappen"}>
        <svg viewBox="0 0 24 24" aria-hidden="true" focusable="false"><path d="m6 9 6 6 6-6" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" /></svg>
      </button>
      <span className={`collapsible-icon ${icon ? iconClassName ?? "" : tileClass(auto.tile)}`.trim()} aria-hidden="true">{icon ?? <svg viewBox="0 0 24 24" focusable="false"><path d={auto.path} /></svg>}</span>
      <div className="collapsible-title">
        <h2 id={`${id}-heading`}>{title}</h2>
        {collapsed
          ? summary ? <div className="collapsible-summary">{summary}</div> : null
          : description ? <p>{description}</p> : null}
      </div>
      {actions ? <div className="collapsible-corner">{actions}</div> : null}
    </div>
    <div id={bodyId} hidden={collapsed}>{children}</div>
  </section>;
}
